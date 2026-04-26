"""
Celery tasks for CRM (async email sending, statistics, etc.)
"""
import csv
import datetime
import io
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workflow Automation helpers (v2.5)
# ---------------------------------------------------------------------------

def _render_template(text: str, context: dict) -> str:
    """Replace {{key}} placeholders in *text* with values from *context*."""
    for key, value in context.items():
        if isinstance(value, str):
            text = text.replace("{{" + key + "}}", value)
    return text


def _get_context_field(field: str, context: dict):
    """Extract a (possibly dot-separated) field from the evaluation context."""
    parts = field.split(".")
    current = context
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _compare(actual, operator: str, expected) -> bool:
    """Return True if *actual* <operator> *expected*."""
    if operator == "eq":
        return str(actual) == str(expected)
    if operator == "neq":
        return str(actual) != str(expected)
    if operator == "contains":
        return str(expected).lower() in str(actual).lower()
    # Numeric comparisons
    try:
        a, e = float(actual), float(expected)
    except (TypeError, ValueError):
        return False
    if operator == "gt":
        return a > e
    if operator == "gte":
        return a >= e
    if operator == "lt":
        return a < e
    if operator == "lte":
        return a <= e
    return False


def _evaluate_conditions(conditions: list, context: dict) -> bool:
    """Return True if all conditions pass (logical AND)."""
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "eq")
        value = cond.get("value")
        actual = _get_context_field(field, context)
        if not _compare(actual, operator, value):
            return False
    return True


def _action_send_email(action: dict, context: dict) -> None:
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    to_spec = action.get("to", "")
    # Resolve recipient
    if to_spec == "assignee":
        recipient = context.get("assignee_email", "")
    elif to_spec == "owner":
        recipient = context.get("owner_email", "")
    elif to_spec == "customer":
        recipient = context.get("customer_email", "")
    else:
        recipient = to_spec  # literal email address

    if not recipient:
        logger.warning("automation send_email: no recipient resolved for to=%r", to_spec)
        return

    subject = _render_template(action.get("subject", "(no subject)"), context)
    body = _render_template(action.get("body", ""), context)
    from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@leadlab.io")

    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=[recipient],
        fail_silently=False,
    )
    logger.info("automation send_email: sent to %s — subject: %s", recipient, subject)


def _action_create_task(action: dict, context: dict, rule) -> None:
    from django.utils import timezone as tz
    from crm.models import Task

    lead_id = context.get("lead_id")
    if not lead_id:
        raise ValueError("create_task: no lead_id in context")

    from crm.models import Lead
    try:
        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        raise ValueError(f"create_task: lead {lead_id} not found")

    title = _render_template(action.get("title", "Follow-up task"), context)
    days_from_now = int(action.get("days_from_now", 0))
    due_date = tz.now() + datetime.timedelta(days=days_from_now) if days_from_now else None

    Task.objects.create(
        firm=lead.firm,
        lead=lead,
        title=title,
        due_date=due_date,
    )
    logger.info("automation create_task: created task '%s' on lead %s", title, lead_id)


def _action_update_field(action: dict, context: dict) -> None:
    lead_id = context.get("lead_id")
    if not lead_id:
        raise ValueError("update_field: no lead_id in context")

    field = action.get("field", "")
    value = action.get("value")

    _ALLOWED_LEAD_FIELDS = {"status", "source", "currency", "description"}
    if field not in _ALLOWED_LEAD_FIELDS:
        raise ValueError(f"update_field: field '{field}' is not allowed")

    from crm.models import Lead
    updated = Lead.objects.filter(id=lead_id).update(**{field: value})
    if not updated:
        raise ValueError(f"update_field: lead {lead_id} not found")
    logger.info("automation update_field: set %s=%r on lead %s", field, value, lead_id)


def _action_call_webhook(action: dict, context: dict) -> None:
    import json
    import urllib.request
    import urllib.error

    url = action.get("url", "")
    if not url:
        raise ValueError("call_webhook: no url provided")

    method = action.get("method", "POST").upper()
    payload = json.dumps(context).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(
                "automation call_webhook: %s %s → %d",
                method, url, resp.status,
            )
    except urllib.error.HTTPError as exc:
        raise ValueError(f"call_webhook: HTTP {exc.code} from {url}") from exc
    except Exception as exc:
        raise ValueError(f"call_webhook: request to {url} failed: {exc}") from exc


def _action_run_plugin(action: dict, context: dict, rule) -> None:
    from leadlab.plugin_registry import plugin_registry
    plugin_name = action.get("plugin_name", "")
    action_name = action.get("action", "")
    params = action.get("params", {})
    plugin = next((p for p in plugin_registry if p.get("name") == plugin_name), None)
    if plugin is None:
        raise ValueError(f"run_plugin_action: plugin '{plugin_name}' not found")
    hook = plugin.get("actions", {}).get(action_name)
    if hook is None:
        raise ValueError(
            f"run_plugin_action: action '{action_name}' not found in plugin '{plugin_name}'"
        )
    hook(context=context, params=params, rule=rule)
    logger.info("automation run_plugin_action: %s.%s executed", plugin_name, action_name)


def _execute_rule(rule, context: dict) -> None:
    """Evaluate conditions and execute actions for a single AutomationRule."""
    from crm.models import AutomationRun, AutomationRunStatus

    try:
        if not _evaluate_conditions(rule.conditions, context):
            AutomationRun.objects.create(
                rule=rule,
                status=AutomationRunStatus.SKIPPED,
                context=context,
            )
            return

        errors = []
        for action in rule.actions:
            action_type = action.get("type")
            try:
                if action_type == "send_email":
                    _action_send_email(action, context)
                elif action_type == "create_task":
                    _action_create_task(action, context, rule)
                elif action_type == "update_field":
                    _action_update_field(action, context)
                elif action_type == "call_webhook":
                    _action_call_webhook(action, context)
                elif action_type == "run_plugin_action":
                    _action_run_plugin(action, context, rule)
                else:
                    errors.append(f"Unknown action type: {action_type!r}")
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "automation rule %s action %r failed: %s",
                    rule.id, action_type, exc,
                )
                errors.append(str(exc))

        AutomationRun.objects.create(
            rule=rule,
            status=AutomationRunStatus.FAILURE if errors else AutomationRunStatus.SUCCESS,
            context=context,
            error_message="; ".join(errors),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("automation rule %s crashed: %s", rule.id, exc)
        from crm.models import AutomationRun, AutomationRunStatus
        AutomationRun.objects.create(
            rule=rule,
            status=AutomationRunStatus.FAILURE,
            context=context,
            error_message=str(exc),
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_activity_email(self, activity_id: str):
    """
    Send an outbound email for an EMAIL_OUT Activity.

    Retries up to 3 times with a 60-second delay on transient SMTP errors.
    """
    from django.core.mail import EmailMessage

    from crm.models import Activity, ActivityType

    try:
        activity = Activity.objects.select_related("lead", "user").get(
            id=activity_id, type=ActivityType.EMAIL_OUT
        )
    except Activity.DoesNotExist:
        logger.error("send_activity_email: Activity %s not found.", activity_id)
        return

    meta = activity.metadata
    to_address = meta.get("to", "")
    subject = meta.get("subject", "(no subject)")
    body = activity.content_text

    if not to_address:
        logger.warning(
            "send_activity_email: Activity %s has no 'to' address in metadata.",
            activity_id,
        )
        return

    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            to=[to_address],
        )
        email.send(fail_silently=False)
        logger.info(
            "send_activity_email: Sent email for Activity %s to '%s'.",
            activity_id,
            to_address,
        )
    except Exception as exc:
        logger.error(
            "send_activity_email: Failed to send email for Activity %s: %s",
            activity_id,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=0)
def process_import_job(self, job_id: str):
    """
    Parse a CSV file and bulk-create Leads or Customers for a Firm.

    Progress is tracked via the ``ImportJob`` model fields:
    ``total``, ``processed``, ``failed_count``, ``errors_json``.
    """
    from django.utils import timezone as tz

    from crm.models import (
        Customer, ImportJob, ImportJobStatus, ImportJobType,
        Lead, LeadSource, LeadStatus,
    )

    try:
        job = ImportJob.objects.select_related("firm", "user").get(id=job_id)
    except ImportJob.DoesNotExist:
        logger.error("process_import_job: job %s not found.", job_id)
        return

    job.status = ImportJobStatus.PROCESSING
    job.save(update_fields=["status"])

    errors = []
    processed = 0
    failed = 0

    try:
        content = job.file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        total = len(rows)
        job.total = total
        job.save(update_fields=["total"])

        if job.type == ImportJobType.LEADS:
            for i, row in enumerate(rows, start=1):
                try:
                    title = (row.get("title") or "").strip()
                    if not title:
                        raise ValueError("'title' column is required.")
                    status = (row.get("status") or LeadStatus.NEW).strip()
                    if status not in {s.value for s in LeadStatus}:
                        status = LeadStatus.NEW
                    source = (row.get("source") or LeadSource.OTHER).strip()
                    if source not in {s.value for s in LeadSource}:
                        source = LeadSource.OTHER
                    raw_value = (row.get("value") or "").strip()
                    value = None
                    if raw_value:
                        try:
                            value = float(raw_value)
                        except ValueError:
                            pass
                    currency = (row.get("currency") or "CZK").strip()[:3]
                    description = (row.get("description") or "").strip()
                    Lead.objects.create(
                        firm=job.firm,
                        title=title,
                        status=status,
                        source=source,
                        value=value,
                        currency=currency,
                        description=description,
                    )
                    processed += 1
                except Exception as exc:
                    failed += 1
                    errors.append({"row": i, "error": str(exc)})
                    logger.warning("process_import_job: row %d failed: %s", i, exc)

        elif job.type == ImportJobType.CUSTOMERS:
            for i, row in enumerate(rows, start=1):
                try:
                    first_name = (row.get("first_name") or "").strip()
                    if not first_name:
                        raise ValueError("'first_name' column is required.")
                    Customer.objects.create(
                        firm=job.firm,
                        first_name=first_name,
                        last_name=(row.get("last_name") or "").strip(),
                        email=(row.get("email") or "").strip(),
                        phone=(row.get("phone") or "").strip(),
                        company_name=(row.get("company_name") or "").strip(),
                    )
                    processed += 1
                except Exception as exc:
                    failed += 1
                    errors.append({"row": i, "error": str(exc)})
                    logger.warning("process_import_job: row %d failed: %s", i, exc)

        job.processed = processed
        job.failed_count = failed
        job.errors_json = errors
        job.status = ImportJobStatus.DONE
        job.finished_at = tz.now()
        job.save(update_fields=["processed", "failed_count", "errors_json", "status", "finished_at"])
        logger.info("process_import_job: job %s done. %d processed, %d failed.", job_id, processed, failed)

    except Exception as exc:
        logger.exception("process_import_job: job %s failed with unexpected error: %s", job_id, exc)
        job.status = ImportJobStatus.FAILED
        job.errors_json = [{"row": 0, "error": str(exc)}]
        job.finished_at = tz.now()
        job.save(update_fields=["status", "errors_json", "finished_at"])


@shared_task(bind=True, max_retries=0)
def send_weekly_digest(self):
    """
    Send a weekly pipeline summary email to all Firm members who have
    ``weekly_digest_enabled=True``.

    Scheduled via ``CELERY_BEAT_SCHEDULE`` to run every Monday at 08:00 UTC.
    Gracefully degrades when email is not configured.
    """
    from django.core.mail import send_mail
    from django.conf import settings

    from crm.models import Lead, LeadStatus, Task
    from firms.models import Firm, Membership

    for firm in Firm.objects.filter(is_active=True):
        recipients = list(
            Membership.objects.filter(firm=firm, weekly_digest_enabled=True)
            .select_related("user")
            .values_list("user__email", flat=True)
        )
        if not recipients:
            continue

        total_leads = Lead.objects.filter(firm=firm).count()
        won = Lead.objects.filter(firm=firm, status=LeadStatus.WON).count()
        lost = Lead.objects.filter(firm=firm, status=LeadStatus.LOST).count()
        active = Lead.objects.filter(
            firm=firm,
            status__in=[
                LeadStatus.NEW, LeadStatus.CONTACTED,
                LeadStatus.PROPOSAL, LeadStatus.NEGOTIATION,
            ],
        ).count()
        open_tasks = Task.objects.filter(firm=firm, is_completed=False).count()

        subject = f"[LeadLab] Weekly Pipeline Digest — {firm.name}"
        body = (
            f"Hi,\n\n"
            f"Here is your weekly pipeline summary for {firm.name}:\n\n"
            f"  Total leads: {total_leads}\n"
            f"  Active:      {active}\n"
            f"  Won:         {won}\n"
            f"  Lost:        {lost}\n"
            f"  Open tasks:  {open_tasks}\n\n"
            f"Log in to LeadLab to see more details.\n\n"
            f"To unsubscribe from this digest, go to Settings → Notifications "
            f"and disable the weekly email.\n"
        )

        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )
            logger.info(
                "send_weekly_digest: Sent digest for firm '%s' to %d recipient(s).",
                firm.name,
                len(recipients),
            )
        except Exception as exc:
            logger.error(
                "send_weekly_digest: Failed to send digest for firm '%s': %s",
                firm.name,
                exc,
            )


# ---------------------------------------------------------------------------
# Push notifications (v1.9)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_push_notification(self, user_id: str, title: str, body: str, url: str = "/app/dashboard"):
    """
    Deliver a Web Push notification to all active subscriptions for a user.

    Silently skips if VAPID keys are not configured.  Removes subscriptions
    that report a 410 Gone response (browser has unsubscribed).
    """
    from django.conf import settings

    from crm.models import PushSubscription

    private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    public_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    admin_email = getattr(settings, "VAPID_ADMIN_EMAIL", "admin@leadlab.io")

    if not private_key or not public_key:
        logger.debug("send_push_notification: VAPID keys not configured — skipping.")
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("send_push_notification: pywebpush not installed.")
        return

    import json

    subscriptions = PushSubscription.objects.filter(user_id=user_id, push_enabled=True)

    payload = json.dumps({"title": title, "body": body, "url": url})

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": f"mailto:{admin_email}"},
            )
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code == 410:
                # Browser has revoked the subscription — remove it.
                sub.delete()
                logger.info("send_push_notification: Removed expired subscription %s.", sub.id)
            else:
                logger.error(
                    "send_push_notification: Failed to deliver to subscription %s: %s",
                    sub.id,
                    exc,
                )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "send_push_notification: Unexpected error for subscription %s: %s",
                sub.id,
                exc,
            )


# ---------------------------------------------------------------------------
# Email Sequences dispatch (v2.4)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0)
def dispatch_sequence_emails(self):
    """
    Process all active SequenceEnrollments whose next_send_at is in the past.

    For each due enrollment:
    1. Look up the next EmailSequenceStep.
    2. Send the email (via Django's email backend).
    3. Log a SEQUENCE_EMAIL_SENT activity on the lead.
    4. Advance the enrollment to the next step (or mark it completed).

    Runs every 15 minutes via Celery beat.
    """
    from django.core.mail import send_mail
    from django.utils import timezone as tz
    from django.conf import settings as django_settings

    from crm.models import (
        Activity,
        EmailSequenceStep,
        SequenceEnrollment,
        SequenceEnrollmentStatus,
    )

    now = tz.now()
    due = SequenceEnrollment.objects.filter(
        status=SequenceEnrollmentStatus.ACTIVE,
        next_send_at__lte=now,
    ).select_related("sequence", "lead", "lead__customer")

    for enrollment in due:
        sequence = enrollment.sequence
        lead = enrollment.lead

        try:
            step = sequence.steps.get(step_order=enrollment.current_step)
        except EmailSequenceStep.DoesNotExist:
            # No more steps — mark enrollment complete
            enrollment.status = SequenceEnrollmentStatus.COMPLETED
            enrollment.completed_at = now
            enrollment.save(update_fields=["status", "completed_at"])
            continue

        # Resolve recipient email from lead's customer
        to_email = ""
        if lead.customer:
            to_email = lead.customer.email
        if not to_email:
            logger.warning(
                "dispatch_sequence_emails: Lead %s has no customer email — skipping step %d.",
                lead.id,
                step.step_order,
            )
        else:
            # Render simple placeholders
            customer_name = ""
            if lead.customer:
                customer_name = f"{lead.customer.first_name} {lead.customer.last_name}".strip()
            body = step.body_template.replace(
                "{{lead_title}}", lead.title
            ).replace(
                "{{customer_name}}", customer_name or lead.title
            )

            from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@leadlab.io")

            # Check plugin config for custom from_email
            try:
                from firms.models import PluginConfig
                pc = PluginConfig.objects.filter(
                    firm_id=lead.firm_id,
                    plugin_name="email-sequences",
                    enabled=True,
                ).first()
                if pc and pc.config.get("from_email"):
                    from_email = pc.config["from_email"]
            except Exception:
                pass

            try:
                send_mail(
                    subject=step.subject,
                    message=body,
                    from_email=from_email,
                    recipient_list=[to_email],
                    fail_silently=False,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "dispatch_sequence_emails: Failed to send step %d of enrollment %s: %s",
                    step.step_order,
                    enrollment.id,
                    exc,
                )
                continue

            # Log activity
            Activity.objects.create(
                lead=lead,
                type="sequence_email_sent",
                content_text=f"Sequence email sent: {step.subject}",
                metadata={
                    "sequence_id": str(sequence.id),
                    "sequence_name": sequence.name,
                    "step_order": step.step_order,
                    "subject": step.subject,
                    "to": to_email,
                },
            )

        # Advance to next step
        next_step_order = enrollment.current_step + 1
        try:
            next_step = sequence.steps.get(step_order=next_step_order)
            enrollment.current_step = next_step_order
            enrollment.next_send_at = now + datetime.timedelta(days=next_step.delay_days)
            enrollment.save(update_fields=["current_step", "next_send_at"])
        except EmailSequenceStep.DoesNotExist:
            enrollment.status = SequenceEnrollmentStatus.COMPLETED
            enrollment.completed_at = now
            enrollment.save(update_fields=["status", "completed_at"])


# ---------------------------------------------------------------------------
# Workflow Automation Celery tasks (v2.5)
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0)
def evaluate_automation_rules(self, trigger: str, firm_id: str, context: dict):
    """
    Evaluate all active AutomationRules for *trigger* in *firm_id*.

    Called by API hooks (lead created, status changed, proposal sent/accepted)
    and by the periodic check tasks below.  Each matching rule is executed
    via ``_execute_rule`` which logs an AutomationRun.
    """
    from crm.models import AutomationRule

    rules = AutomationRule.objects.filter(
        firm_id=firm_id,
        trigger=trigger,
        is_active=True,
    )
    for rule in rules:
        _execute_rule(rule, context)


@shared_task(bind=True, max_retries=0)
def check_task_overdue_automations(self):
    """
    Periodic task: fire ``task_overdue`` automations.

    Runs once per day.  For each firm that has active TASK_OVERDUE rules,
    finds incomplete tasks whose ``due_date`` is in the past or within the
    configured ``warning_days`` window (default 1 day), and evaluates the
    rules.  A rule with ``trigger_config.warning_days = 1`` will fire for
    tasks due within the next 24 hours; one with ``warning_days = 0`` will
    only fire for already-overdue tasks.

    Deduplication: a run is skipped if the same rule already has a SUCCESS or
    SKIPPED run for the same task within the last 24 hours.
    """
    from django.utils import timezone as tz
    from crm.models import AutomationRule, AutomationRun, AutomationRunStatus, Task
    from firms.models import Membership

    now = tz.now()

    # Collect all firms with active task_overdue rules
    firm_ids = (
        AutomationRule.objects
        .filter(trigger="task_overdue", is_active=True)
        .values_list("firm_id", flat=True)
        .distinct()
    )

    for firm_id in firm_ids:
        rules = AutomationRule.objects.filter(
            firm_id=firm_id, trigger="task_overdue", is_active=True
        )
        # Determine the widest warning window across rules
        max_warning_days = max(
            (int(r.trigger_config.get("warning_days", 1)) for r in rules),
            default=1,
        )
        cutoff = now + datetime.timedelta(days=max_warning_days)

        overdue_tasks = (
            Task.objects
            .filter(firm_id=firm_id, is_completed=False, due_date__lte=cutoff)
            .select_related("lead", "lead__customer", "assigned_to")
        )

        # Get owner email (first OWNER of the firm)
        owner_email = (
            Membership.objects
            .filter(firm_id=firm_id, role="owner")
            .select_related("user")
            .values_list("user__email", flat=True)
            .first()
        ) or ""

        for task in overdue_tasks:
            lead = task.lead
            customer_name = ""
            customer_email = ""
            if lead.customer:
                customer_name = (
                    f"{lead.customer.first_name} {lead.customer.last_name}".strip()
                )
                customer_email = lead.customer.email or ""

            context = {
                "task_id": str(task.id),
                "task_title": task.title,
                "lead_id": str(lead.id),
                "lead_title": lead.title,
                "firm_id": str(firm_id),
                "due_date": task.due_date.isoformat() if task.due_date else "",
                "days_until_due": (
                    str((task.due_date - now).days) if task.due_date else "0"
                ),
                "assignee_email": task.assigned_to.email if task.assigned_to else "",
                "assignee_name": (
                    f"{task.assigned_to.first_name} {task.assigned_to.last_name}".strip()
                    if task.assigned_to else ""
                ),
                "owner_email": owner_email,
                "customer_email": customer_email,
                "customer_name": customer_name,
            }

            for rule in rules:
                # Skip if already fired for this task in the last 24 hours
                already_ran = AutomationRun.objects.filter(
                    rule=rule,
                    triggered_at__gte=now - datetime.timedelta(hours=24),
                ).filter(context__task_id=str(task.id)).exists()
                if already_ran:
                    continue
                _execute_rule(rule, context)


@shared_task(bind=True, max_retries=0)
def check_lead_inactivity_automations(self):
    """
    Periodic task: fire ``lead_inactive`` automations.

    Runs once per day.  For each firm that has active LEAD_INACTIVE rules,
    finds leads with no Activity records in the last ``inactive_days`` days
    (from ``trigger_config``, default 30), then evaluates the rules.

    Deduplication: a run is skipped if the same rule already has a SUCCESS or
    SKIPPED run for the same lead within the last 24 hours.
    """
    from django.utils import timezone as tz
    from django.db.models import Max
    from crm.models import Activity, AutomationRule, AutomationRun, Lead
    from firms.models import Membership

    now = tz.now()

    firm_ids = (
        AutomationRule.objects
        .filter(trigger="lead_inactive", is_active=True)
        .values_list("firm_id", flat=True)
        .distinct()
    )

    for firm_id in firm_ids:
        rules = AutomationRule.objects.filter(
            firm_id=firm_id, trigger="lead_inactive", is_active=True
        )
        # Smallest inactive_days across rules (so we don't miss any)
        min_inactive_days = min(
            (int(r.trigger_config.get("inactive_days", 30)) for r in rules),
            default=30,
        )
        inactivity_cutoff = now - datetime.timedelta(days=min_inactive_days)

        # Find leads whose most-recent activity is older than the cutoff
        # (or leads with no activities at all, treating created_at as last activity)
        leads_qs = Lead.objects.filter(firm_id=firm_id)
        # Annotate with latest activity date
        leads_with_last = leads_qs.annotate(
            last_activity=Max("activities__created_at")
        ).filter(
            # Either no activities (last_activity is NULL) and lead is old enough,
            # or the most recent activity predates the cutoff
            last_activity__lt=inactivity_cutoff,
        ) | leads_qs.annotate(
            last_activity=Max("activities__created_at")
        ).filter(
            last_activity__isnull=True,
            created_at__lt=inactivity_cutoff,
        )
        leads_qs = leads_with_last.select_related("customer").distinct()

        # Get owner email
        owner_email = (
            Membership.objects
            .filter(firm_id=firm_id, role="owner")
            .select_related("user")
            .values_list("user__email", flat=True)
            .first()
        ) or ""

        for lead in leads_qs:
            customer_name = ""
            customer_email = ""
            if lead.customer:
                customer_name = (
                    f"{lead.customer.first_name} {lead.customer.last_name}".strip()
                )
                customer_email = lead.customer.email or ""

            # Compute actual inactive_days
            last_act = getattr(lead, "last_activity", None)
            inactive_days = (
                (now - last_act).days if last_act else (now - lead.created_at).days
            )

            context = {
                "lead_id": str(lead.id),
                "lead_title": lead.title,
                "lead_status": lead.status,
                "firm_id": str(firm_id),
                "inactive_days": str(inactive_days),
                "customer_email": customer_email,
                "customer_name": customer_name,
                "owner_email": owner_email,
            }

            for rule in rules:
                # Respect the per-rule inactive_days threshold
                rule_inactive_days = int(rule.trigger_config.get("inactive_days", 30))
                if inactive_days < rule_inactive_days:
                    continue

                # Skip if already fired for this lead in the last 24 hours
                already_ran = AutomationRun.objects.filter(
                    rule=rule,
                    triggered_at__gte=now - datetime.timedelta(hours=24),
                ).filter(context__lead_id=str(lead.id)).exists()
                if already_ran:
                    continue

                _execute_rule(rule, context)

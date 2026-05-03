"""
Celery tasks for CRM (async email sending, statistics, etc.)
"""
import csv
import datetime
import io
import logging
from decimal import Decimal

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


def _evaluate_conditions(conditions: list, context: dict, logic: str = "and") -> bool:
    """Return True if conditions pass. logic='and' requires all to match; 'or' requires any."""
    if not conditions:
        return True
    results = []
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "eq")
        value = cond.get("value")
        actual = _get_context_field(field, context)
        results.append(_compare(actual, operator, value))
    if logic == "or":
        return any(results)
    return all(results)


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

    # Support both legacy "title" and new "title_template" field
    title_template = action.get("title_template") or action.get("title", "Follow-up task")
    title = _render_template(title_template, context)

    # Support both "days_from_now" (legacy) and "due_days_offset" (Phase 4)
    days_from_now = int(action.get("due_days_offset") or action.get("days_from_now") or 0)
    due_date = tz.now() + datetime.timedelta(days=days_from_now) if days_from_now else None

    # Priority and tags
    priority = action.get("priority") or "medium"
    tags = action.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    lead_id = context.get("lead_id")
    lead = None
    firm = None

    if lead_id:
        from crm.models import Lead
        try:
            lead = Lead.objects.get(id=lead_id)
            firm = lead.firm
        except Lead.DoesNotExist:
            raise ValueError(f"create_task: lead {lead_id} not found")
    else:
        # Standalone task — resolve firm from context
        firm_id = context.get("firm_id")
        if not firm_id:
            raise ValueError("create_task: no lead_id or firm_id in context")
        from firms.models import Firm
        try:
            firm = Firm.objects.get(id=firm_id)
        except Firm.DoesNotExist:
            raise ValueError(f"create_task: firm {firm_id} not found")

    # Resolve assignee
    assigned_to = None
    assign_to_user_id = action.get("assign_to_user_id", "")
    if assign_to_user_id == "inherit":
        # Inherit from the triggering context (use assignee_id standardized key)
        inherit_id = context.get("assignee_id")
        if inherit_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                assigned_to = User.objects.get(id=inherit_id)
            except User.DoesNotExist:
                pass
    elif assign_to_user_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            assigned_to = User.objects.get(id=assign_to_user_id)
        except User.DoesNotExist:
            logger.warning("create_task: assign_to_user_id %s not found", assign_to_user_id)

    task = Task.objects.create(
        firm=firm,
        lead=lead,
        title=title,
        due_date=due_date,
        priority=priority,
        tags=tags,
        assigned_to=assigned_to,
    )
    
    # Log the creation activity so the task can accept reactions
    from crm.api import _log_timeline_event
    from crm.models import ActivityType
    
    # We don't have the user object in context typically, so we leave author=None
    # or resolve it if available. Let's just log it safely.
    _log_timeline_event(task, ActivityType.TASK_CREATED, author=None)
    
    logger.info(
        "automation create_task: rule=%s created task '%s' (id=%s)%s",
        getattr(rule, 'id', 'unknown'), title, task.id,
        f" on lead {lead_id}" if lead_id else "",
    )


def _action_set_task_status(action: dict, context: dict) -> None:
    """Set the status of a task identified by task_id in action or context."""
    from crm.models import Task, TaskStatus

    task_id = action.get("task_id") or context.get("task_id")
    if not task_id:
        raise ValueError("set_task_status: no task_id in action or context")

    status = action.get("status", "")
    valid_statuses = [s.value for s in TaskStatus]
    if status not in valid_statuses:
        raise ValueError(
            f"set_task_status: invalid status '{status}'. "
            f"Choose from: {', '.join(valid_statuses)}"
        )

    updated = Task.objects.filter(id=task_id).update(status=status)
    if not updated:
        raise ValueError(f"set_task_status: task {task_id} not found")
    logger.info("automation set_task_status: task %s → %s", task_id, status)


def _action_assign_tag(action: dict, context: dict) -> None:
    """Add a tag to a task or lead."""
    tag = action.get("tag", "").strip()
    if not tag:
        raise ValueError("assign_tag: no tag specified")

    target_type = action.get("target_type", "task")  # "task" or "lead"

    if target_type == "lead":
        lead_id = action.get("lead_id") or context.get("lead_id")
        if not lead_id:
            raise ValueError("assign_tag: no lead_id in action or context")
        from crm.models import Lead
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            raise ValueError(f"assign_tag: lead {lead_id} not found")
        tags = list(lead.tags or [])
        if tag not in tags:
            tags.append(tag)
            Lead.objects.filter(id=lead_id).update(tags=tags)
        logger.info("automation assign_tag: added tag '%s' to lead %s", tag, lead_id)
    else:
        # Default: task
        task_id = action.get("task_id") or context.get("task_id")
        if not task_id:
            raise ValueError("assign_tag: no task_id in action or context")
        from crm.models import Task
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            raise ValueError(f"assign_tag: task {task_id} not found")
        tags = list(task.tags or [])
        if tag not in tags:
            tags.append(tag)
            Task.objects.filter(id=task_id).update(tags=tags)
        logger.info("automation assign_tag: added tag '%s' to task %s", tag, task_id)


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


def _action_create_realization(action: dict, context: dict, rule: "AutomationRule") -> None:
    """Create a Realization record when a lead is won."""
    lead_id = context.get("lead_id")
    firm_id = context.get("firm_id")

    from crm.models import Lead, Realization
    from firms.models import Firm

    if not firm_id:
        raise ValueError("create_realization: no firm_id in context")

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        raise ValueError(f"create_realization: firm {firm_id} not found")

    lead = None
    customer = None
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)
            customer = lead.customer
        except Lead.DoesNotExist:
            pass

    title_template = action.get("title_template", "Realization: {{lead_title}}")
    lead_title = (lead.title if lead else "") or ""
    customer_name = ""
    if customer:
        customer_name = f"{customer.first_name} {customer.last_name}".strip() or customer.company_name
    title = title_template.replace("{{lead_title}}", lead_title).replace("{{customer_name}}", customer_name)

    assigned_to = None
    assign_to_user_id = action.get("assign_to_user_id")
    if assign_to_user_id == "inherit" and lead and lead.assigned_to_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            assigned_to = User.objects.get(id=lead.assigned_to_id)
        except User.DoesNotExist:
            pass
    elif assign_to_user_id and assign_to_user_id != "inherit":
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            assigned_to = User.objects.get(id=assign_to_user_id)
        except User.DoesNotExist:
            logger.warning("create_realization: assign_to_user_id %s not found", assign_to_user_id)

    realization = Realization.objects.create(
        firm=firm,
        lead=lead,
        customer=customer,
        title=title,
        assigned_to=assigned_to,
    )
    logger.info(
        "automation create_realization: rule=%s created realization '%s' (id=%s)",
        rule.id, realization.title, realization.id,
    )


def _action_create_management(action: dict, context: dict, rule: "AutomationRule") -> None:
    """Create a Management record when a Realization is completed."""
    realization_id = context.get("realization_id")
    firm_id = context.get("firm_id")

    from crm.models import Realization, Management, ManagementType
    from firms.models import Firm

    if not firm_id:
        raise ValueError("create_management: no firm_id in context")

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        raise ValueError(f"create_management: firm {firm_id} not found")

    realization = None
    customer = None
    if realization_id:
        try:
            realization = Realization.objects.get(id=realization_id)
            customer = realization.customer
        except Realization.DoesNotExist:
            pass

    title_template = action.get("title_template", "Správa: {{realization_title}}")
    realization_title = (realization.title if realization else "") or ""
    customer_name = ""
    if customer:
        customer_name = f"{customer.first_name} {customer.last_name}".strip() or getattr(customer, "company_name", "")
    title = title_template.replace("{{realization_title}}", realization_title).replace("{{customer_name}}", customer_name)

    mtype = action.get("management_type", ManagementType.CARE)

    assigned_to = None
    assign_to_user_id = action.get("assign_to_user_id")
    if assign_to_user_id == "inherit" and realization and realization.assigned_to_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            assigned_to = User.objects.get(id=realization.assigned_to_id)
        except User.DoesNotExist:
            pass
    elif assign_to_user_id and assign_to_user_id != "inherit":
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            assigned_to = User.objects.get(id=assign_to_user_id)
        except User.DoesNotExist:
            logger.warning("create_management: assign_to_user_id %s not found", assign_to_user_id)

    management = Management.objects.create(
        firm=firm,
        realization=realization,
        customer=customer,
        title=title,
        type=mtype,
        assigned_to=assigned_to,
    )
    logger.info(
        "automation create_management: rule=%s created management '%s' (id=%s)",
        rule.id, management.title, management.id,
    )


def _execute_rule(rule, context: dict) -> None:
    """Evaluate conditions and execute actions for a single AutomationRule."""
    from crm.models import AutomationRun, AutomationRunStatus

    try:
        if not _evaluate_conditions(rule.conditions, context, getattr(rule, "condition_logic", "and")):
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
                elif action_type == "set_task_status":
                    _action_set_task_status(action, context)
                elif action_type == "assign_tag":
                    _action_assign_tag(action, context)
                elif action_type == "create_realization":
                    _action_create_realization(action, context, rule)
                elif action_type == "create_management":
                    _action_create_management(action, context, rule)
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

    from crm.models import Lead, LeadStatus, Task, Realization, RealizationStatus, Management, ManagementStatus
    from firms.models import Firm, Membership
    from django.utils import timezone as tz

    now = tz.now()
    seven_days = now + datetime.timedelta(days=7)

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

        # Phase 5.0 — Realization stats
        total_realizations = Realization.objects.filter(firm=firm).count()
        active_realizations = Realization.objects.filter(
            firm=firm, status__in=[RealizationStatus.PLANNED, RealizationStatus.IN_PROGRESS]
        ).count()
        done_realizations = Realization.objects.filter(firm=firm, status=RealizationStatus.DONE).count()

        # Phase 5.0 — SLA expiry stats
        expiring_sla = Management.objects.filter(
            firm=firm,
            expires_at__isnull=False,
            expires_at__lte=seven_days,
        ).exclude(status=ManagementStatus.CLOSED).count()

        subject = f"[LeadLab] Weekly Pipeline Digest — {firm.name}"
        body = (
            f"Hi,\n\n"
            f"Here is your weekly pipeline summary for {firm.name}:\n\n"
            f"Příležitosti (Leads):\n"
            f"  Total:  {total_leads}\n"
            f"  Active: {active}\n"
            f"  Won:    {won}\n"
            f"  Lost:   {lost}\n\n"
            f"Realizace:\n"
            f"  Total:  {total_realizations}\n"
            f"  Active: {active_realizations}\n"
            f"  Done:   {done_realizations}\n\n"
            f"SLA expirující do 7 dní: {expiring_sla}\n"
            f"Otevřené úkoly:          {open_tasks}\n\n"
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


# ===========================================================================
# Phase 4.6 — Check SLA Expiry Automations
# ===========================================================================

@shared_task(bind=True, max_retries=0)
def check_sla_expiry_automations(self):
    """
    Periodic task: fire ``sla_expiring`` automations for Management records
    whose SLA/warranty expiry is within the configured warning window.

    Runs once per day.  ``trigger_config.warning_days`` (default: 3) controls
    how far in advance the trigger fires.  Records that have already expired
    also fire (warning_days = 0 means fire only on expiry day).
    """
    from django.utils import timezone as tz
    from crm.models import AutomationRule, AutomationRun, AutomationRunStatus, Management

    now = tz.now()

    # Collect all firms with active sla_expiring rules
    firm_ids = (
        AutomationRule.objects
        .filter(trigger="sla_expiring", is_active=True)
        .values_list("firm_id", flat=True)
        .distinct()
    )

    for firm_id in firm_ids:
        rules = list(AutomationRule.objects.filter(
            firm_id=firm_id, trigger="sla_expiring", is_active=True
        ))
        max_warning_days = max(
            (int(r.trigger_config.get("warning_days", 3)) for r in rules),
            default=3,
        )
        cutoff = now + datetime.timedelta(days=max_warning_days)

        # Management records with expiry within the window (including already-expired)
        records = Management.objects.filter(
            firm_id=firm_id,
            expires_at__isnull=False,
            expires_at__lte=cutoff,
        ).exclude(status="closed").select_related("realization", "customer", "assigned_to")

        for record in records:
            days_remaining = (record.expires_at - now).total_seconds() / 86400
            customer_name = ""
            customer_email = ""
            if record.customer:
                customer_name = (
                    f"{record.customer.first_name} {record.customer.last_name}".strip()
                )
                customer_email = record.customer.email or ""

            context = {
                "management_id": str(record.id),
                "management_title": record.title,
                "management_type": record.type,
                "management_status": record.status,
                "realization_id": str(record.realization_id) if record.realization_id else "",
                "realization_title": record.realization.title if record.realization else "",
                "firm_id": str(firm_id),
                "expires_at": record.expires_at.isoformat(),
                "days_remaining": str(int(days_remaining)),
                "assignee_email": record.assigned_to.email if record.assigned_to else "",
                "assignee_name": (
                    f"{record.assigned_to.first_name} {record.assigned_to.last_name}".strip()
                    if record.assigned_to else ""
                ),
                "customer_email": customer_email,
                "customer_name": customer_name,
            }

            for rule in rules:
                warning_days = int(rule.trigger_config.get("warning_days", 3))
                if days_remaining > warning_days:
                    continue  # Not yet in this rule's window

                # Skip if already fired for this record in the last 24 hours
                already_ran = AutomationRun.objects.filter(
                    rule=rule,
                    triggered_at__gte=now - datetime.timedelta(hours=24),
                ).filter(context__management_id=str(record.id)).exists()
                if already_ran:
                    continue

                _execute_rule(rule, context)


# ===========================================================================
# Phase 7 — Spawn Recurring Task Instances
# ===========================================================================

def _next_due_date_for_recurrence(recurrence: dict, from_dt: "datetime.datetime") -> "Optional[datetime.datetime]":
    """
    Compute the next due date based on a recurrence config dict.

    Supported types:
      - ``daily``   — repeat every ``interval`` days
      - ``weekly``  — repeat every ``interval`` weeks; ``day_of_week`` may be
                      a list of weekday numbers (0=Monday … 6=Sunday).
      - ``monthly`` — repeat every ``interval`` months on the same day
      - ``custom``  — alias for ``daily`` with arbitrary interval

    Returns ``None`` when ``ends_at`` is set and has already passed.
    """
    import datetime as _dt
    from django.utils import timezone as _tz

    rec_type = recurrence.get("type", "daily")
    interval = max(1, int(recurrence.get("interval", 1)))
    ends_at_str = recurrence.get("ends_at")

    ends_at = None
    if ends_at_str:
        try:
            from django.utils.dateparse import parse_datetime as _pd
            ends_at = _pd(ends_at_str)
            if ends_at is None:
                ends_at = _dt.datetime.fromisoformat(ends_at_str)
            if _tz.is_naive(ends_at):
                ends_at = _tz.make_aware(ends_at)
        except (ValueError, TypeError):
            ends_at = None

    if rec_type == "daily" or rec_type == "custom":
        next_dt = from_dt + _dt.timedelta(days=interval)
    elif rec_type == "weekly":
        day_of_week = recurrence.get("day_of_week")
        if day_of_week and isinstance(day_of_week, list) and len(day_of_week) > 0:
            # Find the next matching weekday within the week(s) defined by interval.
            # Skip forward at most 7 days to find the nearest matching day.
            normalized_days = [int(d) % 7 for d in day_of_week]
            candidate = from_dt + _dt.timedelta(days=1)
            for _ in range(7):  # at most 7 days to find next matching weekday
                if candidate.weekday() in normalized_days:
                    break
                candidate += _dt.timedelta(days=1)
            # Advance by (interval - 1) additional full weeks for multi-week intervals
            next_dt = candidate + _dt.timedelta(weeks=max(0, interval - 1))
        else:
            next_dt = from_dt + _dt.timedelta(weeks=interval)
    elif rec_type == "monthly":
        import calendar as _cal
        month = from_dt.month + interval
        year = from_dt.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        max_day = _cal.monthrange(year, month)[1]
        day = min(from_dt.day, max_day)
        next_dt = from_dt.replace(year=year, month=month, day=day)
    else:
        next_dt = from_dt + _dt.timedelta(days=interval)

    if ends_at and next_dt > ends_at:
        return None
    return next_dt


@shared_task
def spawn_recurring_tasks():
    """
    Celery periodic task — run once daily (e.g. at midnight UTC).

    Finds all root recurring tasks that were completed since the last run
    and spawns a new instance for the next recurrence date.

    A "root" recurring task is one where ``recurrence`` is not null and
    ``recurrence_parent`` is null (i.e. it is the original template task).
    We spawn from the *most-recent completed instance* (which could be the
    root itself or the last spawned copy).
    """
    import datetime as _dt
    from django.utils import timezone as _tz
    from crm.models import Task, StreamlineItem

    logger.info("spawn_recurring_tasks: starting")
    now = _tz.now()

    # Find all recurring root tasks that have been completed and have no
    # outstanding (incomplete) instance already spawned.
    root_tasks = Task.objects.filter(
        recurrence__isnull=False,
        recurrence_parent__isnull=True,  # only root tasks
        is_completed=True,
    ).select_related("firm", "lead", "proposal", "customer", "assigned_to", "created_by")

    spawned = 0
    for root in root_tasks:
        # Check whether there is already a pending (uncompleted) child instance
        pending_child = Task.objects.filter(
            recurrence_parent=root,
            is_completed=False,
            is_archived=False,
        ).exists()
        if pending_child:
            continue

        # Find the most-recently-completed instance (root or last child)
        last_instance = (
            Task.objects.filter(
                recurrence_parent=root,
                is_completed=True,
            )
            .order_by("-completed_at")
            .first()
        )
        source = last_instance if last_instance else root

        # Use the scheduled due_date as anchor to prevent drift caused by
        # late completions.  Fall back to completed_at only when due_date
        # is absent, and finally to now() as a last resort.
        from_dt = source.due_date or source.completed_at or now

        # Compute next due date
        next_due = _next_due_date_for_recurrence(root.recurrence, from_dt)
        if next_due is None:
            logger.debug("spawn_recurring_tasks: recurrence ended for task %s", root.id)
            continue

        # Create new instance
        try:
            new_task = Task.objects.create(
                firm=root.firm,
                lead=root.lead,
                proposal=root.proposal,
                customer=root.customer,
                title=root.title,
                description=root.description,
                description_html=root.description_html,
                description_added_at=root.description_added_at,
                priority=root.priority,
                assigned_to=root.assigned_to,
                created_by=root.created_by,
                tags=list(root.tags) if isinstance(root.tags, list) else [],
                estimated_minutes=root.estimated_minutes,
                due_date=next_due,
                recurrence=root.recurrence,
                recurrence_parent=root,
                approval_required=root.approval_required,
            )
            # Copy streamline items from root
            for item in StreamlineItem.objects.filter(task=root).order_by("kind", "order", "created_at"):
                StreamlineItem.objects.create(
                    task=new_task,
                    text=item.text,
                    kind=item.kind,
                    order=item.order,
                    created_by=root.created_by,
                )
            spawned += 1
            logger.info(
                "spawn_recurring_tasks: spawned task '%s' (id=%s) for root=%s, due=%s",
                new_task.title, new_task.id, root.id, next_due,
            )
        except Exception as exc:
            logger.exception("spawn_recurring_tasks: failed to spawn for root=%s: %s", root.id, exc)

    logger.info("spawn_recurring_tasks: done — spawned %d tasks", spawned)
    return spawned


# ---------------------------------------------------------------------------
# Auto-expire scheduled tasks (Calendar / Task unification)
# ---------------------------------------------------------------------------
#
# Calendar-bound tasks (kind=call/meeting) carry ``auto_close_on_expiry=True``.
# Once their ``due_date`` (or ``due_date_end`` if set) has passed by more than
# the configured per-kind grace period and the task has not been manually
# resolved (DONE/CANCELLED), this periodic job transitions them to the
# terminal ``EXPIRED`` status and emits a ``task_expired`` Activity into the
# linked entity's timeline so the history stays auditable.
#
# Notifications go to assignee + watchers prompting them to either log the
# real-world outcome (Activity ``call``/``meeting``) or reschedule the task.

# Default grace periods per task kind — how long after ``due_date_end``
# (or ``due_date`` if no end is set) we wait before auto-closing.
_DEFAULT_GRACE_MINUTES_BY_KIND = {
    "call": 120,        # 2 hours
    "meeting": 24 * 60, # 24 hours
    "email_followup": 24 * 60,
    "generic": 0,
}


@shared_task(bind=True, max_retries=0)
def auto_expire_scheduled_tasks(self):
    """
    Periodic Celery job — auto-close calendar-bound tasks past their grace.

    A task is auto-expired when **all** of the following hold:

    * ``auto_close_on_expiry`` is True
    * ``is_completed`` is False and ``is_archived`` is False
    * ``status`` is not already a terminal value (done/cancelled/expired)
    * ``due_date`` is set and the configured grace period (per ``kind``) has
      elapsed since the task's effective end (``due_date_end`` or ``due_date``)

    On expiry the task transitions to ``status='expired'`` and emits a
    ``task_expired`` Activity onto the linked CRM entity's timeline.
    """
    import datetime as _dt
    from django.db import transaction
    from django.utils import timezone as _tz
    from crm.events import broadcast_event
    from crm.models import (
        Activity,
        ActivityType,
        Notification,
        Task,
        TaskStatus,
    )

    now = _tz.now()
    terminal_statuses = {
        TaskStatus.DONE,
        TaskStatus.CANCELLED,
        TaskStatus.EXPIRED,
    }

    candidates = (
        Task.objects
        .filter(
            auto_close_on_expiry=True,
            is_completed=False,
            is_archived=False,
            due_date__isnull=False,
            due_date__lte=now,
        )
        .exclude(status__in=list(terminal_statuses))
        .select_related("firm", "assigned_to", "lead", "customer", "realization", "management", "proposal")
    )

    expired_count = 0
    prompted_count = 0
    for task in candidates:
        effective_end = task.due_date_end or task.due_date
        grace_minutes = _DEFAULT_GRACE_MINUTES_BY_KIND.get(
            task.kind, _DEFAULT_GRACE_MINUTES_BY_KIND["generic"]
        )
        threshold = effective_end + _dt.timedelta(minutes=grace_minutes)

        # Within the grace window: prompt the assignee/watchers once to log
        # the outcome (held / rescheduled / no_show) instead of silently
        # auto-expiring. We only prompt for kinds with a non-zero grace,
        # since "generic" tasks have no grace and thus no prompt window.
        if now < threshold:
            if (
                task.outcome_prompted_at is None
                and grace_minutes > 0
                and now >= effective_end
            ):
                _send_outcome_prompt(task, now, logger=logger)
                prompted_count += 1
            continue

        try:
            with transaction.atomic():
                # Re-check inside the transaction to avoid races.
                task.refresh_from_db()
                if (
                    task.is_completed
                    or task.is_archived
                    or task.status in terminal_statuses
                    or not task.auto_close_on_expiry
                ):
                    continue

                task.status = TaskStatus.EXPIRED
                task.save(update_fields=["status"])

                activity = Activity.objects.create(
                    lead=task.lead,
                    realization=task.realization,
                    management=task.management,
                    customer=task.customer,
                    proposal=task.proposal,
                    task=task,
                    user=None,
                    type=ActivityType.TASK_EXPIRED,
                    content_text="",
                    metadata={
                        "task_id": str(task.id),
                        "task_title": task.title,
                        "task_kind": task.kind,
                        "due_date": task.due_date.isoformat() if task.due_date else None,
                        "expired_at": now.isoformat(),
                    },
                )

                # Notify assignee + watchers (best-effort).
                recipients = set()
                if task.assigned_to_id:
                    recipients.add(task.assigned_to_id)
                try:
                    recipients.update(task.watchers.values_list("id", flat=True))
                except Exception:  # pragma: no cover — defensive
                    logger.debug(
                        "auto_expire_scheduled_tasks: could not resolve watchers for task %s",
                        task.id,
                    )

                notification_payload = {
                    "task_id": str(task.id),
                    "task_title": task.title,
                    "task_kind": task.kind,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                }
                for user_id in recipients:
                    try:
                        Notification.objects.create(
                            firm=task.firm,
                            user_id=user_id,
                            event="task.expired",
                            payload=notification_payload,
                        )
                    except Exception as exc:  # pragma: no cover — defensive
                        logger.debug(
                            "auto_expire_scheduled_tasks: notification failed for user=%s task=%s: %s",
                            user_id, task.id, exc,
                        )
        except Exception as exc:
            logger.exception(
                "auto_expire_scheduled_tasks: failed to expire task=%s: %s",
                task.id, exc,
            )
            continue

        expired_count += 1

        # Best-effort WebSocket broadcast (outside the atomic block so a
        # broker outage cannot roll back the DB transition).
        try:
            broadcast_event(
                firm=task.firm,
                event="task.expired",
                payload={
                    "task_id": str(task.id),
                    "activity_id": str(activity.id),
                    "task_title": task.title,
                    "task_kind": task.kind,
                },
            )
        except Exception:  # pragma: no cover — defensive
            logger.debug(
                "auto_expire_scheduled_tasks: broadcast failed for task=%s",
                task.id,
            )

    logger.info(
        "auto_expire_scheduled_tasks: expired %d task(s), prompted %d task(s)",
        expired_count, prompted_count,
    )
    return expired_count


def _send_outcome_prompt(task, now, *, logger):
    """Persist + broadcast a one-time ``task.outcome_prompt`` notification.

    Sets ``Task.outcome_prompted_at = now`` so a single task is only ever
    prompted once per scheduled occurrence; rescheduling clears the field
    and reopens the prompt window.

    Best-effort: any failure is logged but does not propagate so the
    auto-expire loop keeps draining its queue.
    """
    from django.db import transaction
    from crm.models import Notification

    try:
        with transaction.atomic():
            task.refresh_from_db(fields=["outcome_prompted_at", "is_completed", "is_archived", "status"])
            if task.outcome_prompted_at is not None:
                return
            task.outcome_prompted_at = now
            task.save(update_fields=["outcome_prompted_at"])

            recipients = set()
            if task.assigned_to_id:
                recipients.add(task.assigned_to_id)
            try:
                recipients.update(task.watchers.values_list("id", flat=True))
            except Exception:  # pragma: no cover — defensive
                logger.debug(
                    "_send_outcome_prompt: could not resolve watchers for task %s",
                    task.id,
                )

            payload = {
                "task_id": str(task.id),
                "task_title": task.title,
                "task_kind": task.kind,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "due_date_end": task.due_date_end.isoformat() if task.due_date_end else None,
            }
            for user_id in recipients:
                try:
                    Notification.objects.create(
                        firm=task.firm,
                        user_id=user_id,
                        event="task.outcome_prompt",
                        payload=payload,
                    )
                except Exception as exc:  # pragma: no cover — defensive
                    logger.debug(
                        "_send_outcome_prompt: notification failed for user=%s task=%s: %s",
                        user_id, task.id, exc,
                    )
    except Exception:
        logger.exception("_send_outcome_prompt: failed for task=%s", task.id)
        return

    # Best-effort WS push so a connected SPA refreshes immediately.
    # We send only the channel-layer message; the persistent Notifications
    # were already created above for the targeted recipients.
    try:
        from crm.events import _send_channel_message
        ws_payload = {
            "task_id": str(task.id),
            "task_title": task.title,
            "task_kind": task.kind,
        }
        from django.db import transaction as _transaction
        _transaction.on_commit(
            lambda: _send_channel_message(
                firm_id=str(task.firm_id),
                event="task.outcome_prompt",
                payload=ws_payload,
            )
        )
    except Exception:  # pragma: no cover — defensive
        logger.debug("_send_outcome_prompt: ws push failed for task=%s", task.id)


# ---------------------------------------------------------------------------
# Streamline FileUploadTool — async URL fetch (Fáze 7.2)
# ---------------------------------------------------------------------------

#: Maximum bytes we are willing to pull from a remote URL.  Mirrors the
#: hard ceiling of an authenticated file upload (free plan = 15 MB,
#: pro = 100 MB) — we always honour the higher cap here because the
#: source URL was already user-validated; per-plan validation lives in
#: the request path that schedules this task.
_REMOTE_FETCH_HARD_LIMIT_BYTES = 100 * 1024 * 1024

#: Connect / read timeout (seconds) for the remote fetch.  Files that
#: cannot be retrieved within this window are flagged ``failed`` and the
#: original URL stays as a plain reference in the activity metadata.
_REMOTE_FETCH_TIMEOUT_SECONDS = 30


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def fetch_remote_file_for_activity(self, activity_id: str):
    """Download a remote file referenced by a ``file_upload`` Activity.

    Triggered by ``FileUploadTool.process_action`` whenever the user
    submitted a URL with ``store_locally=true``.  On success the
    associated ``Document`` is populated with the downloaded binary,
    ``activity.metadata`` is patched with ``filename`` / ``size_bytes`` /
    ``mime_type`` / ``document_id`` / ``fetch_status="ok"`` and the
    canonical CRM ``url`` is rewritten to the local storage URL.

    On failure ``fetch_status`` is set to ``"failed"`` and a short
    ``fetch_error`` message is recorded; the source URL stays in
    ``metadata.url`` so the user can still click through.
    """
    import os
    from urllib.parse import urlparse

    import requests
    from django.core.files.base import ContentFile

    from crm.models import Activity, Document

    try:
        activity = Activity.objects.get(id=activity_id)
    except Activity.DoesNotExist:
        logger.warning("fetch_remote_file_for_activity: activity %s missing", activity_id)
        return

    meta = dict(activity.metadata or {})
    source_url = meta.get("url")
    if not source_url:
        return

    try:
        with requests.get(
            source_url,
            stream=True,
            timeout=_REMOTE_FETCH_TIMEOUT_SECONDS,
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()
            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > _REMOTE_FETCH_HARD_LIMIT_BYTES:
                raise ValueError("remote-file-too-large")
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > _REMOTE_FETCH_HARD_LIMIT_BYTES:
                    raise ValueError("remote-file-too-large")
                chunks.append(chunk)
            payload = b"".join(chunks)
            mime_type = (resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()

        # Pick a sensible storage filename from the URL path.
        parsed = urlparse(source_url)
        basename = os.path.basename(parsed.path) or "remote-file"
        if "." not in basename:
            # Best-effort extension from the MIME type so the file is
            # recognisable later.
            ext = ""
            if "/" in mime_type:
                ext = "." + mime_type.split("/", 1)[1].split("+", 1)[0]
            basename = f"{basename}{ext}"

        # Preserve any existing entity links from sibling activity rows
        # so the document shows up in the right "files" tab.  Activity
        # doesn't carry its own ``firm`` FK — derive it from whichever
        # parent entity is set.
        firm = None
        for parent in (
            getattr(activity, "lead", None),
            getattr(activity, "customer", None),
            getattr(activity, "realization", None),
            getattr(activity, "management", None),
            getattr(activity, "proposal", None),
            getattr(activity, "task", None),
        ):
            if parent is not None and getattr(parent, "firm_id", None):
                firm = parent.firm
                break
        if firm is None:
            raise ValueError("activity has no parent entity to attach the file to")

        doc = Document(
            firm=firm,
            lead=getattr(activity, "lead", None),
            customer=getattr(activity, "customer", None),
            realization=getattr(activity, "realization", None),
            management=getattr(activity, "management", None),
            proposal=getattr(activity, "proposal", None),
            task=getattr(activity, "task", None),
            uploaded_by=getattr(activity, "user", None),
            name=basename,
            content_type=mime_type or "application/octet-stream",
            size_bytes=len(payload),
        )
        doc.file.save(basename, ContentFile(payload), save=True)

        meta.update(
            {
                "document_id": str(doc.id),
                "filename": doc.name,
                "size_bytes": doc.size_bytes,
                "mime_type": doc.content_type,
                "url": doc.file.url if doc.file.name else source_url,
                "source_url": source_url,
                "fetch_status": "ok",
            }
        )
        activity.metadata = meta
        activity.save(update_fields=["metadata"])
    except Exception as exc:
        logger.warning(
            "fetch_remote_file_for_activity: %s failed for activity %s",
            exc,
            activity_id,
        )
        meta.update(
            {
                "fetch_status": "failed",
                "fetch_error": str(exc)[:200],
            }
        )
        try:
            activity.metadata = meta
            activity.save(update_fields=["metadata"])
        except Exception:  # pragma: no cover — last-ditch safety
            pass


# ---------------------------------------------------------------------------
# Soft-delete purge task (Phase 5)
# ---------------------------------------------------------------------------

@shared_task(bind=True, name="crm.tasks.purge_soft_deleted_records")
def purge_soft_deleted_records(self):
    """
    Hard-delete soft-deleted records whose ``purge_after`` timestamp has elapsed.

    Runs nightly via Celery Beat (configured in settings.CELERY_BEAT_SCHEDULE).
    For Document records with a physical file, the file is deleted before the
    DB row is removed.
    """
    from django.utils import timezone as tz
    from crm.models import (
        Customer,
        Lead,
        Task,
        Realization,
        Management,
        Activity,
        Proposal,
        TimeEntry,
        ExpenseItem,
        RevenueItem,
        AutomationRule,
        ProposalTemplate,
        FirmProposalItem,
        TaskTemplate,
        TaskCustomField,
        Document,
    )

    now = tz.now()
    total = 0

    models_to_purge = [
        ("Customer", Customer),
        ("Lead", Lead),
        ("Task", Task),
        ("Realization", Realization),
        ("Management", Management),
        ("Proposal", Proposal),
        ("TimeEntry", TimeEntry),
        ("ExpenseItem", ExpenseItem),
        ("RevenueItem", RevenueItem),
        ("AutomationRule", AutomationRule),
        ("ProposalTemplate", ProposalTemplate),
        ("FirmProposalItem", FirmProposalItem),
        ("TaskTemplate", TaskTemplate),
        ("TaskCustomField", TaskCustomField),
    ]

    for label, Model in models_to_purge:
        qs = Model.all_objects.filter(is_deleted=True, purge_after__lte=now)
        count, _ = qs.delete()
        if count:
            logger.info("purge_soft_deleted_records: deleted %d %s record(s)", count, label)
        total += count

    # Activity: uses its own is_deleted field (not SoftDeleteMixin) so
    # we use the standard manager directly.
    act_qs = Activity.objects.filter(
        is_deleted=True, purge_after__isnull=False, purge_after__lte=now
    )
    act_count, _ = act_qs.delete()
    if act_count:
        logger.info("purge_soft_deleted_records: deleted %d Activity record(s)", act_count)
    total += act_count

    # Document: delete physical file before hard-deleting the DB row
    doc_qs = Document.all_objects.filter(is_deleted=True, purge_after__lte=now)
    for doc in doc_qs:
        if doc.file:
            try:
                doc.file.delete(save=False)
            except Exception:
                pass
    doc_count, _ = doc_qs.delete()
    if doc_count:
        logger.info("purge_soft_deleted_records: deleted %d Document record(s)", doc_count)
    total += doc_count

    logger.info("purge_soft_deleted_records: total %d record(s) hard-deleted", total)
    return {"purged": total}


# ---------------------------------------------------------------------------
# Exchange Rate Engine – ECB fetch & canonical amount recalculation
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def fetch_ecb_exchange_rates(self):
    """
    Download the daily ECB XML exchange rate feed and upsert SystemExchangeRate
    records.  Idempotent – skips if rates for today are already present.

    Runs daily at 17:30 CET via Celery beat (ECB publishes by ~16:00 CET).
    When all retries are exhausted, sends an admin email notification.
    """
    import xml.etree.ElementTree as ET

    import requests
    from firms.models import SystemExchangeRate

    ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    ECB_NS = "http://www.gesmes.org/xml/2002-08-01"
    CUBE_NS = "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"

    try:
        resp = requests.get(ECB_URL, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("fetch_ecb_exchange_rates: request failed – %s", exc)
        if self.request.retries >= self.max_retries:
            _notify_ecb_failure(
                f"ECB exchange rate download failed after {self.max_retries} attempts.\n\n"
                f"Error: {exc}\n\nNew canonical_amount calculations may be affected "
                f"until the next successful fetch."
            )
        raise self.retry(exc=exc)

    try:
        root = ET.fromstring(resp.content)
        # ECB XML structure: Envelope/Cube/Cube[@time]/Cube[@currency @rate]
        outer_cubes = root.findall(f"{{{CUBE_NS}}}Cube/{{{CUBE_NS}}}Cube")
        if not outer_cubes:
            # Fall back to unqualified tag names (some versions of the feed)
            outer_cubes = root.findall(".//Cube[@time]")
        if not outer_cubes:
            logger.error("fetch_ecb_exchange_rates: unexpected XML structure")
            return {"status": "error", "detail": "unexpected XML"}

        date_cube = outer_cubes[0]
        rate_date_str = date_cube.attrib.get("time")
        if not rate_date_str:
            logger.error("fetch_ecb_exchange_rates: missing date in XML")
            return {"status": "error", "detail": "missing date"}

        rate_date = datetime.date.fromisoformat(rate_date_str)

        # Idempotency check
        if SystemExchangeRate.objects.filter(date=rate_date).exists():
            logger.info("fetch_ecb_exchange_rates: rates for %s already present, skipping", rate_date)
            return {"status": "skipped", "date": str(rate_date)}

        created_count = 0
        inner_cubes = date_cube.findall(f"{{{CUBE_NS}}}Cube") or date_cube.findall("Cube")
        for cube in inner_cubes:
            currency = cube.attrib.get("currency")
            rate_str = cube.attrib.get("rate")
            if not currency or not rate_str:
                continue
            SystemExchangeRate.objects.update_or_create(
                base_currency="EUR",
                quote_currency=currency,
                date=rate_date,
                defaults={"rate": Decimal(rate_str), "source": "ecb"},
            )
            created_count += 1

        logger.info("fetch_ecb_exchange_rates: upserted %d rates for %s", created_count, rate_date)
        return {"status": "ok", "date": str(rate_date), "count": created_count}

    except Exception as exc:
        logger.exception("fetch_ecb_exchange_rates: parse error – %s", exc)
        if self.request.retries >= self.max_retries:
            _notify_ecb_failure(
                f"ECB exchange rate parsing failed after {self.max_retries} attempts.\n\n"
                f"Error: {exc}"
            )
        raise self.retry(exc=exc)


def _notify_ecb_failure(detail: str) -> None:
    """
    Send an admin notification when the ECB exchange rate fetch fails
    after all retries are exhausted.  Uses Django's mail_admins() so the
    email goes to everyone listed in settings.ADMINS.  Failures are logged
    regardless of whether ADMINS is configured.
    """
    import datetime as _dt

    from django.core.mail import mail_admins

    subject = "LeadLab: ECB exchange rate fetch failed"
    message = (
        f"The daily ECB exchange rate fetch task has failed.\n\n"
        f"{detail}\n\n"
        f"Time: {_dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        "Please check the Celery worker logs for more details. "
        "If the problem persists, consider adding manual exchange rates in the workspace settings "
        "to ensure accurate currency conversions."
    )
    logger.error("fetch_ecb_exchange_rates: all retries exhausted – %s", detail)
    try:
        mail_admins(subject, message, fail_silently=True)
    except Exception as mail_exc:
        logger.warning("_notify_ecb_failure: could not send admin email – %s", mail_exc)


@shared_task
def recalculate_canonical_amounts_for_firm(firm_id: str):
    """
    Recalculate canonical_amount for all financial records of a firm.

    Triggered when:
    - Owner saves a new manual exchange rate
    - Owner changes firm.default_currency
    - Manual admin action via management command
    """
    from decimal import Decimal as _D

    from firms.models import Firm
    from crm.models import Lead, ExpenseItem, RevenueItem
    from crm.money import to_canonical
    from django.utils import timezone

    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        logger.error("recalculate_canonical_amounts_for_firm: firm %s not found", firm_id)
        return {"error": "firm_not_found"}

    updated = 0
    failed = 0

    tasks_def = [
        (Lead, "value", "created_at"),
        (ExpenseItem, "amount", "date"),
        (RevenueItem, "amount", "date"),
    ]

    for model_class, amount_field, date_field in tasks_def:
        qs = model_class.objects.filter(firm=firm).exclude(**{amount_field: None})
        for obj in qs.iterator(chunk_size=500):
            amount = getattr(obj, amount_field)
            record_date = getattr(obj, date_field, None)
            if hasattr(record_date, "date"):
                record_date = record_date.date()

            canonical, rate_used = to_canonical(amount, obj.currency, firm, date=record_date)
            obj.canonical_amount = canonical
            obj.canonical_currency = firm.default_currency
            obj.canonical_rate_used = rate_used
            obj.canonical_updated_at = timezone.now()
            obj.save(update_fields=[
                "canonical_amount", "canonical_currency",
                "canonical_rate_used", "canonical_updated_at",
            ])
            if canonical is not None:
                updated += 1
            else:
                failed += 1

    logger.info(
        "recalculate_canonical_amounts_for_firm [firm=%s]: %d updated, %d failed (no rate)",
        firm_id, updated, failed,
    )
    return {"updated": updated, "failed": failed}

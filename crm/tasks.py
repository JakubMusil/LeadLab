"""
Celery tasks for CRM (async email sending, statistics, etc.)
"""
import csv
import datetime
import io
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


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

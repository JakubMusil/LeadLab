"""
Celery tasks for CRM (async email sending, statistics, etc.)
"""
import csv
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

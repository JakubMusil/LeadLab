"""
Django Ninja router – Integrations

Covers:
  * iCal feed          — GET /api/v1/integrations/ical/tasks?token=<signed>
  * CSV import         — POST /api/v1/integrations/import/{leads|customers}
  * Import job status  — GET  /api/v1/integrations/import/{job_id}
  * CSV export         — GET  /api/v1/integrations/export/leads.csv
                         GET  /api/v1/integrations/export/customers.csv
  * PDF export         — GET  /api/v1/integrations/export/pipeline.pdf
"""

import csv
import hashlib
import hmac
import io
import logging
from typing import List, Optional

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone as tz
from ninja import File, Router, Schema, UploadedFile
from ninja.security import django_auth

from crm.models import Customer, ImportJob, ImportJobStatus, ImportJobType, Lead, LeadStatus, Task
from firms.auth import require_membership
from firms.token_auth import BearerTokenAuth

logger = logging.getLogger(__name__)

router = Router(tags=["integrations"])

_auth = [django_auth, BearerTokenAuth()]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ICAL_HMAC_KEY_SETTING = "SECRET_KEY"


def _ical_sign(user_id: str, firm_id: str) -> str:
    """Return an HMAC-SHA256 hex digest for the (user_id, firm_id) pair."""
    from django.conf import settings
    secret = getattr(settings, _ICAL_HMAC_KEY_SETTING, "").encode()
    msg = f"{user_id}:{firm_id}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _ical_verify(user_id: str, firm_id: str, token: str) -> bool:
    expected = _ical_sign(user_id, firm_id)
    return hmac.compare_digest(expected, token)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ImportJobOut(Schema):
    id: str
    type: str
    status: str
    total: int
    processed: int
    failed_count: int
    errors_json: List[dict]
    original_filename: str
    created_at: str
    finished_at: Optional[str]


class ErrorOut(Schema):
    detail: str


def _job_out(job: ImportJob) -> dict:
    return {
        "id": str(job.id),
        "type": job.type,
        "status": job.status,
        "total": job.total,
        "processed": job.processed,
        "failed_count": job.failed_count,
        "errors_json": job.errors_json,
        "original_filename": job.original_filename,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


# ---------------------------------------------------------------------------
# iCal feed
# ---------------------------------------------------------------------------

class ICalTokenOut(Schema):
    token: str
    url: str


@router.get(
    "/ical/token",
    auth=_auth,
    response={200: ICalTokenOut, 403: ErrorOut},
)
def get_ical_token(request):
    """
    Return a signed token and feed URL for the current user + firm.

    The returned URL can be imported into Google Calendar, Apple Calendar, etc.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    user_id = str(request.user.id)
    firm_id = str(request.firm.id)
    token = _ical_sign(user_id, firm_id)
    url = f"/api/v1/integrations/ical/tasks?user_id={user_id}&firm_id={firm_id}&token={token}"
    return 200, {"token": token, "url": url}


@router.get("/ical/tasks", auth=None)
def ical_feed(request, user_id: str, firm_id: str, token: str):
    """
    Public iCalendar feed for a user's tasks within a firm.

    Authentication is provided by a signed token from ``/ical/token``.
    """
    from icalendar import Calendar, Event, vText

    if not _ical_verify(user_id, firm_id, token):
        return HttpResponse("Forbidden", status=403)

    from firms.models import Firm
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return HttpResponse("Not found", status=404)

    from users.models import User
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return HttpResponse("Not found", status=404)

    from firms.models import Membership
    if not Membership.objects.filter(user=user, firm=firm).exists():
        return HttpResponse("Forbidden", status=403)

    tasks = (
        Task.objects.filter(firm=firm, assigned_to=user)
        .select_related("lead")
        .order_by("due_date")
    )

    cal = Calendar()
    cal.add("prodid", "-//LeadLab//LeadLab iCal Feed//EN")
    cal.add("version", "2.0")
    cal.add("X-WR-CALNAME", vText(f"LeadLab Tasks — {firm.name}"))
    cal.add("X-WR-TIMEZONE", vText("UTC"))

    for task in tasks:
        evt = Event()
        evt.add("uid", f"{task.id}@leadlab")
        evt.add("summary", task.title)
        if task.lead:
            evt.add("description", f"Lead: {task.lead.title}")
        evt.add("status", "COMPLETED" if task.is_completed else "NEEDS-ACTION")
        if task.due_date:
            evt.add("dtstart", task.due_date)
            evt.add("dtend", task.due_date)
        evt.add("dtstamp", tz.now())
        cal.add_component(evt)

    return HttpResponse(
        cal.to_ical(),
        content_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=tasks.ics"},
    )


# ---------------------------------------------------------------------------
# CSV Import
# ---------------------------------------------------------------------------

@router.post(
    "/import/leads",
    auth=_auth,
    response={202: ImportJobOut, 400: ErrorOut, 403: ErrorOut},
)
def import_leads_csv(request, file: UploadedFile = File(...)):
    """
    Upload a CSV file to bulk-import leads.

    Expected columns: ``title``, ``status`` (optional), ``source`` (optional),
    ``value`` (optional), ``currency`` (optional), ``description`` (optional).

    Returns an ``ImportJob`` object; poll ``GET /integrations/import/{id}``
    to track progress.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if not file.name.lower().endswith(".csv"):
        return 400, {"detail": "Only CSV files are accepted."}

    job = ImportJob.objects.create(
        firm=request.firm,
        user=request.user,
        type=ImportJobType.LEADS,
        file=file,
        original_filename=file.name,
    )

    try:
        from crm.tasks import process_import_job
        process_import_job.delay(str(job.id))
    except Exception:
        logger.warning("import_leads_csv: Could not enqueue process_import_job for %s", job.id)

    return 202, _job_out(job)


@router.post(
    "/import/customers",
    auth=_auth,
    response={202: ImportJobOut, 400: ErrorOut, 403: ErrorOut},
)
def import_customers_csv(request, file: UploadedFile = File(...)):
    """
    Upload a CSV file to bulk-import customers.

    Expected columns: ``first_name``, ``last_name`` (optional), ``email``
    (optional), ``phone`` (optional), ``company_name`` (optional).
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if not file.name.lower().endswith(".csv"):
        return 400, {"detail": "Only CSV files are accepted."}

    job = ImportJob.objects.create(
        firm=request.firm,
        user=request.user,
        type=ImportJobType.CUSTOMERS,
        file=file,
        original_filename=file.name,
    )

    try:
        from crm.tasks import process_import_job
        process_import_job.delay(str(job.id))
    except Exception:
        logger.warning("import_customers_csv: Could not enqueue process_import_job for %s", job.id)

    return 202, _job_out(job)


@router.get(
    "/import/{job_id}",
    auth=_auth,
    response={200: ImportJobOut, 403: ErrorOut, 404: ErrorOut},
)
def get_import_job(request, job_id: str):
    """Check the status of a CSV import job."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        job = ImportJob.objects.get(id=job_id, firm=request.firm)
    except ImportJob.DoesNotExist:
        return 404, {"detail": "Import job not found."}

    return 200, _job_out(job)


@router.get(
    "/import",
    auth=_auth,
    response={200: List[ImportJobOut], 403: ErrorOut},
)
def list_import_jobs(request, page: int = 1, page_size: int = 20):
    """List recent import jobs for the current firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    jobs = ImportJob.objects.filter(firm=request.firm)[offset: offset + page_size]
    return 200, [_job_out(j) for j in jobs]


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

def _echo_csv(rows):
    """Generator that yields CSV rows one at a time."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate()


@router.get("/export/leads.csv", auth=_auth)
def export_leads_csv(
    request,
    status: str = "",
    source: str = "",
    search: str = "",
):
    """
    Download the current filtered lead list as a CSV file.
    Accepts the same ``status``, ``source``, and ``search`` filters as the
    leads list endpoint.
    """
    try:
        require_membership(request)
    except Exception:
        return HttpResponse("Forbidden", status=403)

    from django.db.models import Q

    qs = Lead.objects.filter(firm=request.firm).select_related("customer", "assigned_to")
    if status:
        qs = qs.filter(status=status)
    if source:
        qs = qs.filter(source=source)
    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    def rows():
        yield [
            "id", "title", "status", "source", "value", "currency",
            "customer_name", "assigned_to", "created_at", "updated_at",
        ]
        for lead in qs.iterator():
            customer_name = ""
            if lead.customer:
                customer_name = f"{lead.customer.first_name} {lead.customer.last_name}".strip()
            assigned = lead.assigned_to.email if lead.assigned_to else ""
            yield [
                str(lead.id), lead.title, lead.status, lead.source,
                str(lead.value or ""), lead.currency,
                customer_name, assigned,
                lead.created_at.isoformat(), lead.updated_at.isoformat(),
            ]

    response = StreamingHttpResponse(
        _echo_csv(rows()),
        content_type="text/csv",
    )
    response["Content-Disposition"] = "attachment; filename=leads.csv"
    return response


@router.get("/export/customers.csv", auth=_auth)
def export_customers_csv(request, search: str = ""):
    """
    Download the current filtered customer list as a CSV file.
    """
    try:
        require_membership(request)
    except Exception:
        return HttpResponse("Forbidden", status=403)

    from django.db.models import Q

    qs = Customer.objects.filter(firm=request.firm)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(company_name__icontains=search)
        )

    def rows():
        yield ["id", "first_name", "last_name", "email", "phone", "company_name", "tags", "created_at"]
        for c in qs.iterator():
            yield [
                str(c.id), c.first_name, c.last_name, c.email,
                c.phone, c.company_name, ",".join(c.tags), c.created_at.isoformat(),
            ]

    response = StreamingHttpResponse(
        _echo_csv(rows()),
        content_type="text/csv",
    )
    response["Content-Disposition"] = "attachment; filename=customers.csv"
    return response


# ---------------------------------------------------------------------------
# PDF Export (pipeline summary)
# ---------------------------------------------------------------------------

@router.get("/export/pipeline.pdf", auth=_auth)
def export_pipeline_pdf(request):
    """
    Generate and download a pipeline summary PDF for the current firm.

    The PDF is generated on-the-fly via WeasyPrint.
    """
    try:
        require_membership(request)
    except Exception:
        return HttpResponse("Forbidden", status=403)

    from django.db.models import Count, Sum

    firm = request.firm

    # Build per-status summary
    rows = (
        Lead.objects.filter(firm=firm)
        .values("status")
        .annotate(count=Count("id"), total_value=Sum("value"))
        .order_by("status")
    )

    status_labels = {s.value: s.label for s in LeadStatus}

    # Build a simple HTML table for WeasyPrint
    total_leads = 0
    total_value = 0.0
    table_rows = ""
    for row in rows:
        label = status_labels.get(row["status"], row["status"])
        val = float(row["total_value"] or 0)
        total_leads += row["count"]
        total_value += val
        table_rows += (
            f"<tr><td>{label}</td>"
            f"<td>{row['count']}</td>"
            f"<td>{val:,.2f}</td></tr>"
        )

    generated_at = tz.now().strftime("%Y-%m-%d %H:%M UTC")

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
  h1 {{ color: #dc2626; margin-bottom: 4px; }}
  p.sub {{ color: #888; font-size: 12px; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
  th {{ background: #fef2f2; color: #dc2626; text-align: left; padding: 8px 12px; font-size: 13px; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }}
  tfoot td {{ font-weight: bold; border-top: 2px solid #ddd; }}
</style>
</head>
<body>
  <h1>Pipeline Summary — {firm.name}</h1>
  <p class="sub">Generated {generated_at}</p>
  <table>
    <thead>
      <tr><th>Status</th><th>Count</th><th>Total Value</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
    <tfoot>
      <tr><td>Total</td><td>{total_leads}</td><td>{total_value:,.2f}</td></tr>
    </tfoot>
  </table>
</body>
</html>"""

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()
    except Exception as exc:
        logger.exception("export_pipeline_pdf: WeasyPrint failed: %s", exc)
        return HttpResponse("PDF generation failed.", status=500)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=pipeline-summary.pdf"
    return response

"""
Django Ninja API router – CRM (Customers, Leads, Activities, Tasks)

Every endpoint requires:
  1. Session authentication.
  2. A valid Firm supplied via the ``X-Firm-ID`` header (resolved by TenantMiddleware).
  3. The authenticated user to be a member of that Firm.
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Count, Q, Sum

from django.db import transaction
from django.utils import timezone as tz
from ninja import File, Router, Schema, UploadedFile
from ninja.security import django_auth

from crm.models import Activity, ActivityType, Customer, Lead, LeadAttachment, LeadSource, LeadStatus, Notification, Task
from firms.auth import (
    MembershipRole,
    PermissionDenied,
    SubscriptionRequired,
    check_tier_limits,
    require_active_subscription,
    require_membership,
)
from firms.models import Membership

from crm.events import broadcast_event

router = Router(tags=["crm"])


# ---------------------------------------------------------------------------
# Shared error schema
# ---------------------------------------------------------------------------

class ErrorOut(Schema):
    detail: str


# ===========================================================================
# CUSTOMERS
# ===========================================================================

class CustomerOut(Schema):
    id: str
    firm_id: str
    first_name: str
    last_name: str
    email: str
    phone: str
    company_name: str
    tags: List[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CustomerIn(Schema):
    first_name: str
    last_name: str = ""
    email: str = ""
    phone: str = ""
    company_name: str = ""
    tags: List[str] = []
    metadata: Dict[str, Any] = {}


def _customer_out(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "firm_id": str(c.firm_id),
        "first_name": c.first_name,
        "last_name": c.last_name,
        "email": c.email,
        "phone": c.phone,
        "company_name": c.company_name,
        "tags": c.tags,
        "metadata": c.metadata,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get("/customers", auth=django_auth, response={200: List[CustomerOut], 403: ErrorOut})
def list_customers(request, search: str = "", page: int = 1, page_size: int = 20):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Customer.objects.filter(firm=request.firm)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(company_name__icontains=search)
            | Q(phone__icontains=search)
        )
    offset = (page - 1) * page_size
    return 200, [_customer_out(c) for c in qs[offset:offset + page_size]]


@router.post("/customers", auth=django_auth, response={201: CustomerOut, 403: ErrorOut})
def create_customer(request, payload: CustomerIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    customer = Customer.objects.create(firm=request.firm, **payload.dict())
    return 201, _customer_out(customer)


@router.get("/customers/{customer_id}", auth=django_auth, response={200: CustomerOut, 403: ErrorOut, 404: ErrorOut})
def get_customer(request, customer_id: str):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        customer = Customer.objects.get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}
    return 200, _customer_out(customer)


@router.put("/customers/{customer_id}", auth=django_auth, response={200: CustomerOut, 403: ErrorOut, 404: ErrorOut})
def update_customer(request, customer_id: str, payload: CustomerIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        customer = Customer.objects.get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}

    for field, value in payload.dict().items():
        setattr(customer, field, value)
    customer.save()
    return 200, _customer_out(customer)


@router.delete("/customers/{customer_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def delete_customer(request, customer_id: str):
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        customer = Customer.objects.get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}

    customer.delete()
    return 204, None


# ===========================================================================
# LEADS
# ===========================================================================

class LeadOut(Schema):
    id: str
    firm_id: str
    customer_id: Optional[str]
    title: str
    description: str
    status: str
    source: str
    assigned_to_id: Optional[str]
    value: Optional[Decimal]
    currency: str
    created_at: datetime
    updated_at: datetime


class LeadIn(Schema):
    title: str
    description: str = ""
    customer_id: Optional[str] = None
    status: str = LeadStatus.NEW
    source: str = LeadSource.WEB
    assigned_to_id: Optional[str] = None
    value: Optional[Decimal] = None
    currency: str = "CZK"


class LeadUpdateIn(Schema):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    assigned_to_id: Optional[str] = None
    value: Optional[Decimal] = None
    currency: Optional[str] = None


def _lead_out(lead: Lead) -> dict:
    return {
        "id": str(lead.id),
        "firm_id": str(lead.firm_id),
        "customer_id": str(lead.customer_id) if lead.customer_id else None,
        "title": lead.title,
        "description": lead.description,
        "status": lead.status,
        "source": lead.source,
        "assigned_to_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
        "value": lead.value,
        "currency": lead.currency,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


@router.get("/leads", auth=django_auth, response={200: List[LeadOut], 403: ErrorOut})
def list_leads(
    request,
    status: str = "",
    assigned_to: str = "",
    source: str = "",
    tag: str = "",
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Lead.objects.filter(firm=request.firm)
    if status:
        qs = qs.filter(status=status)
    if assigned_to:
        qs = qs.filter(assigned_to_id=assigned_to)
    if source:
        qs = qs.filter(source=source)
    if tag:
        qs = qs.filter(customer__tags__icontains=tag)
    if created_after:
        qs = qs.filter(created_at__gte=created_after)
    if created_before:
        qs = qs.filter(created_at__lte=created_before)
    offset = (page - 1) * page_size
    return 200, [_lead_out(lead) for lead in qs[offset:offset + page_size]]


@router.post("/leads", auth=django_auth, response={201: LeadOut, 400: ErrorOut, 402: ErrorOut, 403: ErrorOut})
def create_lead(request, payload: LeadIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
        check_tier_limits(request.firm)
    except SubscriptionRequired as exc:
        return 402, {"detail": str(exc)}
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    customer = None
    if payload.customer_id:
        try:
            customer = Customer.objects.get(id=payload.customer_id, firm=request.firm)
        except Customer.DoesNotExist:
            return 400, {"detail": "Customer not found in this Firm."}

    assigned_to = None
    if payload.assigned_to_id:
        from users.models import User
        try:
            assigned_to = User.objects.get(id=payload.assigned_to_id)
            if not Membership.objects.filter(user=assigned_to, firm=request.firm).exists():
                return 400, {"detail": "Assigned user is not a member of this Firm."}
        except User.DoesNotExist:
            return 400, {"detail": "Assigned user not found."}

    lead = Lead.objects.create(
        firm=request.firm,
        customer=customer,
        assigned_to=assigned_to,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        source=payload.source,
        value=payload.value,
        currency=payload.currency,
    )
    broadcast_event(firm=request.firm, event='lead.created', payload=_lead_out(lead))
    return 201, _lead_out(lead)


@router.get("/leads/{lead_id}", auth=django_auth, response={200: LeadOut, 403: ErrorOut, 404: ErrorOut})
def get_lead(request, lead_id: str):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}
    return 200, _lead_out(lead)


@router.patch("/leads/{lead_id}", auth=django_auth, response={200: LeadOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut})
def update_lead(request, lead_id: str, payload: LeadUpdateIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}

    old_status = lead.status
    update_data = payload.dict(exclude_none=True)

    # Handle status change — create an Activity in the same transaction
    new_status = update_data.pop("status", None)

    for field, value in update_data.items():
        setattr(lead, field, value)

    with transaction.atomic():
        if new_status and new_status != old_status:
            lead.status = new_status
            lead.save()
            Activity.objects.create(
                lead=lead,
                user=request.user,
                type=ActivityType.STATUS_CHANGE,
                metadata={
                    "old_status": old_status,
                    "new_status": new_status,
                },
            )
        else:
            lead.save()

    broadcast_event(firm=request.firm, event='lead.updated', payload=_lead_out(lead))
    return 200, _lead_out(lead)


@router.delete("/leads/{lead_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def delete_lead(request, lead_id: str):
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}

    lead.delete()
    broadcast_event(firm=request.firm, event='lead.deleted', payload={'id': lead_id})
    return 204, None


# ===========================================================================
# ACTIVITIES (Action Hub)
# ===========================================================================

class ActivityOut(Schema):
    id: str
    lead_id: str
    user_id: Optional[str]
    type: str
    content_text: str
    metadata: Dict[str, Any]
    created_at: datetime


class ActivityIn(Schema):
    lead_id: str
    type: str
    content_text: str = ""
    metadata: Dict[str, Any] = {}


def _activity_out(a: Activity) -> dict:
    return {
        "id": str(a.id),
        "lead_id": str(a.lead_id),
        "user_id": str(a.user_id) if a.user_id else None,
        "type": a.type,
        "content_text": a.content_text,
        "metadata": a.metadata,
        "created_at": a.created_at,
    }


@router.get("/leads/{lead_id}/activities", auth=django_auth, response={200: List[ActivityOut], 403: ErrorOut, 404: ErrorOut})
def list_activities(request, lead_id: str, page: int = 1, page_size: int = 20):
    """Return the timeline for a Lead, newest first (paginated)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(lead=lead).order_by("-created_at")[offset:offset + page_size]
    return 200, [_activity_out(a) for a in activities]


@router.post("/activities", auth=django_auth, response={201: ActivityOut, 400: ErrorOut, 403: ErrorOut})
def create_activity(request, payload: ActivityIn):
    """
    Unified Action Hub endpoint.

    Handles all activity types:
    - COMMENT / CALL / MEETING: stores content_text.
    - EMAIL_OUT: triggers async SMTP send via Celery.
    - STATUS_CHANGE: updates Lead.status atomically.
    - FILE_UPLOAD: expects metadata.url to be pre-signed/uploaded separately.
    - TASK_ASSIGNED / TASK_COMPLETED: mirrors Task state changes.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=payload.lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 400, {"detail": "Lead not found in this Firm."}

    if payload.type not in [t.value for t in ActivityType]:
        return 400, {"detail": f"Unknown activity type '{payload.type}'."}

    with transaction.atomic():
        activity = Activity.objects.create(
            lead=lead,
            user=request.user,
            type=payload.type,
            content_text=payload.content_text,
            metadata=payload.metadata,
        )

        # -- Side effects per activity type --
        if payload.type == ActivityType.STATUS_CHANGE:
            new_status = payload.metadata.get("new_status")
            if new_status and new_status in [s.value for s in LeadStatus]:
                old_status = lead.status
                lead.status = new_status
                lead.save(update_fields=["status", "updated_at"])
                activity.metadata = {**activity.metadata, "old_status": old_status}
                activity.save(update_fields=["metadata"])

        elif payload.type == ActivityType.EMAIL_OUT:
            # Trigger async Celery task (gracefully degrade if Celery not available)
            _trigger_email_task(activity, lead)

    broadcast_event(
        firm=request.firm,
        event='activity.created',
        payload=_activity_out(activity),
    )
    return 201, _activity_out(activity)


def _trigger_email_task(activity: Activity, lead: Lead):
    """Fire-and-forget Celery task for sending outbound emails."""
    try:
        from crm.tasks import send_activity_email
        send_activity_email.delay(str(activity.id))
    except Exception:
        # If Celery / Redis is not configured, log silently and continue.
        pass


# ===========================================================================
# TASKS
# ===========================================================================

class TaskOut(Schema):
    id: str
    firm_id: str
    lead_id: str
    assigned_to_id: Optional[str]
    title: str
    due_date: Optional[datetime]
    is_completed: bool
    completed_at: Optional[datetime]
    created_at: datetime


class TaskIn(Schema):
    lead_id: str
    title: str
    assigned_to_id: Optional[str] = None
    due_date: Optional[datetime] = None


def _task_out(t: Task) -> dict:
    return {
        "id": str(t.id),
        "firm_id": str(t.firm_id),
        "lead_id": str(t.lead_id),
        "assigned_to_id": str(t.assigned_to_id) if t.assigned_to_id else None,
        "title": t.title,
        "due_date": t.due_date,
        "is_completed": t.is_completed,
        "completed_at": t.completed_at,
        "created_at": t.created_at,
    }


@router.get("/tasks", auth=django_auth, response={200: List[TaskOut], 403: ErrorOut})
def list_tasks(request, completed: Optional[bool] = None, page: int = 1, page_size: int = 20):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Task.objects.filter(firm=request.firm)
    if completed is not None:
        qs = qs.filter(is_completed=completed)
    offset = (page - 1) * page_size
    return 200, [_task_out(t) for t in qs[offset:offset + page_size]]


@router.post("/tasks", auth=django_auth, response={201: TaskOut, 400: ErrorOut, 403: ErrorOut})
def create_task(request, payload: TaskIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=payload.lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 400, {"detail": "Lead not found in this Firm."}

    assigned_to = None
    if payload.assigned_to_id:
        from users.models import User
        try:
            assigned_to = User.objects.get(id=payload.assigned_to_id)
            if not Membership.objects.filter(user=assigned_to, firm=request.firm).exists():
                return 400, {"detail": "Assigned user is not a member of this Firm."}
        except User.DoesNotExist:
            return 400, {"detail": "Assigned user not found."}

    with transaction.atomic():
        task = Task.objects.create(
            firm=request.firm,
            lead=lead,
            assigned_to=assigned_to,
            title=payload.title,
            due_date=payload.due_date,
        )
        Activity.objects.create(
            lead=lead,
            user=request.user,
            type=ActivityType.TASK_ASSIGNED,
            metadata={
                "task_id": str(task.id),
                "due_date": payload.due_date.isoformat() if payload.due_date else None,
                "priority": "normal",
            },
        )

    return 201, _task_out(task)


@router.post("/tasks/{task_id}/complete", auth=django_auth, response={200: TaskOut, 403: ErrorOut, 404: ErrorOut})
def complete_task(request, task_id: str):
    """Mark a Task as completed and log a TASK_COMPLETED Activity."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if task.is_completed:
        return 200, _task_out(task)

    with transaction.atomic():
        task.is_completed = True
        task.completed_at = tz.now()
        task.save(update_fields=["is_completed", "completed_at"])
        Activity.objects.create(
            lead=task.lead,
            user=request.user,
            type=ActivityType.TASK_COMPLETED,
            metadata={"task_id": str(task.id), "title": task.title},
        )

    broadcast_event(firm=request.firm, event='task.completed', payload=_task_out(task))
    return 200, _task_out(task)


# ===========================================================================
# STATS
# ===========================================================================

class StatsOut(Schema):
    total_leads: int
    leads_by_status: Dict[str, int]
    total_customers: int
    total_tasks_pending: int
    total_tasks_overdue: int
    pipeline_value: float
    won_value: float
    conversion_rate: float
    recent_activities: List[ActivityOut]


@router.get("/stats", auth=django_auth, response={200: StatsOut, 403: ErrorOut})
def get_stats(request):
    """Return aggregated stats for the current Firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    now = tz.now()

    leads_qs = Lead.objects.filter(firm=request.firm)
    status_counts = {s.value: 0 for s in LeadStatus}
    for row in leads_qs.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]

    pipeline_value = float(
        leads_qs.exclude(status__in=[LeadStatus.WON, LeadStatus.LOST, LeadStatus.CANCELED])
        .aggregate(total=Sum("value"))["total"]
        or 0
    )
    won_value = float(
        leads_qs.filter(status=LeadStatus.WON).aggregate(total=Sum("value"))["total"] or 0
    )

    total_leads = leads_qs.count()
    won_leads = status_counts.get(LeadStatus.WON, 0)
    conversion_rate = round(won_leads / total_leads, 4) if total_leads else 0.0

    tasks_qs = Task.objects.filter(firm=request.firm, is_completed=False)
    total_tasks_pending = tasks_qs.count()
    total_tasks_overdue = tasks_qs.filter(due_date__lt=now).count()

    total_customers = Customer.objects.filter(firm=request.firm).count()

    recent_activities = (
        Activity.objects.filter(lead__firm=request.firm)
        .select_related("lead", "user")
        .order_by("-created_at")[:10]
    )

    return 200, {
        "total_leads": total_leads,
        "leads_by_status": status_counts,
        "total_customers": total_customers,
        "total_tasks_pending": total_tasks_pending,
        "total_tasks_overdue": total_tasks_overdue,
        "pipeline_value": pipeline_value,
        "won_value": won_value,
        "conversion_rate": conversion_rate,
        "recent_activities": [_activity_out(a) for a in recent_activities],
    }


# ===========================================================================
# LEAD ATTACHMENTS
# ===========================================================================

# Maximum allowed file size (20 MB)
_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class AttachmentOut(Schema):
    id: str
    lead_id: str
    firm_id: str
    uploaded_by_id: Optional[str]
    original_filename: str
    content_type: str
    size_bytes: int
    url: str
    created_at: datetime


def _attachment_out(a: LeadAttachment) -> dict:
    return {
        "id": str(a.id),
        "lead_id": str(a.lead_id),
        "firm_id": str(a.firm_id),
        "uploaded_by_id": str(a.uploaded_by_id) if a.uploaded_by_id else None,
        "original_filename": a.original_filename,
        "content_type": a.content_type,
        "size_bytes": a.size_bytes,
        "url": a.file.url if a.file.name else "",
        "created_at": a.created_at,
    }


@router.get(
    "/leads/{lead_id}/attachments",
    auth=django_auth,
    response={200: List[AttachmentOut], 403: ErrorOut, 404: ErrorOut},
)
def list_attachments(request, lead_id: str, page: int = 1, page_size: int = 20):
    """List all file attachments for a Lead, newest first (paginated)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}

    offset = (page - 1) * page_size
    attachments = LeadAttachment.objects.filter(lead=lead).order_by("-created_at")[
        offset: offset + page_size
    ]
    return 200, [_attachment_out(a) for a in attachments]


@router.post(
    "/leads/{lead_id}/attachments",
    auth=django_auth,
    response={201: AttachmentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_attachment(request, lead_id: str, file: UploadedFile = File(...)):
    """
    Upload a file and attach it to a Lead.

    The file is stored via Django's configured storage backend
    (local filesystem in development, S3 in production).
    A ``FILE_UPLOAD`` Activity is created atomically.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}

    if file.size > _MAX_ATTACHMENT_BYTES:
        return 400, {"detail": f"File exceeds the maximum allowed size of {_MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB."}

    with transaction.atomic():
        attachment = LeadAttachment(
            lead=lead,
            firm=request.firm,
            uploaded_by=request.user,
            original_filename=file.name,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file.size,
        )
        # save=True persists the model record after writing the file to storage.
        attachment.file.save(file.name, file, save=True)

        Activity.objects.create(
            lead=lead,
            user=request.user,
            type=ActivityType.FILE_UPLOAD,
            metadata={
                "attachment_id": str(attachment.id),
                "filename": attachment.original_filename,
                "url": attachment.file.url,
                "size_bytes": attachment.size_bytes,
            },
        )

    return 201, _attachment_out(attachment)


@router.delete(
    "/leads/{lead_id}/attachments/{attachment_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_attachment(request, lead_id: str, attachment_id: str):
    """
    Delete a file attachment from a Lead.

    Removes both the database record and the physical file from storage.
    Requires at least Admin role.
    """
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}

    try:
        attachment = LeadAttachment.objects.get(id=attachment_id, lead=lead)
    except LeadAttachment.DoesNotExist:
        return 404, {"detail": "Attachment not found."}

    # Delete the physical file from storage before removing the record.
    attachment.file.delete(save=False)
    attachment.delete()
    return 204, None


# ===========================================================================
# REPORTS (v0.6)
# ===========================================================================

# ---------------------------------------------------------------------------
# Pipeline summary
# ---------------------------------------------------------------------------

class PipelineStatusRow(Schema):
    status: str
    count: int
    total_value: float


class PipelineSummaryOut(Schema):
    statuses: List[PipelineStatusRow]
    total_value: float


@router.get(
    "/reports/pipeline",
    auth=django_auth,
    response={200: PipelineSummaryOut, 403: ErrorOut},
)
def pipeline_summary(request):
    """
    Lead pipeline summary: count and total estimated value per status.

    All lead statuses are always present in the response, even when the
    count is zero, so clients can render a consistent pipeline view.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    leads_qs = Lead.objects.filter(firm=request.firm)

    # Build a base dict with every status initialised to zero so that
    # statuses with no leads are still present in the response.
    counts: Dict[str, int] = {s.value: 0 for s in LeadStatus}
    values: Dict[str, float] = {s.value: 0.0 for s in LeadStatus}

    for row in leads_qs.values("status").annotate(
        n=Count("id"), v=Sum("value")
    ):
        counts[row["status"]] = row["n"]
        values[row["status"]] = float(row["v"] or 0)

    statuses = [
        {"status": s, "count": counts[s], "total_value": values[s]}
        for s in counts
    ]
    total_value = sum(values.values())

    return 200, {"statuses": statuses, "total_value": total_value}


# ---------------------------------------------------------------------------
# Firm-wide activity feed
# ---------------------------------------------------------------------------

class ActivityFeedItemOut(Schema):
    id: str
    lead_id: str
    lead_title: str
    user_id: Optional[str]
    type: str
    content_text: str
    metadata: Dict[str, Any]
    created_at: datetime


def _activity_feed_item_out(a: Activity) -> dict:
    return {
        "id": str(a.id),
        "lead_id": str(a.lead_id),
        "lead_title": a.lead.title,
        "user_id": str(a.user_id) if a.user_id else None,
        "type": a.type,
        "content_text": a.content_text,
        "metadata": a.metadata,
        "created_at": a.created_at,
    }


@router.get(
    "/reports/activities",
    auth=django_auth,
    response={200: List[ActivityFeedItemOut], 403: ErrorOut},
)
def activity_feed(
    request,
    type: str = "",
    page: int = 1,
    page_size: int = 20,
):
    """
    Firm-wide activity feed across all leads, newest first (paginated).

    Optionally filter by ``type`` (e.g. ``comment``, ``call``).
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = (
        Activity.objects.filter(lead__firm=request.firm)
        .select_related("lead")
        .order_by("-created_at")
    )
    if type:
        qs = qs.filter(type=type)

    offset = (page - 1) * page_size
    return 200, [_activity_feed_item_out(a) for a in qs[offset:offset + page_size]]


# ---------------------------------------------------------------------------
# Overdue task report
# ---------------------------------------------------------------------------

class OverdueTaskOut(Schema):
    id: str
    firm_id: str
    lead_id: str
    lead_title: str
    assigned_to_id: Optional[str]
    title: str
    due_date: Optional[datetime]
    created_at: datetime


def _overdue_task_out(t: Task) -> dict:
    return {
        "id": str(t.id),
        "firm_id": str(t.firm_id),
        "lead_id": str(t.lead_id),
        "lead_title": t.lead.title,
        "assigned_to_id": str(t.assigned_to_id) if t.assigned_to_id else None,
        "title": t.title,
        "due_date": t.due_date,
        "created_at": t.created_at,
    }


@router.get(
    "/reports/tasks/overdue",
    auth=django_auth,
    response={200: List[OverdueTaskOut], 403: ErrorOut},
)
def overdue_tasks(request, page: int = 1, page_size: int = 20):
    """
    List all incomplete tasks whose due date is in the past, oldest first.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    now = tz.now()
    qs = (
        Task.objects.filter(
            firm=request.firm,
            is_completed=False,
            due_date__lt=now,
        )
        .select_related("lead")
        .order_by("due_date")
    )
    offset = (page - 1) * page_size
    return 200, [_overdue_task_out(t) for t in qs[offset:offset + page_size]]


# ===========================================================================
# NOTIFICATIONS (v1.5)
# ===========================================================================

class NotificationOut(Schema):
    id: str
    event: str
    payload: Dict[str, Any]
    is_read: bool
    created_at: datetime


def _notification_out(n: Notification) -> dict:
    return {
        "id": str(n.id),
        "event": n.event,
        "payload": n.payload,
        "is_read": n.is_read,
        "created_at": n.created_at,
    }


@router.get(
    "/notifications",
    auth=django_auth,
    response={200: List[NotificationOut], 403: ErrorOut},
)
def list_notifications(request, unread_only: bool = False, page: int = 1, page_size: int = 30):
    """List in-app notifications for the current user within the active firm, newest first."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Notification.objects.filter(firm=request.firm, user=request.user).order_by("-created_at")
    if unread_only:
        qs = qs.filter(is_read=False)
    offset = (page - 1) * page_size
    return 200, [_notification_out(n) for n in qs[offset:offset + page_size]]


@router.post(
    "/notifications/mark-read",
    auth=django_auth,
    response={200: Dict[str, int], 403: ErrorOut},
)
def mark_notifications_read(request, ids: Optional[List[str]] = None):
    """
    Mark notifications as read.

    If ``ids`` is provided, only those notifications are marked.
    If ``ids`` is omitted or empty, all unread notifications for the user are marked.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Notification.objects.filter(firm=request.firm, user=request.user, is_read=False)
    if ids:
        qs = qs.filter(id__in=ids)
    updated = qs.update(is_read=True)
    return 200, {"updated": updated}


@router.get(
    "/notifications/unread-count",
    auth=django_auth,
    response={200: Dict[str, int], 403: ErrorOut},
)
def notifications_unread_count(request):
    """Return the number of unread notifications for the current user in the active firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    count = Notification.objects.filter(firm=request.firm, user=request.user, is_read=False).count()
    return 200, {"count": count}

"""
Django Ninja API router – CRM (Customers, Leads, Activities, Tasks)

Every endpoint requires:
  1. Session authentication.
  2. A valid Firm supplied via the ``X-Firm-ID`` header (resolved by TenantMiddleware).
  3. The authenticated user to be a member of that Firm.
"""
import datetime as dt
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.core.cache import cache
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q, Sum
from django.utils.dateparse import parse_datetime

from django.db import transaction
from django.utils import timezone as tz
from ninja import File, Router, Schema, UploadedFile
from ninja.security import django_auth

from crm.models import (
    Activity,
    ActivityType,
    Customer,
    DashboardLayout,
    Lead,
    LeadAttachment,
    LeadScoringRule,
    LeadSource,
    LeadStatus,
    LeadStatusHistory,
    Notification,
    SavedView,
    Task,
)
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
    score: Optional[int]
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


def _compute_lead_score(lead: Lead, rules: list) -> int:
    """
    Compute a 0–100 lead score by evaluating each scoring rule against
    the lead.  Rules are pre-fetched by the caller to avoid N+1 queries.

    Supported field values
    ----------------------
    ``status``                 — matches if lead.status == operand (string)
    ``source``                 — matches if lead.source == operand (string)
    ``value_gte``              — matches if lead.value >= operand (number)
    ``last_activity_days_lte`` — matches if the lead's most recent activity is
                                  within *operand* days (number)
    """
    score = 50  # baseline
    for rule in rules:
        field = rule.field
        operand = rule.operand
        matched = False

        if field == "status":
            matched = lead.status == operand
        elif field == "source":
            matched = lead.source == operand
        elif field == "value_gte":
            matched = lead.value is not None and lead.value >= Decimal(str(operand))
        elif field == "last_activity_days_lte":
            last_activity = (
                Activity.objects.filter(lead=lead)
                .order_by("-created_at")
                .values_list("created_at", flat=True)
                .first()
            )
            if last_activity:
                age_days = (tz.now() - last_activity).days
                matched = age_days <= int(operand)

        if matched:
            score += rule.score_delta

    return max(0, min(100, score))


def _lead_out(lead: Lead, rules: Optional[list] = None) -> dict:
    score = _compute_lead_score(lead, rules) if rules is not None else None
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
        "score": score,
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
    leads = list(qs[offset:offset + page_size])
    rules = list(LeadScoringRule.objects.filter(firm=request.firm))
    return 200, [_lead_out(lead, rules) for lead in leads]


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
            LeadStatusHistory.objects.create(
                lead=lead,
                from_status=old_status,
                to_status=new_status,
                changed_at=tz.now(),
                changed_by=request.user,
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
                LeadStatusHistory.objects.create(
                    lead=lead,
                    from_status=old_status,
                    to_status=new_status,
                    changed_at=activity.created_at,
                    changed_by=request.user,
                )

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


# ===========================================================================
# ADVANCED ANALYTICS (v1.8)
# ===========================================================================

_ANALYTICS_CACHE_SECONDS = 300  # 5-minute cache TTL


# ---------------------------------------------------------------------------
# Pipeline velocity
# ---------------------------------------------------------------------------

class VelocityRow(Schema):
    status: str
    avg_hours: float
    sample_count: int


@router.get(
    "/reports/pipeline-velocity",
    auth=django_auth,
    response={200: List[VelocityRow], 403: ErrorOut},
)
def pipeline_velocity(request):
    """
    Average time (in hours) a lead spends in each status, computed from
    ``LeadStatusHistory``.  Results are cached for 5 minutes.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    cache_key = f"analytics:pipeline_velocity:{request.firm.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    rows = list(
        LeadStatusHistory.objects.filter(lead__firm=request.firm)
        .values("to_status")
        .annotate(sample_count=Count("id"))
        .order_by("to_status")
    )

    # For each status, compute average dwell time:
    # dwell = time from entering a status until next transition (or now if current)
    status_hours: Dict[str, list] = {s.value: [] for s in LeadStatus}

    history_qs = (
        LeadStatusHistory.objects.filter(lead__firm=request.firm)
        .values("lead_id", "to_status", "changed_at")
        .order_by("lead_id", "changed_at")
    )

    # Group by lead
    lead_history: Dict[str, list] = {}
    for entry in history_qs:
        lead_history.setdefault(str(entry["lead_id"]), []).append(entry)

    now = tz.now()
    for lead_id, entries in lead_history.items():
        for i, entry in enumerate(entries):
            status = entry["to_status"]
            entered_at = entry["changed_at"]
            if i + 1 < len(entries):
                left_at = entries[i + 1]["changed_at"]
            else:
                left_at = now
            hours = (left_at - entered_at).total_seconds() / 3600.0
            if status in status_hours:
                status_hours[status].append(hours)

    result = [
        {
            "status": s.value,
            "avg_hours": (sum(status_hours[s.value]) / len(status_hours[s.value])) if status_hours[s.value] else 0.0,
            "sample_count": len(status_hours[s.value]),
        }
        for s in LeadStatus
    ]

    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Won / Lost breakdown by source
# ---------------------------------------------------------------------------

class WonLostRow(Schema):
    source: str
    won: int
    lost: int


@router.get(
    "/reports/won-lost-by-source",
    auth=django_auth,
    response={200: List[WonLostRow], 400: ErrorOut, 403: ErrorOut},
)
def won_lost_by_source(
    request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    Count of Won and Lost leads grouped by source, optionally filtered by a
    date range (``date_from`` / ``date_to`` in ISO-8601 format).
    Results are cached for 5 minutes per unique query.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    cache_key = f"analytics:won_lost:{request.firm.id}:{date_from}:{date_to}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    qs = Lead.objects.filter(firm=request.firm, status__in=[LeadStatus.WON, LeadStatus.LOST])
    if date_from:
        parsed = parse_datetime(date_from)
        if parsed is None:
            try:
                parsed = dt.datetime.fromisoformat(date_from)
            except ValueError:
                return 400, {"detail": f"Invalid date_from format: '{date_from}'. Use ISO-8601."}
        qs = qs.filter(updated_at__gte=parsed)
    if date_to:
        parsed = parse_datetime(date_to)
        if parsed is None:
            try:
                parsed = dt.datetime.fromisoformat(date_to)
            except ValueError:
                return 400, {"detail": f"Invalid date_to format: '{date_to}'. Use ISO-8601."}
        qs = qs.filter(updated_at__lte=parsed)

    data = qs.values("source", "status").annotate(n=Count("id"))

    result_map: Dict[str, Dict[str, int]] = {s.value: {"won": 0, "lost": 0} for s in LeadSource}
    for row in data:
        source = row["source"]
        if source not in result_map:
            result_map[source] = {"won": 0, "lost": 0}
        if row["status"] == LeadStatus.WON:
            result_map[source]["won"] = row["n"]
        elif row["status"] == LeadStatus.LOST:
            result_map[source]["lost"] = row["n"]

    result = [
        {"source": src, "won": counts["won"], "lost": counts["lost"]}
        for src, counts in result_map.items()
    ]

    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Team performance
# ---------------------------------------------------------------------------

class TeamPerformanceRow(Schema):
    user_id: str
    email: str
    full_name: str
    leads_owned: int
    tasks_completed: int
    activities_logged: int


@router.get(
    "/reports/team-performance",
    auth=django_auth,
    response={200: List[TeamPerformanceRow], 403: ErrorOut},
)
def team_performance(request):
    """
    Per-member stats: leads owned, tasks completed, activities logged.
    Results are cached for 5 minutes.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    cache_key = f"analytics:team_performance:{request.firm.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    from firms.models import Membership
    from users.models import User

    memberships = (
        Membership.objects.filter(firm=request.firm)
        .select_related("user")
    )

    result = []
    for m in memberships:
        user = m.user
        leads_owned = Lead.objects.filter(firm=request.firm, assigned_to=user).count()
        tasks_completed = Task.objects.filter(firm=request.firm, assigned_to=user, is_completed=True).count()
        activities_logged = Activity.objects.filter(lead__firm=request.firm, user=user).count()
        result.append({
            "user_id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "leads_owned": leads_owned,
            "tasks_completed": tasks_completed,
            "activities_logged": activities_logged,
        })

    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Trend charts
# ---------------------------------------------------------------------------

class WeeklyTrendRow(Schema):
    week_start: str
    created: int
    closed: int


class TrendsOut(Schema):
    weekly: List[WeeklyTrendRow]
    conversion_rate_30d: float


@router.get(
    "/reports/trends",
    auth=django_auth,
    response={200: TrendsOut, 403: ErrorOut},
)
def trends(request):
    """
    Leads created vs. closed (Won + Lost) per week for the last 12 weeks,
    plus a rolling 30-day conversion rate.  Results are cached for 5 minutes.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    cache_key = f"analytics:trends:{request.firm.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    now = tz.now()
    twelve_weeks_ago = now - dt.timedelta(weeks=12)
    thirty_days_ago = now - dt.timedelta(days=30)

    leads_qs = Lead.objects.filter(firm=request.firm)

    weekly_rows = []
    for week in range(12):
        week_start = twelve_weeks_ago + dt.timedelta(weeks=week)
        week_end = week_start + dt.timedelta(weeks=1)
        created = leads_qs.filter(created_at__gte=week_start, created_at__lt=week_end).count()
        closed = leads_qs.filter(
            status__in=[LeadStatus.WON, LeadStatus.LOST],
            updated_at__gte=week_start,
            updated_at__lt=week_end,
        ).count()
        weekly_rows.append({
            "week_start": week_start.date().isoformat(),
            "created": created,
            "closed": closed,
        })

    # Rolling 30-day conversion rate: won / (won + lost) in last 30 days
    closed_30d = leads_qs.filter(
        status__in=[LeadStatus.WON, LeadStatus.LOST],
        updated_at__gte=thirty_days_ago,
    )
    won_30d = closed_30d.filter(status=LeadStatus.WON).count()
    total_closed_30d = closed_30d.count()
    conversion_rate = (won_30d / total_closed_30d * 100.0) if total_closed_30d > 0 else 0.0

    result = {"weekly": weekly_rows, "conversion_rate_30d": round(conversion_rate, 2)}
    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Digest preference (opt-out)
# ---------------------------------------------------------------------------

class DigestPreferenceOut(Schema):
    weekly_digest_enabled: bool


class DigestPreferenceIn(Schema):
    enabled: bool


@router.get(
    "/digest-preference",
    auth=django_auth,
    response={200: DigestPreferenceOut, 403: ErrorOut},
)
def get_digest_preference(request):
    """Return the weekly digest preference for the current user in the active firm."""
    try:
        m = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    return 200, {"weekly_digest_enabled": m.weekly_digest_enabled}


@router.patch(
    "/digest-preference",
    auth=django_auth,
    response={200: DigestPreferenceOut, 403: ErrorOut},
)
def update_digest_preference(request, payload: DigestPreferenceIn):
    """Toggle the weekly email digest for the current user in the active firm."""
    try:
        m = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    m.weekly_digest_enabled = payload.enabled
    m.save(update_fields=["weekly_digest_enabled"])
    return 200, {"weekly_digest_enabled": m.weekly_digest_enabled}


# ===========================================================================
# v2.2 — DASHBOARD LAYOUT
# ===========================================================================

class DashboardLayoutOut(Schema):
    layout: List[Dict[str, Any]]
    updated_at: Optional[datetime]


class DashboardLayoutIn(Schema):
    layout: List[Dict[str, Any]]


@router.get(
    "/dashboard-layout",
    auth=django_auth,
    response={200: DashboardLayoutOut, 403: ErrorOut},
)
def get_dashboard_layout(request):
    """Return the current user's dashboard widget layout for the active firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    obj = DashboardLayout.objects.filter(user=request.user, firm=request.firm).first()
    if obj:
        return 200, {"layout": obj.layout, "updated_at": obj.updated_at}
    return 200, {"layout": [], "updated_at": None}


@router.put(
    "/dashboard-layout",
    auth=django_auth,
    response={200: DashboardLayoutOut, 403: ErrorOut},
)
def update_dashboard_layout(request, payload: DashboardLayoutIn):
    """Persist the current user's dashboard widget layout."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    obj, _ = DashboardLayout.objects.update_or_create(
        user=request.user,
        firm=request.firm,
        defaults={"layout": payload.layout},
    )
    return 200, {"layout": obj.layout, "updated_at": obj.updated_at}


# ===========================================================================
# v2.2 — LEAD SCORING RULES
# ===========================================================================

class LeadScoringRuleOut(Schema):
    id: str
    field: str
    operand: Any
    score_delta: int


class LeadScoringRuleIn(Schema):
    field: str
    operand: Any
    score_delta: int


@router.get(
    "/lead-scoring-rules",
    auth=django_auth,
    response={200: List[LeadScoringRuleOut], 403: ErrorOut},
)
def list_lead_scoring_rules(request):
    """List all lead scoring rules for the active firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    rules = LeadScoringRule.objects.filter(firm=request.firm)
    return 200, [
        {"id": str(r.id), "field": r.field, "operand": r.operand, "score_delta": r.score_delta}
        for r in rules
    ]


@router.post(
    "/lead-scoring-rules",
    auth=django_auth,
    response={201: LeadScoringRuleOut, 400: ErrorOut, 403: ErrorOut},
)
def create_lead_scoring_rule(request, payload: LeadScoringRuleIn):
    """Create a new lead scoring rule for the active firm."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    valid_fields = {"status", "source", "value_gte", "last_activity_days_lte"}
    if payload.field not in valid_fields:
        return 400, {"detail": f"Invalid field. Must be one of: {', '.join(sorted(valid_fields))}."}

    rule = LeadScoringRule.objects.create(
        firm=request.firm,
        field=payload.field,
        operand=payload.operand,
        score_delta=payload.score_delta,
    )
    return 201, {"id": str(rule.id), "field": rule.field, "operand": rule.operand, "score_delta": rule.score_delta}


@router.delete(
    "/lead-scoring-rules/{rule_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_lead_scoring_rule(request, rule_id: str):
    """Delete a lead scoring rule."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = LeadScoringRule.objects.get(id=rule_id, firm=request.firm)
    except LeadScoringRule.DoesNotExist:
        return 404, {"detail": "Rule not found."}

    rule.delete()
    return 204, None


# ===========================================================================
# v2.2 — SAVED VIEWS
# ===========================================================================

class SavedViewOut(Schema):
    id: str
    name: str
    entity: str
    filters: Dict[str, Any]
    sort_by: str
    sort_dir: str
    created_at: datetime


class SavedViewIn(Schema):
    name: str
    entity: str
    filters: Dict[str, Any] = {}
    sort_by: str = ""
    sort_dir: str = "asc"


def _saved_view_out(v: SavedView) -> dict:
    return {
        "id": str(v.id),
        "name": v.name,
        "entity": v.entity,
        "filters": v.filters,
        "sort_by": v.sort_by,
        "sort_dir": v.sort_dir,
        "created_at": v.created_at,
    }


@router.get(
    "/saved-views",
    auth=django_auth,
    response={200: List[SavedViewOut], 403: ErrorOut},
)
def list_saved_views(request, entity: str = ""):
    """List the current user's saved views, optionally filtered by entity."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = SavedView.objects.filter(user=request.user, firm=request.firm)
    if entity:
        qs = qs.filter(entity=entity)
    return 200, [_saved_view_out(v) for v in qs]


@router.post(
    "/saved-views",
    auth=django_auth,
    response={201: SavedViewOut, 400: ErrorOut, 403: ErrorOut},
)
def create_saved_view(request, payload: SavedViewIn):
    """Save a named filter+sort preset for the current user."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    valid_entities = {SavedView.ENTITY_LEADS, SavedView.ENTITY_CUSTOMERS}
    if payload.entity not in valid_entities:
        return 400, {"detail": f"Invalid entity. Must be one of: {', '.join(sorted(valid_entities))}."}

    try:
        view = SavedView.objects.create(
            user=request.user,
            firm=request.firm,
            name=payload.name,
            entity=payload.entity,
            filters=payload.filters,
            sort_by=payload.sort_by,
            sort_dir=payload.sort_dir,
        )
    except Exception:
        return 400, {"detail": "A saved view with this name already exists for this entity."}

    return 201, _saved_view_out(view)


@router.delete(
    "/saved-views/{view_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_saved_view(request, view_id: str):
    """Delete a saved view owned by the current user."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        view = SavedView.objects.get(id=view_id, user=request.user, firm=request.firm)
    except SavedView.DoesNotExist:
        return 404, {"detail": "Saved view not found."}

    view.delete()
    return 204, None

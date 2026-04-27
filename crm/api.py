"""
Django Ninja API router – CRM (Customers, Leads, Activities, Tasks)

Every endpoint requires:
  1. Session authentication.
  2. A valid Firm supplied via the ``X-Firm-ID`` header (resolved by TenantMiddleware).
  3. The authenticated user to be a member of that Firm.
"""
import datetime as dt
import logging
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
    Project,
    Proposal,
    SavedView,
    Task,
    TaskAttachment,
    TaskChecklistItem,
    TaskComment,
    TaskCommentReaction,
    TaskDependency,
    TaskDependencyType,
    TaskFavourite,
    TaskPriority,
    TaskPublicShare,
    TaskStatus,
    TaskTimelineEntry,
    TaskVoiceAttachment,
    TimelineEventType,
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

_MENTION_PREVIEW_LENGTH = 120
logger = logging.getLogger(__name__)


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


def _build_lead_automation_context(lead: Lead, firm) -> dict:
    """Build the evaluation context dict for automation rules fired from a Lead event."""
    from firms.models import Membership

    customer_name = ""
    customer_email = ""
    if lead.customer_id:
        try:
            # customer may already be loaded via select_related
            c = lead.customer
            customer_name = f"{c.first_name} {c.last_name}".strip()
            customer_email = c.email or ""
        except Exception:  # noqa: BLE001
            pass

    assignee_email = ""
    assignee_name = ""
    if lead.assigned_to_id:
        try:
            u = lead.assigned_to
            assignee_email = u.email or ""
            assignee_name = f"{u.first_name} {u.last_name}".strip()
        except Exception:  # noqa: BLE001
            pass

    owner_email = (
        Membership.objects
        .filter(firm=firm, role="owner")
        .select_related("user")
        .values_list("user__email", flat=True)
        .first()
    ) or ""

    return {
        "lead_id": str(lead.id),
        "lead_title": lead.title,
        "lead_status": lead.status,
        "lead_source": lead.source,
        "lead_value": str(lead.value) if lead.value is not None else "",
        "firm_id": str(firm.pk),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "assignee_email": assignee_email,
        "assignee_name": assignee_name,
        "owner_email": owner_email,
    }


def _build_task_automation_context(task, firm) -> dict:
    """Build the evaluation context dict for automation rules fired from a Task event."""
    from firms.models import Membership

    lead_id = str(task.lead_id) if task.lead_id else ""
    lead_title = ""
    customer_name = ""
    customer_email = ""

    if task.lead_id:
        try:
            lead = task.lead
            lead_title = lead.title or ""
            if lead.customer_id:
                c = lead.customer
                customer_name = f"{c.first_name} {c.last_name}".strip()
                customer_email = c.email or ""
        except Exception:  # noqa: BLE001
            pass
    elif task.customer_id:
        try:
            c = task.customer
            customer_name = f"{c.first_name} {c.last_name}".strip()
            customer_email = c.email or ""
        except Exception:  # noqa: BLE001
            pass

    assignee_id = ""
    assignee_email = ""
    assignee_name = ""
    if task.assigned_to_id:
        try:
            u = task.assigned_to
            assignee_id = str(u.pk)
            assignee_email = u.email or ""
            assignee_name = f"{u.first_name} {u.last_name}".strip()
        except Exception:  # noqa: BLE001
            pass

    owner_email = (
        Membership.objects
        .filter(firm=firm, role="owner")
        .select_related("user")
        .values_list("user__email", flat=True)
        .first()
    ) or ""

    return {
        "task_id": str(task.id),
        "task_title": task.title,
        "task_status": task.status,
        "task_priority": task.priority,
        "lead_id": lead_id,
        "lead_title": lead_title,
        "firm_id": str(firm.pk),
        "assignee_id": assignee_id,
        "assignee_email": assignee_email,
        "assignee_name": assignee_name,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "owner_email": owner_email,
        "due_date": task.due_date.isoformat() if task.due_date else "",
    }



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

    # Fire workflow automation trigger: lead_created
    from crm.tasks import evaluate_automation_rules
    _automation_ctx = _build_lead_automation_context(lead, request.firm)
    from django.db import transaction
    transaction.on_commit(
        lambda: evaluate_automation_rules.delay("lead_created", str(request.firm.pk), _automation_ctx)
    )

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
            # Fire workflow automation trigger: lead_status_change
            from crm.tasks import evaluate_automation_rules
            _automation_ctx = {
                **_build_lead_automation_context(lead, request.firm),
                "from_status": old_status,
                "to_status": new_status,
            }
            transaction.on_commit(
                lambda ctx=_automation_ctx: evaluate_automation_rules.delay(
                    "lead_status_change", str(request.firm.pk), ctx
                )
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

        # -- @mention notifications (COMMENT activities only) --
        if payload.type == ActivityType.COMMENT:
            mention_ids = payload.metadata.get('mentions', [])
            if mention_ids:
                from django.contrib.auth import get_user_model
                _User = get_user_model()
                mentioned_users = (
                    _User.objects.filter(id__in=[str(uid) for uid in mention_ids])
                    .filter(membership__firm=request.firm)
                    .exclude(id=request.user.id)
                    .distinct()
                )
                for mentioned_user in mentioned_users:
                    Notification.objects.create(
                        firm=request.firm,
                        user=mentioned_user,
                        event='activity.mention',
                        payload={
                            'activity_id': str(activity.id),
                            'lead_id': str(lead.id),
                            'lead_title': lead.title,
                            'by_user': request.user.full_name or request.user.email,
                            'content_preview': activity.content_text[:_MENTION_PREVIEW_LENGTH],
                        },
                    )

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
    # Entity links
    lead_id: Optional[str]
    lead_title: Optional[str]
    proposal_id: Optional[str]
    proposal_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    parent_task_id: Optional[str]
    parent_task_title: Optional[str]
    project_ids: List[str]
    # Authorship
    assigned_to_id: Optional[str]
    assigned_to_name: Optional[str]
    completed_by_id: Optional[str]
    completed_by_name: Optional[str]
    watcher_ids: List[str]
    # Content
    title: str
    description: str
    description_html: str
    description_added_at: Optional[datetime]
    # Classification
    priority: str
    status: str
    tags: List[str]
    # Dates
    due_date: Optional[datetime]
    due_date_end: Optional[datetime]
    # Flags
    is_completed: bool
    completed_at: Optional[datetime]
    is_pinned: bool
    is_archived: bool
    is_favourite: bool
    created_at: datetime
    created_by_id: Optional[str]
    created_by_name: Optional[str]
    # Phase 3: subtask counters
    subtask_count: int
    subtasks_completed: int
    # Phase 3: checklist counters
    checklist_count: int
    checklist_checked: int


class TaskIn(Schema):
    lead_id: Optional[str] = None
    proposal_id: Optional[str] = None
    customer_id: Optional[str] = None
    title: str
    description: str = ""
    description_html: str = ""
    assigned_to_id: Optional[str] = None
    watcher_ids: List[str] = []
    due_date: Optional[datetime] = None
    due_date_end: Optional[datetime] = None
    priority: str = TaskPriority.MEDIUM
    status: str = TaskStatus.TODO
    tags: List[str] = []
    project_ids: List[str] = []


class TaskUpdateIn(Schema):
    title: Optional[str] = None
    description: Optional[str] = None
    description_html: Optional[str] = None
    assigned_to_id: Optional[str] = None
    watcher_ids: Optional[List[str]] = None
    due_date: Optional[datetime] = None
    due_date_end: Optional[datetime] = None
    clear_due_date: bool = False
    clear_due_date_end: bool = False
    priority: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None
    project_ids: Optional[List[str]] = None


class FollowUpTaskIn(Schema):
    title: str
    description: str = ""
    assigned_to_id: Optional[str] = None
    watcher_ids: List[str] = []
    due_date: Optional[datetime] = None
    lead_id: Optional[str] = None


class CompleteTaskIn(Schema):
    follow_up: Optional[FollowUpTaskIn] = None


class TaskCommentOut(Schema):
    id: str
    task_id: str
    author_id: Optional[str]
    author_name: Optional[str]
    content_html: str
    created_at: datetime
    updated_at: datetime


class TaskCommentIn(Schema):
    content_html: str


class TaskAttachmentOut(Schema):
    id: str
    task_id: str
    uploaded_by_id: Optional[str]
    original_filename: str
    content_type: str
    size_bytes: int
    url: str
    created_at: datetime


def _task_out(t: Task, requesting_user=None) -> dict:
    # Resolve lead title (use cached select_related if available)
    lead_id = None
    lead_title = None
    if t.lead_id:
        lead_id = str(t.lead_id)
        try:
            lead_title = t.lead.title
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve lead title for task %s: %s", t.id, exc)

    # Resolve proposal title
    proposal_id = None
    proposal_title = None
    if t.proposal_id:
        proposal_id = str(t.proposal_id)
        try:
            proposal_title = t.proposal.title
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve proposal title for task %s: %s", t.id, exc)

    # Resolve customer name
    customer_id = None
    customer_name = None
    if t.customer_id:
        customer_id = str(t.customer_id)
        try:
            c = t.customer
            customer_name = f"{c.first_name} {c.last_name}".strip() or c.company_name or c.email
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve customer name for task %s: %s", t.id, exc)

    # Resolve assigned_to display name
    assigned_to_name: Optional[str] = None
    if t.assigned_to_id:
        try:
            u = t.assigned_to
            assigned_to_name = f"{u.first_name} {u.last_name}".strip() or u.email
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve assigned_to name for task %s: %s", t.id, exc)

    # Resolve completed_by display name
    completed_by_name: Optional[str] = None
    if t.completed_by_id:
        try:
            completed_by_user = t.completed_by
            completed_by_name = f"{completed_by_user.first_name} {completed_by_user.last_name}".strip() or completed_by_user.email
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve completed_by name for task %s: %s", t.id, exc)

    # Resolve watcher IDs
    try:
        watcher_ids = [str(uid) for uid in t.watchers.values_list("id", flat=True)]
    except Exception as exc:
        logger.debug("Could not resolve watchers for task %s: %s", t.id, exc)
        watcher_ids = []

    # Resolve project IDs
    try:
        project_ids = [str(pid) for pid in t.projects.values_list("id", flat=True)]
    except Exception as exc:
        logger.debug("Could not resolve projects for task %s: %s", t.id, exc)
        project_ids = []

    # Resolve created_by display name
    created_by_name: Optional[str] = None
    if t.created_by_id:
        try:
            cb = t.created_by
            created_by_name = f"{cb.first_name} {cb.last_name}".strip() or cb.email
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve created_by name for task %s: %s", t.id, exc)

    # Resolve parent task title
    parent_task_title: Optional[str] = None
    if t.parent_task_id:
        try:
            parent_task_title = t.parent_task.title
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve parent_task title for task %s: %s", t.id, exc)

    # Resolve is_favourite for the requesting user
    is_favourite = False
    if requesting_user and requesting_user.is_authenticated:
        try:
            is_favourite = TaskFavourite.objects.filter(task=t, user=requesting_user).exists()
        except Exception:
            pass

    # Phase 3: subtask counters
    try:
        subtask_qs = Task.objects.filter(parent_task=t)
        subtask_count = subtask_qs.count()
        subtasks_completed = subtask_qs.filter(is_completed=True).count()
    except Exception:
        subtask_count = 0
        subtasks_completed = 0

    # Phase 3: checklist counters
    try:
        checklist_qs = TaskChecklistItem.objects.filter(task=t)
        checklist_count = checklist_qs.count()
        checklist_checked = checklist_qs.filter(is_checked=True).count()
    except Exception:
        checklist_count = 0
        checklist_checked = 0

    return {
        "id": str(t.id),
        "firm_id": str(t.firm_id),
        "lead_id": lead_id,
        "lead_title": lead_title,
        "proposal_id": proposal_id,
        "proposal_title": proposal_title,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
        "parent_task_title": parent_task_title,
        "project_ids": project_ids,
        "assigned_to_id": str(t.assigned_to_id) if t.assigned_to_id else None,
        "assigned_to_name": assigned_to_name,
        "completed_by_id": str(t.completed_by_id) if t.completed_by_id else None,
        "completed_by_name": completed_by_name,
        "watcher_ids": watcher_ids,
        "title": t.title,
        "description": t.description,
        "description_html": t.description_html,
        "description_added_at": t.description_added_at,
        "priority": t.priority,
        "status": t.status,
        "tags": t.tags if isinstance(t.tags, list) else [],
        "due_date": t.due_date,
        "due_date_end": t.due_date_end,
        "is_completed": t.is_completed,
        "completed_at": t.completed_at,
        "is_pinned": t.is_pinned,
        "is_archived": t.is_archived,
        "is_favourite": is_favourite,
        "created_at": t.created_at,
        "created_by_id": str(t.created_by_id) if t.created_by_id else None,
        "created_by_name": created_by_name,
        "subtask_count": subtask_count,
        "subtasks_completed": subtasks_completed,
        "checklist_count": checklist_count,
        "checklist_checked": checklist_checked,
    }


def _resolve_user_in_firm(user_id: str, firm) -> tuple:
    """Return (user, error_response) where error_response is None on success."""
    from users.models import User
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None, (400, {"detail": "User not found."})
    if not Membership.objects.filter(user=user, firm=firm).exists():
        return None, (400, {"detail": "User is not a member of this Firm."})
    return user, None


def _set_task_watchers(task: Task, watcher_ids: List[str], firm) -> Optional[tuple]:
    """Validate and set watchers on *task*. Returns an error tuple or None."""
    from users.models import User
    if not watcher_ids:
        task.watchers.clear()
        return None
    watcher_qs = User.objects.filter(id__in=watcher_ids)
    member_ids = set(
        Membership.objects.filter(firm=firm, user__in=watcher_qs).values_list("user_id", flat=True)
    )
    invalid = [uid for uid in watcher_ids if uid not in {str(m) for m in member_ids}]
    if invalid:
        return 400, {"detail": f"Some watcher IDs are not members of this Firm: {invalid}"}
    task.watchers.set(watcher_qs.filter(id__in=watcher_ids))
    return None


def _notify_task_watchers(task: Task, event: str) -> None:
    """Broadcast *event* to task watchers only (not the whole firm)."""
    from crm.models import Notification
    payload = _task_out(task)
    try:
        watchers = list(task.watchers.all())
        if watchers:
            notifications = [
                Notification(firm=task.firm, user=w, event=event, payload=payload)
                for w in watchers
            ]
            Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    except Exception:
        logger.exception("Failed to persist watcher notifications for task %s event %s", task.id, event)


@router.get("/tasks", auth=django_auth, response={200: List[TaskOut], 403: ErrorOut})
def list_tasks(
    request,
    completed: Optional[bool] = None,
    assigned_to_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    is_archived: Optional[bool] = None,
    is_pinned: Optional[bool] = None,
    is_favourite: Optional[bool] = None,
    lead_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    project_id: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """
    List tasks for the current firm.

    - Any member sees tasks by default.
    - Pass ``assigned_to_id=<uuid>`` to filter by assignee (any role).
    - Pass ``assigned_to_id=all`` to see all tasks (admin/owner only).
    - Omitting ``assigned_to_id`` returns the current user's tasks (for workers)
      or all tasks (for admins/owners).
    """
    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)

    qs = Task.objects.filter(firm=request.firm).select_related(
        "lead", "assigned_to", "completed_by", "created_by", "proposal", "customer", "parent_task",
    )

    if assigned_to_id == "all":
        if not is_admin:
            qs = qs.filter(assigned_to=request.user)
    elif assigned_to_id:
        qs = qs.filter(assigned_to_id=assigned_to_id)
    else:
        if not is_admin:
            qs = qs.filter(assigned_to=request.user)

    if completed is not None:
        qs = qs.filter(is_completed=completed)
    if status is not None:
        qs = qs.filter(status=status)
    if priority is not None:
        qs = qs.filter(priority=priority)
    if is_archived is not None:
        qs = qs.filter(is_archived=is_archived)
    else:
        # By default, exclude archived tasks
        qs = qs.filter(is_archived=False)
    if is_pinned is not None:
        qs = qs.filter(is_pinned=is_pinned)
    if lead_id is not None:
        qs = qs.filter(lead_id=lead_id)
    if proposal_id is not None:
        qs = qs.filter(proposal_id=proposal_id)
    if customer_id is not None:
        qs = qs.filter(customer_id=customer_id)
    if project_id is not None:
        qs = qs.filter(projects__id=project_id)
    if tag is not None:
        qs = qs.filter(tags__contains=[tag])
    if is_favourite is not None:
        if is_favourite:
            fav_task_ids = TaskFavourite.objects.filter(user=request.user).values_list("task_id", flat=True)
            qs = qs.filter(id__in=fav_task_ids)

    offset = (page - 1) * page_size
    return 200, [_task_out(t, request.user) for t in qs[offset:offset + page_size]]


@router.post("/tasks", auth=django_auth, response={201: TaskOut, 400: ErrorOut, 403: ErrorOut})
def create_task(request, payload: TaskIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    # Resolve optional entity links
    lead = None
    if payload.lead_id:
        try:
            lead = Lead.objects.get(id=payload.lead_id, firm=request.firm)
        except Lead.DoesNotExist:
            return 400, {"detail": "Lead not found in this Firm."}

    proposal = None
    if payload.proposal_id:
        try:
            proposal = Proposal.objects.get(id=payload.proposal_id, firm=request.firm)
        except Proposal.DoesNotExist:
            return 400, {"detail": "Proposal not found in this Firm."}

    customer = None
    if payload.customer_id:
        try:
            customer = Customer.objects.get(id=payload.customer_id, firm=request.firm)
        except Customer.DoesNotExist:
            return 400, {"detail": "Customer not found in this Firm."}

    assigned_to = None
    if payload.assigned_to_id:
        assigned_to, err = _resolve_user_in_firm(payload.assigned_to_id, request.firm)
        if err:
            return err

    # Validate priority and status
    valid_priorities = [p.value for p in TaskPriority]
    if payload.priority not in valid_priorities:
        return 400, {"detail": f"Invalid priority. Choose from: {valid_priorities}"}
    valid_statuses = [s.value for s in TaskStatus]
    if payload.status not in valid_statuses:
        return 400, {"detail": f"Invalid status. Choose from: {valid_statuses}"}

    with transaction.atomic():
        description_added_at = None
        if payload.description_html:
            from django.utils import timezone as _tz
            description_added_at = _tz.now()

        task = Task.objects.create(
            firm=request.firm,
            lead=lead,
            proposal=proposal,
            customer=customer,
            assigned_to=assigned_to,
            created_by=request.user,
            title=payload.title,
            description=payload.description,
            description_html=payload.description_html,
            description_added_at=description_added_at,
            due_date=payload.due_date,
            due_date_end=payload.due_date_end,
            priority=payload.priority,
            status=payload.status,
            tags=payload.tags,
        )
        watcher_err = _set_task_watchers(task, payload.watcher_ids, request.firm)
        if watcher_err:
            return watcher_err

        # Set projects
        if payload.project_ids:
            projects = Project.objects.filter(id__in=payload.project_ids, firm=request.firm)
            task.projects.set(projects)

        # Log activity on lead if linked
        if lead:
            Activity.objects.create(
                lead=lead,
                user=request.user,
                type=ActivityType.TASK_ASSIGNED,
                metadata={
                    "task_id": str(task.id),
                    "due_date": payload.due_date.isoformat() if payload.due_date else None,
                    "priority": payload.priority,
                },
            )

    _notify_task_watchers(task, "task.created")
    broadcast_event(firm=request.firm, event='task.created', payload=_task_out(task, request.user))
    # Phase 2: log system timeline event
    _log_timeline_event(task, TimelineEventType.TASK_CREATED, author=request.user)
    # Phase 4: fire task_created automation trigger
    from crm.tasks import evaluate_automation_rules
    _task_auto_ctx = _build_task_automation_context(task, request.firm)
    transaction.on_commit(
        lambda ctx=_task_auto_ctx: evaluate_automation_rules.delay(
            "task_created", str(request.firm.pk), ctx
        )
    )
    return 201, _task_out(task, request.user)


@router.patch("/tasks/{task_id}", auth=django_auth, response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut})
def update_task(request, task_id: str, payload: TaskUpdateIn):
    """Partially update a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.select_related("assigned_to").get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    # Snapshot old values for timeline event logging
    old_status = task.status
    old_priority = task.priority
    old_assignee_name = _author_name_for(task.assigned_to) if task.assigned_to_id else None
    old_due_date = task.due_date.isoformat() if task.due_date else None
    old_archived = task.is_archived

    update_fields = []

    if payload.title is not None:
        task.title = payload.title
        update_fields.append("title")

    if payload.description is not None:
        task.description = payload.description
        update_fields.append("description")

    if payload.description_html is not None:
        task.description_html = payload.description_html
        if payload.description_html:
            task.description_added_at = tz.now()
            update_fields.append("description_added_at")
        update_fields.append("description_html")

    if payload.clear_due_date:
        task.due_date = None
        update_fields.append("due_date")
    elif payload.due_date is not None:
        task.due_date = payload.due_date
        update_fields.append("due_date")

    if payload.clear_due_date_end:
        task.due_date_end = None
        update_fields.append("due_date_end")
    elif payload.due_date_end is not None:
        task.due_date_end = payload.due_date_end
        update_fields.append("due_date_end")

    if payload.priority is not None:
        valid_priorities = [p.value for p in TaskPriority]
        if payload.priority not in valid_priorities:
            return 400, {"detail": f"Invalid priority. Choose from: {valid_priorities}"}
        task.priority = payload.priority
        update_fields.append("priority")

    if payload.status is not None:
        valid_statuses = [s.value for s in TaskStatus]
        if payload.status not in valid_statuses:
            return 400, {"detail": f"Invalid status. Choose from: {valid_statuses}"}
        task.status = payload.status
        update_fields.append("status")

    if payload.tags is not None:
        task.tags = payload.tags
        update_fields.append("tags")

    if payload.is_pinned is not None:
        task.is_pinned = payload.is_pinned
        update_fields.append("is_pinned")

    if payload.is_archived is not None:
        task.is_archived = payload.is_archived
        update_fields.append("is_archived")

    if payload.assigned_to_id is not None:
        if payload.assigned_to_id == "":
            task.assigned_to = None
            update_fields.append("assigned_to")
        else:
            assigned_to, err = _resolve_user_in_firm(payload.assigned_to_id, request.firm)
            if err:
                return err
            task.assigned_to = assigned_to
            update_fields.append("assigned_to")

    if update_fields:
        task.save(update_fields=update_fields)

    if payload.watcher_ids is not None:
        watcher_err = _set_task_watchers(task, payload.watcher_ids, request.firm)
        if watcher_err:
            return watcher_err

    if payload.project_ids is not None:
        projects = Project.objects.filter(id__in=payload.project_ids, firm=request.firm)
        task.projects.set(projects)

    _notify_task_watchers(task, "task.updated")
    broadcast_event(firm=request.firm, event='task.updated', payload=_task_out(task, request.user))

    # Phase 2: log system timeline events for significant changes
    if payload.status is not None and task.status != old_status:
        _log_timeline_event(
            task, TimelineEventType.STATUS_CHANGE, author=request.user,
            metadata={"from": old_status, "to": task.status},
        )
    if payload.priority is not None and task.priority != old_priority:
        _log_timeline_event(
            task, TimelineEventType.PRIORITY_CHANGE, author=request.user,
            metadata={"from": old_priority, "to": task.priority},
        )
    if payload.assigned_to_id is not None:
        new_assignee_name = _author_name_for(task.assigned_to) if task.assigned_to_id else None
        if new_assignee_name != old_assignee_name:
            _log_timeline_event(
                task, TimelineEventType.ASSIGNEE_CHANGE, author=request.user,
                metadata={"from_name": old_assignee_name, "to_name": new_assignee_name},
            )
    due_date_payload_changed = payload.due_date is not None or payload.clear_due_date
    new_due_date_value = task.due_date.isoformat() if task.due_date else None
    if due_date_payload_changed and new_due_date_value != old_due_date:
        _log_timeline_event(
            task, TimelineEventType.DUE_DATE_CHANGE, author=request.user,
            metadata={"old": old_due_date, "new": new_due_date_value},
        )
    if payload.is_archived is not None and task.is_archived != old_archived and task.is_archived:
        _log_timeline_event(task, TimelineEventType.TASK_ARCHIVED, author=request.user)

    return 200, _task_out(task, request.user)


@router.post("/tasks/{task_id}/complete", auth=django_auth, response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut})
def complete_task(request, task_id: str, payload: Optional[CompleteTaskIn] = None):
    """Mark a Task as completed, log a TASK_COMPLETED Activity, and optionally create a follow-up task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if task.is_completed:
        return 200, _task_out(task, request.user)

    follow_up_data = payload.follow_up if payload else None

    # Validate follow-up assignee before the transaction
    follow_up_assigned_to = None
    if follow_up_data and follow_up_data.assigned_to_id:
        follow_up_assigned_to, err = _resolve_user_in_firm(follow_up_data.assigned_to_id, request.firm)
        if err:
            return err

    with transaction.atomic():
        task.is_completed = True
        task.completed_at = tz.now()
        task.completed_by = request.user
        task.status = TaskStatus.DONE
        task.save(update_fields=["is_completed", "completed_at", "completed_by", "status"])
        # Log Activity only when linked to a lead
        if task.lead_id:
            Activity.objects.create(
                lead=task.lead,
                user=request.user,
                type=ActivityType.TASK_COMPLETED,
                metadata={"task_id": str(task.id), "title": task.title},
            )

        follow_up_task = None
        if follow_up_data:
            follow_up_lead = None
            if follow_up_data.lead_id:
                try:
                    follow_up_lead = Lead.objects.get(id=follow_up_data.lead_id, firm=request.firm)
                except Lead.DoesNotExist:
                    pass
            else:
                follow_up_lead = task.lead

            follow_up_task = Task.objects.create(
                firm=request.firm,
                lead=follow_up_lead,
                assigned_to=follow_up_assigned_to,
                title=follow_up_data.title,
                description=follow_up_data.description,
                due_date=follow_up_data.due_date,
            )
            watcher_err = _set_task_watchers(follow_up_task, follow_up_data.watcher_ids, request.firm)
            if watcher_err:
                return watcher_err
            if follow_up_lead:
                Activity.objects.create(
                    lead=follow_up_lead,
                    user=request.user,
                    type=ActivityType.TASK_ASSIGNED,
                    metadata={
                        "task_id": str(follow_up_task.id),
                        "follow_up_of": str(task.id),
                        "due_date": follow_up_data.due_date.isoformat() if follow_up_data.due_date else None,
                        "priority": "normal",
                    },
                )

    _notify_task_watchers(task, "task.completed")
    broadcast_event(firm=request.firm, event='task.completed', payload=_task_out(task, request.user))
    # Phase 2: log completion event
    _log_timeline_event(task, TimelineEventType.TASK_COMPLETED, author=request.user)
    # Phase 4: fire task_completed automation trigger
    from crm.tasks import evaluate_automation_rules
    _task_auto_ctx = _build_task_automation_context(task, request.firm)
    transaction.on_commit(
        lambda ctx=_task_auto_ctx: evaluate_automation_rules.delay(
            "task_completed", str(request.firm.pk), ctx
        )
    )
    if follow_up_task:
        _notify_task_watchers(follow_up_task, "task.created")
        broadcast_event(firm=request.firm, event='task.created', payload=_task_out(follow_up_task, request.user))
        _log_timeline_event(follow_up_task, TimelineEventType.TASK_CREATED, author=request.user)

    return 200, _task_out(task, request.user)


# ---------------------------------------------------------------------------
# Task detail (single task)
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}", auth=django_auth, response={200: TaskOut, 403: ErrorOut, 404: ErrorOut})
def get_task(request, task_id: str):
    """Retrieve a single task by ID."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.select_related(
            "lead", "assigned_to", "completed_by", "created_by", "proposal", "customer", "parent_task",
        ).get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    return 200, _task_out(task, request.user)


# ---------------------------------------------------------------------------
# Task comments
# ---------------------------------------------------------------------------

def _comment_out(c: TaskComment) -> dict:
    author_name: Optional[str] = None
    if c.author_id:
        try:
            a = c.author
            author_name = f"{a.first_name} {a.last_name}".strip() or a.email
        except (AttributeError, Exception):
            pass
    return {
        "id": str(c.id),
        "task_id": str(c.task_id),
        "author_id": str(c.author_id) if c.author_id else None,
        "author_name": author_name,
        "content_html": c.content_html,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get(
    "/tasks/{task_id}/comments",
    auth=django_auth,
    response={200: List[TaskCommentOut], 403: ErrorOut, 404: ErrorOut},
)
def list_task_comments(request, task_id: str, page: int = 1, page_size: int = 100):
    """List all comments for a task, oldest first."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    offset = (page - 1) * page_size
    comments = (
        TaskComment.objects.filter(task=task)
        .select_related("author")
        .order_by("created_at")[offset: offset + page_size]
    )
    return 200, [_comment_out(c) for c in comments]


@router.post(
    "/tasks/{task_id}/comments",
    auth=django_auth,
    response={201: TaskCommentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_task_comment(request, task_id: str, payload: TaskCommentIn):
    """Add a comment to a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if not payload.content_html or not payload.content_html.strip():
        return 400, {"detail": "Comment content is required."}

    comment = TaskComment.objects.create(
        task=task,
        author=request.user,
        content_html=payload.content_html,
    )
    _notify_task_watchers(task, "task.comment_added")
    return 201, _comment_out(comment)


@router.patch(
    "/tasks/{task_id}/comments/{comment_id}",
    auth=django_auth,
    response={200: TaskCommentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_task_comment(request, task_id: str, comment_id: str, payload: TaskCommentIn):
    """Edit a comment. Only the original author (or admin/owner) may edit."""
    try:
        membership = require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        comment = TaskComment.objects.select_related("author").get(id=comment_id, task_id=task_id)
    except TaskComment.DoesNotExist:
        return 404, {"detail": "Comment not found."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    if str(comment.author_id) != str(request.user.id) and not is_admin:
        return 403, {"detail": "You can only edit your own comments."}

    if not payload.content_html or not payload.content_html.strip():
        return 400, {"detail": "Comment content is required."}

    comment.content_html = payload.content_html
    comment.save(update_fields=["content_html", "updated_at"])
    return 200, _comment_out(comment)


@router.delete(
    "/tasks/{task_id}/comments/{comment_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task_comment(request, task_id: str, comment_id: str):
    """Delete a comment. Only the original author (or admin/owner) may delete."""
    try:
        membership = require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        comment = TaskComment.objects.get(id=comment_id, task_id=task_id)
    except TaskComment.DoesNotExist:
        return 404, {"detail": "Comment not found."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    if str(comment.author_id) != str(request.user.id) and not is_admin:
        return 403, {"detail": "You can only delete your own comments."}

    comment.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Task attachments
# ---------------------------------------------------------------------------

_MAX_TASK_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20 MB


def _task_attachment_out(a: TaskAttachment) -> dict:
    return {
        "id": str(a.id),
        "task_id": str(a.task_id),
        "uploaded_by_id": str(a.uploaded_by_id) if a.uploaded_by_id else None,
        "original_filename": a.original_filename,
        "content_type": a.content_type or "",
        "size_bytes": a.size_bytes,
        "url": a.file.url,
        "created_at": a.created_at,
    }


@router.get(
    "/tasks/{task_id}/attachments",
    auth=django_auth,
    response={200: List[TaskAttachmentOut], 403: ErrorOut, 404: ErrorOut},
)
def list_task_attachments(request, task_id: str, page: int = 1, page_size: int = 50):
    """List all file attachments for a task, newest first."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    offset = (page - 1) * page_size
    attachments = TaskAttachment.objects.filter(task=task).order_by("-created_at")[
        offset: offset + page_size
    ]
    return 200, [_task_attachment_out(a) for a in attachments]


@router.post(
    "/tasks/{task_id}/attachments",
    auth=django_auth,
    response={201: TaskAttachmentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_task_attachment(request, task_id: str, file: UploadedFile = File(...)):
    """Upload a file and attach it to a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if file.size > _MAX_TASK_ATTACHMENT_BYTES:
        return 400, {
            "detail": f"File exceeds the maximum allowed size of {_MAX_TASK_ATTACHMENT_BYTES // (1024 * 1024)} MB."
        }

    attachment = TaskAttachment(
        task=task,
        uploaded_by=request.user,
        original_filename=file.name,
        content_type=file.content_type or "",
        size_bytes=file.size,
    )
    attachment.file.save(file.name, file, save=True)
    return 201, _task_attachment_out(attachment)


@router.delete(
    "/tasks/{task_id}/attachments/{attachment_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task_attachment(request, task_id: str, attachment_id: str):
    """Delete a task attachment. Only uploader or admin/owner may delete."""
    try:
        membership = require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        attachment = TaskAttachment.objects.get(id=attachment_id, task_id=task_id)
    except TaskAttachment.DoesNotExist:
        return 404, {"detail": "Attachment not found."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    if str(attachment.uploaded_by_id) != str(request.user.id) and not is_admin:
        return 403, {"detail": "You can only delete your own attachments."}

    attachment.file.delete(save=False)
    attachment.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Task Favourite (⭐ toggle)
# ---------------------------------------------------------------------------

class TaskFavouriteOut(Schema):
    task_id: str
    is_favourite: bool


@router.post(
    "/tasks/{task_id}/favourite",
    auth=django_auth,
    response={200: TaskFavouriteOut, 403: ErrorOut, 404: ErrorOut},
)
def toggle_task_favourite(request, task_id: str):
    """Toggle the current user's favourite status on a task."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    fav, created = TaskFavourite.objects.get_or_create(task=task, user=request.user)
    if not created:
        fav.delete()
        return 200, {"task_id": str(task.id), "is_favourite": False}
    return 200, {"task_id": str(task.id), "is_favourite": True}


# ===========================================================================
# PHASE 3 — SUBTASKS
# ===========================================================================

def _get_task_depth(task: Task, max_depth: int = 3) -> int:
    """Return the depth of *task* in the hierarchy (root = 1). Stops at max_depth+1."""
    depth = 1
    current = task
    for _ in range(max_depth):
        if current.parent_task_id is None:
            break
        try:
            current = Task.objects.only("id", "parent_task_id").get(pk=current.parent_task_id)
        except Task.DoesNotExist:
            break
        depth += 1
    return depth


class SubtaskIn(Schema):
    title: str
    description: str = ""
    description_html: str = ""
    assigned_to_id: Optional[str] = None
    watcher_ids: List[str] = []
    due_date: Optional[datetime] = None
    priority: str = TaskPriority.MEDIUM
    status: str = TaskStatus.TODO
    tags: List[str] = []


@router.get(
    "/tasks/{task_id}/subtasks",
    auth=django_auth,
    response={200: List[TaskOut], 403: ErrorOut, 404: ErrorOut},
)
def list_subtasks(request, task_id: str):
    """Return all direct subtasks of the specified task."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    subtasks = Task.objects.filter(parent_task=task).select_related(
        "lead", "assigned_to", "completed_by", "created_by", "proposal", "customer", "parent_task",
    )
    return 200, [_task_out(s, request.user) for s in subtasks]


@router.post(
    "/tasks/{task_id}/subtasks",
    auth=django_auth,
    response={201: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_subtask(request, task_id: str, payload: SubtaskIn):
    """Create a direct subtask under *task_id*. Maximum depth is 3."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        parent = Task.objects.select_related("parent_task", "parent_task__parent_task").get(
            id=task_id, firm=request.firm
        )
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    # Enforce maximum depth of 3
    parent_depth = _get_task_depth(parent)
    if parent_depth >= 3:
        return 400, {"detail": "Maximum subtask depth of 3 reached."}

    # Validate priority and status
    valid_priorities = [p.value for p in TaskPriority]
    if payload.priority not in valid_priorities:
        return 400, {"detail": f"Invalid priority. Choose from: {valid_priorities}"}
    valid_statuses = [s.value for s in TaskStatus]
    if payload.status not in valid_statuses:
        return 400, {"detail": f"Invalid status. Choose from: {valid_statuses}"}

    assigned_to = None
    if payload.assigned_to_id:
        assigned_to, err = _resolve_user_in_firm(payload.assigned_to_id, request.firm)
        if err:
            return err

    description_added_at = None
    if payload.description_html:
        description_added_at = tz.now()

    with transaction.atomic():
        subtask = Task.objects.create(
            firm=request.firm,
            parent_task=parent,
            # Inherit entity links from parent
            lead=parent.lead,
            proposal=parent.proposal,
            customer=parent.customer,
            assigned_to=assigned_to,
            created_by=request.user,
            title=payload.title,
            description=payload.description,
            description_html=payload.description_html,
            description_added_at=description_added_at,
            due_date=payload.due_date,
            priority=payload.priority,
            status=payload.status,
            tags=payload.tags,
        )
        watcher_err = _set_task_watchers(subtask, payload.watcher_ids, request.firm)
        if watcher_err:
            return watcher_err

    broadcast_event(firm=request.firm, event='task.created', payload=_task_out(subtask, request.user))
    # Phase 2: log subtask creation on parent's timeline
    _log_timeline_event(
        parent, TimelineEventType.SUB_TASK_ADDED, author=request.user,
        metadata={"subtask_id": str(subtask.id), "title": subtask.title},
    )
    _log_timeline_event(subtask, TimelineEventType.TASK_CREATED, author=request.user)
    return 201, _task_out(subtask, request.user)


# ===========================================================================
# PHASE 3 — CHECKLIST
# ===========================================================================

class ChecklistItemOut(Schema):
    id: str
    task_id: str
    text: str
    is_checked: bool
    position: int
    created_by_id: Optional[str]
    created_at: datetime


class ChecklistItemIn(Schema):
    text: str
    position: int = 0


class ChecklistItemUpdateIn(Schema):
    text: Optional[str] = None
    is_checked: Optional[bool] = None
    position: Optional[int] = None


def _checklist_item_out(item: TaskChecklistItem) -> dict:
    return {
        "id": str(item.id),
        "task_id": str(item.task_id),
        "text": item.text,
        "is_checked": item.is_checked,
        "position": item.position,
        "created_by_id": str(item.created_by_id) if item.created_by_id else None,
        "created_at": item.created_at,
    }


@router.get(
    "/tasks/{task_id}/checklist",
    auth=django_auth,
    response={200: List[ChecklistItemOut], 403: ErrorOut, 404: ErrorOut},
)
def list_checklist_items(request, task_id: str):
    """Return all checklist items for a task, ordered by position."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    items = TaskChecklistItem.objects.filter(task=task).order_by("position", "created_at")
    return 200, [_checklist_item_out(i) for i in items]


@router.post(
    "/tasks/{task_id}/checklist",
    auth=django_auth,
    response={201: ChecklistItemOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_checklist_item(request, task_id: str, payload: ChecklistItemIn):
    """Add a new checklist item to a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if not payload.text.strip():
        return 400, {"detail": "Checklist item text cannot be empty."}

    item = TaskChecklistItem.objects.create(
        task=task,
        text=payload.text.strip(),
        position=payload.position,
        created_by=request.user,
    )
    return 201, _checklist_item_out(item)


@router.patch(
    "/tasks/{task_id}/checklist/{item_id}",
    auth=django_auth,
    response={200: ChecklistItemOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_checklist_item(request, task_id: str, item_id: str, payload: ChecklistItemUpdateIn):
    """Update a checklist item (text, is_checked, position)."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        item = TaskChecklistItem.objects.get(id=item_id, task_id=task_id)
    except TaskChecklistItem.DoesNotExist:
        return 404, {"detail": "Checklist item not found."}

    update_fields = []
    if payload.text is not None:
        if not payload.text.strip():
            return 400, {"detail": "Checklist item text cannot be empty."}
        item.text = payload.text.strip()
        update_fields.append("text")
    if payload.is_checked is not None:
        item.is_checked = payload.is_checked
        update_fields.append("is_checked")
    if payload.position is not None:
        item.position = payload.position
        update_fields.append("position")

    if update_fields:
        item.save(update_fields=update_fields)
    return 200, _checklist_item_out(item)


@router.delete(
    "/tasks/{task_id}/checklist/{item_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_checklist_item(request, task_id: str, item_id: str):
    """Delete a checklist item."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        item = TaskChecklistItem.objects.get(id=item_id, task_id=task_id)
    except TaskChecklistItem.DoesNotExist:
        return 404, {"detail": "Checklist item not found."}

    item.delete()
    return 204, None


# ===========================================================================
# PHASE 3 — DEPENDENCIES
# ===========================================================================

class TaskDependencyOut(Schema):
    id: str
    from_task_id: str
    from_task_title: str
    to_task_id: str
    to_task_title: str
    type: str
    created_by_id: Optional[str]
    created_at: datetime


class TaskDependencyIn(Schema):
    to_task_id: str
    type: str = TaskDependencyType.BLOCKS


def _dependency_out(dep: TaskDependency) -> dict:
    return {
        "id": str(dep.id),
        "from_task_id": str(dep.from_task_id),
        "from_task_title": dep.from_task.title if dep.from_task_id else "",
        "to_task_id": str(dep.to_task_id),
        "to_task_title": dep.to_task.title if dep.to_task_id else "",
        "type": dep.type,
        "created_by_id": str(dep.created_by_id) if dep.created_by_id else None,
        "created_at": dep.created_at,
    }


def _has_blocking_cycle(from_task: Task, to_task: Task, max_depth: int = 50) -> bool:
    """
    Return True if adding a 'blocks' edge from_task → to_task would create a cycle.
    A cycle exists if to_task can already reach from_task through existing 'blocks' edges.
    """
    visited = set()
    queue = [to_task.pk]
    for _ in range(max_depth):
        if not queue:
            break
        current_id = queue.pop(0)
        if current_id == from_task.pk:
            return True
        if current_id in visited:
            continue
        visited.add(current_id)
        # Tasks that current_id blocks
        blocked_ids = TaskDependency.objects.filter(
            from_task_id=current_id, type=TaskDependencyType.BLOCKS
        ).values_list("to_task_id", flat=True)
        queue.extend(blocked_ids)
    return False


@router.get(
    "/tasks/{task_id}/dependencies",
    auth=django_auth,
    response={200: List[TaskDependencyOut], 403: ErrorOut, 404: ErrorOut},
)
def list_task_dependencies(request, task_id: str):
    """Return all dependencies where this task is either source or target."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    deps = TaskDependency.objects.filter(
        Q(from_task=task) | Q(to_task=task)
    ).select_related("from_task", "to_task")
    return 200, [_dependency_out(d) for d in deps]


@router.post(
    "/tasks/{task_id}/dependencies",
    auth=django_auth,
    response={201: TaskDependencyOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_task_dependency(request, task_id: str, payload: TaskDependencyIn):
    """Add a dependency from this task to another task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        from_task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    # Validate dependency type
    valid_types = [t.value for t in TaskDependencyType]
    if payload.type not in valid_types:
        return 400, {"detail": f"Invalid dependency type. Choose from: {valid_types}"}

    # Validate target task exists in the same firm
    try:
        to_task = Task.objects.get(id=payload.to_task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 400, {"detail": "Target task not found in this Firm."}

    if from_task.pk == to_task.pk:
        return 400, {"detail": "A task cannot depend on itself."}

    # Check for cycles on 'blocks' type
    if payload.type == TaskDependencyType.BLOCKS and _has_blocking_cycle(from_task, to_task):
        return 400, {"detail": "Adding this dependency would create a circular blocking cycle."}

    dep, created = TaskDependency.objects.get_or_create(
        from_task=from_task,
        to_task=to_task,
        type=payload.type,
        defaults={"created_by": request.user},
    )
    if not created:
        return 400, {"detail": "This dependency already exists."}

    dep_with_related = TaskDependency.objects.select_related("from_task", "to_task").get(pk=dep.pk)
    return 201, _dependency_out(dep_with_related)


@router.delete(
    "/tasks/{task_id}/dependencies/{dependency_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task_dependency(request, task_id: str, dependency_id: str):
    """Remove a dependency."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        dep = TaskDependency.objects.get(
            Q(id=dependency_id) & (Q(from_task_id=task_id) | Q(to_task_id=task_id))
        )
    except TaskDependency.DoesNotExist:
        return 404, {"detail": "Dependency not found."}

    dep.delete()
    return 204, None


# ===========================================================================
# PHASE 5 — TASK OPERATIONS (delete, archive, pin, copy, move, public share, batch)
# ===========================================================================

@router.delete(
    "/tasks/{task_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task(request, task_id: str):
    """Permanently delete a task. Requires ADMIN role."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    task.delete()
    return 204, None


@router.post(
    "/tasks/{task_id}/archive",
    auth=django_auth,
    response={200: TaskOut, 403: ErrorOut, 404: ErrorOut},
)
def archive_task(request, task_id: str):
    """Archive a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    task.is_archived = True
    task.save(update_fields=["is_archived"])
    _log_timeline_event(task, TimelineEventType.TASK_ARCHIVED, author=request.user)
    return 200, _task_out(task, request.user)


@router.post(
    "/tasks/{task_id}/unarchive",
    auth=django_auth,
    response={200: TaskOut, 403: ErrorOut, 404: ErrorOut},
)
def unarchive_task(request, task_id: str):
    """Unarchive a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    task.is_archived = False
    task.save(update_fields=["is_archived"])
    return 200, _task_out(task, request.user)


@router.post(
    "/tasks/{task_id}/pin",
    auth=django_auth,
    response={200: TaskOut, 403: ErrorOut, 404: ErrorOut},
)
def pin_task(request, task_id: str):
    """Pin a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    task.is_pinned = True
    task.save(update_fields=["is_pinned"])
    return 200, _task_out(task, request.user)


@router.post(
    "/tasks/{task_id}/unpin",
    auth=django_auth,
    response={200: TaskOut, 403: ErrorOut, 404: ErrorOut},
)
def unpin_task(request, task_id: str):
    """Unpin a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    task.is_pinned = False
    task.save(update_fields=["is_pinned"])
    return 200, _task_out(task, request.user)


class TaskCopyIn(Schema):
    include_subtasks: bool = False
    include_checklist: bool = True
    include_attachments: bool = False
    title: Optional[str] = None


def _copy_task(original: Task, firm, created_by, title: str, parent_task=None) -> Task:
    """Create a copy of *original* under *firm*. Does not copy subtasks/checklist."""
    new_task = Task.objects.create(
        firm=firm,
        lead=original.lead,
        proposal=original.proposal,
        customer=original.customer,
        parent_task=parent_task,
        created_by=created_by,
        assigned_to=original.assigned_to,
        title=title,
        description=original.description,
        description_html=original.description_html,
        description_added_at=original.description_added_at,
        priority=original.priority,
        status=TaskStatus.TODO,
        tags=original.tags if isinstance(original.tags, list) else [],
        due_date=original.due_date,
        due_date_end=original.due_date_end,
        is_completed=False,
        is_pinned=False,
        is_archived=False,
    )
    # Copy watchers
    if original.watchers.exists():
        new_task.watchers.set(original.watchers.all())
    # Copy projects
    if original.projects.exists():
        new_task.projects.set(original.projects.all())
    return new_task


def _copy_subtasks_recursive(original: Task, new_parent: Task, firm, created_by, depth: int = 1, max_depth: int = 3):
    """
    Recursively copy direct subtasks of *original* under *new_parent*.

    Mirrors the 3-level depth limit enforced when creating subtasks
    interactively.  *depth* starts at 1 (children of the root copy) and the
    recursion stops when ``depth >= max_depth`` so that the copied hierarchy
    never exceeds the allowed nesting level.
    """
    if depth >= max_depth:
        return
    for sub in Task.objects.filter(parent_task=original):
        new_sub = _copy_task(sub, firm, created_by, title=sub.title, parent_task=new_parent)
        _log_timeline_event(new_sub, TimelineEventType.TASK_CREATED, author=created_by)
        _copy_subtasks_recursive(sub, new_sub, firm, created_by, depth=depth + 1, max_depth=max_depth)


@router.post(
    "/tasks/{task_id}/copy",
    auth=django_auth,
    response={201: TaskOut, 403: ErrorOut, 404: ErrorOut},
)
def copy_task(request, task_id: str, payload: TaskCopyIn):
    """Create a copy of a task, optionally including checklist, subtasks and attachments."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        original = Task.objects.select_related(
            "lead", "proposal", "customer", "assigned_to",
        ).prefetch_related("watchers", "projects").get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    copy_title = payload.title if payload.title else f"{original.title} (copy)"

    with transaction.atomic():
        new_task = _copy_task(original, request.firm, request.user, title=copy_title)

        if payload.include_checklist:
            for item in TaskChecklistItem.objects.filter(task=original).order_by("position", "created_at"):
                TaskChecklistItem.objects.create(
                    task=new_task,
                    text=item.text,
                    position=item.position,
                    is_checked=False,
                    created_by=request.user,
                )

        if payload.include_attachments:
            for att in TaskAttachment.objects.filter(task=original):
                # Metadata record points to the same underlying file; uploaded_by
                # is set to the user performing the copy to reflect actual ownership.
                TaskAttachment.objects.create(
                    task=new_task,
                    uploaded_by=request.user,
                    file=att.file,
                    original_filename=att.original_filename,
                    content_type=att.content_type,
                    size_bytes=att.size_bytes,
                )

        if payload.include_subtasks:
            _copy_subtasks_recursive(original, new_task, request.firm, request.user)

        _log_timeline_event(new_task, TimelineEventType.TASK_CREATED, author=request.user)

    broadcast_event(firm=request.firm, event='task.created', payload=_task_out(new_task, request.user))
    return 201, _task_out(new_task, request.user)


class TaskMoveIn(Schema):
    lead_id: Optional[str] = None
    proposal_id: Optional[str] = None
    customer_id: Optional[str] = None


@router.post(
    "/tasks/{task_id}/move",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def move_task(request, task_id: str, payload: TaskMoveIn):
    """Move a task to a different entity (lead/proposal/customer) or make it standalone."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    # Clear existing entity links
    task.lead = None
    task.proposal = None
    task.customer = None

    if payload.lead_id:
        try:
            task.lead = Lead.objects.get(id=payload.lead_id, firm=request.firm)
        except Lead.DoesNotExist:
            return 400, {"detail": "Lead not found."}
    elif payload.proposal_id:
        try:
            task.proposal = Proposal.objects.get(id=payload.proposal_id, firm=request.firm)
        except Proposal.DoesNotExist:
            return 400, {"detail": "Proposal not found."}
    elif payload.customer_id:
        try:
            task.customer = Customer.objects.get(id=payload.customer_id, firm=request.firm)
        except Customer.DoesNotExist:
            return 400, {"detail": "Customer not found."}

    task.save(update_fields=["lead", "proposal", "customer"])
    return 200, _task_out(task, request.user)


class TaskPublicLinkOut(Schema):
    token: str
    url: str


@router.get(
    "/tasks/{task_id}/public-link",
    auth=django_auth,
    response={200: TaskPublicLinkOut, 403: ErrorOut, 404: ErrorOut},
)
def get_task_public_link(request, task_id: str):
    """Get or create a public share link for a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    share, _ = TaskPublicShare.objects.get_or_create(
        task=task,
        defaults={"created_by": request.user},
    )
    token = str(share.token)
    return 200, {"token": token, "url": f"/app/tasks/public/{token}"}


class PublicTaskOut(Schema):
    id: str
    title: str
    description_html: str
    priority: str
    status: str
    tags: List[str]
    due_date: Optional[datetime]
    due_date_end: Optional[datetime]
    is_completed: bool
    created_at: datetime
    assigned_to_name: Optional[str]
    firm_name: str
    checklist: List[Dict[str, Any]]


@router.get(
    "/public/tasks/{token}",
    auth=None,
    response={200: PublicTaskOut, 404: ErrorOut},
)
def get_public_task(request, token: str):
    """Return a publicly accessible (read-only) task view. No authentication required."""
    try:
        share = TaskPublicShare.objects.select_related("task__firm", "task__assigned_to").get(token=token)
    except TaskPublicShare.DoesNotExist:
        return 404, {"detail": "Not found."}

    if share.expires_at and share.expires_at < tz.now():
        logger.debug("Expired public share token accessed: %s", token)
        return 404, {"detail": "Not found."}

    task = share.task

    assigned_to_name = None
    if task.assigned_to_id:
        try:
            u = task.assigned_to
            assigned_to_name = f"{u.first_name} {u.last_name}".strip() or u.email
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve assigned_to for public task share %s: %s", token, exc)

    firm_name = ""
    try:
        firm_name = task.firm.name
    except (AttributeError, Exception) as exc:
        logger.debug("Could not resolve firm name for public task share %s: %s", token, exc)

    checklist = [
        {"text": item.text, "is_checked": item.is_checked}
        for item in TaskChecklistItem.objects.filter(task=task).order_by("position", "created_at")
    ]

    return 200, {
        "id": str(task.id),
        "title": task.title,
        "description_html": task.description_html,
        "priority": task.priority,
        "status": task.status,
        "tags": task.tags if isinstance(task.tags, list) else [],
        "due_date": task.due_date,
        "due_date_end": task.due_date_end,
        "is_completed": task.is_completed,
        "created_at": task.created_at,
        "assigned_to_name": assigned_to_name,
        "firm_name": firm_name,
        "checklist": checklist,
    }


class TaskBatchIn(Schema):
    task_ids: List[str]
    action: str
    assigned_to_id: Optional[str] = None


@router.post(
    "/tasks/batch",
    auth=django_auth,
    response={200: Dict[str, Any], 403: ErrorOut, 400: ErrorOut},
)
def batch_task_action(request, payload: TaskBatchIn):
    """Apply a bulk action to multiple tasks at once."""
    valid_actions = {"complete", "archive", "unarchive", "delete", "assign"}
    if payload.action not in valid_actions:
        return 400, {"detail": f"Invalid action. Choose from: {', '.join(sorted(valid_actions))}."}

    # delete requires ADMIN, others require WORKER
    required_role = MembershipRole.ADMIN if payload.action == "delete" else MembershipRole.WORKER
    try:
        require_membership(request, min_role=required_role)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    assigned_to_user = None
    if payload.action == "assign":
        if not payload.assigned_to_id:
            return 400, {"detail": "assigned_to_id is required for the 'assign' action."}
        assigned_to_user, err = _resolve_user_in_firm(payload.assigned_to_id, request.firm)
        if err:
            return err

    processed = 0
    failed = 0

    for task_id in payload.task_ids:
        try:
            task = Task.objects.get(id=task_id, firm=request.firm)
        except Task.DoesNotExist:
            failed += 1
            continue

        try:
            if payload.action == "complete":
                if not task.is_completed:
                    task.is_completed = True
                    task.completed_at = tz.now()
                    task.completed_by = request.user
                    task.status = TaskStatus.DONE
                    task.save(update_fields=["is_completed", "completed_at", "completed_by", "status"])
                    _log_timeline_event(task, TimelineEventType.TASK_COMPLETED, author=request.user)
            elif payload.action == "archive":
                task.is_archived = True
                task.save(update_fields=["is_archived"])
                _log_timeline_event(task, TimelineEventType.TASK_ARCHIVED, author=request.user)
            elif payload.action == "unarchive":
                task.is_archived = False
                task.save(update_fields=["is_archived"])
            elif payload.action == "delete":
                task.delete()
            elif payload.action == "assign":
                task.assigned_to = assigned_to_user
                task.save(update_fields=["assigned_to"])
            processed += 1
        except (Exception, OSError):
            logger.exception("Batch action %s failed for task %s", payload.action, task_id)
            failed += 1

    return 200, {"processed": processed, "failed": failed}




# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReactionSummaryOut(Schema):
    """Aggregated count of a single emoji reaction on a timeline entry."""
    emoji: str
    count: int
    user_ids: List[str]
    reacted_by_me: bool


class TimelineAttachmentOut(Schema):
    """Inline attachment metadata embedded in a timeline entry."""
    id: str
    original_filename: str
    content_type: str
    size_bytes: int
    url: str
    uploaded_by_id: Optional[str]
    created_at: datetime


class TaskTimelineEntryOut(Schema):
    """
    A single item in the unified task timeline.

    ``source`` distinguishes the backing model:
      - ``timeline_entry``   — new-style TaskTimelineEntry record
      - ``legacy_comment``   — TaskComment migrated into the feed
      - ``legacy_attachment`` — TaskAttachment shown as a file_upload event
    """
    id: str
    source: str
    event_type: str
    author_id: Optional[str]
    author_name: Optional[str]
    content_html: str
    metadata: Dict[str, Any]
    parent_entry_id: Optional[str]
    reactions: List[ReactionSummaryOut]
    reply_count: int
    attachment: Optional[TimelineAttachmentOut]
    created_at: datetime


class TaskTimelinePostIn(Schema):
    """
    Payload for POST /tasks/{id}/timeline.

    ``content_html`` is required when creating a comment entry.
    Action toggles allow atomic side-effects alongside the comment:
      - ``change_assignee_to`` — reassign the task to this user ID
      - ``log_time_minutes``   — add a time-log entry (Phase 6 placeholder)
      - ``set_due_date``       — update the task's due_date
    """
    content_html: str
    parent_entry_id: Optional[str] = None
    # Action toggles
    change_assignee_to: Optional[str] = None
    log_time_minutes: Optional[int] = None
    log_time_description: str = ""
    set_due_date: Optional[datetime] = None


class TimelineReactionIn(Schema):
    emoji: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _author_name_for(user) -> Optional[str]:
    """Return display name for a user object or None."""
    if user is None:
        return None
    try:
        return f"{user.first_name} {user.last_name}".strip() or user.email
    except Exception:
        return None


def _reactions_for_entry(entry: TaskTimelineEntry, requesting_user) -> List[dict]:
    """Build aggregated reaction list for a TaskTimelineEntry."""
    reactions: dict[str, dict] = {}
    for r in entry.reactions.select_related("user"):
        if r.emoji not in reactions:
            reactions[r.emoji] = {"emoji": r.emoji, "count": 0, "user_ids": [], "reacted_by_me": False}
        reactions[r.emoji]["count"] += 1
        reactions[r.emoji]["user_ids"].append(str(r.user_id))
        if requesting_user and requesting_user.is_authenticated and str(r.user_id) == str(requesting_user.id):
            reactions[r.emoji]["reacted_by_me"] = True
    return list(reactions.values())


def _timeline_entry_out(entry: TaskTimelineEntry, requesting_user=None) -> dict:
    """Serialise a TaskTimelineEntry to the common timeline dict."""
    author_name = None
    if entry.author_id:
        try:
            author_name = _author_name_for(entry.author)
        except Exception:
            pass
    return {
        "id": str(entry.id),
        "source": "timeline_entry",
        "event_type": entry.event_type,
        "author_id": str(entry.author_id) if entry.author_id else None,
        "author_name": author_name,
        "content_html": entry.content_html,
        "metadata": entry.metadata if isinstance(entry.metadata, dict) else {},
        "parent_entry_id": str(entry.parent_entry_id) if entry.parent_entry_id else None,
        "reactions": _reactions_for_entry(entry, requesting_user),
        "reply_count": entry.replies.count(),
        "attachment": None,
        "created_at": entry.created_at,
    }


def _legacy_comment_out(comment: TaskComment) -> dict:
    """Wrap a legacy TaskComment as a timeline entry dict."""
    author_name = None
    if comment.author_id:
        try:
            author_name = _author_name_for(comment.author)
        except Exception:
            pass
    return {
        "id": f"legacy_comment_{comment.id}",
        "source": "legacy_comment",
        "event_type": TimelineEventType.COMMENT,
        "author_id": str(comment.author_id) if comment.author_id else None,
        "author_name": author_name,
        "content_html": comment.content_html,
        "metadata": {},
        "parent_entry_id": None,
        "reactions": [],
        "reply_count": 0,
        "attachment": None,
        "created_at": comment.created_at,
    }


def _legacy_attachment_out(att: TaskAttachment) -> dict:
    """Wrap a legacy TaskAttachment as a file_upload timeline entry dict."""
    uploader_name = None
    if att.uploaded_by_id:
        try:
            uploader_name = _author_name_for(att.uploaded_by)
        except Exception:
            pass
    attachment_data = {
        "id": str(att.id),
        "original_filename": att.original_filename,
        "content_type": att.content_type or "",
        "size_bytes": att.size_bytes,
        "url": att.file.url,
        "uploaded_by_id": str(att.uploaded_by_id) if att.uploaded_by_id else None,
        "created_at": att.created_at,
    }
    return {
        "id": f"legacy_attachment_{att.id}",
        "source": "legacy_attachment",
        "event_type": TimelineEventType.FILE_UPLOAD,
        "author_id": str(att.uploaded_by_id) if att.uploaded_by_id else None,
        "author_name": uploader_name,
        "content_html": "",
        "metadata": {"filename": att.original_filename, "size_bytes": att.size_bytes},
        "parent_entry_id": None,
        "reactions": [],
        "reply_count": 0,
        "attachment": attachment_data,
        "created_at": att.created_at,
    }


def _log_timeline_event(task: Task, event_type: str, author=None, metadata: dict = None) -> None:
    """
    Create a system TaskTimelineEntry for the given event.

    Silently swallows any errors so that it never breaks the main request.
    """
    try:
        TaskTimelineEntry.objects.create(
            task=task,
            author=author,
            event_type=event_type,
            content_html="",
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to log timeline event %s for task %s", event_type, task.id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/tasks/{task_id}/timeline",
    auth=django_auth,
    response={200: List[TaskTimelineEntryOut], 403: ErrorOut, 404: ErrorOut},
)
def get_task_timeline(
    request,
    task_id: str,
    event_type: Optional[str] = None,
    order: str = "asc",
    page: int = 1,
    page_size: int = 100,
):
    """
    Return the unified chronological timeline for a task.

    Merges new-style ``TaskTimelineEntry`` records with legacy ``TaskComment``
    and ``TaskAttachment`` records from older data.

    Query parameters:
      - ``event_type`` — filter to ``comment`` or ``system`` (all non-comment) entries
      - ``order``      — ``asc`` (oldest first, default) or ``desc`` (newest first)
      - ``page`` / ``page_size`` — pagination
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    # --- Collect entries from all sources ---
    entries: list[dict] = []

    # 1. New-style TaskTimelineEntry records
    tle_qs = (
        TaskTimelineEntry.objects.filter(task=task, parent_entry__isnull=True)
        .select_related("author")
        .prefetch_related("reactions__user", "replies")
    )
    if event_type == "comment":
        tle_qs = tle_qs.filter(event_type=TimelineEventType.COMMENT)
    elif event_type == "system":
        tle_qs = tle_qs.exclude(event_type=TimelineEventType.COMMENT)

    for entry in tle_qs:
        entries.append(_timeline_entry_out(entry, request.user))

    # 2. Legacy TaskComment records (only if not filtered to system events)
    if event_type != "system":
        for comment in TaskComment.objects.filter(task=task).select_related("author"):
            entries.append(_legacy_comment_out(comment))

    # 3. Legacy TaskAttachment records as file_upload events (only if not filtered to comment)
    if event_type != "comment":
        for att in TaskAttachment.objects.filter(task=task).select_related("uploaded_by"):
            entries.append(_legacy_attachment_out(att))

    # --- Sort merged results ---
    reverse = order == "desc"
    entries.sort(key=lambda e: e["created_at"], reverse=reverse)

    # --- Paginate ---
    offset = (page - 1) * page_size
    return 200, entries[offset: offset + page_size]


@router.post(
    "/tasks/{task_id}/timeline",
    auth=django_auth,
    response={201: TaskTimelineEntryOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_task_timeline_entry(request, task_id: str, payload: TaskTimelinePostIn):
    """
    Add a comment to the task timeline.

    Optionally performs side-effect actions when the action toggles are set:
      - ``change_assignee_to`` — reassigns the task Řešitel
      - ``set_due_date``       — updates the task due date
      - ``log_time_minutes``   — records a time entry (placeholder; full
                                 implementation in Phase 6)
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.select_related("assigned_to").get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if not payload.content_html or not payload.content_html.strip():
        return 400, {"detail": "Comment content is required."}

    # Validate parent entry if given
    parent_entry = None
    if payload.parent_entry_id:
        try:
            parent_entry = TaskTimelineEntry.objects.get(id=payload.parent_entry_id, task=task)
        except TaskTimelineEntry.DoesNotExist:
            return 400, {"detail": "Parent entry not found on this task."}

    with transaction.atomic():
        # --- Create the comment timeline entry ---
        entry = TaskTimelineEntry.objects.create(
            task=task,
            author=request.user,
            event_type=TimelineEventType.COMMENT,
            content_html=payload.content_html,
            parent_entry=parent_entry,
        )

        # --- Action toggle: reassign task ---
        if payload.change_assignee_to:
            old_name = _author_name_for(task.assigned_to) if task.assigned_to_id else None
            new_user, err = _resolve_user_in_firm(payload.change_assignee_to, request.firm)
            if err:
                return err
            new_name = _author_name_for(new_user)
            task.assigned_to = new_user
            task.save(update_fields=["assigned_to"])
            _log_timeline_event(
                task, TimelineEventType.ASSIGNEE_CHANGE, author=request.user,
                metadata={"from_name": old_name, "to_name": new_name},
            )

        # --- Action toggle: set due date ---
        if payload.set_due_date is not None:
            old_due = task.due_date.isoformat() if task.due_date else None
            task.due_date = payload.set_due_date
            task.save(update_fields=["due_date"])
            _log_timeline_event(
                task, TimelineEventType.DUE_DATE_CHANGE, author=request.user,
                metadata={"old": old_due, "new": payload.set_due_date.isoformat()},
            )

        # --- Action toggle: log time (Phase 6 placeholder) ---
        if payload.log_time_minutes:
            _log_timeline_event(
                task, TimelineEventType.TIME_LOGGED, author=request.user,
                metadata={
                    "minutes": payload.log_time_minutes,
                    "description": payload.log_time_description,
                },
            )

    _notify_task_watchers(task, "task.comment_added")
    # Re-fetch to get prefetched reactions
    entry.refresh_from_db()
    return 201, _timeline_entry_out(entry, request.user)


@router.post(
    "/tasks/{task_id}/timeline/{entry_id}/reactions",
    auth=django_auth,
    response={200: ReactionSummaryOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def toggle_timeline_reaction(request, task_id: str, entry_id: str, payload: TimelineReactionIn):
    """
    Toggle an emoji reaction on a comment timeline entry.

    If the current user has already reacted with this emoji, the reaction is
    removed.  Otherwise it is added.  Returns the updated aggregate for this
    emoji.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        entry = TaskTimelineEntry.objects.get(id=entry_id, task=task)
    except TaskTimelineEntry.DoesNotExist:
        return 404, {"detail": "Timeline entry not found."}

    if entry.event_type != TimelineEventType.COMMENT:
        return 400, {"detail": "Reactions are only supported on comment entries."}

    emoji = payload.emoji.strip()
    if not emoji:
        return 400, {"detail": "Emoji must not be empty."}

    reaction, created = TaskCommentReaction.objects.get_or_create(
        entry=entry, user=request.user, emoji=emoji,
    )
    if not created:
        reaction.delete()

    # Return updated aggregate for this emoji
    count = TaskCommentReaction.objects.filter(entry=entry, emoji=emoji).count()
    user_ids = list(
        TaskCommentReaction.objects.filter(entry=entry, emoji=emoji).values_list("user_id", flat=True)
    )
    # Re-query to get the definitive post-operation state for the requesting user
    reacted_by_me = TaskCommentReaction.objects.filter(entry=entry, user=request.user, emoji=emoji).exists()
    return 200, {
        "emoji": emoji,
        "count": count,
        "user_ids": [str(uid) for uid in user_ids],
        "reacted_by_me": reacted_by_me,
    }


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
    lead_id: Optional[str]
    lead_title: Optional[str]
    assigned_to_id: Optional[str]
    title: str
    due_date: Optional[datetime]
    created_at: datetime


def _overdue_task_out(t: Task) -> dict:
    lead_title = None
    if t.lead_id:
        try:
            lead_title = t.lead.title
        except (AttributeError, Exception):
            pass
    return {
        "id": str(t.id),
        "firm_id": str(t.firm_id),
        "lead_id": str(t.lead_id) if t.lead_id else None,
        "lead_title": lead_title,
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

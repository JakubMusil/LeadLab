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
    ActivityReaction,
    ActivityType,
    ContactType,
    Customer,
    DashboardLayout,
    Document,
    Lead,
    LeadScoringRule,
    LeadSource,
    LeadStatus,
    Management,
    Notification,
    Project,
    Proposal,
    Realization,
    SavedView,
    Task,
    TaskChecklistItem,
    TaskCustomField,
    TaskCustomFieldType,
    TaskCustomFieldValue,
    TaskDependency,
    TaskDependencyType,
    TaskFavourite,
    TaskPriority,
    TaskPublicShare,
    TaskStatus,
    TaskTemplate,
    TaskTimeLog,
    TaskTimer,
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
    type: str
    first_name: str
    last_name: str
    email: str
    phone: str
    company_name: str
    company_id: Optional[str]
    ico: str
    dic: str
    address_street: str
    address_city: str
    address_zip: str
    address_country: str
    website: str
    tags: List[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CustomerIn(Schema):
    type: str = ContactType.PERSON
    first_name: str
    last_name: str = ""
    email: str = ""
    phone: str = ""
    company_name: str = ""
    company_id: Optional[str] = None
    ico: str = ""
    dic: str = ""
    address_street: str = ""
    address_city: str = ""
    address_zip: str = ""
    address_country: str = ""
    website: str = ""
    tags: List[str] = []
    metadata: Dict[str, Any] = {}


def _customer_out(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "firm_id": str(c.firm_id),
        "type": c.type,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "email": c.email,
        "phone": c.phone,
        "company_name": c.company_name,
        "company_id": str(c.company_id) if c.company_id else None,
        "ico": c.ico,
        "dic": c.dic,
        "address_street": c.address_street,
        "address_city": c.address_city,
        "address_zip": c.address_zip,
        "address_country": c.address_country,
        "website": c.website,
        "tags": c.tags,
        "metadata": c.metadata,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get("/directory", auth=django_auth, response={200: List[CustomerOut], 403: ErrorOut})
def list_customers(request, search: str = "", page: int = 1, page_size: int = 20, type: str = ""):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Customer.objects.filter(firm=request.firm)
    if type in (ContactType.PERSON, ContactType.COMPANY):
        qs = qs.filter(type=type)
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(company_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(ico__icontains=search)
        )
    offset = (page - 1) * page_size
    return 200, [_customer_out(c) for c in qs[offset:offset + page_size]]


@router.post("/directory", auth=django_auth, response={201: CustomerOut, 403: ErrorOut})
def create_customer(request, payload: CustomerIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    data = payload.dict()
    company_id = data.pop("company_id", None)
    company = None
    if company_id:
        try:
            company = Customer.objects.get(id=company_id, firm=request.firm, type=ContactType.COMPANY)
        except Customer.DoesNotExist:
            pass
    customer = Customer.objects.create(firm=request.firm, company=company, **data)

    # Fire contact_created automation
    _auto_ctx = {
        "customer_id": str(customer.id),
        "customer_name": f"{customer.first_name} {customer.last_name}".strip() or getattr(customer, "company_name", ""),
        "customer_email": customer.email or "",
        "customer_type": customer.type,
        "firm_id": str(request.firm.id),
    }
    from crm.tasks import evaluate_automation_rules
    from django.db import transaction as db_tx
    db_tx.on_commit(
        lambda ctx=_auto_ctx: evaluate_automation_rules.delay("contact_created", str(request.firm.id), ctx),
        robust=True,
    )

    return 201, _customer_out(customer)


@router.get("/directory/{customer_id}", auth=django_auth, response={200: CustomerOut, 403: ErrorOut, 404: ErrorOut})
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


@router.put("/directory/{customer_id}", auth=django_auth, response={200: CustomerOut, 403: ErrorOut, 404: ErrorOut})
def update_customer(request, customer_id: str, payload: CustomerIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        customer = Customer.objects.get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}

    data = payload.dict()
    company_id = data.pop("company_id", None)
    company = None
    if company_id:
        try:
            company = Customer.objects.get(id=company_id, firm=request.firm, type=ContactType.COMPANY)
        except Customer.DoesNotExist:
            pass
    customer.company = company
    for field, value in data.items():
        setattr(customer, field, value)
    customer.save()
    return 200, _customer_out(customer)


@router.delete("/directory/{customer_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
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


@router.get("/directory/{customer_id}/employees", auth=django_auth, response={200: List[CustomerOut], 403: ErrorOut, 404: ErrorOut})
def list_company_employees(request, customer_id: str):
    """Return all person contacts that reference the given company contact."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Customer.objects.get(id=customer_id, firm=request.firm, type=ContactType.COMPANY)
    except Customer.DoesNotExist:
        return 404, {"detail": "Company not found."}

    employees = Customer.objects.filter(company_id=customer_id, firm=request.firm)
    return 200, [_customer_out(e) for e in employees]


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
    created_by_id: Optional[str]
    created_by_name: Optional[str]


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
    created_by_name: Optional[str] = None
    if lead.created_by_id:
        try:
            cb = lead.created_by
            created_by_name = f"{cb.first_name} {cb.last_name}".strip() or cb.email
        except Exception:
            pass
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
        "created_by_id": str(lead.created_by_id) if lead.created_by_id else None,
        "created_by_name": created_by_name,
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
    """Build the evaluation context dict for automation rules fired from a Task event.

    Args:
        task: A Task model instance (should have lead, customer, assigned_to pre-fetched).
        firm: The Firm instance that owns the task.

    Returns:
        A dict with string values suitable for condition evaluation and template rendering.
        Keys: task_id, task_title, task_status, task_priority, lead_id, lead_title,
              firm_id, assignee_id, assignee_email, assignee_name,
              customer_name, customer_email, owner_email, due_date.
    """
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



@router.get("/opportunities", auth=django_auth, response={200: List[LeadOut], 403: ErrorOut})
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
    leads = list(qs.select_related('created_by')[offset:offset + page_size])
    rules = list(LeadScoringRule.objects.filter(firm=request.firm))
    return 200, [_lead_out(lead, rules) for lead in leads]


@router.post("/opportunities", auth=django_auth, response={201: LeadOut, 400: ErrorOut, 402: ErrorOut, 403: ErrorOut})
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
        created_by=request.user,
    )
    broadcast_event(firm=request.firm, event='lead.created', payload=_lead_out(lead))

    # Fire workflow automation trigger: lead_created
    from crm.tasks import evaluate_automation_rules
    _automation_ctx = _build_lead_automation_context(lead, request.firm)
    from django.db import transaction
    transaction.on_commit(
        lambda: evaluate_automation_rules.delay("lead_created", str(request.firm.pk), _automation_ctx),
        robust=True,
    )

    return 201, _lead_out(lead)


@router.get("/opportunities/{lead_id}", auth=django_auth, response={200: LeadOut, 403: ErrorOut, 404: ErrorOut})
def get_lead(request, lead_id: str):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = Lead.objects.select_related('created_by').get(id=lead_id, firm=request.firm)
    except Lead.DoesNotExist:
        return 404, {"detail": "Lead not found."}
    return 200, _lead_out(lead)


@router.patch("/opportunities/{lead_id}", auth=django_auth, response={200: LeadOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut})
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
        from crm.apps import set_current_user, clear_current_user
        set_current_user(request.user)
        try:
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
                    ),
                    robust=True,
                )
            else:
                lead.save()
        finally:
            clear_current_user()

    broadcast_event(firm=request.firm, event='lead.updated', payload=_lead_out(lead))
    return 200, _lead_out(lead)


@router.delete("/opportunities/{lead_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
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
    entity_type: str
    entity_id: str
    # Kept for backwards-compatibility — None for realization/management activities
    lead_id: Optional[str]
    user_id: Optional[str]
    user_name: Optional[str]
    user_avatar_url: Optional[str] = None
    type: str
    content_text: str
    metadata: Dict[str, Any]
    is_internal: bool = False
    created_at: datetime
    # Tool-specific data; None when the activity type has no registered tool
    tool_payload: Optional[Dict[str, Any]] = None
    # Aggregated emoji reactions for this activity
    reactions: List[Dict[str, Any]] = []


class ActivityIn(Schema):
    # Exactly one of the entity IDs must be provided.
    lead_id: Optional[str] = None
    realization_id: Optional[str] = None
    management_id: Optional[str] = None
    customer_id: Optional[str] = None
    proposal_id: Optional[str] = None
    task_id: Optional[str] = None
    type: str
    content_text: str = ""
    metadata: Dict[str, Any] = {}
    is_internal: bool = False


def _user_display_name(user) -> Optional[str]:
    """Return a human-readable display name for an auth User, or None."""
    if user is None:
        return None
    return f"{user.first_name} {user.last_name}".strip() or user.email


def _activity_out(a: Activity, requesting_user=None) -> dict:
    from crm.streamline.registry import get_tool
    tool = get_tool(a.type)
    avatar_url = None
    pic = getattr(a.user, "profile_picture", None) if a.user else None
    if pic:
        avatar_url = pic.url
    # Aggregated emoji reactions — emoji / count / user_ids / reacted_by_me.
    reactions: list[dict] = []
    try:
        for r in a.reactions.all():
            existing = next((x for x in reactions if x["emoji"] == r.emoji), None)
            if existing is None:
                existing = {"emoji": r.emoji, "count": 0, "user_ids": [], "reacted_by_me": False}
                reactions.append(existing)
            existing["count"] += 1
            existing["user_ids"].append(str(r.user_id))
            if (
                requesting_user is not None
                and getattr(requesting_user, "is_authenticated", False)
                and str(r.user_id) == str(requesting_user.id)
            ):
                existing["reacted_by_me"] = True
    except Exception:
        # If the related manager isn't available (e.g. unsaved instance), silently fall back.
        reactions = []
    return {
        "id": str(a.id),
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "lead_id": str(a.lead_id) if a.lead_id else None,
        "user_id": str(a.user_id) if a.user_id else None,
        "user_name": _user_display_name(a.user),
        "user_avatar_url": avatar_url,
        "type": a.type,
        "content_text": a.content_text,
        "metadata": a.metadata,
        "is_internal": a.is_internal,
        "created_at": a.created_at,
        "tool_payload": tool.render_payload(a) if tool is not None else None,
        "reactions": reactions,
    }


@router.get("/directory/{customer_id}/activities", auth=django_auth, response={200: List[ActivityOut], 403: ErrorOut, 404: ErrorOut})
def list_customer_activities(request, customer_id: str, page: int = 1, page_size: int = 20):
    """Return the activity timeline for a Customer, newest first (paginated)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        customer = Customer.objects.get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(customer=customer).select_related('user').prefetch_related('reactions').order_by("-created_at")[offset:offset + page_size]
    return 200, [_activity_out(a, request.user) for a in activities]


@router.get("/opportunities/{lead_id}/activities", auth=django_auth, response={200: List[ActivityOut], 403: ErrorOut, 404: ErrorOut})
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
    activities = Activity.objects.filter(lead=lead).select_related('user').prefetch_related('reactions').order_by("-created_at")[offset:offset + page_size]
    return 200, [_activity_out(a, request.user) for a in activities]


@router.get("/tasks/{task_id}/activities", auth=django_auth, response={200: List[ActivityOut], 403: ErrorOut, 404: ErrorOut})
def list_task_activities(request, task_id: str, page: int = 1, page_size: int = 20):
    """Return the unified Streamline activity timeline for a Task, newest first (paginated).

    This is the canonical task Activity feed endpoint.  Reactions are toggled
    via ``POST /api/v1/crm/activities/{id}/reactions``.
    """
    from crm.models import Task as TaskModel
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = TaskModel.objects.get(id=task_id, firm=request.firm)
    except TaskModel.DoesNotExist:
        return 404, {"detail": "Task not found."}

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(task=task).select_related('user').prefetch_related('reactions').order_by("-created_at")[offset:offset + page_size]
    return 200, [_activity_out(a, request.user) for a in activities]


@router.post("/activities", auth=django_auth, response={201: ActivityOut, 400: ErrorOut, 403: ErrorOut})
def create_activity(request, payload: ActivityIn):
    """
    Unified Action Hub endpoint — works for Lead, Realization, Management, Customer, and Proposal.

    Exactly one of ``lead_id``, ``realization_id``, ``management_id``, ``customer_id``,
    or ``proposal_id`` must be provided.  Dispatches to the registered ``StreamlineTool``
    for the given activity type, which handles all type-specific side-effects.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    # --- resolve entity ---
    if sum([bool(payload.lead_id), bool(payload.realization_id), bool(payload.management_id),
            bool(payload.customer_id), bool(payload.proposal_id), bool(payload.task_id)]) != 1:
        return 400, {"detail": "Exactly one of lead_id, realization_id, management_id, customer_id, proposal_id, task_id must be provided."}

    lead = realization = management = customer = proposal = task = None
    entity_title = ""

    if payload.lead_id:
        try:
            lead = Lead.objects.get(id=payload.lead_id, firm=request.firm)
            entity_title = lead.title
        except Lead.DoesNotExist:
            return 400, {"detail": "Lead not found in this Firm."}
    elif payload.realization_id:
        try:
            realization = Realization.objects.get(id=payload.realization_id, firm=request.firm)
            entity_title = realization.title
        except Realization.DoesNotExist:
            return 400, {"detail": "Realization not found in this Firm."}
    elif payload.management_id:
        try:
            management = Management.objects.get(id=payload.management_id, firm=request.firm)
            entity_title = management.title
        except Management.DoesNotExist:
            return 400, {"detail": "Management record not found in this Firm."}
    elif payload.customer_id:
        try:
            customer = Customer.objects.get(id=payload.customer_id, firm=request.firm)
            entity_title = f"{customer.first_name} {customer.last_name}".strip() or customer.company_name
        except Customer.DoesNotExist:
            return 400, {"detail": "Customer not found in this Firm."}
    elif payload.proposal_id:
        from crm.models import Proposal as ProposalModel
        try:
            proposal = ProposalModel.objects.get(id=payload.proposal_id, firm=request.firm)
            entity_title = proposal.title
        except ProposalModel.DoesNotExist:
            return 400, {"detail": "Proposal not found in this Firm."}
    elif payload.task_id:
        from crm.models import Task as TaskModel
        try:
            task = TaskModel.objects.get(id=payload.task_id, firm=request.firm)
            entity_title = task.title
        except TaskModel.DoesNotExist:
            return 400, {"detail": "Task not found in this Firm."}

    from crm.streamline.registry import get_tool
    tool = get_tool(payload.type)
    if tool is None:
        return 400, {"detail": f"Unknown activity type '{payload.type}'."}

    # F-3 — structural payload validation against the tool's JSON Schema.
    from crm.streamline.validation import PayloadValidationError, validate_payload
    try:
        validate_payload(payload.type, payload.content_text, payload.metadata)
    except PayloadValidationError as exc:
        return 400, {"detail": str(exc)}

    entity = lead or realization or management or customer or proposal or task
    context = {
        "firm": request.firm,
        "user": request.user,
        "entity_title": entity_title,
    }

    with transaction.atomic():
        activity = Activity.objects.create(
            lead=lead,
            realization=realization,
            management=management,
            customer=customer,
            proposal=proposal,
            task=task,
            user=request.user,
            type=payload.type,
            content_text=payload.content_text,
            metadata=payload.metadata,
            is_internal=payload.is_internal,
        )
        tool.process_action(activity, entity, payload.model_dump(), context)

    broadcast_event(
        firm=request.firm,
        event='activity.created',
        payload=_activity_out(activity),
    )
    return 201, _activity_out(activity, request.user)


class _ReactionToggleIn(Schema):
    emoji: str


@router.post(
    "/activities/{activity_id}/reactions",
    auth=django_auth,
    response={200: dict, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def toggle_activity_reaction(request, activity_id: str, payload: _ReactionToggleIn):
    """
    Toggle an emoji reaction on any Activity (entity-agnostic).

    Works for activities attached to any entity (lead, customer, realization,
    management, proposal, task).  If the requesting user has already reacted
    with this emoji the reaction is removed; otherwise it is added.

    Returns the updated aggregate for this emoji.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        activity = Activity.objects.get(id=activity_id)
    except Activity.DoesNotExist:
        return 404, {"detail": "Activity not found."}

    # Verify the activity belongs to a firm the requesting user is a member of.
    # All entities the activity can reference live within a Firm scope; we
    # check every possible FK and reject if none match the requesting firm.
    firm_id = None
    for related in (activity.lead, activity.realization, activity.management,
                    activity.customer, activity.proposal, activity.task):
        if related is not None and getattr(related, "firm_id", None) is not None:
            firm_id = related.firm_id
            break
    if firm_id is None or str(firm_id) != str(request.firm.id):
        return 404, {"detail": "Activity not found."}

    emoji = (payload.emoji or "").strip()
    if not emoji:
        return 400, {"detail": "Emoji must not be empty."}

    reaction, created = ActivityReaction.objects.get_or_create(
        activity=activity, user=request.user, emoji=emoji,
    )
    if not created:
        reaction.delete()

    qs = ActivityReaction.objects.filter(activity=activity, emoji=emoji)
    user_ids = list(qs.values_list("user_id", flat=True))
    return 200, {
        "emoji": emoji,
        "count": qs.count(),
        "user_ids": [str(uid) for uid in user_ids],
        "reacted_by_me": qs.filter(user=request.user).exists(),
    }


# ===========================================================================
# TASKS
# ===========================================================================

class TaskOut(Schema):
    id: str
    firm_id: str
    # Entity links
    lead_id: Optional[str]
    lead_title: Optional[str]
    realization_id: Optional[str]
    realization_title: Optional[str]
    management_id: Optional[str]
    management_title: Optional[str]
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
    kind: str
    tags: List[str]
    # Dates
    due_date: Optional[datetime]
    due_date_end: Optional[datetime]
    # Calendar fields
    location: str
    attendees: List[str]
    auto_close_on_expiry: bool
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
    # Phase 6: time tracking
    estimated_minutes: Optional[int]
    total_logged_minutes: int
    my_active_timer_started_at: Optional[datetime]
    # Phase 7: recurrence
    recurrence: Optional[Dict[str, Any]]
    recurrence_parent_id: Optional[str]
    # Phase 7: approval
    approval_required: bool
    approval_status: str
    approval_requested_from_id: Optional[str]
    approval_requested_from_name: Optional[str]
    approval_note: str
    # Phase 8: custom fields
    custom_fields: List[Dict[str, Any]]


class TaskIn(Schema):
    lead_id: Optional[str] = None
    realization_id: Optional[str] = None
    management_id: Optional[str] = None
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
    estimated_minutes: Optional[int] = None
    clear_estimated_minutes: bool = False
    # Phase 7: recurrence
    recurrence: Optional[Dict[str, Any]] = None
    clear_recurrence: bool = False
    # Phase 7: approval
    approval_required: Optional[bool] = None


class FollowUpTaskIn(Schema):
    title: str
    description: str = ""
    assigned_to_id: Optional[str] = None
    watcher_ids: List[str] = []
    due_date: Optional[datetime] = None
    lead_id: Optional[str] = None


class CompleteTaskIn(Schema):
    follow_up: Optional[FollowUpTaskIn] = None


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

    # Resolve realization title
    realization_id = None
    realization_title = None
    if t.realization_id:
        realization_id = str(t.realization_id)
        try:
            realization_title = t.realization.title
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve realization title for task %s: %s", t.id, exc)

    # Resolve management title
    management_id = None
    management_title = None
    if t.management_id:
        management_id = str(t.management_id)
        try:
            management_title = t.management.title
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve management title for task %s: %s", t.id, exc)

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

    # Phase 6: time tracking
    try:
        from django.db.models import Sum as _Sum
        total_logged_minutes = (
            TaskTimeLog.objects.filter(task=t).aggregate(total=_Sum("duration_minutes"))["total"] or 0
        )
    except Exception:
        total_logged_minutes = 0

    my_active_timer_started_at = None
    if requesting_user and requesting_user.is_authenticated:
        try:
            active_timer = TaskTimer.objects.filter(
                task=t, user=requesting_user, stopped_at__isnull=True
            ).first()
            if active_timer:
                my_active_timer_started_at = active_timer.started_at
        except Exception:
            pass

    # Phase 7: approval
    approval_requested_from_name: Optional[str] = None
    if t.approval_requested_from_id:
        try:
            arf = t.approval_requested_from
            approval_requested_from_name = f"{arf.first_name} {arf.last_name}".strip() or arf.email
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve approval_requested_from for task %s: %s", t.id, exc)

    # Phase 8: custom field values
    custom_fields = []
    try:
        cf_values = {
            str(v.field_id): v
            for v in TaskCustomFieldValue.objects.filter(task=t).select_related("field")
        }
        all_fields = TaskCustomField.objects.filter(firm=t.firm).order_by("position", "name")
        for cf in all_fields:
            val_obj = cf_values.get(str(cf.id))
            if cf.field_type == "number":
                value = float(val_obj.value_number) if (val_obj and val_obj.value_number is not None) else None
            elif cf.field_type == "date":
                value = val_obj.value_date.isoformat() if (val_obj and val_obj.value_date) else None
            elif cf.field_type == "checkbox":
                value = val_obj.value_bool if (val_obj and val_obj.value_bool is not None) else False
            else:
                value = val_obj.value_text if val_obj else ""
            custom_fields.append({
                "field_id": str(cf.id),
                "name": cf.name,
                "field_type": cf.field_type,
                "options": cf.options if isinstance(cf.options, list) else [],
                "is_required": cf.is_required,
                "position": cf.position,
                "value": value,
            })
    except Exception as exc:
        logger.debug("Could not resolve custom fields for task %s: %s", t.id, exc)

    return {
        "id": str(t.id),
        "firm_id": str(t.firm_id),
        "lead_id": lead_id,
        "lead_title": lead_title,
        "realization_id": realization_id,
        "realization_title": realization_title,
        "management_id": management_id,
        "management_title": management_title,
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
        "kind": t.kind,
        "tags": t.tags if isinstance(t.tags, list) else [],
        "due_date": t.due_date,
        "due_date_end": t.due_date_end,
        "location": t.location,
        "attendees": t.attendees if isinstance(t.attendees, list) else [],
        "auto_close_on_expiry": t.auto_close_on_expiry,
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
        # Phase 6
        "estimated_minutes": t.estimated_minutes,
        "total_logged_minutes": total_logged_minutes,
        "my_active_timer_started_at": my_active_timer_started_at,
        # Phase 7: recurrence
        "recurrence": t.recurrence,
        "recurrence_parent_id": str(t.recurrence_parent_id) if t.recurrence_parent_id else None,
        # Phase 7: approval
        "approval_required": t.approval_required,
        "approval_status": t.approval_status,
        "approval_requested_from_id": str(t.approval_requested_from_id) if t.approval_requested_from_id else None,
        "approval_requested_from_name": approval_requested_from_name,
        "approval_note": t.approval_note,
        # Phase 8
        "custom_fields": custom_fields,
    }


def _resolve_user_in_firm(user_id: str, firm) -> tuple:
    """Return (user, error_response) where error_response is None on success."""
    from django.core.exceptions import ValidationError as DjangoValidationError
    from users.models import User
    try:
        user = User.objects.get(id=user_id)
    except (User.DoesNotExist, ValueError, DjangoValidationError):
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

    realization = None
    if payload.realization_id:
        try:
            realization = Realization.objects.get(id=payload.realization_id, firm=request.firm)
        except Realization.DoesNotExist:
            return 400, {"detail": "Realization not found in this Firm."}

    management = None
    if payload.management_id:
        try:
            management = Management.objects.get(id=payload.management_id, firm=request.firm)
        except Management.DoesNotExist:
            return 400, {"detail": "Management record not found in this Firm."}

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
            realization=realization,
            management=management,
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

        # Log activity on the linked entity (lead, realization, or management).
        # Mirrors the unified Streamline timeline contract: a TASK_ASSIGNED
        # event is emitted onto whichever entity owns the task so that the
        # entity's detail timeline shows it. We log onto each linked entity
        # independently — a task may be linked to both lead and realization.
        primary_entity = lead or realization or management
        if primary_entity is not None:
            assignee_name = ""
            if payload.assigned_to_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    assignee = User.objects.get(id=payload.assigned_to_id)
                    assignee_name = assignee.full_name
                except User.DoesNotExist:
                    pass
            activity_metadata = {
                "task_id": str(task.id),
                "task_title": task.title,
                "due_date": payload.due_date.isoformat() if payload.due_date else None,
                "priority": payload.priority,
                "assigned_to_name": assignee_name,
            }
            if lead:
                Activity.objects.create(
                    lead=lead,
                    user=request.user,
                    type=ActivityType.TASK_ASSIGNED,
                    metadata=activity_metadata,
                )
            if realization:
                Activity.objects.create(
                    realization=realization,
                    user=request.user,
                    type=ActivityType.TASK_ASSIGNED,
                    metadata=activity_metadata,
                )
            if management:
                Activity.objects.create(
                    management=management,
                    user=request.user,
                    type=ActivityType.TASK_ASSIGNED,
                    metadata=activity_metadata,
                )

    _notify_task_watchers(task, "task.created")
    broadcast_event(firm=request.firm, event='task.created', payload=_task_out(task, request.user))
    # Phase 2: log system timeline event
    _log_timeline_event(task, ActivityType.TASK_CREATED, author=request.user)
    # Phase 4: fire task_created automation trigger
    from crm.tasks import evaluate_automation_rules
    _task_auto_ctx = _build_task_automation_context(task, request.firm)
    transaction.on_commit(
        lambda ctx=_task_auto_ctx: evaluate_automation_rules.delay(
            "task_created", str(request.firm.pk), ctx
        ),
        robust=True,
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

    if payload.clear_estimated_minutes:
        task.estimated_minutes = None
        update_fields.append("estimated_minutes")
    elif payload.estimated_minutes is not None:
        task.estimated_minutes = payload.estimated_minutes
        update_fields.append("estimated_minutes")

    # Phase 7: recurrence
    if payload.clear_recurrence:
        task.recurrence = None
        update_fields.append("recurrence")
    elif payload.recurrence is not None:
        _valid_recurrence_types = {"daily", "weekly", "monthly", "custom"}
        rec_type = payload.recurrence.get("type", "")
        if rec_type not in _valid_recurrence_types:
            return 400, {"detail": f"Invalid recurrence type '{rec_type}'. Choose from: {sorted(_valid_recurrence_types)}"}
        task.recurrence = payload.recurrence
        update_fields.append("recurrence")

    # Phase 7: approval_required toggle
    if payload.approval_required is not None:
        task.approval_required = payload.approval_required
        update_fields.append("approval_required")

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
            task, ActivityType.STATUS_CHANGE, author=request.user,
            metadata={"from": old_status, "to": task.status},
        )
    if payload.priority is not None and task.priority != old_priority:
        _log_timeline_event(
            task, ActivityType.PRIORITY_CHANGE, author=request.user,
            metadata={"from": old_priority, "to": task.priority},
        )
    if payload.assigned_to_id is not None:
        new_assignee_name = _author_name_for(task.assigned_to) if task.assigned_to_id else None
        if new_assignee_name != old_assignee_name:
            _log_timeline_event(
                task, ActivityType.ASSIGNEE_CHANGE, author=request.user,
                metadata={"from_name": old_assignee_name, "to_name": new_assignee_name},
            )
    due_date_payload_changed = payload.due_date is not None or payload.clear_due_date
    new_due_date_value = task.due_date.isoformat() if task.due_date else None
    if due_date_payload_changed and new_due_date_value != old_due_date:
        _log_timeline_event(
            task, ActivityType.DUE_DATE_CHANGE, author=request.user,
            metadata={"old": old_due_date, "new": new_due_date_value},
        )
    if payload.is_archived is not None and task.is_archived != old_archived and task.is_archived:
        _log_timeline_event(task, ActivityType.TASK_ARCHIVED, author=request.user)

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
        # Log Activity on every linked entity (lead, realization, management).
        # Mirrors the per-entity pattern from create_task (19th iter): a task
        # may be linked to multiple entities and each timeline must show the
        # completion event independently.
        completion_metadata = {"task_id": str(task.id), "title": task.title}
        if task.lead_id:
            Activity.objects.create(
                lead=task.lead,
                user=request.user,
                type=ActivityType.TASK_COMPLETED,
                metadata=completion_metadata,
            )
        if task.realization_id:
            Activity.objects.create(
                realization=task.realization,
                user=request.user,
                type=ActivityType.TASK_COMPLETED,
                metadata=completion_metadata,
            )
        if task.management_id:
            Activity.objects.create(
                management=task.management,
                user=request.user,
                type=ActivityType.TASK_COMPLETED,
                metadata=completion_metadata,
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
    _log_timeline_event(task, ActivityType.TASK_COMPLETED, author=request.user)
    # Phase 4: fire task_completed automation trigger
    from crm.tasks import evaluate_automation_rules
    _task_auto_ctx = _build_task_automation_context(task, request.firm)
    transaction.on_commit(
        lambda ctx=_task_auto_ctx: evaluate_automation_rules.delay(
            "task_completed", str(request.firm.pk), ctx
        ),
        robust=True,
    )
    if follow_up_task:
        _notify_task_watchers(follow_up_task, "task.created")
        broadcast_event(firm=request.firm, event='task.created', payload=_task_out(follow_up_task, request.user))
        _log_timeline_event(follow_up_task, ActivityType.TASK_CREATED, author=request.user)

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
# Task documents (unified Document model + Activity(file_upload))
# ---------------------------------------------------------------------------

_MAX_TASK_DOCUMENT_BYTES = 20 * 1024 * 1024  # 20 MB


class TaskDocumentOut(Schema):
    id: str
    task_id: str
    uploaded_by_id: Optional[str]
    original_filename: str
    content_type: str
    size_bytes: int
    url: str
    created_at: datetime


def _task_document_out(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "task_id": str(doc.task_id) if doc.task_id else "",
        "uploaded_by_id": str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
        "original_filename": doc.name,
        "content_type": doc.content_type or "",
        "size_bytes": doc.size_bytes,
        "url": doc.file.url if doc.file.name else "",
        "created_at": doc.created_at,
    }


@router.get(
    "/tasks/{task_id}/documents",
    auth=django_auth,
    response={200: List[TaskDocumentOut], 403: ErrorOut, 404: ErrorOut},
)
def list_task_documents(request, task_id: str, page: int = 1, page_size: int = 50):
    """List all documents attached to a task, newest first."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    offset = (page - 1) * page_size
    docs = Document.objects.filter(task=task, firm=request.firm).order_by("-created_at")[
        offset: offset + page_size
    ]
    return 200, [_task_document_out(d) for d in docs]


@router.post(
    "/tasks/{task_id}/documents",
    auth=django_auth,
    response={201: TaskDocumentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_task_document(request, task_id: str, file: UploadedFile = File(...)):
    """Upload a file and attach it to a task as a Document.

    Creates an ``Activity(type=file_upload)`` so the document appears inline
    in the unified task timeline.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if file.size > _MAX_TASK_DOCUMENT_BYTES:
        return 400, {
            "detail": f"File exceeds the maximum allowed size of {_MAX_TASK_DOCUMENT_BYTES // (1024 * 1024)} MB."
        }

    with transaction.atomic():
        doc = Document(
            firm=request.firm,
            task=task,
            uploaded_by=request.user,
            name=file.name,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file.size,
        )
        doc.file.save(file.name, file, save=True)

        Activity.objects.create(
            task=task,
            user=request.user,
            type=ActivityType.FILE_UPLOAD,
            metadata={
                "document_id": str(doc.id),
                "filename": doc.name,
                "url": doc.file.url,
                "size_bytes": doc.size_bytes,
                "content_type": doc.content_type,
            },
        )

    return 201, _task_document_out(doc)


@router.delete(
    "/tasks/{task_id}/documents/{document_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task_document(request, task_id: str, document_id: str):
    """Delete a document attached to a task. Only uploader or admin/owner may delete."""
    try:
        membership = require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        doc = Document.objects.get(id=document_id, task_id=task_id, firm=request.firm)
    except Document.DoesNotExist:
        return 404, {"detail": "Document not found."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    if str(doc.uploaded_by_id) != str(request.user.id) and not is_admin:
        return 403, {"detail": "You can only delete your own documents."}

    doc.file.delete(save=False)
    doc.delete()
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
        parent, ActivityType.SUB_TASK_ADDED, author=request.user,
        metadata={"subtask_id": str(subtask.id), "title": subtask.title},
    )
    _log_timeline_event(subtask, ActivityType.TASK_CREATED, author=request.user)
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
    _log_timeline_event(task, ActivityType.TASK_ARCHIVED, author=request.user)
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
        _log_timeline_event(new_sub, ActivityType.TASK_CREATED, author=created_by)
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

        if payload.include_subtasks:
            _copy_subtasks_recursive(original, new_task, request.firm, request.user)

        _log_timeline_event(new_task, ActivityType.TASK_CREATED, author=request.user)

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
                    _log_timeline_event(task, ActivityType.TASK_COMPLETED, author=request.user)
            elif payload.action == "archive":
                task.is_archived = True
                task.save(update_fields=["is_archived"])
                _log_timeline_event(task, ActivityType.TASK_ARCHIVED, author=request.user)
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
# Helpers (task activity logging)
#
# The legacy ``GET/POST /tasks/{id}/timeline`` and
# ``POST /tasks/{id}/timeline/{entry_id}/reactions`` endpoints (along with
# their schemas ``TaskTimelineEntryOut`` / ``TaskTimelinePostIn`` /
# ``TimelineReactionIn`` / ``TimelineAttachmentOut`` / ``ReactionSummaryOut``)
# were removed as part of the Streamline Phase 4 cleanup.  The unified
# ``Activity`` timeline is now exposed exclusively through
# ``/api/v1/crm/tasks/{id}/activities`` and
# ``/api/v1/crm/activities/{id}/reactions``.
#
# Only the activity-logging helpers below are still used by other endpoints
# in this module (task create/update/complete, subtask, batch action, …).
# ---------------------------------------------------------------------------


def _author_name_for(user) -> Optional[str]:
    """Return display name for a user object or None."""
    if user is None:
        return None
    try:
        return f"{user.first_name} {user.last_name}".strip() or user.email
    except Exception:
        return None


def _log_timeline_event(task: Task, event_type: str, author=None, metadata: dict = None) -> None:
    """
    Create an ``Activity`` of the given type linked to the Task.

    Silently swallows any errors so it never breaks the main request.
    """
    try:
        Activity.objects.create(
            task=task,
            user=author,
            type=event_type,
            content_text="",
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to log task activity %s for task %s", event_type, task.id)


# ===========================================================================
# PHASE 6 — TIME TRACKING
# ===========================================================================

class TaskTimeLogOut(Schema):
    id: str
    task_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    logged_at: datetime
    duration_minutes: int
    description: str
    created_at: datetime


class TaskTimeLogIn(Schema):
    duration_minutes: int
    description: str = ""
    logged_at: Optional[datetime] = None


class TaskTimerOut(Schema):
    id: str
    task_id: str
    user_id: str
    started_at: datetime
    stopped_at: Optional[datetime]
    is_running: bool


def _time_log_out(log: TaskTimeLog) -> dict:
    user_name = None
    if log.user_id:
        try:
            user_name = _author_name_for(log.user)
        except Exception:
            pass
    return {
        "id": str(log.id),
        "task_id": str(log.task_id),
        "user_id": str(log.user_id) if log.user_id else None,
        "user_name": user_name,
        "logged_at": log.logged_at,
        "duration_minutes": log.duration_minutes,
        "description": log.description,
        "created_at": log.created_at,
    }


def _timer_out(timer: TaskTimer) -> dict:
    return {
        "id": str(timer.id),
        "task_id": str(timer.task_id),
        "user_id": str(timer.user_id),
        "started_at": timer.started_at,
        "stopped_at": timer.stopped_at,
        "is_running": timer.stopped_at is None,
    }


@router.get(
    "/tasks/{task_id}/time-logs",
    auth=django_auth,
    response={200: List[TaskTimeLogOut], 403: ErrorOut, 404: ErrorOut},
)
def list_time_logs(request, task_id: str):
    """List all time log entries for a task."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    logs = TaskTimeLog.objects.filter(task=task).select_related("user").order_by("-logged_at", "-created_at")
    return 200, [_time_log_out(log) for log in logs]


@router.post(
    "/tasks/{task_id}/time-logs",
    auth=django_auth,
    response={201: TaskTimeLogOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_time_log(request, task_id: str, payload: TaskTimeLogIn):
    """Manually log time worked on a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if payload.duration_minutes <= 0:
        return 400, {"detail": "duration_minutes must be a positive integer."}

    logged_at = payload.logged_at or tz.now()

    with transaction.atomic():
        log = TaskTimeLog.objects.create(
            task=task,
            user=request.user,
            logged_at=logged_at,
            duration_minutes=payload.duration_minutes,
            description=payload.description,
        )
        _log_timeline_event(
            task, ActivityType.TIME_LOGGED, author=request.user,
            metadata={
                "minutes": payload.duration_minutes,
                "description": payload.description,
                "time_log_id": str(log.id),
            },
        )

    broadcast_event(firm=request.firm, event="task.time_logged", payload={"task_id": task_id})
    return 201, _time_log_out(log)


@router.delete(
    "/tasks/{task_id}/time-logs/{log_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_time_log(request, task_id: str, log_id: str):
    """Delete a time log entry. Users can only delete their own logs unless they are an admin."""
    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        log = TaskTimeLog.objects.get(id=log_id, task=task)
    except TaskTimeLog.DoesNotExist:
        return 404, {"detail": "Time log not found."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    if not is_admin and (log.user_id is None or str(log.user_id) != str(request.user.id)):
        return 403, {"detail": "You can only delete your own time log entries."}

    log.delete()
    return 204, None


@router.post(
    "/tasks/{task_id}/timer/start",
    auth=django_auth,
    response={201: TaskTimerOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def start_timer(request, task_id: str):
    """
    Start a stopwatch timer for the current user on this task.

    Only one active timer per user is allowed. If the user already has a
    running timer on *any* task it is returned as a 400 error — the client
    should stop that timer first.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    # One running timer per user
    existing = TaskTimer.objects.filter(user=request.user, stopped_at__isnull=True).first()
    if existing:
        return 400, {"detail": "You already have a running timer. Stop it before starting a new one."}

    timer = TaskTimer.objects.create(
        task=task,
        user=request.user,
        started_at=tz.now(),
    )
    return 201, _timer_out(timer)


@router.post(
    "/tasks/{task_id}/timer/stop",
    auth=django_auth,
    response={200: TaskTimerOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def stop_timer(request, task_id: str):
    """
    Stop the running timer for the current user on this task.

    Automatically creates a ``TaskTimeLog`` entry for the elapsed time and
    logs a ``time_logged`` timeline event.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    try:
        timer = TaskTimer.objects.get(task=task, user=request.user, stopped_at__isnull=True)
    except TaskTimer.DoesNotExist:
        return 400, {"detail": "No running timer found for this task."}

    now = tz.now()
    elapsed_seconds = (now - timer.started_at).total_seconds()
    duration_minutes = max(1, round(elapsed_seconds / 60))

    with transaction.atomic():
        timer.stopped_at = now
        timer.save(update_fields=["stopped_at"])

        log = TaskTimeLog.objects.create(
            task=task,
            user=request.user,
            logged_at=timer.started_at,
            duration_minutes=duration_minutes,
            description="",
        )
        _log_timeline_event(
            task, ActivityType.TIME_LOGGED, author=request.user,
            metadata={
                "minutes": duration_minutes,
                "description": "Timer stopped",
                "time_log_id": str(log.id),
            },
        )

    broadcast_event(firm=request.firm, event="task.time_logged", payload={"task_id": task_id})
    return 200, _timer_out(timer)


@router.get(
    "/tasks/{task_id}/timer/active",
    auth=django_auth,
    response={200: Optional[TaskTimerOut], 403: ErrorOut, 404: ErrorOut},
)
def get_active_timer(request, task_id: str):
    """
    Return the currently running timer for this task and the current user,
    or ``null`` if no timer is running.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    timer = TaskTimer.objects.filter(task=task, user=request.user, stopped_at__isnull=True).first()
    return 200, _timer_out(timer) if timer else None


# ===========================================================================
# PHASE 7 — APPROVAL WORKFLOW
# ===========================================================================

class ApprovalRequestIn(Schema):
    approver_id: str


class ApprovalRejectIn(Schema):
    note: str = ""


@router.post(
    "/tasks/{task_id}/request-approval",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def request_approval(request, task_id: str, payload: ApprovalRequestIn):
    """
    Send an approval request for a task to a specific firm member.

    Sets ``approval_status`` to ``pending`` and records the approver.
    A timeline entry is logged automatically.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if task.approval_status == Task.ApprovalStatus.PENDING:
        return 400, {"detail": "An approval request is already pending for this task."}

    approver, err = _resolve_user_in_firm(payload.approver_id, request.firm)
    if err:
        return err

    with transaction.atomic():
        task.approval_required = True
        task.approval_requested_from = approver
        task.approval_status = Task.ApprovalStatus.PENDING
        task.approval_note = ""
        task.save(update_fields=["approval_required", "approval_requested_from", "approval_status", "approval_note"])

        _log_timeline_event(
            task, ActivityType.APPROVAL_REQUESTED, author=request.user,
            metadata={
                "approver_id": str(approver.id),
                "approver_name": _author_name_for(approver),
            },
        )

    broadcast_event(firm=request.firm, event="task.approval_requested", payload=_task_out(task, request.user))
    _notify_task_watchers(task, "task.updated")
    return 200, _task_out(task, request.user)


@router.post(
    "/tasks/{task_id}/approve",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def approve_task(request, task_id: str):
    """
    Approve a pending task.  Only the designated approver (or an admin/owner)
    can approve.  Sets ``approval_status`` to ``approved``.
    """
    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.select_related("approval_requested_from").get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if task.approval_status != Task.ApprovalStatus.PENDING:
        return 400, {"detail": "Task does not have a pending approval request."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    is_approver = task.approval_requested_from_id and str(task.approval_requested_from_id) == str(request.user.id)
    if not is_approver and not is_admin:
        return 403, {"detail": "Only the designated approver or an admin can approve this task."}

    with transaction.atomic():
        task.approval_status = Task.ApprovalStatus.APPROVED
        task.save(update_fields=["approval_status"])

        _log_timeline_event(
            task, ActivityType.APPROVAL_RESOLVED, author=request.user,
            metadata={"decision": "approved", "approver_name": _author_name_for(request.user)},
        )

    broadcast_event(firm=request.firm, event="task.approval_resolved", payload=_task_out(task, request.user))
    _notify_task_watchers(task, "task.updated")
    return 200, _task_out(task, request.user)


@router.post(
    "/tasks/{task_id}/reject",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def reject_task(request, task_id: str, payload: ApprovalRejectIn):
    """
    Reject a pending task approval.  Only the designated approver (or an
    admin/owner) can reject.  Sets ``approval_status`` to ``rejected`` and
    stores the optional rejection note.
    """
    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.select_related("approval_requested_from").get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if task.approval_status != Task.ApprovalStatus.PENDING:
        return 400, {"detail": "Task does not have a pending approval request."}

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    is_approver = task.approval_requested_from_id and str(task.approval_requested_from_id) == str(request.user.id)
    if not is_approver and not is_admin:
        return 403, {"detail": "Only the designated approver or an admin can reject this task."}

    with transaction.atomic():
        task.approval_status = Task.ApprovalStatus.REJECTED
        task.approval_note = payload.note
        task.save(update_fields=["approval_status", "approval_note"])

        _log_timeline_event(
            task, ActivityType.APPROVAL_RESOLVED, author=request.user,
            metadata={
                "decision": "rejected",
                "note": payload.note,
                "approver_name": _author_name_for(request.user),
            },
        )

    broadcast_event(firm=request.firm, event="task.approval_resolved", payload=_task_out(task, request.user))
    _notify_task_watchers(task, "task.updated")
    return 200, _task_out(task, request.user)


# ===========================================================================
# PHASE 7 — TASK TEMPLATES
# ===========================================================================

class TaskTemplateOut(Schema):
    id: str
    firm_id: str
    name: str
    description_html: str
    priority: str
    estimated_minutes: Optional[int]
    checklist_items: List[Dict[str, Any]]
    tags: List[str]
    created_by_id: Optional[str]
    created_by_name: Optional[str]
    created_at: datetime
    updated_at: datetime


class TaskTemplateIn(Schema):
    name: str
    description_html: str = ""
    priority: str = TaskPriority.MEDIUM
    estimated_minutes: Optional[int] = None
    checklist_items: List[Dict[str, Any]] = []
    tags: List[str] = []


class TaskTemplateUpdateIn(Schema):
    name: Optional[str] = None
    description_html: Optional[str] = None
    priority: Optional[str] = None
    estimated_minutes: Optional[int] = None
    clear_estimated_minutes: bool = False
    checklist_items: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[str]] = None


class TaskTemplateApplyIn(Schema):
    title: str
    lead_id: Optional[str] = None
    proposal_id: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_to_id: Optional[str] = None
    watcher_ids: List[str] = []
    due_date: Optional[datetime] = None


def _template_out(tmpl: TaskTemplate) -> dict:
    created_by_name = None
    if tmpl.created_by_id:
        try:
            created_by_name = _author_name_for(tmpl.created_by)
        except Exception:
            pass
    return {
        "id": str(tmpl.id),
        "firm_id": str(tmpl.firm_id),
        "name": tmpl.name,
        "description_html": tmpl.description_html,
        "priority": tmpl.priority,
        "estimated_minutes": tmpl.estimated_minutes,
        "checklist_items": tmpl.checklist_items if isinstance(tmpl.checklist_items, list) else [],
        "tags": tmpl.tags if isinstance(tmpl.tags, list) else [],
        "created_by_id": str(tmpl.created_by_id) if tmpl.created_by_id else None,
        "created_by_name": created_by_name,
        "created_at": tmpl.created_at,
        "updated_at": tmpl.updated_at,
    }


@router.get(
    "/task-templates",
    auth=django_auth,
    response={200: List[TaskTemplateOut], 403: ErrorOut},
)
def list_task_templates(request):
    """List all task templates for the active firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    templates = TaskTemplate.objects.filter(firm=request.firm).select_related("created_by")
    return 200, [_template_out(tmpl) for tmpl in templates]


@router.post(
    "/task-templates",
    auth=django_auth,
    response={201: TaskTemplateOut, 400: ErrorOut, 403: ErrorOut},
)
def create_task_template(request, payload: TaskTemplateIn):
    """Create a new task template for the active firm."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    if not payload.name.strip():
        return 400, {"detail": "Template name must not be empty."}

    valid_priorities = [p.value for p in TaskPriority]
    if payload.priority not in valid_priorities:
        return 400, {"detail": f"Invalid priority. Choose from: {valid_priorities}"}

    tmpl = TaskTemplate.objects.create(
        firm=request.firm,
        name=payload.name.strip(),
        description_html=payload.description_html,
        priority=payload.priority,
        estimated_minutes=payload.estimated_minutes,
        checklist_items=payload.checklist_items,
        tags=payload.tags,
        created_by=request.user,
    )
    return 201, _template_out(tmpl)


@router.get(
    "/task-templates/{template_id}",
    auth=django_auth,
    response={200: TaskTemplateOut, 403: ErrorOut, 404: ErrorOut},
)
def get_task_template(request, template_id: str):
    """Get a single task template by ID."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = TaskTemplate.objects.select_related("created_by").get(id=template_id, firm=request.firm)
    except TaskTemplate.DoesNotExist:
        return 404, {"detail": "Task template not found."}

    return 200, _template_out(tmpl)


@router.patch(
    "/task-templates/{template_id}",
    auth=django_auth,
    response={200: TaskTemplateOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_task_template(request, template_id: str, payload: TaskTemplateUpdateIn):
    """Partially update an existing task template."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = TaskTemplate.objects.get(id=template_id, firm=request.firm)
    except TaskTemplate.DoesNotExist:
        return 404, {"detail": "Task template not found."}

    update_fields = []

    if payload.name is not None:
        if not payload.name.strip():
            return 400, {"detail": "Template name must not be empty."}
        tmpl.name = payload.name.strip()
        update_fields.append("name")

    if payload.description_html is not None:
        tmpl.description_html = payload.description_html
        update_fields.append("description_html")

    if payload.priority is not None:
        valid_priorities = [p.value for p in TaskPriority]
        if payload.priority not in valid_priorities:
            return 400, {"detail": f"Invalid priority. Choose from: {valid_priorities}"}
        tmpl.priority = payload.priority
        update_fields.append("priority")

    if payload.clear_estimated_minutes:
        tmpl.estimated_minutes = None
        update_fields.append("estimated_minutes")
    elif payload.estimated_minutes is not None:
        tmpl.estimated_minutes = payload.estimated_minutes
        update_fields.append("estimated_minutes")

    if payload.checklist_items is not None:
        tmpl.checklist_items = payload.checklist_items
        update_fields.append("checklist_items")

    if payload.tags is not None:
        tmpl.tags = payload.tags
        update_fields.append("tags")

    if update_fields:
        tmpl.save(update_fields=update_fields)

    return 200, _template_out(tmpl)


@router.delete(
    "/task-templates/{template_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task_template(request, template_id: str):
    """Delete a task template."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = TaskTemplate.objects.get(id=template_id, firm=request.firm)
    except TaskTemplate.DoesNotExist:
        return 404, {"detail": "Task template not found."}

    tmpl.delete()
    return 204, None


@router.post(
    "/task-templates/{template_id}/apply",
    auth=django_auth,
    response={201: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def apply_task_template(request, template_id: str, payload: TaskTemplateApplyIn):
    """
    Create a new task from a template.

    The template's description, priority, estimated_minutes, tags, and
    checklist items are all copied into the newly created task.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    try:
        tmpl = TaskTemplate.objects.get(id=template_id, firm=request.firm)
    except TaskTemplate.DoesNotExist:
        return 404, {"detail": "Task template not found."}

    if not payload.title.strip():
        return 400, {"detail": "Task title must not be empty."}

    # Resolve optional entity links
    lead = None
    if payload.lead_id:
        try:
            lead = Lead.objects.get(id=payload.lead_id, firm=request.firm)
        except Lead.DoesNotExist:
            return 400, {"detail": "Lead not found."}

    proposal = None
    if payload.proposal_id:
        try:
            proposal = Proposal.objects.get(id=payload.proposal_id, lead__firm=request.firm)
        except Proposal.DoesNotExist:
            return 400, {"detail": "Proposal not found."}

    customer = None
    if payload.customer_id:
        try:
            customer = Customer.objects.get(id=payload.customer_id, firm=request.firm)
        except Customer.DoesNotExist:
            return 400, {"detail": "Customer not found."}

    # Resolve assignee
    assigned_to = None
    if payload.assigned_to_id:
        assigned_to, err = _resolve_user_in_firm(payload.assigned_to_id, request.firm)
        if err:
            return err

    with transaction.atomic():
        task = Task.objects.create(
            firm=request.firm,
            lead=lead,
            proposal=proposal,
            customer=customer,
            title=payload.title.strip(),
            description_html=tmpl.description_html,
            description_added_at=tz.now() if tmpl.description_html else None,
            priority=tmpl.priority,
            estimated_minutes=tmpl.estimated_minutes,
            tags=list(tmpl.tags),
            assigned_to=assigned_to,
            due_date=payload.due_date,
            created_by=request.user,
        )

        # Set watchers
        if payload.watcher_ids:
            watcher_err = _set_task_watchers(task, payload.watcher_ids, request.firm)
            if watcher_err:
                raise ValueError(f"Watcher error: {watcher_err}")

        # Copy checklist items from template
        checklist_items = tmpl.checklist_items if isinstance(tmpl.checklist_items, list) else []
        for item_data in checklist_items:
            text = str(item_data.get("text", "")).strip()
            if text:
                TaskChecklistItem.objects.create(
                    task=task,
                    text=text,
                    position=int(item_data.get("position", 0)),
                    created_by=request.user,
                )

        _log_timeline_event(
            task, ActivityType.TASK_CREATED, author=request.user,
            metadata={"from_template_id": str(tmpl.id), "template_name": tmpl.name},
        )

    broadcast_event(firm=request.firm, event="task.created", payload=_task_out(task, request.user))
    _notify_task_watchers(task, "task.created")
    return 201, _task_out(task, request.user)


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
# LEAD ATTACHMENTS  (backed by Document + Activity)
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


def _attachment_out(doc: Document) -> dict:
    return {
        "id": str(doc.id),
        "lead_id": str(doc.lead_id),
        "firm_id": str(doc.firm_id),
        "uploaded_by_id": str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
        "original_filename": doc.name,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "url": doc.file.url if doc.file.name else "",
        "created_at": doc.created_at,
    }


@router.get(
    "/opportunities/{lead_id}/attachments",
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
    docs = Document.objects.filter(lead=lead, firm=request.firm).order_by("-created_at")[
        offset: offset + page_size
    ]
    return 200, [_attachment_out(d) for d in docs]


@router.post(
    "/opportunities/{lead_id}/attachments",
    auth=django_auth,
    response={201: AttachmentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_attachment(request, lead_id: str, file: UploadedFile = File(...)):
    """
    Upload a file and attach it to a Lead.

    Creates a ``Document`` record and a ``FILE_UPLOAD`` Activity atomically.
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
        doc = Document(
            firm=request.firm,
            lead=lead,
            uploaded_by=request.user,
            name=file.name,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file.size,
        )
        doc.file.save(file.name, file, save=True)

        Activity.objects.create(
            lead=lead,
            user=request.user,
            type=ActivityType.FILE_UPLOAD,
            metadata={
                "document_id": str(doc.id),
                "filename": doc.name,
                "url": doc.file.url,
                "size_bytes": doc.size_bytes,
            },
        )

    return 201, _attachment_out(doc)


@router.delete(
    "/opportunities/{lead_id}/attachments/{attachment_id}",
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
        doc = Document.objects.get(id=attachment_id, lead=lead, firm=request.firm)
    except Document.DoesNotExist:
        return 404, {"detail": "Attachment not found."}

    doc.file.delete(save=False)
    doc.delete()
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
    ``Activity(type=status_change)`` records.  Results are cached for 5 minutes.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    cache_key = f"analytics:pipeline_velocity:{request.firm.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    # For each status, compute average dwell time:
    # dwell = time from entering a status until next transition (or now if current)
    status_hours: Dict[str, list] = {s.value: [] for s in LeadStatus}

    history_qs = (
        Activity.objects.filter(
            lead__firm=request.firm,
            type=ActivityType.STATUS_CHANGE,
            lead__isnull=False,
        )
        .values("lead_id", "metadata", "created_at")
        .order_by("lead_id", "created_at")
    )

    # Group by lead — each row is a status_change Activity with new_status in metadata
    lead_history: Dict[str, list] = {}
    for entry in history_qs:
        new_status = entry["metadata"].get("new_status") if isinstance(entry["metadata"], dict) else None
        if new_status:
            lead_history.setdefault(str(entry["lead_id"]), []).append(
                {"to_status": new_status, "changed_at": entry["created_at"]}
            )

    now = tz.now()
    for lead_id, entries in lead_history.items():
        for i, entry in enumerate(entries):
            status = entry["to_status"]
            entered_at = entry["changed_at"]
            left_at = entries[i + 1]["changed_at"] if i + 1 < len(entries) else now
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
# Phase 4.5 — Realization metrics
# ---------------------------------------------------------------------------

class RealizationStatusRow(Schema):
    status: str
    count: int
    avg_days: float


class RealizationTrendRow(Schema):
    week_start: str
    created: int
    completed: int


class RealizationMetricsOut(Schema):
    by_status: List[RealizationStatusRow]
    trend: List[RealizationTrendRow]
    total: int
    completed_total: int


@router.get(
    "/reports/realization-metrics",
    auth=django_auth,
    response={200: RealizationMetricsOut, 403: ErrorOut},
)
def realization_metrics(request):
    """
    Realization pipeline metrics: count by status, average days in each status,
    and a 12-week trend (created vs. completed).  Cached 5 minutes.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    from crm.models import Realization, RealizationStatus

    cache_key = f"analytics:realization_metrics:{request.firm.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    now = tz.now()
    qs = Realization.objects.filter(firm=request.firm)

    # Prefetch created_at and updated_at for all realizations once
    all_items = list(qs.only("id", "status", "created_at", "updated_at"))

    # Build per-status buckets
    from collections import defaultdict
    buckets: Dict[str, list] = defaultdict(list)
    for item in all_items:
        buckets[item.status].append(item)

    completed_statuses = {RealizationStatus.DONE.value, RealizationStatus.CANCELLED.value}

    # Count and average days per status
    status_rows = []
    for s in RealizationStatus:
        items_in_status = buckets.get(s.value, [])
        count = len(items_in_status)
        if count == 0:
            avg_days = 0.0
        elif s.value in completed_statuses:
            # avg time from creation to last update (approximation for completed duration)
            total_days = sum(
                (item.updated_at - item.created_at).total_seconds() / 86400
                for item in items_in_status
            )
            avg_days = total_days / count
        else:
            # Active: time since creation until now
            total_days = sum(
                (now - item.created_at).total_seconds() / 86400
                for item in items_in_status
            )
            avg_days = total_days / count
        status_rows.append({"status": s.value, "count": count, "avg_days": round(avg_days, 1)})

    # 12-week trend
    twelve_weeks_ago = now - dt.timedelta(weeks=12)
    trend = []
    for week in range(12):
        week_start = twelve_weeks_ago + dt.timedelta(weeks=week)
        week_end = week_start + dt.timedelta(weeks=1)
        created = qs.filter(created_at__gte=week_start, created_at__lt=week_end).count()
        completed = qs.filter(
            status=RealizationStatus.DONE,
            updated_at__gte=week_start,
            updated_at__lt=week_end,
        ).count()
        trend.append({
            "week_start": week_start.date().isoformat(),
            "created": created,
            "completed": completed,
        })

    total = qs.count()
    completed_total = qs.filter(status=RealizationStatus.DONE).count()

    result = {
        "by_status": status_rows,
        "trend": trend,
        "total": total,
        "completed_total": completed_total,
    }
    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Phase 4.5 — SLA compliance
# ---------------------------------------------------------------------------

class SlaComplianceOut(Schema):
    total: int
    green: int    # expires_at > now + 7 days (or no expiry)
    yellow: int   # expires_at in next 7 days
    red: int      # already expired
    no_expiry: int


@router.get(
    "/reports/sla-compliance",
    auth=django_auth,
    response={200: SlaComplianceOut, 403: ErrorOut},
)
def sla_compliance(request):
    """
    SLA compliance summary for Management records in the active firm.
    Green = > 7 days remaining, Yellow = 1–7 days, Red = expired.
    Cached 5 minutes.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    from crm.models import Management, ManagementStatus

    cache_key = f"analytics:sla_compliance:{request.firm.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return 200, cached

    now = tz.now()
    seven_days = now + dt.timedelta(days=7)

    qs = Management.objects.filter(firm=request.firm).exclude(status=ManagementStatus.CLOSED)

    total = qs.count()
    no_expiry = qs.filter(expires_at__isnull=True).count()
    with_expiry = qs.filter(expires_at__isnull=False)

    red = with_expiry.filter(expires_at__lt=now).count()
    yellow = with_expiry.filter(expires_at__gte=now, expires_at__lte=seven_days).count()
    green = with_expiry.filter(expires_at__gt=seven_days).count()

    result = {
        "total": total,
        "green": green,
        "yellow": yellow,
        "red": red,
        "no_expiry": no_expiry,
    }
    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Phase 4.5 — Profitability report
# ---------------------------------------------------------------------------

class ProfitabilityRow(Schema):
    entity_id: str
    entity_type: str   # "realization" | "lead" | "customer"
    entity_title: str
    total_minutes: int
    total_expenses: float
    total_revenues: float
    profit_loss: float


class ProfitabilityOut(Schema):
    rows: List[ProfitabilityRow]
    totals: ProfitabilityRow


@router.get(
    "/reports/profitability",
    auth=django_auth,
    response={200: ProfitabilityOut, 403: ErrorOut},
)
def profitability_report(
    request,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
):
    """
    Profitability breakdown per Realization (and top-level per Lead / Customer
    where no Realization exists).  Aggregates TimeEntry, ExpenseItem and
    RevenueItem data.  Results are NOT cached (supports date filters).
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    from crm.models import Realization, TimeEntry, ExpenseItem, RevenueItem

    firm = request.firm

    def _filter_dates(qs, date_field_prefix=""):
        if date_from:
            qs = qs.filter(**{f"{date_field_prefix}__gte": date_from})
        if date_to:
            qs = qs.filter(**{f"{date_field_prefix}__lte": date_to})
        return qs

    # Aggregate per realization
    realizationqs = Realization.objects.filter(firm=firm).order_by("-created_at")[:50]
    rows = []

    for r in realizationqs:
        te = TimeEntry.objects.filter(firm=firm, realization=r)
        ex = ExpenseItem.objects.filter(firm=firm, realization=r)
        rev = RevenueItem.objects.filter(firm=firm, realization=r)

        if date_from:
            te = te.filter(started_at__date__gte=date_from)
            ex = ex.filter(date__gte=date_from)
            rev = rev.filter(date__gte=date_from)
        if date_to:
            te = te.filter(started_at__date__lte=date_to)
            ex = ex.filter(date__lte=date_to)
            rev = rev.filter(date__lte=date_to)

        mins = te.aggregate(s=Sum("duration_minutes"))["s"] or 0
        expenses = float(ex.aggregate(s=Sum("amount"))["s"] or 0)
        revenues = float(rev.aggregate(s=Sum("amount"))["s"] or 0)

        rows.append({
            "entity_id": str(r.id),
            "entity_type": "realization",
            "entity_title": r.title,
            "total_minutes": mins,
            "total_expenses": expenses,
            "total_revenues": revenues,
            "profit_loss": revenues - expenses,
        })

    # Totals
    all_te = TimeEntry.objects.filter(firm=firm)
    all_ex = ExpenseItem.objects.filter(firm=firm)
    all_rev = RevenueItem.objects.filter(firm=firm)

    if date_from:
        all_te = all_te.filter(started_at__date__gte=date_from)
        all_ex = all_ex.filter(date__gte=date_from)
        all_rev = all_rev.filter(date__gte=date_from)
    if date_to:
        all_te = all_te.filter(started_at__date__lte=date_to)
        all_ex = all_ex.filter(date__lte=date_to)
        all_rev = all_rev.filter(date__lte=date_to)

    total_mins = all_te.aggregate(s=Sum("duration_minutes"))["s"] or 0
    total_expenses = float(all_ex.aggregate(s=Sum("amount"))["s"] or 0)
    total_revenues = float(all_rev.aggregate(s=Sum("amount"))["s"] or 0)

    totals = {
        "entity_id": "total",
        "entity_type": "total",
        "entity_title": "Total",
        "total_minutes": total_mins,
        "total_expenses": total_expenses,
        "total_revenues": total_revenues,
        "profit_loss": total_revenues - total_expenses,
    }

    return 200, {"rows": rows, "totals": totals}


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


# ===========================================================================
# PHASE 8 — Custom Fields
# ===========================================================================

class TaskCustomFieldOut(Schema):
    id: str
    firm_id: str
    name: str
    field_type: str
    options: List[str]
    is_required: bool
    position: int
    created_at: datetime


class TaskCustomFieldIn(Schema):
    name: str
    field_type: str = "text"
    options: List[str] = []
    is_required: bool = False
    position: int = 0


class TaskCustomFieldUpdateIn(Schema):
    name: Optional[str] = None
    field_type: Optional[str] = None
    options: Optional[List[str]] = None
    is_required: Optional[bool] = None
    position: Optional[int] = None


class TaskCustomFieldValueIn(Schema):
    field_id: str
    value_text: Optional[str] = None
    value_number: Optional[float] = None
    value_date: Optional[str] = None
    value_bool: Optional[bool] = None


class TaskCustomFieldValueBulkIn(Schema):
    values: List[TaskCustomFieldValueIn]


def _custom_field_out(cf: TaskCustomField) -> dict:
    return {
        "id": str(cf.id),
        "firm_id": str(cf.firm_id),
        "name": cf.name,
        "field_type": cf.field_type,
        "options": cf.options if isinstance(cf.options, list) else [],
        "is_required": cf.is_required,
        "position": cf.position,
        "created_at": cf.created_at,
    }


@router.get(
    "/custom-fields",
    auth=django_auth,
    response={200: List[TaskCustomFieldOut], 403: ErrorOut},
)
def list_custom_fields(request):
    """List all custom field definitions for the current firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}
    qs = TaskCustomField.objects.filter(firm=request.firm).order_by("position", "name")
    return 200, [_custom_field_out(cf) for cf in qs]


@router.post(
    "/custom-fields",
    auth=django_auth,
    response={201: TaskCustomFieldOut, 400: ErrorOut, 403: ErrorOut},
)
def create_custom_field(request, payload: TaskCustomFieldIn):
    """Create a new custom field definition (admin/owner only)."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    valid_types = [c[0] for c in TaskCustomFieldType.choices]
    if payload.field_type not in valid_types:
        return 400, {"detail": f"Invalid field_type '{payload.field_type}'. Must be one of: {valid_types}"}

    cf = TaskCustomField.objects.create(
        firm=request.firm,
        name=payload.name,
        field_type=payload.field_type,
        options=payload.options,
        is_required=payload.is_required,
        position=payload.position,
    )
    return 201, _custom_field_out(cf)


@router.patch(
    "/custom-fields/{field_id}",
    auth=django_auth,
    response={200: TaskCustomFieldOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_custom_field(request, field_id: str, payload: TaskCustomFieldUpdateIn):
    """Update a custom field definition (admin/owner only)."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        cf = TaskCustomField.objects.get(id=field_id, firm=request.firm)
    except TaskCustomField.DoesNotExist:
        return 404, {"detail": "Custom field not found."}

    if payload.name is not None:
        cf.name = payload.name
    if payload.field_type is not None:
        valid_types = [c[0] for c in TaskCustomFieldType.choices]
        if payload.field_type not in valid_types:
            return 400, {"detail": f"Invalid field_type '{payload.field_type}'."}
        cf.field_type = payload.field_type
    if payload.options is not None:
        cf.options = payload.options
    if payload.is_required is not None:
        cf.is_required = payload.is_required
    if payload.position is not None:
        cf.position = payload.position
    cf.save()
    return 200, _custom_field_out(cf)


@router.delete(
    "/custom-fields/{field_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_custom_field(request, field_id: str):
    """Delete a custom field definition and all its values (admin/owner only)."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        cf = TaskCustomField.objects.get(id=field_id, firm=request.firm)
    except TaskCustomField.DoesNotExist:
        return 404, {"detail": "Custom field not found."}

    cf.delete()
    return 204, None


@router.patch(
    "/tasks/{task_id}/custom-fields",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upsert_task_custom_fields(request, task_id: str, payload: TaskCustomFieldValueBulkIn):
    """Bulk-upsert custom field values for a task."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    for item in payload.values:
        try:
            cf = TaskCustomField.objects.get(id=item.field_id, firm=request.firm)
        except TaskCustomField.DoesNotExist:
            return 400, {"detail": f"Custom field {item.field_id} not found."}

        defaults: dict = {}
        if cf.field_type in ("text", "dropdown", "url"):
            defaults["value_text"] = item.value_text or ""
        elif cf.field_type == "number":
            defaults["value_number"] = item.value_number
        elif cf.field_type == "date":
            from django.utils.dateparse import parse_date
            defaults["value_date"] = parse_date(item.value_date) if item.value_date else None
        elif cf.field_type == "checkbox":
            defaults["value_bool"] = item.value_bool

        TaskCustomFieldValue.objects.update_or_create(
            task=task,
            field=cf,
            defaults=defaults,
        )

    return 200, _task_out(task, request.user)

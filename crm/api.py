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
from typing import Any, Dict, List, NamedTuple, Optional

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
    Category,
    CategoryField,
    Checkpoint,
    ContactType,
    Customer,
    DashboardLayout,
    Document,
    PipelineRecord,
    LeadScoringRule,
    RecordSource,
    RecordStatus,
    Notification,
    Project,
    Proposal,
    SavedView,
    Stage,
    Task,
    StreamlineItem,
    StreamlineItemKind,
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
from crm.soft_delete import perform_soft_delete

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

    perform_soft_delete(customer, request.user)
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

class RecordOut(Schema):
    id: str
    firm_id: str
    customer_id: Optional[str]
    title: str
    status: str
    source: str
    assigned_to_id: Optional[str]
    assigned_to_name: Optional[str] = None
    value: Optional[Decimal]
    currency: str
    score: Optional[int]
    created_at: datetime
    updated_at: datetime
    created_by_id: Optional[str]
    created_by_name: Optional[str]
    # Company & contact person from address book
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    contact_person_id: Optional[str] = None
    contact_person_name: Optional[str] = None
    # Pipeline category & stage
    category_id: Optional[str] = None
    current_stage_id: Optional[str] = None
    current_stage_name: Optional[str] = None
    parent_id: Optional[str] = None
    # Date fields
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    expires_at: Optional[datetime] = None
    notes: str = ""
    extra_data: Dict[str, Any] = {}


class RecordIn(Schema):
    title: str
    customer_id: Optional[str] = None
    status: str = RecordStatus.NEW
    source: str = RecordSource.WEB
    assigned_to_id: Optional[str] = None
    value: Optional[Decimal] = None
    currency: str = "CZK"
    company_id: Optional[str] = None
    contact_person_id: Optional[str] = None
    category_id: Optional[str] = None
    current_stage_id: Optional[str] = None
    parent_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    expires_at: Optional[datetime] = None
    notes: str = ""
    extra_data: Dict[str, Any] = {}


class RecordUpdateIn(Schema):
    title: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    assigned_to_id: Optional[str] = None
    value: Optional[Decimal] = None
    currency: Optional[str] = None
    customer_id: Optional[str] = None
    company_id: Optional[str] = None
    contact_person_id: Optional[str] = None
    category_id: Optional[str] = None
    current_stage_id: Optional[str] = None
    parent_id: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


def _validate_record_field_rules(
    category_id,
    value=None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
) -> Optional[str]:
    """
    Validate record field values against the CategoryField.validation_rules
    configured for the record's category.

    Returns an error string on failure, or None if everything is valid.

    Supported rule keys per field_key
    -----------------------------------
    value_currency : min / max  (numeric bounds on the record value)
    notes          : pattern    (full-match regex on the notes text)
    source         : options    (allowed values list)
    """
    import re

    if not category_id:
        return None

    fields_qs = CategoryField.objects.filter(category_id=category_id).values(
        "field_key", "validation_rules"
    )
    rules_by_key: Dict[str, Any] = {
        row["field_key"]: (row["validation_rules"] or {}) for row in fields_qs
    }

    # --- value_currency: min/max ---
    if value is not None and "value_currency" in rules_by_key:
        rules = rules_by_key["value_currency"]
        try:
            fval = float(value)
            if "min" in rules and fval < float(rules["min"]):
                return f"Value must be at least {rules['min']}."
            if "max" in rules and fval > float(rules["max"]):
                return f"Value must be at most {rules['max']}."
        except (TypeError, ValueError):
            pass  # non-numeric value handled by model / other validators

    # --- notes: pattern (regex) ---
    if notes is not None and notes and "notes" in rules_by_key:
        rules = rules_by_key["notes"]
        pattern = rules.get("pattern")
        if pattern:
            try:
                if not re.fullmatch(pattern, notes):
                    return "Notes does not match the required pattern."
            except re.error:
                pass  # invalid regex in config — skip silently

    # --- source: options (select) ---
    if source is not None and "source" in rules_by_key:
        rules = rules_by_key["source"]
        options = rules.get("options")
        if isinstance(options, list) and len(options) > 0 and source not in options:
            return f"Source must be one of: {', '.join(str(o) for o in options)}."

    return None


def _compute_record_score(lead: PipelineRecord, rules: list) -> int:
    """
    Compute a 0–100 record score by evaluating each scoring rule against
    the record.  Rules are pre-fetched by the caller to avoid N+1 queries.

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
                Activity.objects.filter(record=lead)
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


def _record_out(lead: PipelineRecord, rules: Optional[list] = None) -> dict:
    score = _compute_record_score(lead, rules) if rules is not None else None
    created_by_name: Optional[str] = None
    if lead.created_by_id:
        try:
            cb = lead.created_by
            created_by_name = f"{cb.first_name} {cb.last_name}".strip() or cb.email
        except Exception as exc:
            logger.debug("Could not resolve created_by name for lead %s: %s", lead.id, exc)
    assigned_to_name: Optional[str] = None
    if lead.assigned_to_id:
        try:
            at = lead.assigned_to
            assigned_to_name = f"{at.first_name} {at.last_name}".strip() or at.email
        except Exception as exc:
            logger.debug("Could not resolve assigned_to name for lead %s: %s", lead.id, exc)
    # Company & contact person
    company_id = str(lead.company_id) if lead.company_id else None
    company_name: Optional[str] = None
    contact_person_id = str(lead.contact_person_id) if lead.contact_person_id else None
    contact_person_name: Optional[str] = None
    if lead.company_id:
        try:
            co = lead.company
            company_name = co.company_name or f"{co.first_name} {co.last_name}".strip()
        except Exception:
            pass
    if lead.contact_person_id:
        try:
            cp = lead.contact_person
            contact_person_name = f"{cp.first_name} {cp.last_name}".strip() or cp.email
        except Exception:
            pass
    # Resolve current_stage name
    current_stage_name: Optional[str] = None
    if lead.current_stage_id:
        try:
            current_stage_name = lead.current_stage.name
        except Exception:
            pass
    return {
        "id": str(lead.id),
        "firm_id": str(lead.firm_id),
        "customer_id": str(lead.customer_id) if lead.customer_id else None,
        "title": lead.title,
        "status": lead.status,
        "source": lead.source,
        "assigned_to_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
        "assigned_to_name": assigned_to_name,
        "value": lead.value,
        "currency": lead.currency,
        "score": score,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
        "created_by_id": str(lead.created_by_id) if lead.created_by_id else None,
        "created_by_name": created_by_name,
        "company_id": company_id,
        "company_name": company_name,
        "contact_person_id": contact_person_id,
        "contact_person_name": contact_person_name,
        # Pipeline fields
        "category_id": str(lead.category_id) if lead.category_id else None,
        "current_stage_id": str(lead.current_stage_id) if lead.current_stage_id else None,
        "current_stage_name": current_stage_name,
        "parent_id": str(lead.parent_id) if lead.parent_id else None,
        "start_date": lead.start_date.isoformat() if lead.start_date else None,
        "end_date": lead.end_date.isoformat() if lead.end_date else None,
        "expires_at": lead.expires_at,
        "notes": lead.notes or "",
        "extra_data": lead.extra_data or {},
    }


def _build_record_automation_context(lead: PipelineRecord, firm) -> dict:
    """Build the evaluation context dict for automation rules fired from a Record event."""
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

    lead_id = str(task.record_id) if task.record_id else ""
    lead_title = ""
    customer_name = ""
    customer_email = ""

    if task.record_id:
        try:
            lead = task.record
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




@router.get("/records/counts-by-category", auth=django_auth, response={200: dict, 403: ErrorOut})
def records_counts_by_category(request):
    """Return active record counts per category for the current firm.

    Returns a mapping of ``{category_id: count}`` for records that are not in a
    terminal state (won/lost/canceled).  Records with no category assigned are
    omitted from the response.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    from django.db.models import Count as DjCount
    qs = (
        PipelineRecord.objects.filter(firm=request.firm)
        .exclude(status__in=["won", "lost", "canceled"])
        .exclude(category_id__isnull=True)
        .values("category_id")
        .annotate(count=DjCount("id"))
    )
    counts: dict = {}
    for row in qs:
        counts[str(row["category_id"])] = row["count"]
    return 200, counts


@router.get("/records", auth=django_auth, response={200: List[RecordOut], 403: ErrorOut})
def list_records(
    request,
    status: str = "",
    assigned_to: str = "",
    created_by: str = "",
    source: str = "",
    tag: str = "",
    category_id: str = "",
    stage_id: str = "",
    customer_id: str = "",
    parent_id: str = "",
    value_min: Optional[Decimal] = None,
    value_max: Optional[Decimal] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = PipelineRecord.objects.filter(firm=request.firm)
    if status:
        qs = qs.filter(status=status)
    if assigned_to:
        qs = qs.filter(assigned_to_id=assigned_to)
    if created_by:
        qs = qs.filter(created_by_id=created_by)
    if source:
        qs = qs.filter(source=source)
    if tag:
        qs = qs.filter(customer__tags__icontains=tag)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if stage_id:
        qs = qs.filter(current_stage_id=stage_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if parent_id:
        qs = qs.filter(parent_id=parent_id)
    if value_min is not None:
        qs = qs.filter(value__gte=value_min)
    if value_max is not None:
        qs = qs.filter(value__lte=value_max)
    if created_after:
        qs = qs.filter(created_at__gte=created_after)
    if created_before:
        qs = qs.filter(created_at__lte=created_before)
    # Sorting
    _allowed_sort_fields = {'title', 'status', 'source', 'value', 'created_at', 'updated_at'}
    order_field = sort_by if sort_by in _allowed_sort_fields else 'created_at'
    if sort_dir == 'asc':
        qs = qs.order_by(order_field)
    else:
        qs = qs.order_by(f'-{order_field}')
    offset = (page - 1) * page_size
    leads = list(qs.select_related('created_by', 'assigned_to', 'current_stage')[offset:offset + page_size])
    rules = list(LeadScoringRule.objects.filter(firm=request.firm))
    return 200, [_record_out(lead, rules) for lead in leads]


@router.post("/records", auth=django_auth, response={201: RecordOut, 400: ErrorOut, 402: ErrorOut, 403: ErrorOut})
def create_record(request, payload: RecordIn):
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

    company = None
    if payload.company_id:
        try:
            company = Customer.objects.get(id=payload.company_id, firm=request.firm, type="company")
        except Customer.DoesNotExist:
            return 400, {"detail": "Company not found in this Firm."}

    contact_person = None
    if payload.contact_person_id:
        try:
            contact_person = Customer.objects.get(id=payload.contact_person_id, firm=request.firm)
        except Customer.DoesNotExist:
            return 400, {"detail": "Contact person not found in this Firm."}

    assigned_to = None
    if payload.assigned_to_id:
        from users.models import User
        try:
            assigned_to = User.objects.get(id=payload.assigned_to_id)
            if not Membership.objects.filter(user=assigned_to, firm=request.firm).exists():
                return 400, {"detail": "Assigned user is not a member of this Firm."}
        except User.DoesNotExist:
            return 400, {"detail": "Assigned user not found."}

    category = None
    if payload.category_id:
        try:
            category = Category.objects.get(id=payload.category_id, firm=request.firm)
        except Category.DoesNotExist:
            return 400, {"detail": "Category not found in this Firm."}

    current_stage = None
    if payload.current_stage_id:
        try:
            current_stage = Stage.objects.get(id=payload.current_stage_id)
            if category and current_stage.category_id != category.id:
                return 400, {"detail": "Stage does not belong to the specified category."}
        except Stage.DoesNotExist:
            return 400, {"detail": "Stage not found."}

    parent = None
    if payload.parent_id:
        try:
            parent = PipelineRecord.objects.get(id=payload.parent_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return 400, {"detail": "Parent record not found."}

    start_date = None
    if payload.start_date:
        try:
            start_date = dt.date.fromisoformat(payload.start_date)
        except ValueError:
            return 400, {"detail": "Invalid start_date format. Use YYYY-MM-DD."}

    end_date = None
    if payload.end_date:
        try:
            end_date = dt.date.fromisoformat(payload.end_date)
        except ValueError:
            return 400, {"detail": "Invalid end_date format. Use YYYY-MM-DD."}

    lead = PipelineRecord.objects.create(
        firm=request.firm,
        customer=customer,
        company=company,
        contact_person=contact_person,
        assigned_to=assigned_to,
        title=payload.title,
        status=payload.status,
        source=payload.source,
        value=payload.value,
        currency=payload.currency,
        created_by=request.user,
        category=category,
        current_stage=current_stage,
        parent=parent,
        start_date=start_date,
        end_date=end_date,
        expires_at=payload.expires_at,
        notes=payload.notes,
        extra_data=payload.extra_data,
    )
    broadcast_event(firm=request.firm, event='record.created', payload=_record_out(lead))

    # Fire workflow automation trigger: record_created
    from crm.tasks import evaluate_automation_rules
    _automation_ctx = _build_record_automation_context(lead, request.firm)
    from django.db import transaction
    transaction.on_commit(
        lambda: evaluate_automation_rules.delay("record_created", str(request.firm.pk), _automation_ctx),
        robust=True,
    )

    return 201, _record_out(lead)


@router.get("/records/{record_id}", auth=django_auth, response={200: RecordOut, 403: ErrorOut, 404: ErrorOut})
def get_record(request, record_id: str):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.select_related('created_by').get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}
    return 200, _record_out(lead)


@router.patch("/records/{record_id}", auth=django_auth, response={200: RecordOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut})
def update_record(request, record_id: str, payload: RecordUpdateIn):
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    old_status = lead.status
    update_data = payload.dict(exclude_none=True)

    # Handle status change — create an Activity in the same transaction
    new_status = update_data.pop("status", None)

    # Resolve FK overrides (company, contact_person, customer, assigned_to)
    # These cannot be set via setattr(lead, "company_id", ...) reliably through
    # the loop below — we pop and resolve them explicitly.
    if "company_id" in update_data:
        cid = update_data.pop("company_id")
        if cid:
            try:
                lead.company = Customer.objects.get(id=cid, firm=request.firm, type="company")
            except Customer.DoesNotExist:
                return 400, {"detail": "Company not found."}
        else:
            lead.company = None

    if "contact_person_id" in update_data:
        cpid = update_data.pop("contact_person_id")
        if cpid:
            try:
                lead.contact_person = Customer.objects.get(id=cpid, firm=request.firm)
            except Customer.DoesNotExist:
                return 400, {"detail": "Contact person not found."}
        else:
            lead.contact_person = None

    if "customer_id" in update_data:
        cust_id = update_data.pop("customer_id")
        if cust_id:
            try:
                lead.customer = Customer.objects.get(id=cust_id, firm=request.firm)
            except Customer.DoesNotExist:
                return 400, {"detail": "Customer not found."}
        else:
            lead.customer = None

    if "category_id" in update_data:
        cat_id = update_data.pop("category_id")
        if cat_id:
            try:
                lead.category = Category.objects.get(id=cat_id, firm=request.firm)
            except Category.DoesNotExist:
                return 400, {"detail": "Category not found."}
        else:
            lead.category = None

    if "current_stage_id" in update_data:
        stage_id = update_data.pop("current_stage_id")
        if stage_id:
            try:
                stage = Stage.objects.get(id=stage_id)
                if lead.category_id and stage.category_id != lead.category_id:
                    return 400, {"detail": "Stage does not belong to the record's category."}
                lead.current_stage = stage
            except Stage.DoesNotExist:
                return 400, {"detail": "Stage not found."}
        else:
            lead.current_stage = None

    if "parent_id" in update_data:
        par_id = update_data.pop("parent_id")
        if par_id:
            try:
                lead.parent = PipelineRecord.objects.get(id=par_id, firm=request.firm)
            except PipelineRecord.DoesNotExist:
                return 400, {"detail": "Parent record not found."}
        else:
            lead.parent = None

    if "start_date" in update_data:
        sd = update_data.pop("start_date")
        if sd:
            try:
                lead.start_date = dt.date.fromisoformat(sd)
            except ValueError:
                return 400, {"detail": "Invalid start_date format. Use YYYY-MM-DD."}
        else:
            lead.start_date = None

    if "end_date" in update_data:
        ed = update_data.pop("end_date")
        if ed:
            try:
                lead.end_date = dt.date.fromisoformat(ed)
            except ValueError:
                return 400, {"detail": "Invalid end_date format. Use YYYY-MM-DD."}
        else:
            lead.end_date = None

    # Validate field values against CategoryField.validation_rules
    validation_err = _validate_record_field_rules(
        category_id=lead.category_id,
        value=update_data.get("value"),
        notes=update_data.get("notes"),
        source=update_data.get("source"),
    )
    if validation_err:
        return 400, {"detail": validation_err}

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
                    record=lead,
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
                    **_build_record_automation_context(lead, request.firm),
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

    broadcast_event(firm=request.firm, event='record.updated', payload=_record_out(lead))
    return 200, _record_out(lead)


@router.delete("/records/{record_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def delete_record(request, record_id: str):
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    perform_soft_delete(lead, request.user)
    broadcast_event(firm=request.firm, event='record.deleted', payload={'id': record_id})
    return 204, None


# ===========================================================================
# CHECKPOINTS
# ===========================================================================

class CheckpointOut(Schema):
    id: str
    record_id: str
    name: str
    date: Optional[str]
    is_completed: bool
    description: str
    created_at: str


class CheckpointIn(Schema):
    name: str
    date: Optional[str] = None
    is_completed: bool = False
    description: str = ""


class CheckpointUpdateIn(Schema):
    name: Optional[str] = None
    date: Optional[str] = None
    is_completed: Optional[bool] = None
    description: Optional[str] = None


def _checkpoint_out(cp: Checkpoint) -> dict:
    return {
        "id": str(cp.id),
        "record_id": str(cp.record_id),
        "name": cp.name,
        "date": cp.date.isoformat() if cp.date else None,
        "is_completed": cp.is_completed,
        "description": cp.description,
        "created_at": cp.created_at.isoformat(),
    }


@router.get(
    "/records/{record_id}/checkpoints",
    auth=django_auth,
    response={200: List[CheckpointOut], 403: ErrorOut, 404: ErrorOut},
)
def list_checkpoints(request, record_id: str):
    """List all checkpoints for a record, ordered by date then name."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    checkpoints = Checkpoint.objects.filter(record=lead).order_by("date", "name")
    return 200, [_checkpoint_out(cp) for cp in checkpoints]


@router.post(
    "/records/{record_id}/checkpoints",
    auth=django_auth,
    response={201: CheckpointOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_checkpoint(request, record_id: str, payload: CheckpointIn):
    """Create a checkpoint for a record."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    date = None
    if payload.date:
        try:
            date = dt.date.fromisoformat(payload.date)
        except ValueError:
            return 400, {"detail": "Invalid date format. Use YYYY-MM-DD."}

    cp = Checkpoint.objects.create(
        record=lead,
        name=payload.name,
        date=date,
        is_completed=payload.is_completed,
        description=payload.description,
    )
    return 201, _checkpoint_out(cp)


@router.patch(
    "/records/{record_id}/checkpoints/{checkpoint_id}",
    auth=django_auth,
    response={200: CheckpointOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_checkpoint(request, record_id: str, checkpoint_id: str, payload: CheckpointUpdateIn):
    """Update a checkpoint."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        cp = Checkpoint.objects.get(id=checkpoint_id, record=lead)
    except Checkpoint.DoesNotExist:
        return 404, {"detail": "Checkpoint not found."}

    update_data = payload.dict(exclude_none=True)
    if "date" in update_data:
        d = update_data.pop("date")
        if d:
            try:
                cp.date = dt.date.fromisoformat(d)
            except ValueError:
                return 400, {"detail": "Invalid date format. Use YYYY-MM-DD."}
        else:
            cp.date = None

    for field, value in update_data.items():
        setattr(cp, field, value)
    cp.save()
    return 200, _checkpoint_out(cp)


@router.delete(
    "/records/{record_id}/checkpoints/{checkpoint_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_checkpoint(request, record_id: str, checkpoint_id: str):
    """Delete a checkpoint."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        cp = Checkpoint.objects.get(id=checkpoint_id, record=lead)
    except Checkpoint.DoesNotExist:
        return 404, {"detail": "Checkpoint not found."}

    perform_soft_delete(cp, request.user)
    return 204, None

class ActivityOut(Schema):
    id: str
    entity_type: str
    entity_id: str
    # Kept for backwards-compatibility
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
    # Calendar / Task unification
    task_id: Optional[str] = None
    # Soft-delete tombstone
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by_name: Optional[str] = None
    # Edit tracking
    is_edited: bool = False
    edited_at: Optional[datetime] = None

class ActivityUpdateIn(Schema):
    content_text: str = ""
    metadata: Optional[Dict[str, Any]] = None


class ActivityIn(Schema):
    # Exactly one of the entity IDs must be provided.
    record_id: Optional[str] = None
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
        "lead_id": str(a.record_id) if a.record_id else None,
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
        "task_id": str(a.task_id) if a.task_id else None,
        "is_deleted": a.is_deleted,
        "deleted_at": a.deleted_at,
        "deleted_by_name": _user_display_name(a.deleted_by) if a.deleted_by_id else None,
        "is_edited": a.is_edited,
        "edited_at": a.edited_at,
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
        lead = PipelineRecord.objects.get(id=lead_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(record=lead).select_related('user').prefetch_related('reactions').order_by("-created_at")[offset:offset + page_size]
    return 200, [_activity_out(a, request.user) for a in activities]


# ---------------------------------------------------------------------------
# Unified feed — Activities + Tasks merged into one chronological timeline
# ---------------------------------------------------------------------------

class FeedItemOut(Schema):
    """
    A single item in the unified entity feed.

    ``item_type`` distinguishes between an Activity record (``"activity"``)
    and a Task record (``"task"``).  The ``activity`` / ``task`` fields are
    mutually exclusive — exactly one is populated.
    """
    item_type: str   # "activity" | "task"
    created_at: datetime
    activity: Optional[Dict[str, Any]] = None
    task: Optional[Dict[str, Any]] = None


def _feed_item_from_activity(a: "Activity", requesting_user=None) -> dict:
    return {
        "item_type": "activity",
        "created_at": a.created_at,
        "activity": _activity_out(a, requesting_user),
        "task": None,
    }


def _feed_item_from_task(t: "Task", requesting_user=None) -> dict:
    return {
        "item_type": "task",
        "created_at": t.created_at,
        "activity": None,
        "task": _task_out(t, requesting_user),
    }


@router.get(
    "/records/{record_id}/feed",
    auth=django_auth,
    response={200: List[FeedItemOut], 403: ErrorOut, 404: ErrorOut},
)
def get_record_feed(request, record_id: str, page: int = 1, page_size: int = 20):
    """
    Unified chronological feed for a Lead — merges Activities and Tasks into
    one list sorted by ``created_at`` descending.

    Activities are the standard Streamline records (comments, calls, emails,
    file uploads, etc.).  Tasks are surfaced as rich cards so the user can see
    and interact with them inline without leaving the Lead detail.

    Pagination works over the merged set — ``page_size`` items total per page.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    offset = (page - 1) * page_size

    # Fetch both sets — slightly over-fetch then merge & sort in Python.
    # For typical page sizes (20) this is negligible; for very active leads
    # with thousands of records a keyset-pagination approach would be better,
    # but that optimisation can be added later without breaking the contract.
    fetch_size = page_size * 2 + 10  # generous buffer for the merge window

    activities = list(
        Activity.objects.filter(record=lead)
        .select_related("user")
        .prefetch_related("reactions")
        .order_by("-created_at")[:offset + fetch_size]
    )
    tasks = list(
        Task.objects.filter(record=lead, is_archived=False)
        .select_related("assigned_to", "completed_by", "created_by")
        .order_by("-created_at")[:offset + fetch_size]
    )

    # Merge and sort
    feed: list[dict] = []
    for a in activities:
        feed.append(_feed_item_from_activity(a, request.user))
    for t in tasks:
        feed.append(_feed_item_from_task(t, request.user))

    feed.sort(key=lambda x: x["created_at"], reverse=True)

    # Apply pagination window
    page_items = feed[offset: offset + page_size]
    return 200, page_items


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
    from django.db.models import Q
    activities = Activity.objects.filter(
        Q(task=task) | Q(metadata__task_id=str(task.id))
    ).select_related('user').prefetch_related('reactions').order_by("-created_at")
    
    # Self-healing: if a task has no activities (e.g. created by old automation),
    # create a TASK_CREATED activity so the frontend can anchor reactions to it.
    if not activities.exists() and page == 1:
        from crm.models import ActivityType
        _log_timeline_event(task, ActivityType.TASK_CREATED, author=request.user)
        activities = Activity.objects.filter(task=task).select_related('user').prefetch_related('reactions').order_by("-created_at")

    page_items = activities[offset:offset + page_size]
    return 200, [_activity_out(a, request.user) for a in page_items]


@router.post("/activities", auth=django_auth, response={201: ActivityOut, 400: ErrorOut, 403: ErrorOut})
def create_activity(request, payload: ActivityIn):
    """
    Unified Action Hub endpoint — works for Record, Customer, and Proposal.

    Exactly one of ``record_id``, ``customer_id``,
    or ``proposal_id`` must be provided.  Dispatches to the registered ``StreamlineTool``
    for the given activity type, which handles all type-specific side-effects.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    # --- resolve entity ---
    if sum([bool(payload.record_id), bool(payload.customer_id), bool(payload.proposal_id), bool(payload.task_id)]) != 1:
        return 400, {"detail": "Exactly one of record_id, customer_id, proposal_id, task_id must be provided."}

    record = customer = proposal = task = None
    entity_title = ""

    if payload.record_id:
        try:
            record = PipelineRecord.objects.get(id=payload.record_id, firm=request.firm)
            entity_title = record.title
        except PipelineRecord.DoesNotExist:
            return 400, {"detail": "Record not found in this Firm."}
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

    entity = record or customer or proposal or task
    context = {
        "firm": request.firm,
        "user": request.user,
        "entity_title": entity_title,
    }

    with transaction.atomic():
        activity = Activity.objects.create(
            record=record,
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

    Works for activities attached to any entity (lead, customer,
    proposal, task).  If the requesting user has already reacted
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
    for related in (activity.record,
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


@router.delete(
    "/activities/{activity_id}",
    auth=django_auth,
    response={200: ActivityOut, 403: ErrorOut, 404: ErrorOut},
)
def delete_activity(request, activity_id: str):
    """
    Soft-delete an Activity.

    - The author (``activity.user``) can delete their own activities.
    - Admins and owners can delete any activity.

    The record is NOT removed from the database. Instead:
    - ``is_deleted = True``, ``deleted_at`` and ``deleted_by`` are set.
    - ``content_text`` and ``metadata`` are cleared so no sensitive content
      remains visible, but the tombstone entry stays in the timeline.

    The response returns the updated (tombstoned) ``ActivityOut`` so the
    frontend can replace the item in-place without a reload.
    """
    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        activity = Activity.objects.get(id=activity_id)
    except Activity.DoesNotExist:
        return 404, {"detail": "Activity not found."}

    # Permission: author or admin/owner
    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)
    is_author = activity.user_id and str(activity.user_id) == str(request.user.id)
    if not is_author and not is_admin:
        return 403, {"detail": "You can only delete your own activities."}

    if activity.is_deleted:
        return 200, _activity_out(activity, request.user)

    activity.is_deleted = True
    activity.deleted_at = tz.now()
    activity.deleted_by = request.user
    activity.content_text = ""
    activity.metadata = {}
    from django.conf import settings as _settings
    purge_days = getattr(_settings, "SOFT_DELETE_PURGE_DAYS", 30)
    activity.purge_after = activity.deleted_at + dt.timedelta(days=purge_days)
    activity.save(update_fields=["is_deleted", "deleted_at", "deleted_by", "content_text", "metadata", "purge_after"])

    broadcast_event(
        firm=request.firm,
        event="activity.deleted",
        payload={"id": str(activity.id), "entity_type": activity.entity_type, "entity_id": activity.entity_id},
    )
    return 200, _activity_out(activity, request.user)


@router.patch(
    "/activities/{activity_id}",
    auth=django_auth,
    response={200: ActivityOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_activity(request, activity_id: str, payload: ActivityUpdateIn):
    """
    Edit the content of a user-generated Activity.
    
    Only the original author can edit their own activity.
    Only specific types (COMMENT, CALL, MEETING) are allowed to be edited.
    System-generated activities are immutable.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        activity = Activity.objects.get(id=activity_id)
    except Activity.DoesNotExist:
        return 404, {"detail": "Activity not found."}

    # Must be the author
    if activity.user_id is None or str(activity.user_id) != str(request.user.id):
        return 403, {"detail": "Only the author can edit this activity."}

    # Must be an editable type
    from crm.models import ActivityType
    allowed_types = [ActivityType.COMMENT, ActivityType.CALL, ActivityType.MEETING, ActivityType.CHECKLIST]
    if activity.type not in allowed_types:
        return 400, {"detail": "This type of activity cannot be edited."}

    # Cannot edit deleted activities
    if activity.is_deleted:
        return 400, {"detail": "Cannot edit a deleted activity."}

    from django.utils import timezone as tz
    update_fields = ["is_edited", "edited_at"]

    if activity.type == ActivityType.CHECKLIST:
        # For checklist, re-parse the text into items and update metadata
        if payload.metadata is not None:
            from crm.streamline.tools import _parse_checklist_text, _items_to_edit_text
            meta = dict(activity.metadata or {})
            title = payload.metadata.get("title", meta.get("title", ""))
            raw_text = payload.metadata.get("text", "")
            items = _parse_checklist_text(raw_text)
            edit_text = _items_to_edit_text(items)
            meta.update({"title": title, "items": items, "text": edit_text})
            activity.metadata = meta
            update_fields.append("metadata")
    else:
        activity.content_text = payload.content_text
        update_fields.append("content_text")

    activity.is_edited = True
    activity.edited_at = tz.now()
    activity.save(update_fields=update_fields)

    # We do not broadcast event for edits right now, frontend relies on page reload or 
    # the request response updating the local cache.

    return 200, _activity_out(activity, request.user)


@router.post(
    "/activities/{activity_id}/checklist-items/{item_index}/toggle",
    auth=django_auth,
    response={200: ActivityOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def toggle_checklist_item(request, activity_id: str, item_index: int):
    """
    Toggle the done/undone state of a single checklist item.

    Any authenticated firm member may toggle items (not just the activity author),
    because checklists are collaborative by nature.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        activity = Activity.objects.get(id=activity_id)
    except Activity.DoesNotExist:
        return 404, {"detail": "Activity not found."}

    from crm.models import ActivityType
    if activity.type != ActivityType.CHECKLIST:
        return 400, {"detail": "Activity is not a checklist."}

    if activity.is_deleted:
        return 400, {"detail": "Cannot modify a deleted activity."}

    meta = dict(activity.metadata or {})
    items = list(meta.get("items", []))
    if item_index < 0 or item_index >= len(items):
        return 400, {"detail": "Item index out of range."}

    items[item_index] = {**items[item_index], "done": not items[item_index].get("done", False)}
    from crm.streamline.tools import _items_to_edit_text
    meta["items"] = items
    meta["text"] = _items_to_edit_text(items)
    activity.metadata = meta
    activity.save(update_fields=["metadata"])

    return 200, _activity_out(activity, request.user)


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
    is_all_day: bool
    outcome_prompted_at: Optional[datetime]
    # Flags
    is_completed: bool
    completed_at: Optional[datetime]
    is_pinned: bool
    is_archived: bool
    is_favourite: bool
    created_at: datetime
    created_by_id: Optional[str]
    created_by_name: Optional[str]
    # Streamline item counters (replaces legacy checklist + subtask counters)
    streamline_count: int
    streamline_resolved: int
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
    if t.record_id:
        lead_id = str(t.record_id)
        try:
            lead_title = t.record.title
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

    # Resolve is_favourite for the requesting user
    is_favourite = False
    if requesting_user and requesting_user.is_authenticated:
        try:
            is_favourite = TaskFavourite.objects.filter(task=t, user=requesting_user).exists()
        except Exception:
            pass

    # Streamline item counters (replaces legacy checklist + subtask counters)
    try:
        streamline_qs = StreamlineItem.objects.filter(task=t)
        streamline_count = streamline_qs.count()
        streamline_resolved = streamline_qs.filter(is_resolved=True).count()
    except Exception:
        streamline_count = 0
        streamline_resolved = 0

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
        "proposal_id": proposal_id,
        "proposal_title": proposal_title,
        "customer_id": customer_id,
        "customer_name": customer_name,
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
        "is_all_day": t.is_all_day,
        "outcome_prompted_at": t.outcome_prompted_at,
        "is_completed": t.is_completed,
        "completed_at": t.completed_at,
        "is_pinned": t.is_pinned,
        "is_archived": t.is_archived,
        "is_favourite": is_favourite,
        "created_at": t.created_at,
        "created_by_id": str(t.created_by_id) if t.created_by_id else None,
        "created_by_name": created_by_name,
        "streamline_count": streamline_count,
        "streamline_resolved": streamline_resolved,
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


class CalendarTaskOut(Schema):
    """Lightweight calendar entry derived from a ``Task``.

    Returned by ``GET /calendar/tasks`` for rendering month/week/day views.
    Carries only what the calendar needs — full Task details remain
    available via ``GET /tasks/{id}``.
    """
    id: str
    title: str
    kind: str
    status: str
    priority: str
    is_completed: bool
    # Calendar slot — start = ``due_date``, end = ``due_date_end`` if set
    # otherwise the same as ``due_date`` (point-in-time event).
    start: datetime
    end: datetime
    location: str
    attendees: List[str]
    is_all_day: bool
    assigned_to_id: Optional[str]
    assigned_to_name: Optional[str]
    # Entity link for click-through; exactly one is populated.
    lead_id: Optional[str]
    lead_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    proposal_id: Optional[str]
    proposal_title: Optional[str]


def _calendar_task_out(t: Task) -> dict:
    """Serialize a ``Task`` as a calendar entry."""
    start = t.due_date
    end = t.due_date_end or t.due_date
    return {
        "id": str(t.id),
        "title": t.title,
        "kind": t.kind,
        "status": t.status,
        "priority": t.priority,
        "is_completed": bool(t.is_completed),
        "start": start,
        "end": end,
        "location": t.location or "",
        "attendees": list(t.attendees or []),
        "is_all_day": bool(t.is_all_day),
        "assigned_to_id": str(t.assigned_to_id) if t.assigned_to_id else None,
        "assigned_to_name": _user_display_name(t.assigned_to),
        "lead_id": str(t.record_id) if t.record_id else None,
        "lead_title": t.record.title if t.record_id else None,
        "customer_id": str(t.customer_id) if t.customer_id else None,
        "customer_name": (
            f"{t.customer.first_name or ''} {t.customer.last_name or ''}".strip()
            or t.customer.email
            or t.customer.company_name
            or None
        ) if t.customer_id else None,
        "proposal_id": str(t.proposal_id) if t.proposal_id else None,
        "proposal_title": getattr(t.proposal, "title", None) if t.proposal_id else None,
    }


# Hard cap on the number of entries returned in a single calendar query.
# Calendars typically render at most a few hundred items per view; cap
# protects against an accidental year-wide query melting the API.
_CALENDAR_MAX_RESULTS = 1000
# Maximum window the caller is allowed to request in a single call.
# Keeps DB scans bounded; SPA can page month-by-month if it needs more.
_CALENDAR_MAX_WINDOW_DAYS = 366


def _parse_iso_datetime(value: str, field_name: str):
    """Parse an ISO-8601 string supporting the ``Z`` suffix, returning
    a tuple ``(dt_or_none, error_response_or_none)``.
    """
    parsed = parse_datetime(value)
    if parsed is None:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None, (400, {"detail": f"Invalid {field_name} format: '{value}'. Use ISO-8601."})
    if tz.is_naive(parsed):
        parsed = tz.make_aware(parsed, tz.get_current_timezone())
    return parsed, None


@router.get(
    "/calendar/tasks",
    auth=django_auth,
    response={200: List[CalendarTaskOut], 400: ErrorOut, 403: ErrorOut},
)
def list_calendar_tasks(
    request,
    start: str,
    end: str,
    assigned_to_id: Optional[str] = None,
    kind: Optional[str] = None,
    status: Optional[str] = None,
    include_completed: bool = False,
    include_archived: bool = False,
):
    """
    Return tasks whose calendar slot overlaps the ``[start, end]`` window.

    A task overlaps the window when ``due_date <= end`` **and**
    ``coalesce(due_date_end, due_date) >= start``. Tasks without a
    ``due_date`` are not calendar events and are excluded.

    Scope (``assigned_to_id``):
      * omitted / ``"me"`` — tasks assigned to the current user
      * ``"watching"``     — tasks where the current user is in ``watchers``
      * ``"all"``          — all firm tasks (admin/owner only; workers
                              are silently narrowed to their own)
      * ``<uuid>``         — tasks assigned to that user (admin/owner can
                              query anyone; workers can only query themselves)

    By default ``status=expired`` and ``is_completed=True`` tasks are
    excluded; pass ``include_completed=true`` to bring them back in.
    Archived tasks are always excluded unless ``include_archived=true``.
    """
    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    start_dt, err = _parse_iso_datetime(start, "start")
    if err is not None:
        return err
    end_dt, err = _parse_iso_datetime(end, "end")
    if err is not None:
        return err

    if end_dt < start_dt:
        return 400, {"detail": "'end' must be greater than or equal to 'start'."}
    if (end_dt - start_dt) > dt.timedelta(days=_CALENDAR_MAX_WINDOW_DAYS):
        return 400, {
            "detail": (
                f"Requested window is too large; maximum is "
                f"{_CALENDAR_MAX_WINDOW_DAYS} days."
            )
        }

    is_admin = membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)

    qs = Task.objects.filter(firm=request.firm).select_related(
        "record", "customer", "proposal", "assigned_to",
    )

    # Window overlap: due_date <= end AND coalesce(due_date_end, due_date) >= start.
    qs = qs.filter(due_date__isnull=False, due_date__lte=end_dt).filter(
        Q(due_date_end__isnull=False, due_date_end__gte=start_dt)
        | Q(due_date_end__isnull=True, due_date__gte=start_dt)
    )

    # Scope filter.
    if assigned_to_id in (None, "", "me"):
        qs = qs.filter(assigned_to=request.user)
    elif assigned_to_id == "watching":
        qs = qs.filter(watchers=request.user)
    elif assigned_to_id == "all":
        if not is_admin:
            qs = qs.filter(assigned_to=request.user)
        # admins/owners: no extra filter
    else:
        # Specific UUID — workers can only ask about themselves.
        if not is_admin and str(request.user.id) != str(assigned_to_id):
            qs = qs.filter(assigned_to=request.user)
        else:
            qs = qs.filter(assigned_to_id=assigned_to_id)

    if kind is not None:
        qs = qs.filter(kind=kind)
    if status is not None:
        qs = qs.filter(status=status)
    if not include_completed:
        qs = qs.filter(is_completed=False).exclude(status=TaskStatus.EXPIRED)
    if not include_archived:
        qs = qs.filter(is_archived=False)

    qs = qs.order_by("due_date").distinct()[: _CALENDAR_MAX_RESULTS]
    return 200, [_calendar_task_out(t) for t in qs]


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
        "record", "assigned_to", "completed_by", "created_by", "proposal", "customer",
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
        qs = qs.filter(record_id=lead_id)
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
            lead = PipelineRecord.objects.get(id=payload.lead_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return 400, {"detail": "Record not found in this Firm."}

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
            record=lead,
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

        # Log activity on the linked entity (lead, customer, or proposal).
        # Mirrors the unified Streamline timeline contract: a TASK_ASSIGNED
        # event is emitted onto whichever entity owns the task so that the
        # entity's detail timeline shows it.
        primary_entity = lead or customer or proposal
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
                    record=lead,
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
        # Log Activity on every linked entity (lead, customer, proposal).
        completion_metadata = {"task_id": str(task.id), "title": task.title}
        if task.record_id:
            Activity.objects.create(
                record=task.record,
                user=request.user,
                type=ActivityType.TASK_COMPLETED,
                metadata=completion_metadata,
            )

        follow_up_task = None
        if follow_up_data:
            follow_up_lead = None
            if follow_up_data.lead_id:
                try:
                    follow_up_lead = PipelineRecord.objects.get(id=follow_up_data.lead_id, firm=request.firm)
                except PipelineRecord.DoesNotExist:
                    pass
            else:
                follow_up_lead = task.record

            follow_up_task = Task.objects.create(
                firm=request.firm,
                record=follow_up_lead,
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


@router.post("/tasks/{task_id}/reopen", auth=django_auth, response={200: TaskOut, 403: ErrorOut, 404: ErrorOut})
def reopen_task(request, task_id: str):
    """Mark a completed Task as not completed (reopen it)."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if not task.is_completed:
        return 200, _task_out(task, request.user)

    with transaction.atomic():
        task.is_completed = False
        task.completed_at = None
        task.completed_by = None
        task.status = TaskStatus.TODO
        task.save(update_fields=["is_completed", "completed_at", "completed_by", "status"])
        reopen_metadata = {"task_id": str(task.id), "title": task.title}
        if task.record_id:
            Activity.objects.create(
                record=task.record,
                user=request.user,
                type=ActivityType.TASK_REOPENED,
                metadata=reopen_metadata,
            )

    broadcast_event(firm=request.firm, event='task.updated', payload=_task_out(task, request.user))
    return 200, _task_out(task, request.user)


# ---------------------------------------------------------------------------
# Task detail (single task)
# ---------------------------------------------------------------------------

class TaskOutcomeIn(Schema):
    """Payload for ``POST /tasks/{id}/outcome``.

    The ``action`` discriminates between the three possible answers to the
    "what happened with this calendar task?" prompt:

    * ``held``        — the call/meeting took place; mark task DONE and log
                        a ``call``/``meeting`` Activity (kind-driven). Optional
                        ``note`` becomes the Activity content.
    * ``rescheduled`` — move the task to a new date; resets status to TODO
                        and re-opens the prompt window. Requires
                        ``new_due_date``.
    * ``no_show``     — the event did not happen and won't be rescheduled;
                        terminal ``EXPIRED`` status with ``outcome=no_show``
                        in the Activity metadata.
    """
    action: str
    note: str = ""
    new_due_date: Optional[datetime] = None
    new_due_date_end: Optional[datetime] = None


_TASK_OUTCOME_ACTIONS = {"held", "rescheduled", "no_show"}


@router.post(
    "/tasks/{task_id}/outcome",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def record_task_outcome(request, task_id: str, payload: TaskOutcomeIn):
    """Record the user's response to the calendar-task outcome prompt.

    Accepts one of three actions (``held`` / ``rescheduled`` / ``no_show``)
    and adjusts the Task + timeline accordingly. See :class:`TaskOutcomeIn`
    for semantics.

    Authorisation: any worker of the firm can record an outcome on any
    task they are allowed to see (mirrors ``complete_task``).
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if payload.action not in _TASK_OUTCOME_ACTIONS:
        return 400, {
            "detail": (
                f"Invalid action '{payload.action}'. "
                f"Expected one of: {sorted(_TASK_OUTCOME_ACTIONS)}."
            )
        }

    try:
        task = Task.objects.select_related(
            "record", "customer", "proposal",
        ).get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    if task.is_completed and payload.action != "rescheduled":
        # Already resolved — surface a 400 so the SPA can refresh state
        # rather than silently no-op (which would mask a stale prompt).
        return 400, {"detail": "Task is already completed."}

    note = (payload.note or "").strip()

    with transaction.atomic():
        if payload.action == "held":
            task.is_completed = True
            task.completed_at = tz.now()
            task.completed_by = request.user
            task.status = TaskStatus.DONE
            task.save(update_fields=["is_completed", "completed_at", "completed_by", "status"])

            # Map task kind → outcome Activity type. Generic / unknown
            # kinds fall back to TASK_COMPLETED so the timeline is still
            # truthful even if an automation set kind to something exotic.
            kind_to_activity = {
                "call": ActivityType.CALL,
                "meeting": ActivityType.MEETING,
            }
            outcome_type = kind_to_activity.get(task.kind, ActivityType.TASK_COMPLETED)
            outcome_metadata = {
                "task_id": str(task.id),
                "task_title": task.title,
                "task_kind": task.kind,
                "outcome": "held",
            }
            # Log on every linked entity timeline (mirrors complete_task).
            for entity_kwargs in _task_entity_kwargs_iter(task):
                Activity.objects.create(
                    user=request.user,
                    type=outcome_type,
                    content_text=note,
                    metadata=outcome_metadata,
                    task=task,
                    **entity_kwargs,
                )

        elif payload.action == "rescheduled":
            if payload.new_due_date is None:
                return 400, {"detail": "'new_due_date' is required when rescheduling."}
            if (
                payload.new_due_date_end is not None
                and payload.new_due_date_end < payload.new_due_date
            ):
                return 400, {"detail": "'new_due_date_end' cannot precede 'new_due_date'."}

            old_due_date = task.due_date.isoformat() if task.due_date else None
            task.due_date = payload.new_due_date
            task.due_date_end = payload.new_due_date_end
            # Re-open the task: reset status if it had been auto-expired
            # and clear the prompt mark so the next occurrence prompts
            # again from scratch.
            if task.status == TaskStatus.EXPIRED:
                task.status = TaskStatus.TODO
            task.outcome_prompted_at = None
            task.is_completed = False
            task.completed_at = None
            task.completed_by = None
            task.save(update_fields=[
                "due_date", "due_date_end", "status", "outcome_prompted_at",
                "is_completed", "completed_at", "completed_by",
            ])
            _log_timeline_event(
                task,
                ActivityType.DUE_DATE_CHANGE,
                author=request.user,
                metadata={
                    "old": old_due_date,
                    "new": payload.new_due_date.isoformat(),
                    "outcome": "rescheduled",
                    "note": note,
                },
            )

        else:  # no_show
            task.status = TaskStatus.EXPIRED
            task.save(update_fields=["status"])
            outcome_metadata = {
                "task_id": str(task.id),
                "task_title": task.title,
                "task_kind": task.kind,
                "outcome": "no_show",
                "note": note,
            }
            for entity_kwargs in _task_entity_kwargs_iter(task):
                Activity.objects.create(
                    user=request.user,
                    type=ActivityType.TASK_EXPIRED,
                    content_text=note,
                    metadata=outcome_metadata,
                    task=task,
                    **entity_kwargs,
                )

    return 200, _task_out(task, request.user)


def _task_entity_kwargs_iter(task: Task):
    """Yield ``Activity`` constructor kwargs for each linked CRM entity.

    A task can be tied to several entities (lead/customer/proposal).
    We log a separate Activity per timeline so each entity's history
    is self-contained. If no entity is linked we still yield one empty
    dict so the Activity is created (orphan timeline).
    """
    yielded = False
    if task.record_id:
        yield {"record": task.record}
        yielded = True
    if task.customer_id and not task.record_id:
        yield {"customer": task.customer}
        yielded = True
    if task.proposal_id and not yielded:
        yield {"proposal": task.proposal}
        yielded = True
    if not yielded:
        yield {}


@router.get("/tasks/{task_id}", auth=django_auth, response={200: TaskOut, 403: ErrorOut, 404: ErrorOut})
def get_task(request, task_id: str):
    """Retrieve a single task by ID."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.select_related(
            "record", "assigned_to", "completed_by", "created_by", "proposal", "customer",
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


def _task_document_out(doc: Document, request=None) -> dict:
    file_url = doc.file.url if doc.file.name else ""
    if file_url and request is not None:
        file_url = request.build_absolute_uri(file_url)
    return {
        "id": str(doc.id),
        "task_id": str(doc.task_id) if doc.task_id else "",
        "uploaded_by_id": str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
        "original_filename": doc.name,
        "content_type": doc.content_type or "",
        "size_bytes": doc.size_bytes,
        "url": file_url,
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
    return 200, [_task_document_out(d, request) for d in docs]


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
                "url": request.build_absolute_uri(doc.file.url),
                "size_bytes": doc.size_bytes,
                "content_type": doc.content_type,
            },
        )

    return 201, _task_document_out(doc, request)


@router.delete(
    "/tasks/{task_id}/documents/{document_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_task_document(request, task_id: str, document_id: str):
    """Soft-delete a document attached to a task. Only uploader or admin/owner may delete."""
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

    perform_soft_delete(doc, request.user)
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
# PHASE 3 — STREAMLINE ITEMS (unified TODO / subtask list)
# ===========================================================================
# Legacy subtask endpoints (parent_task FK) have been removed.
# Items are now managed via POST /tasks/{id}/items and PATCH/DELETE /items/{id}.




# ===========================================================================
# PHASE 3 — CHECKLIST
# ===========================================================================

class StreamlineItemOut(Schema):
    id: str
    task_id: str
    text: str
    kind: str
    is_resolved: bool
    order: int
    created_by_id: Optional[str]
    created_at: datetime
    resolved_by_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by_name: Optional[str] = None


class StreamlineItemCreateIn(Schema):
    text: str
    kind: Optional[str] = "todo"


class StreamlineItemUpdateIn(Schema):
    is_resolved: Optional[bool] = None


def _streamline_item_out(item: StreamlineItem) -> dict:
    return {
        "id": str(item.id),
        "task_id": str(item.task_id),
        "text": item.text,
        "kind": item.kind,
        "is_resolved": item.is_resolved,
        "order": item.order,
        "created_by_id": str(item.created_by_id) if item.created_by_id else None,
        "created_at": item.created_at,
        "resolved_by_id": str(item.resolved_by_id) if item.resolved_by_id else None,
        "resolved_at": item.resolved_at,
        "is_deleted": item.is_deleted,
        "deleted_at": item.deleted_at,
        "deleted_by_name": item.deleted_by_name if item.is_deleted else None,
    }


@router.get(
    "/tasks/{task_id}/streamline_items",
    auth=django_auth,
    response={200: List[StreamlineItemOut], 403: ErrorOut, 404: ErrorOut},
)
def list_streamline_items(request, task_id: str):
    """Return all streamline items for a task, ordered by kind, order, created_at."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}
    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}
    items = StreamlineItem.all_objects.filter(task=task).order_by("kind", "order", "created_at")
    return 200, [_streamline_item_out(i) for i in items]


@router.post(
    "/tasks/{task_id}/items",
    auth=django_auth,
    response={201: List[StreamlineItemOut], 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_streamline_items(request, task_id: str, payload: StreamlineItemCreateIn):
    """Add one or more streamline items to a task (multi-line text split)."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}
    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}
    text = payload.text.strip()
    if not text:
        return 400, {"detail": "Item text cannot be empty."}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 400, {"detail": "No valid items found."}
    kind = payload.kind or "todo"
    if kind not in [k.value for k in StreamlineItemKind]:
        return 400, {"detail": f"Invalid kind. Choose from: {[k.value for k in StreamlineItemKind]}"}
    items = []
    for idx, line in enumerate(lines):
        item = StreamlineItem.objects.create(
            task=task,
            text=line[:500],
            kind=kind,
            order=idx,
            created_by=request.user,
        )
        items.append(item)
    # Log activity
    try:
        from crm.models import Activity
        Activity.objects.create(
            firm=request.firm,
            record=task.record,
            customer=task.customer,
            proposal=task.proposal,
            task=task,
            type="streamline_items_added",
            metadata={"count": len(items), "items": [i.text for i in items], "kind": kind},
            user=request.user,
        )
    except Exception:
        pass
    return 201, [_streamline_item_out(i) for i in items]


@router.patch(
    "/items/{item_id}",
    auth=django_auth,
    response={200: StreamlineItemOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_streamline_item(request, item_id: str, payload: StreamlineItemUpdateIn):
    """Toggle resolve status of a streamline item."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}
    try:
        item = StreamlineItem.objects.get(id=item_id, task__firm=request.firm)
    except StreamlineItem.DoesNotExist:
        return 404, {"detail": "Streamline item not found."}
    if payload.is_resolved is None:
        return 400, {"detail": "is_resolved is required."}
    item.is_resolved = payload.is_resolved
    if payload.is_resolved:
        item.resolved_by = request.user
        item.resolved_at = tz.now()
    else:
        item.resolved_by = None
        item.resolved_at = None
    item.save(update_fields=["is_resolved", "resolved_by", "resolved_at"])
    # Log activity
    try:
        from crm.models import Activity
        task = item.task
        activity_type = "streamline_item_resolved" if payload.is_resolved else "streamline_item_reopened"
        Activity.objects.create(
            firm=request.firm,
            record=task.record,
            customer=task.customer,
            proposal=task.proposal,
            task=task,
            type=activity_type,
            metadata={
                "item_id": str(item.id),
                "item_text": item.text,
                "kind": item.kind,
                "resolved": payload.is_resolved,
            },
            user=request.user,
        )
    except Exception:
        pass
    return 200, _streamline_item_out(item)


@router.delete(
    "/items/{item_id}",
    auth=django_auth,
    response={200: StreamlineItemOut, 403: ErrorOut, 404: ErrorOut},
)
def delete_streamline_item(request, item_id: str):
    """Delete a streamline item."""
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
    except Exception as exc:
        return 403, {"detail": str(exc)}
    try:
        item = StreamlineItem.objects.get(id=item_id, task__firm=request.firm)
    except StreamlineItem.DoesNotExist:
        return 404, {"detail": "Streamline item not found."}
    # Manual soft-delete without purge_after: StreamlineItems are purged
    # together with their parent Task rather than on an independent schedule.
    from django.utils import timezone as tz
    item.is_deleted = True
    item.deleted_at = tz.now()
    item.deleted_by = request.user
    item.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])
    return 200, _streamline_item_out(item)



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
    """Soft-delete a task. Requires ADMIN role."""
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        task = Task.objects.get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    perform_soft_delete(task, request.user)
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


def _copy_task(original: Task, firm, created_by, title: str) -> Task:
    """Create a copy of *original* under *firm*. Does not copy subtasks/checklist."""
    new_task = Task.objects.create(
        firm=firm,
        record=original.record,
        proposal=original.proposal,
        customer=original.customer,
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
            "record", "proposal", "customer", "assigned_to",
        ).prefetch_related("watchers", "projects").get(id=task_id, firm=request.firm)
    except Task.DoesNotExist:
        return 404, {"detail": "Task not found."}

    copy_title = payload.title if payload.title else f"{original.title} (copy)"

    with transaction.atomic():
        new_task = _copy_task(original, request.firm, request.user, title=copy_title)

        if payload.include_checklist or payload.include_subtasks:
            for item in StreamlineItem.objects.filter(task=original).order_by("kind", "order", "created_at"):
                StreamlineItem.objects.create(
                    task=new_task,
                    text=item.text,
                    kind=item.kind,
                    order=item.order,
                    created_by=request.user,
                )

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
    task.record = None
    task.proposal = None
    task.customer = None

    if payload.lead_id:
        try:
            task.record = PipelineRecord.objects.get(id=payload.lead_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return 400, {"detail": "Record not found."}
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
        {"text": item.text, "is_checked": item.is_resolved, "kind": item.kind, "order": item.order}
        for item in StreamlineItem.objects.filter(task=task).order_by("kind", "order", "created_at")
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

    perform_soft_delete(tmpl, request.user)
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
            lead = PipelineRecord.objects.get(id=payload.lead_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return 400, {"detail": "Record not found."}

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
            record=lead,
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

        # Copy streamline items from template
        checklist_items = tmpl.checklist_items if isinstance(tmpl.checklist_items, list) else []
        for item_data in checklist_items:
            text = str(item_data.get("text", "")).strip()
            if text:
                StreamlineItem.objects.create(
                    task=task,
                    text=text,
                    kind="todo",
                    order=int(item_data.get("position", 0)),
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
    mixed_currencies: bool = False


@router.get("/stats", auth=django_auth, response={200: StatsOut, 403: ErrorOut})
def get_stats(request):
    """Return aggregated stats for the current Firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    now = tz.now()

    leads_qs = PipelineRecord.objects.filter(firm=request.firm)
    status_counts = {s.value: 0 for s in RecordStatus}
    for row in leads_qs.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]

    default_currency = request.firm.default_currency
    same_currency_qs = leads_qs.filter(currency=default_currency)
    mixed_currencies = leads_qs.exclude(currency=default_currency).exists()

    pipeline_value = float(
        same_currency_qs.exclude(status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED])
        .aggregate(total=Sum("value"))["total"]
        or 0
    )
    won_value = float(
        same_currency_qs.filter(status=RecordStatus.WON).aggregate(total=Sum("value"))["total"] or 0
    )

    total_leads = leads_qs.count()
    won_leads = status_counts.get(RecordStatus.WON, 0)
    conversion_rate = round(won_leads / total_leads, 4) if total_leads else 0.0

    tasks_qs = Task.objects.filter(firm=request.firm, is_completed=False)
    total_tasks_pending = tasks_qs.count()
    total_tasks_overdue = tasks_qs.filter(due_date__lt=now).count()

    total_customers = Customer.objects.filter(firm=request.firm).count()

    recent_activities = (
        Activity.objects.filter(record__firm=request.firm)
        .select_related("record", "user")
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
        "mixed_currencies": mixed_currencies,
    }


# ===========================================================================
# LEAD ATTACHMENTS  (backed by Document + Activity)
# ===========================================================================

# Maximum allowed file size (20 MB)
_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class AttachmentOut(Schema):
    id: str
    lead_id: Optional[str]
    firm_id: str
    uploaded_by_id: Optional[str]
    original_filename: str
    content_type: str
    size_bytes: int
    url: str
    created_at: datetime


def _attachment_out(doc: Document, request=None) -> dict:
    file_url = doc.file.url if doc.file.name else ""
    if file_url and request is not None:
        file_url = request.build_absolute_uri(file_url)
    return {
        "id": str(doc.id),
        "lead_id": str(doc.record_id) if doc.record_id else None,
        "firm_id": str(doc.firm_id),
        "uploaded_by_id": str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
        "original_filename": doc.name,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "url": file_url,
        "created_at": doc.created_at,
    }


@router.get(
    "/records/{record_id}/attachments",
    auth=django_auth,
    response={200: List[AttachmentOut], 403: ErrorOut, 404: ErrorOut},
)
def list_attachments(request, record_id: str, page: int = 1, page_size: int = 20):
    """List all file attachments for a Lead, newest first (paginated)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    offset = (page - 1) * page_size
    docs = Document.objects.filter(record=lead, firm=request.firm).order_by("-created_at")[
        offset: offset + page_size
    ]
    return 200, [_attachment_out(d, request) for d in docs]


@router.post(
    "/records/{record_id}/attachments",
    auth=django_auth,
    response={201: AttachmentOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_attachment(request, record_id: str, file: UploadedFile = File(...)):
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
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    if file.size > _MAX_ATTACHMENT_BYTES:
        return 400, {"detail": f"File exceeds the maximum allowed size of {_MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB."}

    with transaction.atomic():
        doc = Document(
            firm=request.firm,
            record=lead,
            uploaded_by=request.user,
            name=file.name,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file.size,
        )
        doc.file.save(file.name, file, save=True)

        Activity.objects.create(
            record=lead,
            user=request.user,
            type=ActivityType.FILE_UPLOAD,
            metadata={
                "document_id": str(doc.id),
                "filename": doc.name,
                "url": request.build_absolute_uri(doc.file.url),
                "size_bytes": doc.size_bytes,
            },
        )

    return 201, _attachment_out(doc, request)


@router.delete(
    "/records/{record_id}/attachments/{attachment_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_attachment(request, record_id: str, attachment_id: str):
    """
    Soft-delete a file attachment from a Lead.

    Marks the record as deleted; the physical file is removed by the purge task.
    Requires at least Admin role.
    """
    try:
        require_membership(request, min_role=MembershipRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        lead = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        doc = Document.objects.get(id=attachment_id, record=lead, firm=request.firm)
    except Document.DoesNotExist:
        return 404, {"detail": "Attachment not found."}

    perform_soft_delete(doc, request.user)
    return 204, None


# ===========================================================================
# VOICE MEMO UPLOAD  (audio blob → Document, no automatic Activity)
# ===========================================================================
#
# The voice-memo composer in the SPA records audio with the browser
# ``MediaRecorder`` API and uploads the resulting blob to this endpoint.
# We persist the binary as a ``Document`` (so it gets a stable URL backed
# by ``MEDIA_ROOT/documents/``) but, unlike ``upload_attachment`` above, we
# do **not** create an ``Activity`` here — the SPA follows up with a
# regular ``POST /api/v1/crm/activities`` of ``type=voice_memo`` whose
# ``metadata`` references the returned URL plus the captured
# ``duration_seconds``.  This keeps technical metadata (filename, MIME,
# size) entirely server-side and out of the user-facing form.
#
# The endpoint is entity-agnostic: it accepts an optional ``lead_id`` /
# ``customer_id`` / ``proposal_id`` query parameter so the resulting
# ``Document`` is correctly linked, but linking is best-effort and the
# upload succeeds even without it.
# ===========================================================================

# Audio payload limit — 25 MB is enough for a ~30 minute Opus recording
# at 64 kbps and well within the 20 MB attachment ceiling we keep for
# generic file uploads.
_MAX_VOICE_MEMO_BYTES = 25 * 1024 * 1024


class VoiceMemoUploadOut(Schema):
    document_id: str
    url: str
    size_bytes: int
    content_type: str
    filename: str


class _VoiceMemoEntities(NamedTuple):
    """Resolved parent entities for a voice-memo upload.

    All fields are optional — the upload endpoint accepts no parent at
    all (resulting in a standalone Document) — and ``error`` is set to a
    human-readable string when one of the supplied IDs failed to resolve
    inside the active firm tenant.
    """

    record: Optional[PipelineRecord] = None
    customer: Optional[Customer] = None
    proposal: Optional[Proposal] = None
    error: Optional[str] = None


def _resolve_voice_memo_entity(
    request,
    *,
    record_id: Optional[str],
    customer_id: Optional[str],
    proposal_id: Optional[str],
) -> _VoiceMemoEntities:
    """Look up the optional parent entity for a voice-memo upload.

    When ``error`` is non-``None`` the caller should bail out with a 404
    response.  Tenants are enforced via ``firm=request.firm``.
    """
    record = customer = proposal = None
    if record_id:
        try:
            record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return _VoiceMemoEntities(error="Record not found.")
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id, firm=request.firm)
        except Customer.DoesNotExist:
            return _VoiceMemoEntities(error="Customer not found.")
    if proposal_id:
        try:
            proposal = Proposal.objects.get(id=proposal_id, firm=request.firm)
        except Proposal.DoesNotExist:
            return _VoiceMemoEntities(error="Proposal not found.")
    return _VoiceMemoEntities(
        record=record,
        customer=customer,
        proposal=proposal,
    )


@router.post(
    "/voice-memos/upload",
    auth=django_auth,
    response={201: VoiceMemoUploadOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_voice_memo(
    request,
    file: UploadedFile = File(...),
    record_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
):
    """Persist a recorded voice-memo audio blob and return its URL.

    The SPA calls this endpoint with the audio blob produced by the
    browser ``MediaRecorder``; the returned ``url`` / ``document_id`` are
    then included as metadata in a follow-up ``voice_memo`` Activity
    submission.  This endpoint deliberately does **not** create an
    Activity itself, so the audio can be discarded if the user cancels
    the composer after recording.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    if file.size > _MAX_VOICE_MEMO_BYTES:
        return 400, {
            "detail": (
                f"Voice memo exceeds the maximum allowed size of "
                f"{_MAX_VOICE_MEMO_BYTES // (1024 * 1024)} MB."
            )
        }

    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("audio/"):
        return 400, {"detail": "Only audio uploads are accepted on this endpoint."}

    record, customer, proposal, error = _resolve_voice_memo_entity(
        request,
        record_id=record_id,
        customer_id=customer_id,
        proposal_id=proposal_id,
    )
    if error:
        return 404, {"detail": error}

    # Auto-generated filename — the user never sees it; we only need
    # something stable for storage / download.  Preserve the extension
    # from the upload so the browser can play the file back without
    # MIME sniffing surprises.
    original_name = (file.name or "voice-memo").strip() or "voice-memo"
    timestamp = tz.now().strftime("%Y%m%d-%H%M%S")
    extension = ""
    if "." in original_name:
        extension = "." + original_name.rsplit(".", 1)[-1].lower()
    storage_name = f"voice-memo-{timestamp}{extension}"

    doc = Document(
        firm=request.firm,
        record=record,
        customer=customer,
        proposal=proposal,
        uploaded_by=request.user,
        name=storage_name,
        content_type=content_type or "audio/webm",
        size_bytes=file.size,
    )
    doc.file.save(storage_name, file, save=True)

    return 201, {
        "document_id": str(doc.id),
        "url": request.build_absolute_uri(doc.file.url) if doc.file.name else "",
        "size_bytes": doc.size_bytes,
        "content_type": doc.content_type,
        "filename": doc.name,
    }


# ===========================================================================
# FILE UPLOAD COMPOSER  (multi-file blob → Documents, no automatic Activity)
# ===========================================================================
#
# The Streamline ``file_upload`` composer in the SPA accepts either a
# remote URL (handled entirely client-side and submitted directly to
# ``POST /activities``) or one or more uploaded binary files.  This
# endpoint covers the latter: it persists the binary as a ``Document``
# but does **not** create an ``Activity`` itself — the SPA instead
# follows up with a regular ``POST /api/v1/crm/activities`` of
# ``type=file_upload`` whose metadata references the returned URL +
# filename + size.  This mirrors the voice-memo flow (see above) and is
# what lets the user discard a recording after upload.
#
# A single multipart request can carry several files in the ``files``
# field; each file becomes its own Document/response entry and the SPA
# is responsible for fanning out one Activity per file.
# ===========================================================================

# Plan-aware size limits — kept in sync with the client-side caps
# advertised in `streamline_goals.md` § Fáze 7.2.
_FILE_UPLOAD_LIMIT_FREE_BYTES = 15 * 1024 * 1024
_FILE_UPLOAD_LIMIT_PRO_BYTES = 100 * 1024 * 1024


def _file_upload_limit_for_firm(firm) -> int:
    """Return the per-file size cap (bytes) for the active firm's plan."""
    tier = (getattr(firm, "subscription_tier", "") or "").lower()
    if tier == "pro":
        return _FILE_UPLOAD_LIMIT_PRO_BYTES
    return _FILE_UPLOAD_LIMIT_FREE_BYTES


class FileUploadEntryOut(Schema):
    document_id: str
    url: str
    filename: str
    content_type: str
    size_bytes: int


class FileUploadResponseOut(Schema):
    files: List[FileUploadEntryOut]


def _resolve_file_upload_entity(
    request,
    *,
    record_id: Optional[str],
    customer_id: Optional[str],
    proposal_id: Optional[str],
) -> _VoiceMemoEntities:
    """Reuse the voice-memo entity resolver for file uploads."""
    return _resolve_voice_memo_entity(
        request,
        record_id=record_id,
        customer_id=customer_id,
        proposal_id=proposal_id,
    )


@router.post(
    "/file-uploads/upload",
    auth=django_auth,
    response={201: FileUploadResponseOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def upload_file_blobs(
    request,
    files: List[UploadedFile] = File(...),
    record_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
):
    """Persist one or more uploaded binaries; return their stable URLs.

    The SPA composer fans these out into one ``file_upload`` Activity
    per returned entry.  Per-file size is capped by the firm's plan
    (15 MB free / 100 MB pro); exceeding the cap fails the entire
    request so the user gets a single clear toast rather than a partial
    success.
    """
    try:
        require_membership(request, min_role=MembershipRole.WORKER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    if not files:
        return 400, {"detail": "No files were uploaded."}

    limit = _file_upload_limit_for_firm(request.firm)
    for upload in files:
        if upload.size > limit:
            return 400, {
                "detail": (
                    f"File '{upload.name}' exceeds the maximum allowed size of "
                    f"{limit // (1024 * 1024)} MB for your current plan."
                )
            }

    entities = _resolve_file_upload_entity(
        request,
        record_id=record_id,
        customer_id=customer_id,
        proposal_id=proposal_id,
    )
    if entities.error:
        return 404, {"detail": entities.error}

    results: list[dict] = []
    for upload in files:
        original_name = (upload.name or "file").strip() or "file"
        content_type = (upload.content_type or "application/octet-stream").lower()
        doc = Document(
            firm=request.firm,
            record=entities.record,
            customer=entities.customer,
            proposal=entities.proposal,
            uploaded_by=request.user,
            name=original_name,
            content_type=content_type,
            size_bytes=upload.size,
        )
        doc.file.save(original_name, upload, save=True)
        results.append(
            {
                "document_id": str(doc.id),
                "url": request.build_absolute_uri(doc.file.url) if doc.file.name else "",
                "filename": doc.name,
                "content_type": doc.content_type,
                "size_bytes": doc.size_bytes,
            }
        )

    return 201, {"files": results}


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

    leads_qs = PipelineRecord.objects.filter(firm=request.firm)

    # Build a base dict with every status initialised to zero so that
    # statuses with no leads are still present in the response.
    counts: Dict[str, int] = {s.value: 0 for s in RecordStatus}
    values: Dict[str, float] = {s.value: 0.0 for s in RecordStatus}

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
    lead_id: Optional[str]
    lead_title: Optional[str]
    user_id: Optional[str]
    type: str
    content_text: str
    metadata: Dict[str, Any]
    created_at: datetime


def _activity_feed_item_out(a: Activity) -> dict:
    return {
        "id": str(a.id),
        "lead_id": str(a.record_id) if a.record_id else None,
        "lead_title": a.record.title if a.record_id else None,
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
        Activity.objects.filter(record__firm=request.firm)
        .select_related("record")
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
    if t.record_id:
        try:
            lead_title = t.record.title
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
        .select_related("record")
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
    status_hours: Dict[str, list] = {s.value: [] for s in RecordStatus}

    history_qs = (
        Activity.objects.filter(
            record__firm=request.firm,
            type=ActivityType.STATUS_CHANGE,
            record__isnull=False,
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
        for s in RecordStatus
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

    qs = PipelineRecord.objects.filter(firm=request.firm, status__in=[RecordStatus.WON, RecordStatus.LOST])
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

    result_map: Dict[str, Dict[str, int]] = {s.value: {"won": 0, "lost": 0} for s in RecordSource}
    for row in data:
        source = row["source"]
        if source not in result_map:
            result_map[source] = {"won": 0, "lost": 0}
        if row["status"] == RecordStatus.WON:
            result_map[source]["won"] = row["n"]
        elif row["status"] == RecordStatus.LOST:
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
        leads_owned = PipelineRecord.objects.filter(firm=request.firm, assigned_to=user).count()
        tasks_completed = Task.objects.filter(firm=request.firm, assigned_to=user, is_completed=True).count()
        activities_logged = Activity.objects.filter(record__firm=request.firm, user=user).count()
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

    leads_qs = PipelineRecord.objects.filter(firm=request.firm)

    weekly_rows = []
    for week in range(12):
        week_start = twelve_weeks_ago + dt.timedelta(weeks=week)
        week_end = week_start + dt.timedelta(weeks=1)
        created = leads_qs.filter(created_at__gte=week_start, created_at__lt=week_end).count()
        closed = leads_qs.filter(
            status__in=[RecordStatus.WON, RecordStatus.LOST],
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
        status__in=[RecordStatus.WON, RecordStatus.LOST],
        updated_at__gte=thirty_days_ago,
    )
    won_30d = closed_30d.filter(status=RecordStatus.WON).count()
    total_closed_30d = closed_30d.count()
    conversion_rate = (won_30d / total_closed_30d * 100.0) if total_closed_30d > 0 else 0.0

    result = {"weekly": weekly_rows, "conversion_rate_30d": round(conversion_rate, 2)}
    cache.set(cache_key, result, _ANALYTICS_CACHE_SECONDS)
    return 200, result


# ---------------------------------------------------------------------------
# Phase 4.5 — Profitability report
# ---------------------------------------------------------------------------

class ProfitabilityRow(Schema):
    entity_id: str
    entity_type: str   # "lead" | "customer" | "total"
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
    Profitability breakdown aggregated from TimeEntry, ExpenseItem and
    RevenueItem data.  Results are NOT cached (supports date filters).
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    from crm.models import TimeEntry, ExpenseItem, RevenueItem

    firm = request.firm

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

    return 200, {"rows": [], "totals": totals}


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
    columns: List[str]
    created_at: datetime


class SavedViewIn(Schema):
    name: str
    entity: str
    filters: Dict[str, Any] = {}
    sort_by: str = ""
    sort_dir: str = "asc"
    columns: List[str] = []


def _saved_view_out(v: SavedView) -> dict:
    return {
        "id": str(v.id),
        "name": v.name,
        "entity": v.entity,
        "filters": v.filters,
        "sort_by": v.sort_by,
        "sort_dir": v.sort_dir,
        "columns": v.columns if isinstance(v.columns, list) else [],
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
            columns=payload.columns,
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

    perform_soft_delete(cf, request.user)
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

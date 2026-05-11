"""
Django Ninja API router – CRM (Customers, Records, Activities, Tasks)

Every endpoint requires:
  1. Session authentication.
  2. A valid Firm supplied via the ``X-Firm-ID`` header (resolved by TenantMiddleware).
  3. The authenticated user to be a member of that Firm.
"""
import datetime as dt
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Mapping, NamedTuple, Optional

from django.core.cache import cache
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Max, Q, Sum
from django.utils.dateparse import parse_datetime

from django.db import transaction
from django.utils import timezone as tz
from ninja import File, Query, Router, Schema, UploadedFile
from ninja.security import django_auth

from crm.models import (
    Activity,
    ActivityReaction,
    ActivityType,
    Category,
    CategoryField,
    Checkpoint,
    ConditionEffectType,
    ConditionRule,
    ConditionScopeType,
    ConditionTriggerType,
    ConditionSeverity,
    RuleEvaluationLog,
    RuleEvaluationResult,
    RequirementType,
    ContactType,
    Customer,
    DashboardLayout,
    Document,
    PipelineRecord,
    RecordScoringRule,
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
    StageRequirement,
    StageScenario,
)
from firms.auth import (
    InvitationRole,
    PermissionDenied,
    SubscriptionRequired,
    AuthenticationRequired,
    FirmNotFound,
    SuperuserMembership,
    check_tier_limits,
    require_active_subscription,
    require_membership,
    require_permission,
)
from firms.models import Membership, PermissionAuditLog
from firms.permissions import Permission

from crm.apps import set_current_user, clear_current_user
from crm.events import broadcast_event
from crm.permissions import filter_records_qs, filter_activities_qs, filter_tasks_qs
from crm.soft_delete import perform_soft_delete

router = Router(tags=["crm"])

_MENTION_PREVIEW_LENGTH = 120
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared error schema
# ---------------------------------------------------------------------------

class ErrorOut(Schema):
    detail: str
    code: Optional[str] = None
    stage_change_evaluation: Optional[Dict[str, Any]] = None


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
    created_by_id: Optional[str]
    created_by_name: Optional[str]
    assigned_to_id: Optional[str]
    assigned_to_name: Optional[str]
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
    assigned_to_id: Optional[str] = None
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
    created_by_name: Optional[str] = None
    if c.created_by_id:
        try:
            cb = c.created_by
            created_by_name = f"{cb.first_name} {cb.last_name}".strip() or cb.email
        except Exception:
            pass
    assigned_to_name: Optional[str] = None
    if c.assigned_to_id:
        try:
            at = c.assigned_to
            assigned_to_name = f"{at.first_name} {at.last_name}".strip() or at.email
        except Exception:
            pass
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
        "created_by_id": str(c.created_by_id) if c.created_by_id else None,
        "created_by_name": created_by_name,
        "assigned_to_id": str(c.assigned_to_id) if c.assigned_to_id else None,
        "assigned_to_name": assigned_to_name,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get("/directory", auth=django_auth, response={200: List[CustomerOut], 403: ErrorOut})
def list_customers(request, search: str = "", page: int = 1, page_size: int = 20, type: str = "", tag: str = ""):
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = Customer.objects.filter(firm=request.firm).select_related('created_by', 'assigned_to')
    if type in (ContactType.PERSON, ContactType.COMPANY):
        qs = qs.filter(type=type)
    if tag:
        qs = qs.filter(tags__contains=[tag])
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


@router.get("/directory/tags", auth=django_auth, response={200: List[str], 403: ErrorOut})
def list_directory_tags(request):
    """Return all unique tags used across a firm's customer records."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    tags: set[str] = set()
    for tag_list in Customer.objects.filter(firm=request.firm).values_list("tags", flat=True):
        if tag_list:
            tags.update(tag_list)
    return 200, sorted(tags)


@router.post("/directory", auth=django_auth, response={201: CustomerOut, 403: ErrorOut})
def create_customer(request, payload: CustomerIn):
    try:
        require_membership(request, min_role=InvitationRole.MEMBER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    data = payload.dict()
    company_id = data.pop("company_id", None)
    assigned_to_id = data.pop("assigned_to_id", None)
    company = None
    if company_id:
        try:
            company = Customer.objects.get(id=company_id, firm=request.firm, type=ContactType.COMPANY)
        except Customer.DoesNotExist:
            pass
    assigned_to = None
    if assigned_to_id:
        assigned_to, err = _resolve_user_in_firm(assigned_to_id, request.firm)
        if err:
            return err
    customer = Customer.objects.create(
        firm=request.firm,
        company=company,
        created_by=request.user,
        assigned_to=assigned_to,
        **data,
    )

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
        customer = Customer.objects.select_related('created_by', 'assigned_to').get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}
    return 200, _customer_out(customer)


@router.put("/directory/{customer_id}", auth=django_auth, response={200: CustomerOut, 403: ErrorOut, 404: ErrorOut})
def update_customer(request, customer_id: str, payload: CustomerIn):
    try:
        require_membership(request, min_role=InvitationRole.MEMBER)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        customer = Customer.objects.select_related('created_by', 'assigned_to').get(id=customer_id, firm=request.firm)
    except Customer.DoesNotExist:
        return 404, {"detail": "Customer not found."}

    data = payload.dict()
    company_id = data.pop("company_id", None)
    assigned_to_id = data.pop("assigned_to_id", None)
    company = None
    if company_id:
        try:
            company = Customer.objects.get(id=company_id, firm=request.firm, type=ContactType.COMPANY)
        except Customer.DoesNotExist:
            pass
    assigned_to = None
    if assigned_to_id:
        assigned_to, err = _resolve_user_in_firm(assigned_to_id, request.firm)
        if err:
            return err
    customer.company = company
    customer.assigned_to = assigned_to
    for field, value in data.items():
        setattr(customer, field, value)
    set_current_user(request.user)
    try:
        customer.save()
    finally:
        clear_current_user()
    return 200, _customer_out(customer)


@router.delete("/directory/{customer_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def delete_customer(request, customer_id: str):
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
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

    employees = Customer.objects.filter(company_id=customer_id, firm=request.firm).select_related('created_by', 'assigned_to')
    return 200, [_customer_out(e) for e in employees]


# ===========================================================================
# RECORDS
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


class RecordUpdateOut(RecordOut):
    stage_change_evaluation: Optional[Dict[str, Any]] = None
    field_change_evaluation: Optional[Dict[str, Any]] = None


def _validate_record_field_rules(
    category_id: Optional[Any],
    value: Optional[Any] = None,
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
                    hint = rules.get("pattern_hint", pattern)
                    return f"Notes does not match the required pattern: {hint}"
            except re.error:
                pass  # invalid regex in config — skip silently

    # --- source: options (select) ---
    if source is not None and "source" in rules_by_key:
        rules = rules_by_key["source"]
        options = rules.get("options")
        if isinstance(options, list) and len(options) > 0 and source not in options:
            return f"Source must be one of: {', '.join(str(o) for o in options)}."

    return None


def _compute_record_score(record: PipelineRecord, rules: list) -> int:
    """
    Compute a 0–100 record score by evaluating each scoring rule against
    the record.  Rules are pre-fetched by the caller to avoid N+1 queries.

    Supported field values
    ----------------------
    ``status``                 — matches if record.status == operand (string)
    ``source``                 — matches if record.source == operand (string)
    ``value_gte``              — matches if record.value >= operand (number)
    ``last_activity_days_lte`` — matches if the record's most recent activity is
                                  within *operand* days (number)
    """
    score = 50  # baseline
    for rule in rules:
        field = rule.field
        operand = rule.operand
        matched = False

        if field == "status":
            matched = record.status == operand
        elif field == "source":
            matched = record.source == operand
        elif field == "value_gte":
            matched = record.value is not None and record.value >= Decimal(str(operand))
        elif field == "last_activity_days_lte":
            last_activity = (
                Activity.objects.filter(record=record)
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


def _record_out(record: PipelineRecord, rules: Optional[list] = None) -> dict:
    score = _compute_record_score(record, rules) if rules is not None else None
    created_by_name: Optional[str] = None
    if record.created_by_id:
        try:
            cb = record.created_by
            created_by_name = f"{cb.first_name} {cb.last_name}".strip() or cb.email
        except Exception as exc:
            logger.debug("Could not resolve created_by name for record %s: %s", record.id, exc)
    assigned_to_name: Optional[str] = None
    if record.assigned_to_id:
        try:
            at = record.assigned_to
            assigned_to_name = f"{at.first_name} {at.last_name}".strip() or at.email
        except Exception as exc:
            logger.debug("Could not resolve assigned_to name for record %s: %s", record.id, exc)
    # Company & contact person
    company_id = str(record.company_id) if record.company_id else None
    company_name: Optional[str] = None
    contact_person_id = str(record.contact_person_id) if record.contact_person_id else None
    contact_person_name: Optional[str] = None
    if record.company_id:
        try:
            co = record.company
            company_name = co.company_name or f"{co.first_name} {co.last_name}".strip()
        except Exception:
            pass
    if record.contact_person_id:
        try:
            cp = record.contact_person
            contact_person_name = f"{cp.first_name} {cp.last_name}".strip() or cp.email
        except Exception:
            pass
    # Resolve current_stage name
    current_stage_name: Optional[str] = None
    if record.current_stage_id:
        try:
            current_stage_name = record.current_stage.name
        except Exception:
            pass
    return {
        "id": str(record.id),
        "firm_id": str(record.firm_id),
        "customer_id": str(record.customer_id) if record.customer_id else None,
        "title": record.title,
        "status": record.status,
        "source": record.source,
        "assigned_to_id": str(record.assigned_to_id) if record.assigned_to_id else None,
        "assigned_to_name": assigned_to_name,
        "value": record.value,
        "currency": record.currency,
        "score": score,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "created_by_id": str(record.created_by_id) if record.created_by_id else None,
        "created_by_name": created_by_name,
        "company_id": company_id,
        "company_name": company_name,
        "contact_person_id": contact_person_id,
        "contact_person_name": contact_person_name,
        # Pipeline fields
        "category_id": str(record.category_id) if record.category_id else None,
        "current_stage_id": str(record.current_stage_id) if record.current_stage_id else None,
        "current_stage_name": current_stage_name,
        "parent_id": str(record.parent_id) if record.parent_id else None,
        "start_date": record.start_date.isoformat() if record.start_date else None,
        "end_date": record.end_date.isoformat() if record.end_date else None,
        "expires_at": record.expires_at,
        "notes": record.notes or "",
        "extra_data": record.extra_data or {},
    }


def _build_stage_change_condition_context(
    record: PipelineRecord,
    *,
    from_stage_id: Any,
    to_stage_id: Any,
) -> dict:
    from crm.condition_rules import RecordConditionContextBuilder

    context = RecordConditionContextBuilder().build(
        record,
        changed_field="current_stage_id",
        old_value=str(from_stage_id) if from_stage_id else None,
        new_value=str(to_stage_id) if to_stage_id else None,
        changed_field_source="field",
    )
    context["stage_change"] = {
        "from_stage_id": str(from_stage_id) if from_stage_id else None,
        "to_stage_id": str(to_stage_id) if to_stage_id else None,
    }
    return context


def _get_applicable_stage_change_rules(
    *,
    firm,
    record: PipelineRecord,
    trigger_type: str,
    from_stage_id: Any,
    to_stage_id: Any,
) -> list[ConditionRule]:
    rules = (
        ConditionRule.objects
        .filter(
            firm=firm,
            is_active=True,
            trigger_type=trigger_type,
        )
        .order_by("priority", "created_at", "id")
    )

    applicable: list[ConditionRule] = []
    record_category_id = str(record.category_id) if record.category_id else None
    from_stage = str(from_stage_id) if from_stage_id else None
    to_stage = str(to_stage_id) if to_stage_id else None
    for rule in rules:
        scope_type = rule.scope_type
        if scope_type == ConditionScopeType.FIRM:
            applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.CATEGORY:
            if rule.category_id and str(rule.category_id) == record_category_id:
                applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.STAGE:
            if rule.stage_id and str(rule.stage_id) == to_stage:
                applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.STAGE_TRANSITION:
            if (
                rule.source_stage_id
                and rule.target_stage_id
                and str(rule.source_stage_id) == from_stage
                and str(rule.target_stage_id) == to_stage
            ):
                applicable.append(rule)
            continue
    return applicable


def _serialize_stage_rule_output(output: dict[str, Any]) -> dict[str, Any]:
    effect_config = output.get("effect_config")
    message = ""
    if isinstance(effect_config, dict):
        message = (
            str(effect_config.get("message") or "")
            or str(effect_config.get("title") or "")
        )
    return {
        "rule_id": str(output.get("rule_id")) if output.get("rule_id") else "",
        "name": str(output.get("name") or ""),
        "priority": output.get("priority"),
        "effect": output.get("effect"),
        "severity": output.get("severity"),
        "message": message,
        "effect_config": effect_config if isinstance(effect_config, dict) else {},
    }


def _log_stage_rule_outputs(
    *,
    firm,
    record: PipelineRecord,
    trigger_type: str,
    context: dict[str, Any],
    outputs: list[dict[str, Any]],
    evaluated_by,
):
    compact_context = {
        "record_id": str(record.id),
        "category_id": str(record.category_id) if record.category_id else None,
        "current_stage_id": str(record.current_stage_id) if record.current_stage_id else None,
        "stage_change": context.get("stage_change", {}),
    }
    if not outputs:
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            trigger_type=trigger_type,
            input_context=compact_context,
            result=RuleEvaluationResult.PASSED,
            messages=[],
            recommendations=[],
            evaluated_by=evaluated_by,
        )
        return

    for output in outputs:
        effect = output.get("effect")
        if effect == ConditionEffectType.BLOCK:
            result = RuleEvaluationResult.BLOCKED
        elif effect == ConditionEffectType.WARNING:
            result = RuleEvaluationResult.WARNING
        else:
            result = RuleEvaluationResult.PASSED

        effect_config = output.get("effect_config")
        message = ""
        if isinstance(effect_config, dict):
            message = str(effect_config.get("message") or "")
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            rule_id=output.get("rule_id"),
            trigger_type=trigger_type,
            input_context=compact_context,
            result=result,
            messages=[message] if message else [],
            recommendations=[effect_config] if effect == ConditionEffectType.RECOMMENDATION and isinstance(effect_config, dict) else [],
            evaluated_by=evaluated_by,
        )


def _log_stage_rule_error(
    *,
    firm,
    record: PipelineRecord,
    trigger_type: str,
    context: dict[str, Any],
    evaluated_by,
    error: Exception,
):
    RuleEvaluationLog.objects.create(
        firm=firm,
        record=record,
        trigger_type=trigger_type,
        input_context={
            "record_id": str(record.id),
            "stage_change": context.get("stage_change", {}),
        },
        result=RuleEvaluationResult.ERROR,
        messages=[],
        recommendations=[],
        error_message=str(error),
        evaluated_by=evaluated_by,
    )


def _evaluate_stage_change_trigger(
    *,
    firm,
    record: PipelineRecord,
    trigger_type: str,
    from_stage_id: Any,
    to_stage_id: Any,
    evaluated_by,
    fail_closed: bool,
) -> dict[str, list[dict[str, Any]]]:
    from crm.condition_rules import evaluate_condition_rule_outputs

    context = _build_stage_change_condition_context(
        record,
        from_stage_id=from_stage_id,
        to_stage_id=to_stage_id,
    )
    try:
        rules = _get_applicable_stage_change_rules(
            firm=firm,
            record=record,
            trigger_type=trigger_type,
            from_stage_id=from_stage_id,
            to_stage_id=to_stage_id,
        )
        outputs = evaluate_condition_rule_outputs(rules, context)
        _log_stage_rule_outputs(
            firm=firm,
            record=record,
            trigger_type=trigger_type,
            context=context,
            outputs=outputs,
            evaluated_by=evaluated_by,
        )
    except Exception as exc:
        logger.exception(
            "Stage change rule evaluation failed for record %s (trigger=%s)",
            record.id,
            trigger_type,
        )
        _log_stage_rule_error(
            firm=firm,
            record=record,
            trigger_type=trigger_type,
            context=context,
            evaluated_by=evaluated_by,
            error=exc,
        )
        if fail_closed:
            return {
                "blocking": [
                    {
                        "rule_id": "",
                        "name": "Condition evaluation failed",
                        "priority": None,
                        "effect": ConditionEffectType.BLOCK,
                        "severity": ConditionSeverity.ERROR,
                        "message": "Condition evaluation failed.",
                        "effect_config": {},
                    },
                ],
                "warnings": [],
            }
        return {"blocking": [], "warnings": []}

    blocking = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.BLOCK
    ]
    warnings = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.WARNING
    ]
    return {
        "blocking": blocking,
        "warnings": warnings,
    }


def _to_json_compatible_value(value: Any, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (dict, list, tuple, set)):
        value_id = id(value)
        if value_id in seen:
            return "<circular_reference>"
        seen.add(value_id)

    if isinstance(value, dict):
        return {
            str(key): _to_json_compatible_value(item, seen)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible_value(item, seen) for item in value]

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _build_field_change_condition_context(
    record: PipelineRecord,
    *,
    field_key: str,
    old_value: Any,
    new_value: Any,
) -> dict:
    from crm.condition_rules import RecordConditionContextBuilder

    context = RecordConditionContextBuilder().build(
        record,
        changed_field=field_key,
        old_value=_to_json_compatible_value(old_value),
        new_value=_to_json_compatible_value(new_value),
        changed_field_source="field",
    )
    context["field_changes"] = {
        field_key: {
            "source_type": "field",
            "old_value": context.get("change", {}).get("old_value"),
            "new_value": context.get("change", {}).get("new_value"),
        },
    }
    return context


def _extract_record_category_fields(extra_data: Any) -> dict[str, Any]:
    if not isinstance(extra_data, Mapping):
        return {}
    category_fields = extra_data.get("category_fields")
    if isinstance(category_fields, Mapping):
        return dict(category_fields)
    # Backward-compatible fallback for legacy records storing category fields at root.
    return {
        key: value
        for key, value in extra_data.items()
        if key not in {"active_stage_scenario_id", "active_stage_requirements"}
    }


def _build_category_field_change_condition_context(
    record: PipelineRecord,
    *,
    category_field_key: str,
    old_value: Any,
    new_value: Any,
) -> dict:
    from crm.condition_rules import RecordConditionContextBuilder

    context = RecordConditionContextBuilder().build(
        record,
        changed_field=category_field_key,
        old_value=_to_json_compatible_value(old_value),
        new_value=_to_json_compatible_value(new_value),
        changed_field_source="category_field",
    )
    change = context.get("change")
    if isinstance(change, dict):
        change["category_field_key"] = category_field_key
    context["field_changes"] = {
        category_field_key: {
            "source_type": "category_field",
            "category_field_key": category_field_key,
            "old_value": context.get("change", {}).get("old_value"),
            "new_value": context.get("change", {}).get("new_value"),
        },
    }
    return context


def _get_applicable_field_change_rules(
    *,
    firm,
    record: PipelineRecord,
) -> list[ConditionRule]:
    rules = (
        ConditionRule.objects
        .filter(
            firm=firm,
            is_active=True,
            trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
        )
        .order_by("priority", "created_at", "id")
    )

    applicable: list[ConditionRule] = []
    record_category_id = str(record.category_id) if record.category_id else None
    current_stage_id = str(record.current_stage_id) if record.current_stage_id else None
    for rule in rules:
        scope_type = rule.scope_type
        if scope_type == ConditionScopeType.FIRM:
            applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.CATEGORY:
            if rule.category_id and str(rule.category_id) == record_category_id:
                applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.STAGE:
            if rule.stage_id and str(rule.stage_id) == current_stage_id:
                applicable.append(rule)
            continue
    return applicable


def _get_applicable_category_field_change_rules(
    *,
    firm,
    record: PipelineRecord,
) -> list[ConditionRule]:
    rules = (
        ConditionRule.objects
        .filter(
            firm=firm,
            is_active=True,
            trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
        )
        .order_by("priority", "created_at", "id")
    )

    applicable: list[ConditionRule] = []
    record_category_id = str(record.category_id) if record.category_id else None
    current_stage_id = str(record.current_stage_id) if record.current_stage_id else None
    for rule in rules:
        scope_type = rule.scope_type
        if scope_type == ConditionScopeType.FIRM:
            applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.CATEGORY:
            if rule.category_id and str(rule.category_id) == record_category_id:
                applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.STAGE:
            if rule.stage_id and str(rule.stage_id) == current_stage_id:
                applicable.append(rule)
            continue
    return applicable


def _log_field_change_rule_outputs(
    *,
    firm,
    record: PipelineRecord,
    context: dict[str, Any],
    outputs: list[dict[str, Any]],
    evaluated_by,
):
    compact_context = {
        "record_id": str(record.id),
        "category_id": str(record.category_id) if record.category_id else None,
        "current_stage_id": str(record.current_stage_id) if record.current_stage_id else None,
        "change": _to_json_compatible_value(context.get("change", {})),
    }
    if not outputs:
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
            input_context=compact_context,
            result=RuleEvaluationResult.PASSED,
            messages=[],
            recommendations=[],
            evaluated_by=evaluated_by,
        )
        return

    for output in outputs:
        effect = output.get("effect")
        if effect == ConditionEffectType.BLOCK:
            result = RuleEvaluationResult.BLOCKED
        elif effect == ConditionEffectType.WARNING:
            result = RuleEvaluationResult.WARNING
        elif effect == ConditionEffectType.ACTIVATE_SCENARIO:
            result = RuleEvaluationResult.SCENARIO_ACTIVATED
        elif effect == ConditionEffectType.COMPLETE_REQUIREMENT:
            result = RuleEvaluationResult.REQUIREMENT_COMPLETED
        else:
            result = RuleEvaluationResult.PASSED

        effect_config = output.get("effect_config")
        message = ""
        if isinstance(effect_config, dict):
            message = str(effect_config.get("message") or "")
        recommendations: list[dict[str, Any]] = []
        if effect == ConditionEffectType.RECOMMENDATION and isinstance(effect_config, dict):
            recommendations = [effect_config]
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            rule_id=output.get("rule_id"),
            trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
            input_context=compact_context,
            result=result,
            messages=[message] if message else [],
            recommendations=recommendations,
            evaluated_by=evaluated_by,
        )


def _log_category_field_change_rule_outputs(
    *,
    firm,
    record: PipelineRecord,
    context: dict[str, Any],
    outputs: list[dict[str, Any]],
    evaluated_by,
):
    compact_context = {
        "record_id": str(record.id),
        "category_id": str(record.category_id) if record.category_id else None,
        "current_stage_id": str(record.current_stage_id) if record.current_stage_id else None,
        "change": _to_json_compatible_value(context.get("change", {})),
    }
    if not outputs:
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
            input_context=compact_context,
            result=RuleEvaluationResult.PASSED,
            messages=[],
            recommendations=[],
            evaluated_by=evaluated_by,
        )
        return

    for output in outputs:
        effect = output.get("effect")
        if effect == ConditionEffectType.BLOCK:
            result = RuleEvaluationResult.BLOCKED
        elif effect == ConditionEffectType.WARNING:
            result = RuleEvaluationResult.WARNING
        elif effect == ConditionEffectType.ACTIVATE_SCENARIO:
            result = RuleEvaluationResult.SCENARIO_ACTIVATED
        elif effect == ConditionEffectType.COMPLETE_REQUIREMENT:
            result = RuleEvaluationResult.REQUIREMENT_COMPLETED
        else:
            result = RuleEvaluationResult.PASSED

        effect_config = output.get("effect_config")
        message = ""
        if isinstance(effect_config, dict):
            message = str(effect_config.get("message") or "")
        recommendations: list[dict[str, Any]] = []
        if effect == ConditionEffectType.RECOMMENDATION and isinstance(effect_config, dict):
            recommendations = [effect_config]
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            rule_id=output.get("rule_id"),
            trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
            input_context=compact_context,
            result=result,
            messages=[message] if message else [],
            recommendations=recommendations,
            evaluated_by=evaluated_by,
        )


def _log_field_change_rule_error(
    *,
    firm,
    record: PipelineRecord,
    field_key: str,
    context: dict[str, Any],
    evaluated_by,
    error: Exception,
):
    RuleEvaluationLog.objects.create(
        firm=firm,
        record=record,
        trigger_type=ConditionTriggerType.RECORD_FIELD_CHANGED,
        input_context={
            "record_id": str(record.id),
            "field_key": field_key,
            "change": _to_json_compatible_value(context.get("change", {})),
        },
        result=RuleEvaluationResult.ERROR,
        messages=[],
        recommendations=[],
        error_message=str(error),
        evaluated_by=evaluated_by,
    )


def _log_category_field_change_rule_error(
    *,
    firm,
    record: PipelineRecord,
    category_field_key: str,
    context: dict[str, Any],
    evaluated_by,
    error: Exception,
):
    RuleEvaluationLog.objects.create(
        firm=firm,
        record=record,
        trigger_type=ConditionTriggerType.RECORD_CATEGORY_FIELD_CHANGED,
        input_context={
            "record_id": str(record.id),
            "category_field_key": category_field_key,
            "change": _to_json_compatible_value(context.get("change", {})),
        },
        result=RuleEvaluationResult.ERROR,
        messages=[],
        recommendations=[],
        error_message=str(error),
        evaluated_by=evaluated_by,
    )


def _evaluate_field_change_trigger(
    *,
    firm,
    record: PipelineRecord,
    field_key: str,
    old_value: Any,
    new_value: Any,
    evaluated_by,
) -> dict[str, list[dict[str, Any]]]:
    from crm.condition_rules import evaluate_condition_rule_outputs

    context = _build_field_change_condition_context(
        record,
        field_key=field_key,
        old_value=old_value,
        new_value=new_value,
    )
    try:
        rules = _get_applicable_field_change_rules(
            firm=firm,
            record=record,
        )
        outputs = evaluate_condition_rule_outputs(rules, context)
        _log_field_change_rule_outputs(
            firm=firm,
            record=record,
            context=context,
            outputs=outputs,
            evaluated_by=evaluated_by,
        )
    except Exception as exc:
        logger.exception(
            "Field change rule evaluation failed for record %s (field=%s)",
            record.id,
            field_key,
        )
        _log_field_change_rule_error(
            firm=firm,
            record=record,
            field_key=field_key,
            context=context,
            evaluated_by=evaluated_by,
            error=exc,
        )
        return {"blocking": [], "warnings": []}

    blocking = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.BLOCK
    ]
    warnings = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.WARNING
    ]
    return {
        "blocking": blocking,
        "warnings": warnings,
    }


def _evaluate_category_field_change_trigger(
    *,
    firm,
    record: PipelineRecord,
    category_field_key: str,
    old_value: Any,
    new_value: Any,
    evaluated_by,
) -> dict[str, list[dict[str, Any]]]:
    from crm.condition_rules import evaluate_condition_rule_outputs

    context = _build_category_field_change_condition_context(
        record,
        category_field_key=category_field_key,
        old_value=old_value,
        new_value=new_value,
    )
    try:
        rules = _get_applicable_category_field_change_rules(
            firm=firm,
            record=record,
        )
        outputs = evaluate_condition_rule_outputs(rules, context)
        _log_category_field_change_rule_outputs(
            firm=firm,
            record=record,
            context=context,
            outputs=outputs,
            evaluated_by=evaluated_by,
        )
    except Exception as exc:
        logger.exception(
            "Category field change rule evaluation failed for record %s (field=%s)",
            record.id,
            category_field_key,
        )
        _log_category_field_change_rule_error(
            firm=firm,
            record=record,
            category_field_key=category_field_key,
            context=context,
            evaluated_by=evaluated_by,
            error=exc,
        )
        return {"blocking": [], "warnings": []}

    blocking = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.BLOCK
    ]
    warnings = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.WARNING
    ]
    return {
        "blocking": blocking,
        "warnings": warnings,
    }


def _activity_to_condition_snapshot(activity: Activity) -> dict[str, Any]:
    metadata = activity.metadata if isinstance(activity.metadata, Mapping) else {}
    tool_type = metadata.get("tool_type") if isinstance(metadata, Mapping) else None
    return {
        "id": str(activity.id),
        "type": activity.type,
        "tool_type": tool_type,
        "entity_type": activity.entity_type,
        "entity_id": activity.entity_id,
        "record_id": str(activity.record_id) if activity.record_id else None,
        "customer_id": str(activity.customer_id) if activity.customer_id else None,
        "proposal_id": str(activity.proposal_id) if activity.proposal_id else None,
        "task_id": str(activity.task_id) if activity.task_id else None,
        "created_at": _to_json_compatible_value(activity.created_at),
    }


def _extend_context_with_activity_snapshots(
    context: dict[str, Any],
    activity_snapshots: list[dict[str, Any]] | None,
):
    if not activity_snapshots:
        return

    existing_activities = context.get("activities")
    activities: list[dict[str, Any]] = []
    if isinstance(existing_activities, list):
        activities = [item for item in existing_activities if isinstance(item, Mapping)]

    seen_signatures = {
        (
            str(item.get("type") or ""),
            str(item.get("entity_type") or ""),
            str(item.get("record_id") or ""),
            str(item.get("customer_id") or ""),
            str(item.get("proposal_id") or ""),
            str(item.get("task_id") or ""),
            str(item.get("tool_type") or ""),
            str(item.get("created_at") or ""),
        )
        for item in activities
    }
    for snapshot in activity_snapshots:
        signature = (
            str(snapshot.get("type") or ""),
            str(snapshot.get("entity_type") or ""),
            str(snapshot.get("record_id") or ""),
            str(snapshot.get("customer_id") or ""),
            str(snapshot.get("proposal_id") or ""),
            str(snapshot.get("task_id") or ""),
            str(snapshot.get("tool_type") or ""),
            str(snapshot.get("created_at") or ""),
        )
        if signature in seen_signatures:
            continue
        activities.append(snapshot)
        seen_signatures.add(signature)
    context["activities"] = activities


def _build_streamline_activity_condition_context(
    record: PipelineRecord,
    *,
    activity: Activity,
) -> dict[str, Any]:
    from crm.condition_rules import RecordConditionContextBuilder

    context = RecordConditionContextBuilder().build(record)
    activity_snapshot = _activity_to_condition_snapshot(activity)
    context["streamline_event"] = activity_snapshot
    if str(activity.record_id or "") != str(record.id):
        _extend_context_with_activity_snapshots(context, [activity_snapshot])
    return context


def _get_applicable_streamline_activity_rules(
    *,
    firm,
    record: PipelineRecord,
    activity_type: str,
) -> list[ConditionRule]:
    rules = (
        ConditionRule.objects
        .filter(
            firm=firm,
            is_active=True,
            trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
        )
        .filter(Q(activity_type="") | Q(activity_type=activity_type))
        .order_by("priority", "created_at", "id")
    )

    applicable: list[ConditionRule] = []
    record_category_id = str(record.category_id) if record.category_id else None
    current_stage_id = str(record.current_stage_id) if record.current_stage_id else None
    for rule in rules:
        scope_type = rule.scope_type
        if scope_type == ConditionScopeType.FIRM:
            applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.CATEGORY:
            if rule.category_id and str(rule.category_id) == record_category_id:
                applicable.append(rule)
            continue
        if scope_type == ConditionScopeType.STAGE:
            if rule.stage_id and str(rule.stage_id) == current_stage_id:
                applicable.append(rule)
            continue
    return applicable


def _log_streamline_activity_rule_outputs(
    *,
    firm,
    record: PipelineRecord,
    context: dict[str, Any],
    outputs: list[dict[str, Any]],
    evaluated_by,
):
    compact_context = {
        "record_id": str(record.id),
        "category_id": str(record.category_id) if record.category_id else None,
        "current_stage_id": str(record.current_stage_id) if record.current_stage_id else None,
        "streamline_event": _to_json_compatible_value(context.get("streamline_event", {})),
    }
    if not outputs:
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
            input_context=compact_context,
            result=RuleEvaluationResult.PASSED,
            messages=[],
            recommendations=[],
            evaluated_by=evaluated_by,
        )
        return

    for output in outputs:
        effect = output.get("effect")
        if effect == ConditionEffectType.BLOCK:
            result = RuleEvaluationResult.BLOCKED
        elif effect == ConditionEffectType.WARNING:
            result = RuleEvaluationResult.WARNING
        elif effect == ConditionEffectType.ACTIVATE_SCENARIO:
            result = RuleEvaluationResult.SCENARIO_ACTIVATED
        elif effect == ConditionEffectType.COMPLETE_REQUIREMENT:
            result = RuleEvaluationResult.REQUIREMENT_COMPLETED
        else:
            result = RuleEvaluationResult.PASSED

        effect_config = output.get("effect_config")
        message = ""
        if isinstance(effect_config, dict):
            message = str(effect_config.get("message") or "")
        recommendations: list[dict[str, Any]] = []
        if effect == ConditionEffectType.RECOMMENDATION and isinstance(effect_config, dict):
            recommendations = [effect_config]
        RuleEvaluationLog.objects.create(
            firm=firm,
            record=record,
            rule_id=output.get("rule_id"),
            trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
            input_context=compact_context,
            result=result,
            messages=[message] if message else [],
            recommendations=recommendations,
            evaluated_by=evaluated_by,
        )


def _log_streamline_activity_rule_error(
    *,
    firm,
    record: PipelineRecord,
    context: dict[str, Any],
    evaluated_by,
    error: Exception,
):
    RuleEvaluationLog.objects.create(
        firm=firm,
        record=record,
        trigger_type=ConditionTriggerType.STREAMLINE_ACTIVITY_CREATED,
        input_context={
            "record_id": str(record.id),
            "streamline_event": _to_json_compatible_value(context.get("streamline_event", {})),
        },
        result=RuleEvaluationResult.ERROR,
        messages=[],
        recommendations=[],
        error_message=str(error),
        evaluated_by=evaluated_by,
    )


def _evaluate_streamline_activity_trigger(
    *,
    firm,
    record: PipelineRecord,
    activity: Activity,
    evaluated_by,
) -> dict[str, list[dict[str, Any]]]:
    from crm.condition_rules import evaluate_condition_rule_outputs

    context = _build_streamline_activity_condition_context(record, activity=activity)
    try:
        rules = _get_applicable_streamline_activity_rules(
            firm=firm,
            record=record,
            activity_type=activity.type,
        )
        outputs = evaluate_condition_rule_outputs(rules, context)
        _log_streamline_activity_rule_outputs(
            firm=firm,
            record=record,
            context=context,
            outputs=outputs,
            evaluated_by=evaluated_by,
        )
    except Exception as exc:
        logger.exception(
            "Streamline activity rule evaluation failed for record %s (activity=%s): %s",
            record.id,
            activity.id,
            exc,
        )
        _log_streamline_activity_rule_error(
            firm=firm,
            record=record,
            context=context,
            evaluated_by=evaluated_by,
            error=exc,
        )
        return {"blocking": [], "warnings": []}

    blocking = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.BLOCK
    ]
    warnings = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.WARNING
    ]
    return {
        "blocking": blocking,
        "warnings": warnings,
    }


def _resolve_records_for_streamline_activity(
    *,
    firm,
    record: PipelineRecord | None = None,
    customer: Customer | None = None,
    proposal: Proposal | None = None,
    task: Task | None = None,
) -> list[PipelineRecord]:
    records_by_id: dict[str, PipelineRecord] = {}

    def _add(candidate: PipelineRecord | None):
        if candidate is None:
            return
        if str(candidate.firm_id) != str(firm.id):
            return
        records_by_id[str(candidate.id)] = candidate

    _add(record)
    if proposal and proposal.record_id:
        _add(proposal.record)
    if task:
        if task.record_id:
            _add(task.record)
        elif task.proposal_id and task.proposal and task.proposal.record_id:
            _add(task.proposal.record)

    customer_ids: set[str] = set()
    if customer:
        customer_ids.add(str(customer.id))
    if proposal and proposal.customer_id:
        customer_ids.add(str(proposal.customer_id))
    if task and task.customer_id:
        customer_ids.add(str(task.customer_id))
    if task and task.proposal_id and task.proposal and task.proposal.customer_id:
        customer_ids.add(str(task.proposal.customer_id))

    if customer_ids:
        customer_records = PipelineRecord.objects.filter(
            firm=firm,
            customer_id__in=customer_ids,
        )
        for customer_record in customer_records:
            _add(customer_record)

    return list(records_by_id.values())


def _run_streamline_activity_created_hooks(
    *,
    firm,
    activity: Activity,
    evaluated_by,
    record: PipelineRecord | None = None,
    customer: Customer | None = None,
    proposal: Proposal | None = None,
    task: Task | None = None,
):
    impacted_records = _resolve_records_for_streamline_activity(
        firm=firm,
        record=record,
        customer=customer,
        proposal=proposal,
        task=task,
    )
    if not impacted_records:
        return

    activity_snapshot = _activity_to_condition_snapshot(activity)
    activity_record_id = str(activity.record_id) if activity.record_id else None
    for impacted_record in impacted_records:
        _evaluate_streamline_activity_trigger(
            firm=firm,
            record=impacted_record,
            activity=activity,
            evaluated_by=evaluated_by,
        )
        additional_activities = None
        if activity_record_id != str(impacted_record.id):
            additional_activities = [activity_snapshot]
        _refresh_active_stage_scenario(
            impacted_record,
            additional_activities=additional_activities,
        )


def _refresh_active_stage_scenario(
    record: PipelineRecord,
    *,
    additional_activities: list[dict[str, Any]] | None = None,
):
    from crm.condition_rules import ConditionTreeEvaluator

    existing_extra_data = dict(record.extra_data or {})
    extra_data = dict(existing_extra_data)
    if not record.category_id or not record.current_stage_id:
        if "active_stage_scenario_id" in extra_data or "active_stage_requirements" in extra_data:
            extra_data.pop("active_stage_scenario_id", None)
            extra_data.pop("active_stage_requirements", None)
            record.extra_data = extra_data
            record.save(update_fields=["extra_data"])
        return

    context = _build_stage_change_condition_context(
        record,
        from_stage_id=record.current_stage_id,
        to_stage_id=record.current_stage_id,
    )
    _extend_context_with_activity_snapshots(context, additional_activities)
    evaluator = ConditionTreeEvaluator()
    active_scenario: Optional[StageScenario] = None
    active_scenario_id: str | None = None
    scenarios = (
        StageScenario.objects
        .filter(
            firm=record.firm,
            category_id=record.category_id,
            stage_id=record.current_stage_id,
            is_active=True,
        )
        .prefetch_related("requirements")
        .order_by("priority", "created_at", "id")
    )
    for scenario in scenarios:
        tree = scenario.activation_condition
        is_active = True if tree in (None, {}) else evaluator.evaluate(tree, context)
        if is_active:
            active_scenario = scenario
            active_scenario_id = str(scenario.id)
            break

    if active_scenario_id and active_scenario:
        extra_data["active_stage_scenario_id"] = active_scenario_id
        requirement_items: list[dict[str, Any]] = []
        requirements = active_scenario.requirements.all().order_by("sort_order", "created_at", "id")
        for requirement in requirements:
            tree = requirement.condition
            is_met = True if tree in (None, {}) else evaluator.evaluate(tree, context)
            references = _extract_requirement_references(tree)
            requirement_items.append(
                {
                    "id": str(requirement.id),
                    "name": requirement.name,
                    "requirement_type": requirement.requirement_type,
                    "blocking": requirement.blocking,
                    "visible_to_user": requirement.visible_to_user,
                    "is_met": is_met,
                    "relevant_field_key": references["relevant_field_key"],
                    "relevant_activity_type": references["relevant_activity_type"],
                    "relevant_tool_type": references["relevant_tool_type"],
                }
            )
        if requirement_items:
            extra_data["active_stage_requirements"] = requirement_items
        else:
            extra_data.pop("active_stage_requirements", None)
    else:
        extra_data.pop("active_stage_scenario_id", None)
        extra_data.pop("active_stage_requirements", None)

    if extra_data != existing_extra_data:
        record.extra_data = extra_data
        record.save(update_fields=["extra_data"])


def _extract_requirement_references(condition_tree: Any) -> dict[str, str | None]:
    """Extract lightweight field/activity references from a requirement condition tree.

    The output is intentionally simple and UI-oriented so the record detail view can
    present contextual links (jump to field / jump to activity) without additional
    privileged API calls.

    Args:
        condition_tree: Requirement condition tree (leaf or nested group structure).

    Returns:
        Dict with keys:
            - relevant_field_key: Standard/category field key if detected, else None.
            - relevant_activity_type: Activity type if detected, else None.
            - relevant_tool_type: Streamline tool type if detected, else None.
    """
    references: dict[str, str | None] = {
        "relevant_field_key": None,
        "relevant_activity_type": None,
        "relevant_tool_type": None,
    }
    category_fields_prefix = "category_fields."

    def visit(node: Any):
        if not isinstance(node, (dict, list)):
            return
        if isinstance(node, list):
            for child in node:
                visit(child)
            return

        raw_source_type = node.get("source_type")
        source_type = raw_source_type.strip().lower() if isinstance(raw_source_type, str) else ""
        field_key: str | None = None
        if source_type in {"category_field", "category_field_change"}:
            key = node.get("category_field_key") or node.get("field") or node.get("path")
            if isinstance(key, str):
                field_key = key.removeprefix(category_fields_prefix)
        elif source_type in {"field", "field_change", "record_field_change"}:
            key = node.get("field") or node.get("path")
            if isinstance(key, str):
                field_key = key
        elif not source_type:
            key = node.get("field") or node.get("path")
            if isinstance(key, str) and "." not in key:
                field_key = key

        if references["relevant_field_key"] is None and field_key:
            references["relevant_field_key"] = field_key

        if references["relevant_activity_type"] is None and source_type in {"activity", "streamline_activity"}:
            activity_type = node.get("activity_type")
            if not activity_type:
                activity_type = node.get("value")
            if isinstance(activity_type, str) and activity_type:
                references["relevant_activity_type"] = activity_type

        if references["relevant_tool_type"] is None and source_type == "streamline_tool":
            tool_type = node.get("tool_type")
            if not tool_type:
                tool_type = node.get("value")
            if isinstance(tool_type, str) and tool_type:
                references["relevant_tool_type"] = tool_type

        nested_children = node.get("conditions") or node.get("children") or []
        if isinstance(nested_children, list):
            for child in nested_children:
                visit(child)
        nested_condition = node.get("condition")
        if nested_condition is not None:
            visit(nested_condition)

    visit(condition_tree)
    return references


def _run_post_stage_change_hooks(
    *,
    firm,
    record: PipelineRecord,
    old_stage_id: Any,
    evaluated_by,
) -> dict[str, list[dict[str, Any]]]:
    changed_eval = _evaluate_stage_change_trigger(
        firm=firm,
        record=record,
        trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGED,
        from_stage_id=old_stage_id,
        to_stage_id=record.current_stage_id,
        evaluated_by=evaluated_by,
        fail_closed=False,
    )
    _refresh_active_stage_scenario(record)
    return changed_eval


def _build_record_automation_context(record: PipelineRecord, firm) -> dict:
    """Build the evaluation context dict for automation rules fired from a Record event."""
    from firms.models import Membership
    from crm.condition_rules import RecordConditionContextBuilder

    customer_name = ""
    customer_email = ""
    if record.customer_id:
        try:
            # customer may already be loaded via select_related
            c = record.customer
            customer_name = f"{c.first_name} {c.last_name}".strip()
            customer_email = c.email or ""
        except Exception:  # noqa: BLE001
            pass

    assignee_email = ""
    assignee_name = ""
    if record.assigned_to_id:
        try:
            u = record.assigned_to
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
        "record_id": str(record.id),
        "record_title": record.title,
        "record_status": record.status,
        "record_source": record.source,
        "record_value": str(record.value) if record.value is not None else "",
        "firm_id": str(firm.pk),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "assignee_email": assignee_email,
        "assignee_name": assignee_name,
        "owner_email": owner_email,
        "condition_context": RecordConditionContextBuilder().build(record),
    }


def _build_task_automation_context(task, firm) -> dict:
    """Build the evaluation context dict for automation rules fired from a Task event.

    Args:
        task: A Task model instance (should have record, customer, assigned_to pre-fetched).
        firm: The Firm instance that owns the task.

    Returns:
        A dict with string values suitable for condition evaluation and template rendering.
        Keys: task_id, task_title, task_status, task_priority, record_id, record_title,
              firm_id, assignee_id,
              assignee_email, assignee_name, customer_name, customer_email, owner_email,
              due_date.
    """
    from firms.models import Membership

    record_id = str(task.record_id) if task.record_id else ""
    record_title = ""
    customer_name = ""
    customer_email = ""

    if task.record_id:
        try:
            rec = task.record
            record_title = rec.title or ""
            if rec.customer_id:
                c = rec.customer
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
        "record_id": record_id,
        "record_title": record_title,
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
    company_id: str = "",
    company_name: str = "",
    contact_person_id: str = "",
    value_min: Optional[Decimal] = None,
    value_max: Optional[Decimal] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    updated_after: Optional[datetime] = None,
    updated_before: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 20,
):
    try:
        require_permission(request, Permission.RECORD_VIEW)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    qs = filter_records_qs(PipelineRecord.objects.filter(firm=request.firm), request)
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
    if company_id:
        qs = qs.filter(company_id=company_id)
    if company_name:
        qs = qs.filter(company__company_name__icontains=company_name)
    if contact_person_id:
        qs = qs.filter(contact_person_id=contact_person_id)
    if updated_after:
        qs = qs.filter(updated_at__gte=updated_after)
    if updated_before:
        qs = qs.filter(updated_at__lte=updated_before)
    # Sorting
    _allowed_sort_fields = {'title', 'status', 'source', 'value', 'created_at', 'updated_at'}
    order_field = sort_by if sort_by in _allowed_sort_fields else 'created_at'
    if sort_dir == 'asc':
        qs = qs.order_by(order_field)
    else:
        qs = qs.order_by(f'-{order_field}')
    offset = (page - 1) * page_size
    records = list(qs.select_related('created_by', 'assigned_to', 'current_stage')[offset:offset + page_size])
    rules = list(RecordScoringRule.objects.filter(firm=request.firm))
    return 200, [_record_out(record, rules) for record in records]


@router.post("/records", auth=django_auth, response={201: RecordOut, 400: ErrorOut, 402: ErrorOut, 403: ErrorOut})
def create_record(request, payload: RecordIn):
    try:
        require_permission(request, Permission.RECORD_CREATE)
        require_active_subscription(request.firm)
        check_tier_limits(request.firm)
    except SubscriptionRequired as exc:
        return 402, {"detail": str(exc)}
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}
    except Exception as exc:
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

    record = PipelineRecord.objects.create(
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
    broadcast_event(firm=request.firm, event='record.created', payload=_record_out(record))

    # Fire workflow automation trigger: record_created
    from crm.tasks import evaluate_automation_rules
    _automation_ctx = _build_record_automation_context(record, request.firm)
    from django.db import transaction
    transaction.on_commit(
        lambda: evaluate_automation_rules.delay("record_created", str(request.firm.pk), _automation_ctx),
        robust=True,
    )

    return 201, _record_out(record)


@router.get("/records/{record_id}", auth=django_auth, response={200: RecordOut, 403: ErrorOut, 404: ErrorOut})
def get_record(request, record_id: str):
    try:
        require_permission(request, Permission.RECORD_VIEW)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = filter_records_qs(
            PipelineRecord.objects.select_related('created_by').filter(firm=request.firm),
            request,
        ).get(id=record_id)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}
    return 200, _record_out(record)


@router.patch("/records/{record_id}", auth=django_auth, response={200: RecordUpdateOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut})
def update_record(request, record_id: str, payload: RecordUpdateIn):
    try:
        require_permission(request, Permission.RECORD_EDIT)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    old_status = record.status
    old_stage_id = record.current_stage_id
    update_data = payload.dict(exclude_none=True)
    requested_field_keys = set(update_data.keys())
    old_category_fields = _extract_record_category_fields(record.extra_data)
    old_standard_field_values = {
        "title": record.title,
        "status": record.status,
        "source": record.source,
        "assigned_to_id": record.assigned_to_id,
        "value": record.value,
        "currency": record.currency,
        "customer_id": record.customer_id,
        "company_id": record.company_id,
        "contact_person_id": record.contact_person_id,
        "category_id": record.category_id,
        "current_stage_id": record.current_stage_id,
        "parent_id": record.parent_id,
        "start_date": record.start_date,
        "end_date": record.end_date,
        "expires_at": record.expires_at,
        "notes": record.notes,
    }
    requested_stage_eval: dict[str, list[dict[str, Any]]] = {"blocking": [], "warnings": []}
    changed_stage_eval: dict[str, list[dict[str, Any]]] = {"blocking": [], "warnings": []}
    field_change_eval: dict[str, dict[str, list[dict[str, Any]]]] = {}
    stage_change_performed = False

    # Handle status change — create an Activity in the same transaction
    new_status = update_data.pop("status", None)

    # Resolve FK overrides (company, contact_person, customer, assigned_to)
    # These cannot be set via setattr(record, "company_id", ...) reliably through
    # the loop below — we pop and resolve them explicitly.
    if "company_id" in update_data:
        cid = update_data.pop("company_id")
        if cid:
            try:
                record.company = Customer.objects.get(id=cid, firm=request.firm, type="company")
            except Customer.DoesNotExist:
                return 400, {"detail": "Company not found."}
        else:
            record.company = None

    if "contact_person_id" in update_data:
        cpid = update_data.pop("contact_person_id")
        if cpid:
            try:
                record.contact_person = Customer.objects.get(id=cpid, firm=request.firm)
            except Customer.DoesNotExist:
                return 400, {"detail": "Contact person not found."}
        else:
            record.contact_person = None

    if "customer_id" in update_data:
        cust_id = update_data.pop("customer_id")
        if cust_id:
            try:
                record.customer = Customer.objects.get(id=cust_id, firm=request.firm)
            except Customer.DoesNotExist:
                return 400, {"detail": "Customer not found."}
        else:
            record.customer = None

    if "category_id" in update_data:
        cat_id = update_data.pop("category_id")
        if cat_id:
            try:
                record.category = Category.objects.get(id=cat_id, firm=request.firm)
            except Category.DoesNotExist:
                return 400, {"detail": "Category not found."}
        else:
            record.category = None

    if "current_stage_id" in update_data:
        stage_id = update_data.pop("current_stage_id")
        if stage_id:
            try:
                stage = Stage.objects.get(id=stage_id)
                if record.category_id and stage.category_id != record.category_id:
                    return 400, {"detail": "Stage does not belong to the record's category."}
                if old_stage_id != stage.id:
                    stage_change_performed = True
                    requested_stage_eval = _evaluate_stage_change_trigger(
                        firm=request.firm,
                        record=record,
                        trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
                        from_stage_id=old_stage_id,
                        to_stage_id=stage.id,
                        evaluated_by=request.user,
                        fail_closed=True,
                    )
                    if requested_stage_eval["blocking"]:
                        return 400, {
                            "detail": "Stage change blocked by condition rules.",
                            "code": "stage_change_blocked",
                            "stage_change_evaluation": {
                                "requested": requested_stage_eval,
                            },
                        }
                record.current_stage = stage
            except Stage.DoesNotExist:
                return 400, {"detail": "Stage not found."}
        else:
            if old_stage_id is not None:
                stage_change_performed = True
                requested_stage_eval = _evaluate_stage_change_trigger(
                    firm=request.firm,
                    record=record,
                    trigger_type=ConditionTriggerType.RECORD_STAGE_CHANGE_REQUESTED,
                    from_stage_id=old_stage_id,
                    to_stage_id=None,
                    evaluated_by=request.user,
                    fail_closed=True,
                )
                if requested_stage_eval["blocking"]:
                    return 400, {
                        "detail": "Stage change blocked by condition rules.",
                        "code": "stage_change_blocked",
                        "stage_change_evaluation": {
                            "requested": requested_stage_eval,
                        },
                    }
            record.current_stage = None

    if "parent_id" in update_data:
        par_id = update_data.pop("parent_id")
        if par_id:
            try:
                record.parent = PipelineRecord.objects.get(id=par_id, firm=request.firm)
            except PipelineRecord.DoesNotExist:
                return 400, {"detail": "Parent record not found."}
        else:
            record.parent = None

    if "start_date" in update_data:
        sd = update_data.pop("start_date")
        if sd:
            try:
                record.start_date = dt.date.fromisoformat(sd)
            except ValueError:
                return 400, {"detail": "Invalid start_date format. Use YYYY-MM-DD."}
        else:
            record.start_date = None

    if "end_date" in update_data:
        ed = update_data.pop("end_date")
        if ed:
            try:
                record.end_date = dt.date.fromisoformat(ed)
            except ValueError:
                return 400, {"detail": "Invalid end_date format. Use YYYY-MM-DD."}
        else:
            record.end_date = None

    # Validate field values against CategoryField.validation_rules
    validation_err = _validate_record_field_rules(
        category_id=record.category_id,
        value=update_data.get("value"),
        notes=update_data.get("notes"),
        source=update_data.get("source"),
    )
    if validation_err:
        return 400, {"detail": validation_err}

    for field, value in update_data.items():
        setattr(record, field, value)

    changed_standard_fields: dict[str, dict[str, Any]] = {}
    changed_category_fields: dict[str, dict[str, Any]] = {}
    if new_status is not None and new_status != old_status:
        changed_standard_fields["status"] = {
            "old_value": old_status,
            "new_value": new_status,
        }

    for field_key in sorted(requested_field_keys - {"status"}):
        if field_key not in old_standard_field_values:
            continue
        old_value = old_standard_field_values[field_key]
        new_value = getattr(record, field_key)
        if old_value != new_value:
            changed_standard_fields[field_key] = {
                "old_value": old_value,
                "new_value": new_value,
            }

    if "extra_data" in requested_field_keys:
        new_category_fields = _extract_record_category_fields(record.extra_data)
        for category_field_key in sorted(set(old_category_fields.keys()) | set(new_category_fields.keys())):
            old_value = old_category_fields.get(category_field_key)
            new_value = new_category_fields.get(category_field_key)
            if old_value != new_value:
                changed_category_fields[category_field_key] = {
                    "old_value": old_value,
                    "new_value": new_value,
                }

    if changed_category_fields:
        if not record.category_id:
            return 400, {"detail": "Cannot update category fields when record has no category."}
        allowed_category_field_keys = set(
            CategoryField.objects
            .filter(category_id=record.category_id)
            .values_list("field_key", flat=True)
        )
        extra_data_update = update_data.get("extra_data")
        explicitly_updated_category_keys: set[str] = set()
        if isinstance(extra_data_update, Mapping):
            explicit_category_fields = extra_data_update.get("category_fields")
            if isinstance(explicit_category_fields, Mapping):
                explicitly_updated_category_keys = {str(key) for key in explicit_category_fields.keys()}

        invalid_keys = sorted(
            key for key in explicitly_updated_category_keys
            if key not in allowed_category_field_keys
        )
        if invalid_keys:
            return 400, {
                "detail": (
                    "Category field(s) not configured for the record category: "
                    + ", ".join(invalid_keys)
                ),
                "code": "invalid_category_field_key",
            }
        changed_category_fields = {
            key: values
            for key, values in changed_category_fields.items()
            if key in allowed_category_field_keys
        }

    with transaction.atomic():
        from crm.apps import set_current_user, clear_current_user
        set_current_user(request.user)
        try:
            if new_status and new_status != old_status:
                record.status = new_status
                record.save()
                if stage_change_performed:
                    changed_stage_eval = _run_post_stage_change_hooks(
                        firm=request.firm,
                        record=record,
                        old_stage_id=old_stage_id,
                        evaluated_by=request.user,
                    )
                Activity.objects.create(
                    record=record,
                    user=request.user,
                    type=ActivityType.STATUS_CHANGE,
                    metadata={
                        "old_status": old_status,
                        "new_status": new_status,
                    },
                )
                # Fire workflow automation trigger: record_status_change
                from crm.tasks import evaluate_automation_rules
                _automation_ctx = {
                    **_build_record_automation_context(record, request.firm),
                    "from_status": old_status,
                    "to_status": new_status,
                }
                transaction.on_commit(
                    lambda ctx=_automation_ctx: evaluate_automation_rules.delay(
                        "record_status_change", str(request.firm.pk), ctx
                    ),
                    robust=True,
                )
            else:
                record.save()
                if stage_change_performed:
                    changed_stage_eval = _run_post_stage_change_hooks(
                        firm=request.firm,
                        record=record,
                        old_stage_id=old_stage_id,
                        evaluated_by=request.user,
                    )
            if changed_standard_fields:
                for field_key, values in changed_standard_fields.items():
                    field_change_eval[field_key] = _evaluate_field_change_trigger(
                        firm=request.firm,
                        record=record,
                        field_key=field_key,
                        old_value=values.get("old_value"),
                        new_value=values.get("new_value"),
                        evaluated_by=request.user,
                    )
            if changed_category_fields:
                for category_field_key, values in changed_category_fields.items():
                    _evaluate_category_field_change_trigger(
                        firm=request.firm,
                        record=record,
                        category_field_key=category_field_key,
                        old_value=values.get("old_value"),
                        new_value=values.get("new_value"),
                        evaluated_by=request.user,
                    )
            if (changed_standard_fields or changed_category_fields) and not stage_change_performed:
                _refresh_active_stage_scenario(record)
        finally:
            clear_current_user()

    broadcast_event(firm=request.firm, event='record.updated', payload=_record_out(record))
    response = _record_out(record)
    if stage_change_performed:
        response["stage_change_evaluation"] = {
            "requested": requested_stage_eval,
            "changed": changed_stage_eval,
        }
    if field_change_eval:
        response["field_change_evaluation"] = field_change_eval
    return 200, response


@router.delete("/records/{record_id}", auth=django_auth, response={204: None, 403: ErrorOut, 404: ErrorOut})
def delete_record(request, record_id: str):
    try:
        require_permission(request, Permission.RECORD_DELETE)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    perform_soft_delete(record, request.user)
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
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    checkpoints = Checkpoint.objects.filter(record=record).order_by("date", "name")
    return 200, [_checkpoint_out(cp) for cp in checkpoints]


@router.post(
    "/records/{record_id}/checkpoints",
    auth=django_auth,
    response={201: CheckpointOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_checkpoint(request, record_id: str, payload: CheckpointIn):
    """Create a checkpoint for a record."""
    try:
        require_membership(request, min_role=InvitationRole.MEMBER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    date = None
    if payload.date:
        try:
            date = dt.date.fromisoformat(payload.date)
        except ValueError:
            return 400, {"detail": "Invalid date format. Use YYYY-MM-DD."}

    cp = Checkpoint.objects.create(
        record=record,
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
        require_membership(request, min_role=InvitationRole.MEMBER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        cp = Checkpoint.objects.get(id=checkpoint_id, record=record)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        cp = Checkpoint.objects.get(id=checkpoint_id, record=record)
    except Checkpoint.DoesNotExist:
        return 404, {"detail": "Checkpoint not found."}

    perform_soft_delete(cp, request.user)
    return 204, None

class ActivityOut(Schema):
    id: str
    entity_type: str
    entity_id: str
    # Kept for backwards-compatibility
    record_id: Optional[str]
    user_id: Optional[str]
    user_name: Optional[str]
    user_avatar_url: Optional[str] = None
    type: str
    content_text: str
    metadata: Dict[str, Any]
    is_internal: bool = False
    visibility: str = "public"
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
    visibility: Optional[str] = None


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
    visibility: str = "public"


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
        "record_id": str(a.record_id) if a.record_id else None,
        "user_id": str(a.user_id) if a.user_id else None,
        "user_name": _user_display_name(a.user),
        "user_avatar_url": avatar_url,
        "type": a.type,
        "content_text": a.content_text,
        "metadata": a.metadata,
        "is_internal": a.is_internal,
        "visibility": a.visibility,
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


@router.get("/records/{record_id}/activities", auth=django_auth, response={200: List[ActivityOut], 403: ErrorOut, 404: ErrorOut})
def list_activities(request, record_id: str, page: int = 1, page_size: int = 20):
    """Return the timeline for a Record, newest first (paginated)."""
    try:
        require_permission(request, Permission.RECORD_VIEW)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = filter_records_qs(
            PipelineRecord.objects.filter(firm=request.firm), request
        ).get(id=record_id)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    offset = (page - 1) * page_size
    activities = filter_activities_qs(
        Activity.objects.filter(record=record).select_related('user').prefetch_related('reactions'),
        request,
    ).order_by("-created_at")[offset:offset + page_size]
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
    Unified chronological feed for a Record — merges Activities and Tasks into
    one list sorted by ``created_at`` descending.

    Activities are the standard Streamline records (comments, calls, emails,
    file uploads, etc.).  Tasks are surfaced as rich cards so the user can see
    and interact with them inline without leaving the Record detail.

    Pagination works over the merged set — ``page_size`` items total per page.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    offset = (page - 1) * page_size

    # Fetch both sets — slightly over-fetch then merge & sort in Python.
    # For typical page sizes (20) this is negligible; for very active records
    # with thousands of entries a keyset-pagination approach would be better,
    # but that optimisation can be added later without breaking the contract.
    fetch_size = page_size * 2 + 10  # generous buffer for the merge window

    activities = list(
        Activity.objects.filter(record=record)
        .select_related("user")
        .prefetch_related("reactions")
        .order_by("-created_at")[:offset + fetch_size]
    )
    tasks = list(
        Task.objects.filter(record=record, is_archived=False)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
            visibility=payload.visibility,
        )
        tool.process_action(activity, entity, payload.model_dump(), context)
        try:
            _run_streamline_activity_created_hooks(
                firm=request.firm,
                activity=activity,
                evaluated_by=request.user,
                record=record,
                customer=customer,
                proposal=proposal,
                task=task,
            )
        except Exception as exc:
            logger.exception(
                "Post-create streamline condition hooks failed for activity %s: %s",
                activity.id,
                exc,
            )

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

    Works for activities attached to any entity (record, customer,
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
    is_admin = membership.is_admin_or_above
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

    if payload.visibility is not None:
        from crm.models import ActivityVisibility
        valid_values = {ActivityVisibility.PUBLIC, ActivityVisibility.RESTRICTED}
        if payload.visibility not in valid_values:
            return 400, {"detail": f"Invalid visibility value '{payload.visibility}'. Must be 'public' or 'restricted'."}
        activity.visibility = payload.visibility
        update_fields.append("visibility")

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
    record_id: Optional[str]
    record_title: Optional[str]
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
    record_id: Optional[str] = None
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
    record_id: Optional[str] = None


class CompleteTaskIn(Schema):
    follow_up: Optional[FollowUpTaskIn] = None


def _task_out(t: Task, requesting_user=None) -> dict:
    # Resolve record title (use cached select_related if available)
    record_id = None
    record_title = None
    if t.record_id:
        record_id = str(t.record_id)
        try:
            record_title = t.record.title
        except (AttributeError, Exception) as exc:
            logger.debug("Could not resolve record title for task %s: %s", t.id, exc)

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
        "record_id": record_id,
        "record_title": record_title,
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
    record_id: Optional[str]
    record_title: Optional[str]
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
        "record_id": str(t.record_id) if t.record_id else None,
        "record_title": t.record.title if t.record_id else None,
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

    is_admin = membership.is_admin_or_above

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
    record_id: Optional[str] = None,
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
        membership = require_permission(request, Permission.RECORD_VIEW)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    is_admin = membership.is_admin_or_above

    qs = filter_tasks_qs(
        Task.objects.filter(firm=request.firm).select_related(
            "record", "assigned_to", "completed_by", "created_by", "proposal", "customer",
        ),
        request,
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
    if record_id is not None:
        qs = qs.filter(record_id=record_id)
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
        require_permission(request, Permission.RECORD_CREATE)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    # Resolve optional entity links
    record = None
    if payload.record_id:
        try:
            record = PipelineRecord.objects.get(id=payload.record_id, firm=request.firm)
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
            record=record,
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

        # Log activity on the linked entity (record, customer, or proposal).
        # Mirrors the unified Streamline timeline contract: a TASK_ASSIGNED
        # event is emitted onto whichever entity owns the task so that the
        # entity's detail timeline shows it.
        primary_entity = record or customer or proposal
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
            if record:
                Activity.objects.create(
                    record=record,
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        # Log Activity on every linked entity (record, customer, proposal).
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
            follow_up_record = None
            if follow_up_data.record_id:
                try:
                    follow_up_record = PipelineRecord.objects.get(id=follow_up_data.record_id, firm=request.firm)
                except PipelineRecord.DoesNotExist:
                    pass
            else:
                follow_up_record = task.record

            follow_up_task = Task.objects.create(
                firm=request.firm,
                record=follow_up_record,
                assigned_to=follow_up_assigned_to,
                title=follow_up_data.title,
                description=follow_up_data.description,
                due_date=follow_up_data.due_date,
            )
            watcher_err = _set_task_watchers(follow_up_task, follow_up_data.watcher_ids, request.firm)
            if watcher_err:
                return watcher_err
            if follow_up_record:
                Activity.objects.create(
                    record=follow_up_record,
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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

    A task can be tied to several entities (record/customer/proposal).
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        membership = require_membership(request, min_role=InvitationRole.MEMBER)
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

    is_admin = membership.is_admin_or_above
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.ADMIN)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
    record_id: Optional[str] = None
    proposal_id: Optional[str] = None
    customer_id: Optional[str] = None


@router.post(
    "/tasks/{task_id}/move",
    auth=django_auth,
    response={200: TaskOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def move_task(request, task_id: str, payload: TaskMoveIn):
    """Move a task to a different entity (record/proposal/customer) or make it standalone."""
    try:
        require_membership(request, min_role=InvitationRole.MEMBER)
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

    if payload.record_id:
        try:
            task.record = PipelineRecord.objects.get(id=payload.record_id, firm=request.firm)
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

    task.save(update_fields=["record", "proposal", "customer"])
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
    required_role = InvitationRole.ADMIN if payload.action == "delete" else InvitationRole.MEMBER
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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

    is_admin = membership.is_admin_or_above
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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

    is_admin = membership.is_admin_or_above
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

    is_admin = membership.is_admin_or_above
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
    record_id: Optional[str] = None
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.ADMIN)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
    record = None
    if payload.record_id:
        try:
            record = PipelineRecord.objects.get(id=payload.record_id, firm=request.firm)
        except PipelineRecord.DoesNotExist:
            return 400, {"detail": "Record not found."}

    proposal = None
    if payload.proposal_id:
        try:
            proposal = Proposal.objects.get(id=payload.proposal_id, record__firm=request.firm)
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
            record=record,
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


class CurrencyBreakdownItem(Schema):
    currency: str
    value: float
    canonical_value: Optional[float] = None


class StatsOut(Schema):
    total_records: int
    records_by_status: Dict[str, int]
    total_customers: int
    total_tasks_pending: int
    total_tasks_overdue: int
    pipeline_value: float
    won_value: float
    conversion_rate: float
    recent_activities: List[ActivityOut]
    mixed_currencies: bool = False
    # ---- v2.3 dashboard extensions (all optional / backwards-compat) ----
    pipeline_value_canonical: float = 0.0
    won_value_canonical: float = 0.0
    canonical_currency: Optional[str] = None
    avg_cycle_days: Optional[float] = None
    created_in_range: int = 0
    won_in_range: int = 0
    lost_in_range: int = 0
    range: Optional[str] = None
    currency_breakdown: List[CurrencyBreakdownItem] = []


# Allowed ``range`` query param values for dashboard endpoints.
_RANGE_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "qtd": 90,   # quarter ≈ 90d for simplicity
    "ytd": None,  # special-cased below
    "all": None,
}


def _resolve_range(range_key: Optional[str]):
    """Return (since_datetime|None, normalized_key)."""
    key = (range_key or "all").lower()
    if key not in _RANGE_DAYS:
        key = "all"
    now = tz.now()
    if key == "ytd":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), key
    days = _RANGE_DAYS[key]
    if days is None:
        return None, key
    return now - dt.timedelta(days=days), key


@router.get("/stats", auth=django_auth, response={200: StatsOut, 403: ErrorOut})
def get_stats(
    request,
    range_: Optional[str] = Query(None, alias="range"),
    category_id: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    """Return aggregated stats for the current Firm.

    Optional query parameters:
      - ``range``  : 7d | 30d | 90d | qtd | ytd | all (default: all)
      - ``category_id`` : restrict to one ``Category`` (UUID).
      - ``owner_id``    : restrict to one ``assigned_to`` user (UUID or 'me').
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    now = tz.now()
    since, range_key = _resolve_range(range_)

    records_qs = PipelineRecord.objects.filter(firm=request.firm)
    if category_id:
        records_qs = records_qs.filter(category_id=category_id)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        records_qs = records_qs.filter(assigned_to_id=oid)

    status_counts = {s.value: 0 for s in RecordStatus}
    for row in records_qs.values("status").annotate(n=Count("id")):
        status_counts[row["status"]] = row["n"]

    default_currency = request.firm.default_currency
    same_currency_qs = records_qs.filter(currency=default_currency)
    mixed_currencies = records_qs.exclude(currency=default_currency).exists()

    open_q = ~Q(status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED])

    # Native (same-currency) totals (kept for backwards compat with old UI).
    pipeline_value = float(
        same_currency_qs.filter(open_q).aggregate(total=Sum("value"))["total"] or 0
    )
    won_value = float(
        same_currency_qs.filter(status=RecordStatus.WON).aggregate(total=Sum("value"))["total"] or 0
    )

    # Canonical totals across all currencies (mixed-currency safe).
    pipeline_value_canonical = float(
        records_qs.filter(open_q).aggregate(total=Sum("canonical_amount"))["total"] or 0
    )
    won_value_canonical = float(
        records_qs.filter(status=RecordStatus.WON)
        .aggregate(total=Sum("canonical_amount"))["total"] or 0
    )

    # Per-currency breakdown for tooltip display.
    breakdown: List[Dict[str, Any]] = []
    for row in (
        records_qs.filter(open_q)
        .values("currency")
        .annotate(value=Sum("value"), canonical=Sum("canonical_amount"))
    ):
        breakdown.append({
            "currency": row["currency"],
            "value": float(row["value"] or 0),
            "canonical_value": float(row["canonical"]) if row["canonical"] is not None else None,
        })

    total_records = records_qs.count()
    won_records = status_counts.get(RecordStatus.WON, 0)
    conversion_rate = round(won_records / total_records, 4) if total_records else 0.0

    # In-range deltas.
    if since is not None:
        in_range_qs = records_qs.filter(created_at__gte=since)
        created_in_range = in_range_qs.count()
    else:
        created_in_range = total_records

    if since is not None:
        won_in_range = records_qs.filter(
            status=RecordStatus.WON, updated_at__gte=since
        ).count()
        lost_in_range = records_qs.filter(
            status__in=[RecordStatus.LOST, RecordStatus.CANCELED],
            updated_at__gte=since,
        ).count()
    else:
        won_in_range = won_records
        lost_in_range = (
            status_counts.get(RecordStatus.LOST, 0)
            + status_counts.get(RecordStatus.CANCELED, 0)
        )

    # Average cycle time (created_at → updated_at on WON records, in days).
    won_records_qs = records_qs.filter(status=RecordStatus.WON)
    if since is not None:
        won_records_qs = won_records_qs.filter(updated_at__gte=since)
    avg_cycle_days: Optional[float] = None
    cycle_pairs = list(won_records_qs.values_list("created_at", "updated_at")[:1000])
    if cycle_pairs:
        total_seconds = sum((u - c).total_seconds() for c, u in cycle_pairs if u and c)
        if total_seconds > 0:
            avg_cycle_days = round(total_seconds / 86400.0 / len(cycle_pairs), 2)

    # Tasks (also scoped to owner if requested).
    tasks_qs = Task.objects.filter(firm=request.firm, is_completed=False)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        tasks_qs = tasks_qs.filter(assigned_to_id=oid)
    total_tasks_pending = tasks_qs.count()
    total_tasks_overdue = tasks_qs.filter(due_date__lt=now).count()

    total_customers = Customer.objects.filter(firm=request.firm).count()

    activities_qs = Activity.objects.filter(record__firm=request.firm)
    if category_id:
        activities_qs = activities_qs.filter(record__category_id=category_id)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        activities_qs = activities_qs.filter(record__assigned_to_id=oid)
    recent_activities = (
        activities_qs.select_related("record", "user").order_by("-created_at")[:10]
    )

    return 200, {
        "total_records": total_records,
        "records_by_status": status_counts,
        "total_customers": total_customers,
        "total_tasks_pending": total_tasks_pending,
        "total_tasks_overdue": total_tasks_overdue,
        "pipeline_value": pipeline_value,
        "won_value": won_value,
        "conversion_rate": conversion_rate,
        "recent_activities": [_activity_out(a) for a in recent_activities],
        "mixed_currencies": mixed_currencies,
        "pipeline_value_canonical": pipeline_value_canonical,
        "won_value_canonical": won_value_canonical,
        "canonical_currency": default_currency,
        "avg_cycle_days": avg_cycle_days,
        "created_in_range": created_in_range,
        "won_in_range": won_in_range,
        "lost_in_range": lost_in_range,
        "range": range_key,
        "currency_breakdown": breakdown,
    }


# ===========================================================================
# v2.3 — DASHBOARD WIDGET ENDPOINTS
# ===========================================================================
#
# These endpoints power the new pipeline-aware dashboard widgets.  All of them
# accept optional ``range`` / ``category_id`` / ``owner_id`` filters where
# meaningful and return canonical (firm default currency) money values.

class CategoryOverviewItem(Schema):
    category_id: str
    name: str
    icon: str = ""
    color: str = ""
    records_total: int
    records_open: int
    records_won: int
    value_open_canonical: float
    value_won_canonical: float
    win_rate: float
    sparkline: List[int]  # creations per day, last 30 days


class CategoryOverviewOut(Schema):
    canonical_currency: Optional[str] = None
    items: List[CategoryOverviewItem]
    uncategorized: Optional[CategoryOverviewItem] = None


@router.get(
    "/dashboard/category-overview",
    auth=django_auth,
    response={200: CategoryOverviewOut, 403: ErrorOut},
)
def get_dashboard_category_overview(
    request,
    range_: Optional[str] = Query(None, alias="range"),
    owner_id: Optional[str] = None,
):
    """Per-category aggregates for the dashboard ``category_overview`` widget."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    since, _ = _resolve_range(range_)
    sparkline_since = tz.now() - dt.timedelta(days=30)

    base_records = PipelineRecord.objects.filter(firm=request.firm)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        base_records = base_records.filter(assigned_to_id=oid)
    if since is not None:
        # ``range`` filters the *active* / time-bound aggregates; sparkline is
        # always last 30 days regardless.
        scoped_records = base_records.filter(created_at__gte=since)
    else:
        scoped_records = base_records

    open_q = ~Q(status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED])

    def _build_item(category, qs):
        total = qs.count()
        won = qs.filter(status=RecordStatus.WON).count()
        win_rate = round(won / total, 4) if total else 0.0
        value_open = float(qs.filter(open_q).aggregate(t=Sum("canonical_amount"))["t"] or 0)
        value_won = float(qs.filter(status=RecordStatus.WON).aggregate(t=Sum("canonical_amount"))["t"] or 0)
        # Sparkline (30 days, count of created records per day).
        spark_days = [0] * 30
        spark_qs = qs.filter(created_at__gte=sparkline_since).values_list("created_at", flat=True)
        for created in spark_qs:
            day_idx = (created.date() - sparkline_since.date()).days
            if 0 <= day_idx < 30:
                spark_days[day_idx] += 1
        return {
            "category_id": str(category.id) if category else "",
            "name": category.name if category else "—",
            "icon": getattr(category, "icon", "") or "",
            "color": getattr(category, "color", "") or "",
            "records_total": total,
            "records_open": qs.filter(open_q).count(),
            "records_won": won,
            "value_open_canonical": value_open,
            "value_won_canonical": value_won,
            "win_rate": win_rate,
            "sparkline": spark_days,
        }

    items: List[Dict[str, Any]] = []
    for cat in Category.objects.filter(firm=request.firm, is_active=True).order_by("order", "name"):
        items.append(_build_item(cat, scoped_records.filter(category=cat)))

    uncat_qs = scoped_records.filter(category__isnull=True)
    uncategorized = _build_item(None, uncat_qs) if uncat_qs.exists() else None

    return 200, {
        "canonical_currency": request.firm.default_currency,
        "items": items,
        "uncategorized": uncategorized,
    }


class StageFunnelStage(Schema):
    stage_id: str
    name: str
    color: str = ""
    is_terminal: bool = False
    is_won: bool = False
    order: int
    count: int
    value_canonical: float
    conversion_to_next: Optional[float] = None  # ratio 0..1, null for last stage


class StageFunnelOut(Schema):
    category_id: Optional[str]
    category_name: Optional[str]
    canonical_currency: Optional[str] = None
    stages: List[StageFunnelStage]


@router.get(
    "/dashboard/stage-funnel",
    auth=django_auth,
    response={200: StageFunnelOut, 403: ErrorOut, 404: ErrorOut},
)
def get_dashboard_stage_funnel(
    request,
    category_id: Optional[str] = None,
    range_: Optional[str] = Query(None, alias="range"),
    owner_id: Optional[str] = None,
):
    """Stage-by-stage funnel for the chosen ``Category``.

    If ``category_id`` is omitted, the first active category for the firm is
    used (or returns an empty funnel if none exist).
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if category_id:
        category = Category.objects.filter(firm=request.firm, id=category_id).first()
        if category is None:
            return 404, {"detail": "Category not found."}
    else:
        category = (
            Category.objects.filter(firm=request.firm, is_active=True)
            .order_by("order", "name")
            .first()
        )

    if category is None:
        return 200, {
            "category_id": None,
            "category_name": None,
            "canonical_currency": request.firm.default_currency,
            "stages": [],
        }

    since, _ = _resolve_range(range_)
    records_qs = PipelineRecord.objects.filter(firm=request.firm, category=category)
    if since is not None:
        records_qs = records_qs.filter(created_at__gte=since)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        records_qs = records_qs.filter(assigned_to_id=oid)

    stages = list(category.stages.all().order_by("order"))
    stage_data: List[Dict[str, Any]] = []
    counts: List[int] = []
    for st in stages:
        qs = records_qs.filter(current_stage=st)
        c = qs.count()
        v = float(qs.aggregate(t=Sum("canonical_amount"))["t"] or 0)
        counts.append(c)
        stage_data.append({
            "stage_id": str(st.id),
            "name": st.label or st.name,
            "color": st.color or "",
            "is_terminal": st.is_terminal,
            "is_won": st.is_won,
            "order": st.order,
            "count": c,
            "value_canonical": v,
            "conversion_to_next": None,
        })

    # Conversion = count(next) / count(self) (clamped 0..1).
    for i in range(len(stage_data) - 1):
        if counts[i] > 0:
            stage_data[i]["conversion_to_next"] = round(min(counts[i + 1] / counts[i], 1.0), 4)

    return 200, {
        "category_id": str(category.id),
        "category_name": category.name,
        "canonical_currency": request.firm.default_currency,
        "stages": stage_data,
    }


class TrendPoint(Schema):
    date: str  # ISO date YYYY-MM-DD
    value: float


class TrendOut(Schema):
    metric: str
    range: str
    canonical_currency: Optional[str] = None
    points: List[TrendPoint]


@router.get(
    "/dashboard/trend",
    auth=django_auth,
    response={200: TrendOut, 403: ErrorOut},
)
def get_dashboard_trend(
    request,
    metric: str = "created",
    range_: Optional[str] = Query(None, alias="range"),
    category_id: Optional[str] = None,
    owner_id: Optional[str] = None,
):
    """Time-series for the ``pipeline_trend`` widget.

    ``metric`` ∈ {created, won, lost, value_won, value_pipeline, activities}.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    valid_metrics = {"created", "won", "lost", "value_won", "value_pipeline", "activities"}
    if metric not in valid_metrics:
        metric = "created"

    since, range_key = _resolve_range(range_)
    if since is None:
        since = tz.now() - dt.timedelta(days=30)
        range_key = "30d"

    days = max(1, (tz.now().date() - since.date()).days + 1)
    points: List[Dict[str, Any]] = [
        {"date": (since.date() + dt.timedelta(days=i)).isoformat(), "value": 0.0}
        for i in range(days)
    ]
    index_for = {p["date"]: i for i, p in enumerate(points)}

    records_qs = PipelineRecord.objects.filter(firm=request.firm)
    if category_id:
        records_qs = records_qs.filter(category_id=category_id)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        records_qs = records_qs.filter(assigned_to_id=oid)

    if metric == "created":
        rows = records_qs.filter(created_at__gte=since).values_list("created_at", flat=True)
        for ts in rows:
            key = ts.date().isoformat()
            if key in index_for:
                points[index_for[key]]["value"] += 1
    elif metric == "won":
        rows = records_qs.filter(status=RecordStatus.WON, updated_at__gte=since).values_list("updated_at", flat=True)
        for ts in rows:
            key = ts.date().isoformat()
            if key in index_for:
                points[index_for[key]]["value"] += 1
    elif metric == "lost":
        rows = records_qs.filter(
            status__in=[RecordStatus.LOST, RecordStatus.CANCELED], updated_at__gte=since
        ).values_list("updated_at", flat=True)
        for ts in rows:
            key = ts.date().isoformat()
            if key in index_for:
                points[index_for[key]]["value"] += 1
    elif metric == "value_won":
        rows = records_qs.filter(
            status=RecordStatus.WON, updated_at__gte=since
        ).values_list("updated_at", "canonical_amount")
        for ts, amt in rows:
            key = ts.date().isoformat()
            if key in index_for and amt is not None:
                points[index_for[key]]["value"] += float(amt)
    elif metric == "value_pipeline":
        # Snapshot of current pipeline value per "creation date" bucket
        # (interpretation: cumulative pipeline value as of each day).
        rows = list(
            records_qs.exclude(status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED])
            .order_by("created_at")
            .values_list("created_at", "canonical_amount")
        )
        for ts, amt in rows:
            key = ts.date().isoformat()
            if amt is None:
                continue
            if key in index_for:
                points[index_for[key]]["value"] += float(amt)
        # Convert to running total
        for i in range(1, len(points)):
            points[i]["value"] += points[i - 1]["value"]
    elif metric == "activities":
        act_qs = Activity.objects.filter(record__firm=request.firm, created_at__gte=since)
        if category_id:
            act_qs = act_qs.filter(record__category_id=category_id)
        if owner_id:
            oid = request.user.id if owner_id == "me" else owner_id
            act_qs = act_qs.filter(record__assigned_to_id=oid)
        for ts in act_qs.values_list("created_at", flat=True):
            key = ts.date().isoformat()
            if key in index_for:
                points[index_for[key]]["value"] += 1

    return 200, {
        "metric": metric,
        "range": range_key,
        "canonical_currency": request.firm.default_currency,
        "points": points,
    }


class MyDayTask(Schema):
    id: str
    kind: str  # "task" | "checkpoint"
    title: str
    record_id: Optional[str] = None
    record_title: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    is_completed: bool = False


class MyDayOut(Schema):
    overdue: List[MyDayTask]
    today: List[MyDayTask]
    this_week: List[MyDayTask]


@router.get(
    "/dashboard/my-day",
    auth=django_auth,
    response={200: MyDayOut, 403: ErrorOut},
)
def get_dashboard_my_day(request):
    """Tasks + checkpoints for the current user, bucketed by due-date."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    now = tz.now()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    week_end = today_end + dt.timedelta(days=7)

    overdue: List[Dict[str, Any]] = []
    today: List[Dict[str, Any]] = []
    this_week: List[Dict[str, Any]] = []

    # Tasks assigned to the current user.
    tasks = (
        Task.objects.filter(
            firm=request.firm, assigned_to=request.user, is_completed=False
        )
        .select_related("record")
        .order_by("due_date")
    )
    for t in tasks:
        item = {
            "id": str(t.id),
            "kind": "task",
            "title": t.title,
            "record_id": str(t.record_id) if getattr(t, "record_id", None) else None,
            "record_title": getattr(t.record, "title", None) if getattr(t, "record", None) else None,
            "due_date": t.due_date,
            "priority": t.priority,
            "is_completed": t.is_completed,
        }
        if t.due_date is None:
            this_week.append(item)
        elif t.due_date < now:
            overdue.append(item)
        elif t.due_date <= today_end:
            today.append(item)
        elif t.due_date <= week_end:
            this_week.append(item)

    # Checkpoints on records assigned to the current user.
    cps = (
        Checkpoint.objects.filter(
            record__firm=request.firm,
            record__assigned_to=request.user,
            is_completed=False,
        )
        .select_related("record")
    )
    for cp in cps:
        if cp.date is None:
            continue
        cp_due = dt.datetime.combine(cp.date, dt.time(23, 59, 0), tzinfo=now.tzinfo)
        item = {
            "id": str(cp.id),
            "kind": "checkpoint",
            "title": cp.name,
            "record_id": str(cp.record_id),
            "record_title": cp.record.title if cp.record else None,
            "due_date": cp_due,
            "priority": None,
            "is_completed": cp.is_completed,
        }
        if cp_due < now:
            overdue.append(item)
        elif cp_due <= today_end:
            today.append(item)
        elif cp_due <= week_end:
            this_week.append(item)

    overdue.sort(key=lambda x: x["due_date"] or now)
    today.sort(key=lambda x: x["due_date"] or now)
    this_week.sort(key=lambda x: x["due_date"] or now)

    return 200, {"overdue": overdue, "today": today, "this_week": this_week}


class StaleRecordItem(Schema):
    id: str
    title: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    stage_id: Optional[str] = None
    stage_name: Optional[str] = None
    status: str
    value_canonical: Optional[float] = None
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    days_since_activity: int


class StaleRecordsOut(Schema):
    threshold_days: int
    items: List[StaleRecordItem]


@router.get(
    "/dashboard/stale-records",
    auth=django_auth,
    response={200: StaleRecordsOut, 403: ErrorOut},
)
def get_dashboard_stale_records(
    request,
    days: int = 14,
    category_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    limit: int = 20,
):
    """Records whose last activity is older than ``days`` (or none at all)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    days = max(1, min(int(days or 14), 365))
    limit = max(1, min(int(limit or 20), 100))
    threshold = tz.now() - dt.timedelta(days=days)

    qs = (
        PipelineRecord.objects.filter(firm=request.firm)
        .exclude(status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED])
        .select_related("category", "current_stage", "assigned_to")
    )
    if category_id:
        qs = qs.filter(category_id=category_id)
    if owner_id:
        oid = request.user.id if owner_id == "me" else owner_id
        qs = qs.filter(assigned_to_id=oid)

    # Annotate with last activity timestamp; fall back to record's updated_at.
    qs = qs.annotate(last_activity=Max("activities__created_at"))
    qs = qs.filter(Q(last_activity__lt=threshold) | Q(last_activity__isnull=True))
    qs = qs.order_by("last_activity", "updated_at")[:limit]

    now = tz.now()
    items: List[Dict[str, Any]] = []
    for r in qs:
        last = r.last_activity or r.updated_at
        days_since = max(0, (now - last).days) if last else days
        items.append({
            "id": str(r.id),
            "title": r.title,
            "category_id": str(r.category_id) if r.category_id else None,
            "category_name": r.category.name if r.category else None,
            "stage_id": str(r.current_stage_id) if r.current_stage_id else None,
            "stage_name": (r.current_stage.label or r.current_stage.name) if r.current_stage else None,
            "status": r.status,
            "value_canonical": float(r.canonical_amount) if r.canonical_amount is not None else None,
            "assigned_to_id": str(r.assigned_to_id) if r.assigned_to_id else None,
            "assigned_to_name": _user_display_name(r.assigned_to),
            "last_activity_at": r.last_activity,
            "days_since_activity": days_since,
        })

    return 200, {"threshold_days": days, "items": items}


class CheckpointDashboardItem(Schema):
    id: str
    name: str
    date: Optional[str] = None  # ISO date
    is_completed: bool
    record_id: str
    record_title: str
    category_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    days_until: Optional[int] = None  # negative = overdue


class CheckpointsOut(Schema):
    items: List[CheckpointDashboardItem]


@router.get(
    "/dashboard/checkpoints",
    auth=django_auth,
    response={200: CheckpointsOut, 403: ErrorOut},
)
def get_dashboard_checkpoints(
    request,
    upcoming_days: int = 14,
    scope: str = "mine",  # "mine" | "firm"
):
    """Upcoming checkpoints for the current user (or whole firm if scope=firm)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    upcoming_days = max(1, min(int(upcoming_days or 14), 365))
    today = tz.now().date()
    horizon = today + dt.timedelta(days=upcoming_days)

    qs = (
        Checkpoint.objects.filter(record__firm=request.firm, is_completed=False)
        .select_related("record", "record__category", "record__assigned_to")
    )
    if scope != "firm":
        qs = qs.filter(record__assigned_to=request.user)
    # ``date <= horizon`` already covers overdue items because horizon ≥ today.
    # Checkpoints without a date are considered backlog and excluded here.
    qs = qs.filter(date__lte=horizon).order_by("date")[:100]

    items: List[Dict[str, Any]] = []
    for cp in qs:
        days_until = None
        if cp.date is not None:
            days_until = (cp.date - today).days
        items.append({
            "id": str(cp.id),
            "name": cp.name,
            "date": cp.date.isoformat() if cp.date else None,
            "is_completed": cp.is_completed,
            "record_id": str(cp.record_id),
            "record_title": cp.record.title if cp.record else "",
            "category_name": cp.record.category.name if cp.record and cp.record.category else None,
            "assigned_to_name": _user_display_name(cp.record.assigned_to) if cp.record else None,
            "days_until": days_until,
        })
    return 200, {"items": items}


class LeaderboardEntry(Schema):
    user_id: str
    name: str
    won_count: int
    won_value_canonical: float
    activities_count: int
    records_open: int


class TeamLeaderboardOut(Schema):
    range: str
    canonical_currency: Optional[str] = None
    entries: List[LeaderboardEntry]


@router.get(
    "/dashboard/team-leaderboard",
    auth=django_auth,
    response={200: TeamLeaderboardOut, 403: ErrorOut},
)
def get_dashboard_team_leaderboard(
    request,
    range_: Optional[str] = Query(None, alias="range"),
):
    """Per-user aggregates for the ``team_leaderboard`` widget (admin only)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    membership = Membership.objects.filter(user=request.user, firm=request.firm).first()
    if membership is None or not membership.is_admin_or_above:
        return 403, {"detail": "Admin access required."}

    since, range_key = _resolve_range(range_)

    members = (
        Membership.objects.filter(firm=request.firm)
        .select_related("user")
    )

    entries: List[Dict[str, Any]] = []
    for m in members:
        u = m.user
        if u is None:
            continue

        records_qs = PipelineRecord.objects.filter(firm=request.firm, assigned_to=u)
        won_qs = records_qs.filter(status=RecordStatus.WON)
        if since is not None:
            won_qs = won_qs.filter(updated_at__gte=since)

        won_count = won_qs.count()
        won_value = float(won_qs.aggregate(t=Sum("canonical_amount"))["t"] or 0)
        records_open = records_qs.exclude(
            status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED]
        ).count()

        act_qs = Activity.objects.filter(record__firm=request.firm, user=u)
        if since is not None:
            act_qs = act_qs.filter(created_at__gte=since)
        activities_count = act_qs.count()

        entries.append({
            "user_id": str(u.id),
            "name": _user_display_name(u) or u.email,
            "won_count": won_count,
            "won_value_canonical": won_value,
            "activities_count": activities_count,
            "records_open": records_open,
        })

    entries.sort(key=lambda e: (-e["won_value_canonical"], -e["won_count"]))

    return 200, {
        "range": range_key,
        "canonical_currency": request.firm.default_currency,
        "entries": entries,
    }


# ---------------------------------------------------------------------------
# /dashboard/focus-next
# ---------------------------------------------------------------------------

class FocusNextRecordOut(Schema):
    id: str
    title: str
    company_name: Optional[str] = None
    contact_person_name: Optional[str] = None
    value_canonical: Optional[float] = None
    status: str
    stage_name: Optional[str] = None
    category_name: Optional[str] = None
    assigned_to_name: Optional[str] = None
    days_since_activity: int
    score: Optional[int] = None


class FocusNextOut(Schema):
    record: Optional[FocusNextRecordOut] = None


@router.get(
    "/dashboard/focus-next",
    auth=django_auth,
    response={200: FocusNextOut, 403: ErrorOut},
)
def get_dashboard_focus_next(request):
    """Return the single highest-priority active record the user should focus on next."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    active_records = (
        PipelineRecord.objects.filter(
            firm=request.firm,
            assigned_to=request.user,
        )
        .exclude(status__in=[RecordStatus.WON, RecordStatus.LOST, RecordStatus.CANCELED])
        .select_related("category", "current_stage", "assigned_to", "contact_person")
    )

    today_start = tz.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = tz.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    records_with_open_task_today = Task.objects.filter(
        firm=request.firm,
        record__in=active_records,
        is_completed=False,
        due_date__gte=today_start,
        due_date__lte=today_end,
    ).values_list("record_id", flat=True)

    candidates = list(
        active_records.exclude(id__in=records_with_open_task_today)
    )

    if not candidates:
        return 200, {"record": None}

    now = tz.now()

    def _days_since(record):
        ref = getattr(record, "last_activity_at", None) or record.updated_at
        if ref is None:
            return 0
        return (now - ref).days

    def _sort_key(record):
        score = getattr(record, "score", None) or 0
        return (-score, -_days_since(record))

    candidates.sort(key=_sort_key)
    best = candidates[0]

    company = getattr(best, "company", None) or getattr(best, "customer", None)
    company_name = getattr(company, "name", None) if company else None
    contact = best.contact_person
    contact_name = _user_display_name(contact) if contact else None

    return 200, {
        "record": {
            "id": str(best.id),
            "title": best.title,
            "company_name": company_name,
            "contact_person_name": contact_name,
            "value_canonical": float(best.canonical_amount) if best.canonical_amount is not None else None,
            "status": best.status,
            "stage_name": best.current_stage.name if best.current_stage else None,
            "category_name": best.category.name if best.category else None,
            "assigned_to_name": _user_display_name(best.assigned_to),
            "days_since_activity": _days_since(best),
            "score": getattr(best, "score", None),
        }
    }


# ---------------------------------------------------------------------------
# /dashboard/recent-wins
# ---------------------------------------------------------------------------

class RecentWinItem(Schema):
    id: str
    title: str
    value_canonical: Optional[float] = None
    won_at: datetime
    assigned_to_name: Optional[str] = None


class RecentWinsOut(Schema):
    items: List[RecentWinItem]
    canonical_currency: str


@router.get(
    "/dashboard/recent-wins",
    auth=django_auth,
    response={200: RecentWinsOut, 403: ErrorOut},
)
def get_dashboard_recent_wins(request, days: int = 30):
    """Return recently won records within the given number of days."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    since = tz.now() - dt.timedelta(days=days)
    won_records = (
        PipelineRecord.objects.filter(
            firm=request.firm,
            status=RecordStatus.WON,
            updated_at__gte=since,
        )
        .select_related("assigned_to")
        .order_by("-updated_at")[:10]
    )

    items = [
        {
            "id": str(r.id),
            "title": r.title,
            "value_canonical": float(r.canonical_amount) if r.canonical_amount is not None else None,
            "won_at": r.updated_at,
            "assigned_to_name": _user_display_name(r.assigned_to),
        }
        for r in won_records
    ]

    return 200, {
        "items": items,
        "canonical_currency": request.firm.default_currency or "",
    }


# ---------------------------------------------------------------------------
# /dashboard/my-goals
# ---------------------------------------------------------------------------

class MyGoalsOut(Schema):
    activities_today: int
    target_activities: int
    streak_days: int
    best_day_count: int
    best_day_date: Optional[str] = None  # ISO date string


@router.get(
    "/dashboard/my-goals",
    auth=django_auth,
    response={200: MyGoalsOut, 403: ErrorOut},
)
def get_dashboard_my_goals(request):
    """Return the current user's daily activity goal progress and streak."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    today = tz.now().date()
    target_activities = 10

    activities_today = Activity.objects.filter(
        record__firm=request.firm,
        user=request.user,
        created_at__date=today,
    ).count()

    # Streak: count consecutive days (back from today inclusive) with >= 1 activity.
    # Query up to 365 days back so long streaks are not incorrectly capped.
    since_streak = tz.now() - dt.timedelta(days=365)
    daily_counts = (
        Activity.objects.filter(
            record__firm=request.firm,
            user=request.user,
            created_at__date__gte=since_streak.date(),
        )
        .values("created_at__date")
        .annotate(cnt=Count("id"))
    )
    day_map = {entry["created_at__date"]: entry["cnt"] for entry in daily_counts}

    streak_days = 0
    check_day = today
    while True:
        if day_map.get(check_day, 0) >= 1:
            streak_days += 1
            check_day -= dt.timedelta(days=1)
        else:
            break

    # Best day: over last 90 days
    since_best = tz.now() - dt.timedelta(days=90)
    best_daily = (
        Activity.objects.filter(
            record__firm=request.firm,
            user=request.user,
            created_at__date__gte=since_best.date(),
        )
        .values("created_at__date")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")
        .first()
    )

    best_day_count = best_daily["cnt"] if best_daily else 0
    best_day_date = best_daily["created_at__date"].isoformat() if best_daily else None

    return 200, {
        "activities_today": activities_today,
        "target_activities": target_activities,
        "streak_days": streak_days,
        "best_day_count": best_day_count,
        "best_day_date": best_day_date,
    }




# ===========================================================================
# RECORD ATTACHMENTS  (backed by Document + Activity)
# ===========================================================================

# Maximum allowed file size (20 MB)
_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class AttachmentOut(Schema):
    id: str
    record_id: Optional[str]
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
        "record_id": str(doc.record_id) if doc.record_id else None,
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
    """List all file attachments for a Record, newest first (paginated)."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    offset = (page - 1) * page_size
    docs = Document.objects.filter(record=record, firm=request.firm).order_by("-created_at")[
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
    Upload a file and attach it to a PipelineRecord.

    Creates a ``Document`` record and a ``FILE_UPLOAD`` Activity atomically.
    """
    try:
        require_membership(request, min_role=InvitationRole.MEMBER)
        require_active_subscription(request.firm)
    except (PermissionDenied, SubscriptionRequired) as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    if file.size > _MAX_ATTACHMENT_BYTES:
        return 400, {"detail": f"File exceeds the maximum allowed size of {_MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB."}

    with transaction.atomic():
        doc = Document(
            firm=request.firm,
            record=record,
            uploaded_by=request.user,
            name=file.name,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=file.size,
        )
        doc.file.save(file.name, file, save=True)

        Activity.objects.create(
            record=record,
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
    Soft-delete a file attachment from a PipelineRecord.

    Marks the document as deleted; the physical file is removed by the purge task.
    Requires at least Admin role.
    """
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        doc = Document.objects.get(id=attachment_id, record=record, firm=request.firm)
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
# The endpoint is entity-agnostic: it accepts an optional ``record_id`` /
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
    Pipeline summary: count and total estimated value per status.

    All record statuses are always present in the response, even when the
    count is zero, so clients can render a consistent pipeline view.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    records_qs = PipelineRecord.objects.filter(firm=request.firm)

    # Build a base dict with every status initialised to zero so that
    # statuses with no records are still present in the response.
    counts: Dict[str, int] = {s.value: 0 for s in RecordStatus}
    values: Dict[str, float] = {s.value: 0.0 for s in RecordStatus}

    for row in records_qs.values("status").annotate(
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
    record_id: Optional[str]
    record_title: Optional[str]
    user_id: Optional[str]
    type: str
    content_text: str
    metadata: Dict[str, Any]
    created_at: datetime


def _activity_feed_item_out(a: Activity) -> dict:
    return {
        "id": str(a.id),
        "record_id": str(a.record_id) if a.record_id else None,
        "record_title": a.record.title if a.record_id else None,
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
    Firm-wide activity feed across all records, newest first (paginated).

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


class UserActivityTimelineItemOut(Schema):
    id: str
    entity_type: str
    entity_id: str
    record_id: Optional[str]
    record_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    proposal_id: Optional[str]
    proposal_title: Optional[str]
    task_id: Optional[str]
    task_title: Optional[str]
    user_id: Optional[str]
    type: str
    content_text: str
    metadata: Dict[str, Any]
    created_at: datetime


class UserActivityTimelineOut(Schema):
    items: List[UserActivityTimelineItemOut]
    total_count: int
    page: int
    page_size: int


def _user_activity_timeline_item_out(a: Activity) -> dict:
    customer_name = None
    if a.customer_id:
        customer = a.customer
        customer_name = f"{customer.first_name} {customer.last_name}".strip() or customer.company_name or customer.email

    return {
        "id": str(a.id),
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "record_id": str(a.record_id) if a.record_id else None,
        "record_title": a.record.title if a.record_id else None,
        "customer_id": str(a.customer_id) if a.customer_id else None,
        "customer_name": customer_name,
        "proposal_id": str(a.proposal_id) if a.proposal_id else None,
        "proposal_title": a.proposal.title if a.proposal_id else None,
        "task_id": str(a.task_id) if a.task_id else None,
        "task_title": a.task.title if a.task_id else None,
        "user_id": str(a.user_id) if a.user_id else None,
        "type": a.type,
        "content_text": a.content_text,
        "metadata": a.metadata,
        "created_at": a.created_at,
    }


@router.get(
    "/reports/users/{membership_id}/timeline",
    auth=django_auth,
    response={200: UserActivityTimelineOut, 403: ErrorOut, 404: ErrorOut},
)
def user_timeline_report(
    request,
    membership_id: str,
    page: int = 1,
    page_size: int = 20,
    type: str = "",
    entity_type: str = "",
):
    """
    Paginated activity timeline for one firm member across all entity types.
    """
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    target_membership = (
        Membership.objects.filter(id=membership_id, firm=request.firm)
        .select_related("user")
        .first()
    )
    if target_membership is None:
        return 404, {"detail": "Member not found."}

    qs = (
        Activity.objects.filter(user_id=target_membership.user_id)
        .filter(
            Q(record__firm=request.firm)
            | Q(customer__firm=request.firm)
            | Q(proposal__firm=request.firm)
            | Q(task__firm=request.firm)
        )
        .select_related("record", "customer", "proposal", "task")
        .order_by("-created_at")
    )
    qs = filter_activities_qs(qs, request)

    if type:
        qs = qs.filter(type=type)

    if entity_type:
        if entity_type == "record":
            qs = qs.filter(record_id__isnull=False)
        elif entity_type == "customer":
            qs = qs.filter(customer_id__isnull=False)
        elif entity_type == "proposal":
            qs = qs.filter(proposal_id__isnull=False)
        elif entity_type == "task":
            qs = qs.filter(task_id__isnull=False)
        elif entity_type == "other":
            qs = qs.filter(
                record_id__isnull=True,
                customer_id__isnull=True,
                proposal_id__isnull=True,
                task_id__isnull=True,
            )

    total_count = qs.count()
    offset = (page - 1) * page_size
    page_items = [_user_activity_timeline_item_out(a) for a in qs[offset:offset + page_size]]
    return 200, {
        "items": page_items,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Overdue task report
# ---------------------------------------------------------------------------

class OverdueTaskOut(Schema):
    id: str
    firm_id: str
    record_id: Optional[str]
    record_title: Optional[str]
    assigned_to_id: Optional[str]
    title: str
    due_date: Optional[datetime]
    created_at: datetime


def _overdue_task_out(t: Task) -> dict:
    record_title = None
    if t.record_id:
        try:
            record_title = t.record.title
        except (AttributeError, Exception):
            pass
    return {
        "id": str(t.id),
        "firm_id": str(t.firm_id),
        "record_id": str(t.record_id) if t.record_id else None,
        "record_title": record_title,
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


class MarkNotificationsReadIn(Schema):
    ids: Optional[List[str]] = None


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
def mark_notifications_read(request, payload: MarkNotificationsReadIn):
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
    if payload.ids:
        qs = qs.filter(id__in=payload.ids)
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
    Average time (in hours) a record spends in each status, computed from
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
        .values("record_id", "metadata", "created_at")
        .order_by("record_id", "created_at")
    )

    # Group by record — each row is a status_change Activity with new_status in metadata
    record_history: Dict[str, list] = {}
    for entry in history_qs:
        new_status = entry["metadata"].get("new_status") if isinstance(entry["metadata"], dict) else None
        if new_status:
            record_history.setdefault(str(entry["record_id"]), []).append(
                {"to_status": new_status, "changed_at": entry["created_at"]}
            )

    now = tz.now()
    for record_id, entries in record_history.items():
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
    Count of Won and Lost records grouped by source, optionally filtered by a
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
    records_owned: int
    tasks_completed: int
    activities_logged: int


@router.get(
    "/reports/team-performance",
    auth=django_auth,
    response={200: List[TeamPerformanceRow], 403: ErrorOut},
)
def team_performance(request):
    """
    Per-member stats: records owned, tasks completed, activities logged.
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
        records_owned = PipelineRecord.objects.filter(firm=request.firm, assigned_to=user).count()
        tasks_completed = Task.objects.filter(firm=request.firm, assigned_to=user, is_completed=True).count()
        activities_logged = Activity.objects.filter(record__firm=request.firm, user=user).count()
        result.append({
            "user_id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "records_owned": records_owned,
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
    Records created vs. closed (Won + Lost) per week for the last 12 weeks,
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

    records_qs = PipelineRecord.objects.filter(firm=request.firm)

    weekly_rows = []
    for week in range(12):
        week_start = twelve_weeks_ago + dt.timedelta(weeks=week)
        week_end = week_start + dt.timedelta(weeks=1)
        created = records_qs.filter(created_at__gte=week_start, created_at__lt=week_end).count()
        closed = records_qs.filter(
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
    closed_30d = records_qs.filter(
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
    entity_type: str   # "record" | "customer" | "total"
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

    # Superuser sentinel is not a real DB row — accept the request as a no-op
    # but echo the requested value so the UI stays in sync.
    if isinstance(m, SuperuserMembership):
        return 200, {"weekly_digest_enabled": payload.enabled}

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
# v2.2 — RECORD SCORING RULES
# ===========================================================================

class RecordScoringRuleOut(Schema):
    id: str
    field: str
    operand: Any
    score_delta: int


class RecordScoringRuleIn(Schema):
    field: str
    operand: Any
    score_delta: int


@router.get(
    "/record-scoring-rules",
    auth=django_auth,
    response={200: List[RecordScoringRuleOut], 403: ErrorOut},
)
def list_record_scoring_rules(request):
    """List all record scoring rules for the active firm."""
    try:
        require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    rules = RecordScoringRule.objects.filter(firm=request.firm)
    return 200, [
        {"id": str(r.id), "field": r.field, "operand": r.operand, "score_delta": r.score_delta}
        for r in rules
    ]


@router.post(
    "/record-scoring-rules",
    auth=django_auth,
    response={201: RecordScoringRuleOut, 400: ErrorOut, 403: ErrorOut},
)
def create_record_scoring_rule(request, payload: RecordScoringRuleIn):
    """Create a new record scoring rule for the active firm."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    valid_fields = {"status", "source", "value_gte", "last_activity_days_lte"}
    if payload.field not in valid_fields:
        return 400, {"detail": f"Invalid field. Must be one of: {', '.join(sorted(valid_fields))}."}

    rule = RecordScoringRule.objects.create(
        firm=request.firm,
        field=payload.field,
        operand=payload.operand,
        score_delta=payload.score_delta,
    )
    return 201, {"id": str(rule.id), "field": rule.field, "operand": rule.operand, "score_delta": rule.score_delta}


@router.delete(
    "/record-scoring-rules/{rule_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_record_scoring_rule(request, rule_id: str):
    """Delete a record scoring rule."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = RecordScoringRule.objects.get(id=rule_id, firm=request.firm)
    except RecordScoringRule.DoesNotExist:
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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
        require_membership(request, min_role=InvitationRole.ADMIN)
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
        require_membership(request, min_role=InvitationRole.ADMIN)
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
        require_membership(request, min_role=InvitationRole.ADMIN)
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
        require_membership(request, min_role=InvitationRole.MEMBER)
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


# ===========================================================================
# Phase 6 – Per-category & per-record Grant endpoints
# ===========================================================================

import uuid as _uuid  # noqa: E402 – used by grant endpoints below

from crm.models import CategoryGrant, RecordGrant  # noqa: E402 – placed here to avoid circular at module load


class GrantIn(Schema):
    principal_type: str   # "user" or "team"
    principal_id: str     # UUID of user or team
    level: str            # "view" / "edit" / "manage"
    expires_at: Optional[str] = None  # ISO 8601 datetime, optional


class GrantOut(Schema):
    id: str
    principal_type: str
    principal_id: str
    principal_name: Optional[str]  # resolved display name (email or team name)
    level: str
    granted_by_id: Optional[str]
    granted_at: str
    expires_at: Optional[str]


class GrantAccessOut(Schema):
    category_grants: List[GrantOut]
    record_grants: List[GrantOut]


def _resolve_principal_name(principal_type: str, principal_id) -> Optional[str]:
    """Return a human-readable display name for a grant principal."""
    try:
        if principal_type == "user":
            # principal_id is the User's UUID (User.pk), not Membership.pk
            m = Membership.objects.select_related("user").filter(user_id=str(principal_id)).first()
            if m:
                return m.user.get_full_name() or m.user.email
        elif principal_type == "team":
            from firms.models import Team  # noqa: PLC0415
            t = Team.objects.filter(id=str(principal_id)).first()
            if t:
                return t.name
    except Exception:  # noqa: BLE001 - best-effort; never crash the response
        pass
    return None


def _grant_out(grant) -> dict:
    return {
        "id": str(grant.id),
        "principal_type": grant.principal_type,
        "principal_id": str(grant.principal_id),
        "principal_name": _resolve_principal_name(grant.principal_type, grant.principal_id),
        "level": grant.level,
        "granted_by_id": str(grant.granted_by_id) if grant.granted_by_id else None,
        "granted_at": grant.granted_at.isoformat(),
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
    }


def _parse_expires_at(expires_at_str: Optional[str]):
    if not expires_at_str:
        return None
    parsed = parse_datetime(expires_at_str)
    if parsed is None:
        raise ValueError(f"Invalid expires_at datetime: {expires_at_str!r}")
    return parsed


def _notify_grant_recipient(
    principal_type: str,
    principal_id,
    firm,
    resource_name: str,
    resource_type: str,
    level: str,
    granted_by_user,
) -> None:
    """Send an email to the grantee informing them of a new access grant.

    Only sends for ``principal_type='user'``.  Team grants do not have a
    single email recipient, so they are silently skipped.  All errors are
    caught so that a notification failure never blocks the API response.
    """
    if principal_type != "user":
        return
    try:
        from django.core.mail import send_mail  # noqa: PLC0415
        from django.conf import settings as django_settings  # noqa: PLC0415

        grantee_membership = (
            Membership.objects.select_related("user")
            .filter(user_id=str(principal_id), firm=firm)
            .first()
        )
        if grantee_membership is None:
            return

        grantee_email = grantee_membership.user.email
        granted_by_name = (
            granted_by_user.get_full_name() or granted_by_user.email
            if granted_by_user
            else "an administrator"
        )
        level_labels = {"view": "view-only", "edit": "edit", "manage": "manage"}
        level_label = level_labels.get(level, level)

        subject = f"[LeadLab] You have been granted {level_label} access to a {resource_type}"
        body = (
            f"Hi,\n\n"
            f"{granted_by_name} has granted you {level_label} access to the "
            f"{resource_type} \"{resource_name}\" in the workspace \"{firm.name}\".\n\n"
            f"You can now access it by logging in to LeadLab.\n\n"
            f"Best regards,\nThe LeadLab team"
        )
        from_email = getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@leadlab.app")
        send_mail(subject, body, from_email, [grantee_email], fail_silently=False)
    except Exception:  # noqa: BLE001 – notifications must never crash the API
        import logging as _logging
        _logging.getLogger(__name__).warning(
            "_notify_grant_recipient: failed to send grant notification",
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Category grants
# ---------------------------------------------------------------------------

@router.get(
    "/categories/{category_id}/grants",
    auth=django_auth,
    response={200: List[GrantOut], 403: ErrorOut, 404: ErrorOut},
)
def list_category_grants(request, category_id: str):
    """List all access grants for a category. Requires ``category.manage``."""
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    grants = CategoryGrant.objects.filter(category=category)
    return 200, [_grant_out(g) for g in grants]


@router.post(
    "/categories/{category_id}/grants",
    auth=django_auth,
    response={201: GrantOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_category_grant(request, category_id: str, payload: GrantIn):
    """Grant access to a category for a user or team. Requires ``category.manage``."""
    try:
        membership = require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        category = Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    if payload.principal_type not in ("user", "team"):
        return 400, {"detail": "principal_type must be 'user' or 'team'."}
    if payload.level not in ("view", "edit", "manage"):
        return 400, {"detail": "level must be 'view', 'edit', or 'manage'."}

    try:
        principal_uuid = _uuid.UUID(payload.principal_id)
    except ValueError:
        return 400, {"detail": "principal_id must be a valid UUID."}

    try:
        expires_at = _parse_expires_at(payload.expires_at)
    except ValueError as exc:
        return 400, {"detail": str(exc)}

    grant, created = CategoryGrant.objects.update_or_create(
        category=category,
        principal_type=payload.principal_type,
        principal_id=principal_uuid,
        defaults={
            "level": payload.level,
            "granted_by": membership,
            "expires_at": expires_at,
        },
    )
    status = 201 if created else 200
    if created:
        _notify_grant_recipient(
            principal_type=payload.principal_type,
            principal_id=principal_uuid,
            firm=request.firm,
            resource_name=category.name,
            resource_type="category",
            level=payload.level,
            granted_by_user=membership.user,
        )
    return status, _grant_out(grant)


@router.delete(
    "/categories/{category_id}/grants/{grant_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_category_grant(request, category_id: str, grant_id: str):
    """Revoke a category access grant. Requires ``category.manage``."""
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        Category.objects.get(id=category_id, firm=request.firm)
    except Category.DoesNotExist:
        return 404, {"detail": "Category not found."}

    try:
        grant = CategoryGrant.objects.get(id=grant_id, category__id=category_id)
    except CategoryGrant.DoesNotExist:
        return 404, {"detail": "Grant not found."}

    grant.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Record grants
# ---------------------------------------------------------------------------

@router.get(
    "/records/{record_id}/access",
    auth=django_auth,
    response={200: GrantAccessOut, 403: ErrorOut, 404: ErrorOut},
)
def get_record_access(request, record_id: str):
    """Return all grants (category-level and record-level) effective for a record.

    Useful for the "Share" UI dialog.  Requires at least ``record.view``.
    """
    try:
        require_permission(request, Permission.RECORD_VIEW)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.select_related("category").get(
            id=record_id, firm=request.firm
        )
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    category_grants = CategoryGrant.objects.filter(category=record.category) if record.category else []
    record_grants = RecordGrant.objects.filter(record=record)

    return 200, {
        "category_grants": [_grant_out(g) for g in category_grants],
        "record_grants": [_grant_out(g) for g in record_grants],
    }


@router.get(
    "/records/{record_id}/grants",
    auth=django_auth,
    response={200: List[GrantOut], 403: ErrorOut, 404: ErrorOut},
)
def list_record_grants(request, record_id: str):
    """List direct (per-record) access grants. Requires ``record.edit``."""
    try:
        require_permission(request, Permission.RECORD_EDIT)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    grants = RecordGrant.objects.filter(record=record)
    return 200, [_grant_out(g) for g in grants]


@router.post(
    "/records/{record_id}/grants",
    auth=django_auth,
    response={201: GrantOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_record_grant(request, record_id: str, payload: GrantIn):
    """Grant access to a record for a user or team. Requires ``record.edit``."""
    try:
        membership = require_permission(request, Permission.RECORD_EDIT)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        record = PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    if payload.principal_type not in ("user", "team"):
        return 400, {"detail": "principal_type must be 'user' or 'team'."}
    if payload.level not in ("view", "edit", "manage"):
        return 400, {"detail": "level must be 'view', 'edit', or 'manage'."}

    try:
        principal_uuid = _uuid.UUID(payload.principal_id)
    except ValueError:
        return 400, {"detail": "principal_id must be a valid UUID."}

    try:
        expires_at = _parse_expires_at(payload.expires_at)
    except ValueError as exc:
        return 400, {"detail": str(exc)}

    grant, created = RecordGrant.objects.update_or_create(
        record=record,
        principal_type=payload.principal_type,
        principal_id=principal_uuid,
        defaults={
            "level": payload.level,
            "granted_by": membership,
            "expires_at": expires_at,
        },
    )
    status = 201 if created else 200
    if created:
        _notify_grant_recipient(
            principal_type=payload.principal_type,
            principal_id=principal_uuid,
            firm=request.firm,
            resource_name=record.title,
            resource_type="record",
            level=payload.level,
            granted_by_user=membership.user,
        )
    return status, _grant_out(grant)


@router.delete(
    "/records/{record_id}/grants/{grant_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_record_grant(request, record_id: str, grant_id: str):
    """Revoke a per-record access grant. Requires ``record.edit``."""
    try:
        require_permission(request, Permission.RECORD_EDIT)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        PipelineRecord.objects.get(id=record_id, firm=request.firm)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    try:
        grant = RecordGrant.objects.get(id=grant_id, record__id=record_id)
    except RecordGrant.DoesNotExist:
        return 404, {"detail": "Grant not found."}

    grant.delete()
    return 204, None


# ===========================================================================
# Condition Rules API (podminky.md §13.9)
# ===========================================================================

class ConditionRuleOut(Schema):
    id: str
    firm_id: str
    name: str
    description: str
    is_active: bool
    scope_type: str
    category_id: Optional[str]
    stage_id: Optional[str]
    source_stage_id: Optional[str]
    target_stage_id: Optional[str]
    trigger_type: str
    condition_tree: Dict[str, Any]
    effect: str
    severity: str
    effect_config: Dict[str, Any]
    activity_type: str
    priority: int
    created_by_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class ConditionRuleIn(Schema):
    name: str
    description: str = ""
    is_active: bool = True
    scope_type: str = ConditionScopeType.FIRM
    category_id: Optional[str] = None
    stage_id: Optional[str] = None
    source_stage_id: Optional[str] = None
    target_stage_id: Optional[str] = None
    trigger_type: str
    condition_tree: Dict[str, Any] = {}
    effect: str = ConditionEffectType.BLOCK
    severity: str = ConditionSeverity.ERROR
    effect_config: Dict[str, Any] = {}
    activity_type: str = ""
    priority: int = 100


class ConditionRulePatchIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    scope_type: Optional[str] = None
    category_id: Optional[str] = None
    stage_id: Optional[str] = None
    source_stage_id: Optional[str] = None
    target_stage_id: Optional[str] = None
    trigger_type: Optional[str] = None
    condition_tree: Optional[Dict[str, Any]] = None
    effect: Optional[str] = None
    severity: Optional[str] = None
    effect_config: Optional[Dict[str, Any]] = None
    activity_type: Optional[str] = None
    priority: Optional[int] = None


class StageScenarioOut(Schema):
    id: str
    firm_id: str
    category_id: str
    stage_id: str
    name: str
    description: str
    activation_condition: Dict[str, Any]
    completion_condition: Dict[str, Any]
    recommended_next_stage_id: Optional[str]
    priority: int
    is_active: bool
    created_by_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class StageScenarioIn(Schema):
    name: str
    description: str = ""
    activation_condition: Dict[str, Any] = {}
    completion_condition: Dict[str, Any] = {}
    recommended_next_stage_id: Optional[str] = None
    priority: int = 100
    is_active: bool = True


class StageScenarioPatchIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    activation_condition: Optional[Dict[str, Any]] = None
    completion_condition: Optional[Dict[str, Any]] = None
    recommended_next_stage_id: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class StageRequirementOut(Schema):
    id: str
    firm_id: str
    scenario_id: str
    name: str
    description: str
    requirement_type: str
    condition: Dict[str, Any]
    blocking: bool
    visible_to_user: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class StageRequirementIn(Schema):
    name: str
    description: str = ""
    requirement_type: str = RequirementType.CUSTOM
    condition: Dict[str, Any] = {}
    blocking: bool = True
    visible_to_user: bool = True
    sort_order: int = 0


class StageRequirementPatchIn(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    requirement_type: Optional[str] = None
    condition: Optional[Dict[str, Any]] = None
    blocking: Optional[bool] = None
    visible_to_user: Optional[bool] = None
    sort_order: Optional[int] = None


class ConditionRuleTestEvaluationIn(Schema):
    record_id: str
    rule_id: Optional[str] = None
    condition_tree: Optional[Dict[str, Any]] = None
    effect: str = ConditionEffectType.BLOCK
    severity: str = ConditionSeverity.ERROR
    effect_config: Dict[str, Any] = {}
    activity_type: str = ""


class ConditionRuleTestEvaluationOut(Schema):
    matched: bool
    outputs: List[Dict[str, Any]]
    blocking: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]


class ActiveStageRequirementsOut(Schema):
    record_id: str
    active_stage_scenario_id: Optional[str]
    active_stage_scenario_name: Optional[str]
    recommended_next_stage_id: Optional[str]
    recommended_next_stage_name: Optional[str]
    active_stage_requirements: List[Dict[str, Any]]


class RuleEvaluationLogOut(Schema):
    id: str
    firm_id: str
    record_id: Optional[str]
    rule_id: Optional[str]
    scenario_id: Optional[str]
    requirement_id: Optional[str]
    trigger_type: str
    result: str
    messages: List[Any]
    recommendations: List[Any]
    error_message: str
    input_context: Dict[str, Any]
    evaluated_by_id: Optional[str]
    evaluated_at: datetime


def _condition_rule_out(rule: ConditionRule) -> dict:
    return {
        "id": str(rule.id),
        "firm_id": str(rule.firm_id),
        "name": rule.name,
        "description": rule.description or "",
        "is_active": rule.is_active,
        "scope_type": rule.scope_type,
        "category_id": str(rule.category_id) if rule.category_id else None,
        "stage_id": str(rule.stage_id) if rule.stage_id else None,
        "source_stage_id": str(rule.source_stage_id) if rule.source_stage_id else None,
        "target_stage_id": str(rule.target_stage_id) if rule.target_stage_id else None,
        "trigger_type": rule.trigger_type,
        "condition_tree": rule.condition_tree if isinstance(rule.condition_tree, dict) else {},
        "effect": rule.effect,
        "severity": rule.severity,
        "effect_config": rule.effect_config if isinstance(rule.effect_config, dict) else {},
        "activity_type": rule.activity_type or "",
        "priority": rule.priority,
        "created_by_id": str(rule.created_by_id) if rule.created_by_id else None,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _stage_scenario_out(scenario: StageScenario) -> dict:
    return {
        "id": str(scenario.id),
        "firm_id": str(scenario.firm_id),
        "category_id": str(scenario.category_id),
        "stage_id": str(scenario.stage_id),
        "name": scenario.name,
        "description": scenario.description or "",
        "activation_condition": (
            scenario.activation_condition
            if isinstance(scenario.activation_condition, dict)
            else {}
        ),
        "completion_condition": (
            scenario.completion_condition
            if isinstance(scenario.completion_condition, dict)
            else {}
        ),
        "recommended_next_stage_id": (
            str(scenario.recommended_next_stage_id)
            if scenario.recommended_next_stage_id
            else None
        ),
        "priority": scenario.priority,
        "is_active": scenario.is_active,
        "created_by_id": str(scenario.created_by_id) if scenario.created_by_id else None,
        "created_at": scenario.created_at,
        "updated_at": scenario.updated_at,
    }


def _stage_requirement_out(requirement: StageRequirement) -> dict:
    return {
        "id": str(requirement.id),
        "firm_id": str(requirement.firm_id),
        "scenario_id": str(requirement.scenario_id),
        "name": requirement.name,
        "description": requirement.description or "",
        "requirement_type": requirement.requirement_type,
        "condition": requirement.condition if isinstance(requirement.condition, dict) else {},
        "blocking": requirement.blocking,
        "visible_to_user": requirement.visible_to_user,
        "sort_order": requirement.sort_order,
        "created_at": requirement.created_at,
        "updated_at": requirement.updated_at,
    }


def _rule_evaluation_log_out(log: RuleEvaluationLog) -> dict:
    return {
        "id": str(log.id),
        "firm_id": str(log.firm_id),
        "record_id": str(log.record_id) if log.record_id else None,
        "rule_id": str(log.rule_id) if log.rule_id else None,
        "scenario_id": str(log.scenario_id) if log.scenario_id else None,
        "requirement_id": str(log.requirement_id) if log.requirement_id else None,
        "trigger_type": log.trigger_type,
        "result": log.result,
        "messages": list(log.messages or []),
        "recommendations": list(log.recommendations or []),
        "error_message": log.error_message or "",
        "input_context": log.input_context if isinstance(log.input_context, dict) else {},
        "evaluated_by_id": str(log.evaluated_by_id) if log.evaluated_by_id else None,
        "evaluated_at": log.evaluated_at,
    }


def _condition_rule_audit_snapshot(rule: ConditionRule) -> dict:
    return {
        "name": rule.name,
        "is_active": rule.is_active,
        "scope_type": rule.scope_type,
        "category_id": str(rule.category_id) if rule.category_id else None,
        "stage_id": str(rule.stage_id) if rule.stage_id else None,
        "source_stage_id": str(rule.source_stage_id) if rule.source_stage_id else None,
        "target_stage_id": str(rule.target_stage_id) if rule.target_stage_id else None,
        "trigger_type": rule.trigger_type,
        "effect": rule.effect,
        "severity": rule.severity,
        "activity_type": rule.activity_type or None,
        "priority": rule.priority,
    }


def _log_condition_rule_audit(
    *,
    request,
    rule: ConditionRule,
    action: str,
    changed_fields: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    try:
        PermissionAuditLog.objects.create(
            firm=request.firm,
            actor=request.user if getattr(request.user, "is_authenticated", False) else None,
            action=action,
            target_type="condition_rule",
            target_id=str(rule.id),
            payload={
                "rule_id": str(rule.id),
                "trigger_type": rule.trigger_type,
                "scope_type": rule.scope_type,
                "changed_fields": changed_fields or {},
            },
        )
    except Exception:
        logger.warning(
            "Failed to log audit entry for %s (condition_rule=%s)",
            action,
            rule.id,
            exc_info=True,
        )


def _resolve_stage_in_firm(stage_id: Optional[str], firm) -> tuple[Optional[Stage], Optional[tuple[int, dict]]]:
    if not stage_id:
        return None, None
    try:
        stage = Stage.objects.select_related("category").get(id=stage_id, category__firm=firm)
    except Stage.DoesNotExist:
        return None, (400, {"detail": f"Stage {stage_id} not found in current firm."})
    return stage, None


def _validate_condition_rule_scope_fields(
    *,
    scope_type: str,
    category: Optional[Category],
    stage: Optional[Stage],
    source_stage: Optional[Stage],
    target_stage: Optional[Stage],
) -> Optional[tuple[int, dict]]:
    if scope_type == ConditionScopeType.CATEGORY and category is None:
        return 400, {"detail": "scope_type=category requires category_id."}
    if scope_type == ConditionScopeType.STAGE and stage is None:
        return 400, {"detail": "scope_type=stage requires stage_id."}
    if scope_type == ConditionScopeType.STAGE_TRANSITION and (source_stage is None or target_stage is None):
        return 400, {"detail": "scope_type=stage_transition requires source_stage_id and target_stage_id."}

    if category and stage and str(stage.category_id) != str(category.id):
        return 400, {"detail": "stage_id must belong to category_id."}
    if category and source_stage and str(source_stage.category_id) != str(category.id):
        return 400, {"detail": "source_stage_id must belong to category_id."}
    if category and target_stage and str(target_stage.category_id) != str(category.id):
        return 400, {"detail": "target_stage_id must belong to category_id."}
    return None


@router.get(
    "/condition-rules",
    auth=django_auth,
    response={200: List[ConditionRuleOut], 403: ErrorOut},
)
def list_condition_rules(
    request,
    category_id: str = "",
    stage_id: str = "",
    trigger_type: str = "",
    is_active: Optional[bool] = None,
):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    qs = ConditionRule.objects.filter(firm=request.firm)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if stage_id:
        qs = qs.filter(stage_id=stage_id)
    if trigger_type:
        qs = qs.filter(trigger_type=trigger_type)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    qs = qs.order_by("priority", "created_at", "id")
    return 200, [_condition_rule_out(rule) for rule in qs]


@router.get(
    "/condition-rules/{rule_id}",
    auth=django_auth,
    response={200: ConditionRuleOut, 403: ErrorOut, 404: ErrorOut},
)
def get_condition_rule(request, rule_id: str):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = ConditionRule.objects.get(id=rule_id, firm=request.firm)
    except ConditionRule.DoesNotExist:
        return 404, {"detail": "Condition rule not found."}
    return 200, _condition_rule_out(rule)


@router.post(
    "/condition-rules",
    auth=django_auth,
    response={201: ConditionRuleOut, 400: ErrorOut, 403: ErrorOut},
)
def create_condition_rule(request, payload: ConditionRuleIn):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    category = None
    if payload.category_id:
        try:
            category = Category.objects.get(id=payload.category_id, firm=request.firm)
        except Category.DoesNotExist:
            return 400, {"detail": "category_id not found in current firm."}

    stage, err = _resolve_stage_in_firm(payload.stage_id, request.firm)
    if err:
        return err
    source_stage, err = _resolve_stage_in_firm(payload.source_stage_id, request.firm)
    if err:
        return err
    target_stage, err = _resolve_stage_in_firm(payload.target_stage_id, request.firm)
    if err:
        return err

    if category is None and stage is not None:
        category = stage.category

    scope_error = _validate_condition_rule_scope_fields(
        scope_type=payload.scope_type,
        category=category,
        stage=stage,
        source_stage=source_stage,
        target_stage=target_stage,
    )
    if scope_error:
        return scope_error

    rule = ConditionRule.objects.create(
        firm=request.firm,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        scope_type=payload.scope_type,
        category=category,
        stage=stage,
        source_stage=source_stage,
        target_stage=target_stage,
        trigger_type=payload.trigger_type,
        condition_tree=payload.condition_tree,
        effect=payload.effect,
        severity=payload.severity,
        effect_config=payload.effect_config,
        activity_type=payload.activity_type or "",
        priority=payload.priority,
        created_by=request.user,
    )
    _log_condition_rule_audit(
        request=request,
        rule=rule,
        action="condition_rule.created",
        changed_fields={},
    )
    return 201, _condition_rule_out(rule)


@router.patch(
    "/condition-rules/{rule_id}",
    auth=django_auth,
    response={200: ConditionRuleOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_condition_rule(request, rule_id: str, payload: ConditionRulePatchIn):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = ConditionRule.objects.get(id=rule_id, firm=request.firm)
    except ConditionRule.DoesNotExist:
        return 404, {"detail": "Condition rule not found."}

    updates = payload.dict(exclude_unset=True)

    category = rule.category
    if "category_id" in updates:
        category_id = updates.pop("category_id")
        if category_id:
            try:
                category = Category.objects.get(id=category_id, firm=request.firm)
            except Category.DoesNotExist:
                return 400, {"detail": "category_id not found in current firm."}
        else:
            category = None

    stage = rule.stage
    if "stage_id" in updates:
        stage, err = _resolve_stage_in_firm(updates.pop("stage_id"), request.firm)
        if err:
            return err

    source_stage = rule.source_stage
    if "source_stage_id" in updates:
        source_stage, err = _resolve_stage_in_firm(updates.pop("source_stage_id"), request.firm)
        if err:
            return err

    target_stage = rule.target_stage
    if "target_stage_id" in updates:
        target_stage, err = _resolve_stage_in_firm(updates.pop("target_stage_id"), request.firm)
        if err:
            return err

    if category is None and stage is not None:
        category = stage.category

    scope_type = updates.get("scope_type", rule.scope_type)
    scope_error = _validate_condition_rule_scope_fields(
        scope_type=scope_type,
        category=category,
        stage=stage,
        source_stage=source_stage,
        target_stage=target_stage,
    )
    if scope_error:
        return scope_error

    before_snapshot = _condition_rule_audit_snapshot(rule)
    rule.category = category
    rule.stage = stage
    rule.source_stage = source_stage
    rule.target_stage = target_stage
    for key, value in updates.items():
        setattr(rule, key, value)
    rule.save()
    after_snapshot = _condition_rule_audit_snapshot(rule)
    changed_fields = {
        key: {"old": before_snapshot.get(key), "new": value}
        for key, value in after_snapshot.items()
        if before_snapshot.get(key) != value
    }
    _log_condition_rule_audit(
        request=request,
        rule=rule,
        action="condition_rule.updated",
        changed_fields=changed_fields,
    )
    return 200, _condition_rule_out(rule)


@router.delete(
    "/condition-rules/{rule_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def deactivate_condition_rule(request, rule_id: str):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = ConditionRule.objects.get(id=rule_id, firm=request.firm)
    except ConditionRule.DoesNotExist:
        return 404, {"detail": "Condition rule not found."}

    was_active = rule.is_active
    rule.is_active = False
    rule.save(update_fields=["is_active", "updated_at"])
    if was_active:
        _log_condition_rule_audit(
            request=request,
            rule=rule,
            action="condition_rule.deactivated",
            changed_fields={"is_active": {"old": True, "new": False}},
        )
    return 204, None


@router.get(
    "/categories/{category_id}/stages/{stage_id}/scenarios",
    auth=django_auth,
    response={200: List[StageScenarioOut], 403: ErrorOut, 404: ErrorOut},
)
def list_stage_scenarios(request, category_id: str, stage_id: str):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        stage = Stage.objects.select_related("category").get(
            id=stage_id,
            category_id=category_id,
            category__firm=request.firm,
        )
    except Stage.DoesNotExist:
        return 404, {"detail": "Stage not found in category for current firm."}

    scenarios = StageScenario.objects.filter(
        firm=request.firm,
        category=stage.category,
        stage=stage,
    ).order_by("priority", "created_at", "id")
    return 200, [_stage_scenario_out(scenario) for scenario in scenarios]


@router.post(
    "/categories/{category_id}/stages/{stage_id}/scenarios",
    auth=django_auth,
    response={201: StageScenarioOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_stage_scenario(request, category_id: str, stage_id: str, payload: StageScenarioIn):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        stage = Stage.objects.select_related("category").get(
            id=stage_id,
            category_id=category_id,
            category__firm=request.firm,
        )
    except Stage.DoesNotExist:
        return 404, {"detail": "Stage not found in category for current firm."}

    recommended_next_stage = None
    if payload.recommended_next_stage_id:
        recommended_next_stage, err = _resolve_stage_in_firm(payload.recommended_next_stage_id, request.firm)
        if err:
            return err

    scenario = StageScenario.objects.create(
        firm=request.firm,
        category=stage.category,
        stage=stage,
        name=payload.name,
        description=payload.description,
        activation_condition=payload.activation_condition,
        completion_condition=payload.completion_condition,
        recommended_next_stage=recommended_next_stage,
        priority=payload.priority,
        is_active=payload.is_active,
        created_by=request.user,
    )
    return 201, _stage_scenario_out(scenario)


@router.patch(
    "/categories/{category_id}/stages/{stage_id}/scenarios/{scenario_id}",
    auth=django_auth,
    response={200: StageScenarioOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_stage_scenario(
    request,
    category_id: str,
    stage_id: str,
    scenario_id: str,
    payload: StageScenarioPatchIn,
):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        scenario = StageScenario.objects.get(
            id=scenario_id,
            firm=request.firm,
            category_id=category_id,
            stage_id=stage_id,
        )
    except StageScenario.DoesNotExist:
        return 404, {"detail": "Stage scenario not found."}

    updates = payload.dict(exclude_unset=True)
    if "recommended_next_stage_id" in updates:
        recommended_next_stage_id = updates.pop("recommended_next_stage_id")
        if recommended_next_stage_id:
            recommended_next_stage, err = _resolve_stage_in_firm(recommended_next_stage_id, request.firm)
            if err:
                return err
            scenario.recommended_next_stage = recommended_next_stage
        else:
            scenario.recommended_next_stage = None

    for key, value in updates.items():
        setattr(scenario, key, value)
    scenario.save()
    return 200, _stage_scenario_out(scenario)


@router.delete(
    "/categories/{category_id}/stages/{stage_id}/scenarios/{scenario_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_stage_scenario(request, category_id: str, stage_id: str, scenario_id: str):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    deleted, _ = StageScenario.objects.filter(
        id=scenario_id,
        firm=request.firm,
        category_id=category_id,
        stage_id=stage_id,
    ).delete()
    if not deleted:
        return 404, {"detail": "Stage scenario not found."}
    return 204, None


@router.get(
    "/scenarios/{scenario_id}/requirements",
    auth=django_auth,
    response={200: List[StageRequirementOut], 403: ErrorOut, 404: ErrorOut},
)
def list_stage_scenario_requirements(request, scenario_id: str):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        scenario = StageScenario.objects.get(id=scenario_id, firm=request.firm)
    except StageScenario.DoesNotExist:
        return 404, {"detail": "Stage scenario not found."}

    requirements = scenario.requirements.all().order_by("sort_order", "created_at", "id")
    return 200, [_stage_requirement_out(requirement) for requirement in requirements]


@router.post(
    "/scenarios/{scenario_id}/requirements",
    auth=django_auth,
    response={201: StageRequirementOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_stage_scenario_requirement(request, scenario_id: str, payload: StageRequirementIn):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        scenario = StageScenario.objects.get(id=scenario_id, firm=request.firm)
    except StageScenario.DoesNotExist:
        return 404, {"detail": "Stage scenario not found."}

    requirement = StageRequirement.objects.create(
        firm=request.firm,
        scenario=scenario,
        name=payload.name,
        description=payload.description,
        requirement_type=payload.requirement_type,
        condition=payload.condition,
        blocking=payload.blocking,
        visible_to_user=payload.visible_to_user,
        sort_order=payload.sort_order,
    )
    return 201, _stage_requirement_out(requirement)


@router.patch(
    "/scenarios/{scenario_id}/requirements/{requirement_id}",
    auth=django_auth,
    response={200: StageRequirementOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_stage_scenario_requirement(
    request,
    scenario_id: str,
    requirement_id: str,
    payload: StageRequirementPatchIn,
):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        requirement = StageRequirement.objects.get(
            id=requirement_id,
            scenario_id=scenario_id,
            firm=request.firm,
        )
    except StageRequirement.DoesNotExist:
        return 404, {"detail": "Stage requirement not found."}

    updates = payload.dict(exclude_unset=True)
    for key, value in updates.items():
        setattr(requirement, key, value)
    requirement.save()
    return 200, _stage_requirement_out(requirement)


@router.delete(
    "/scenarios/{scenario_id}/requirements/{requirement_id}",
    auth=django_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_stage_scenario_requirement(request, scenario_id: str, requirement_id: str):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    deleted, _ = StageRequirement.objects.filter(
        id=requirement_id,
        scenario_id=scenario_id,
        firm=request.firm,
    ).delete()
    if not deleted:
        return 404, {"detail": "Stage requirement not found."}
    return 204, None


@router.post(
    "/condition-rules/test-evaluation/run",
    auth=django_auth,
    response={200: ConditionRuleTestEvaluationOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def test_condition_rule_evaluation(request, payload: ConditionRuleTestEvaluationIn):
    from crm.condition_rules import RecordConditionContextBuilder, evaluate_condition_rule_outputs

    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        record = filter_records_qs(
            PipelineRecord.objects.filter(firm=request.firm),
            request,
        ).select_related("category", "current_stage").get(id=payload.record_id)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    if not payload.rule_id and payload.condition_tree is None:
        return 400, {"detail": "Provide either rule_id or condition_tree."}

    if payload.rule_id:
        try:
            rule = ConditionRule.objects.get(id=payload.rule_id, firm=request.firm)
        except ConditionRule.DoesNotExist:
            return 404, {"detail": "Condition rule not found."}
        rules: list[Any] = [rule]
    else:
        rules = [
            {
                "id": "adhoc",
                "name": "Adhoc evaluation",
                "is_active": True,
                "priority": 100,
                "condition_tree": payload.condition_tree or {},
                "effect": payload.effect,
                "severity": payload.severity,
                "effect_config": payload.effect_config,
            },
        ]

    context = RecordConditionContextBuilder().build(record)
    outputs = evaluate_condition_rule_outputs(rules, context)
    blocking = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.BLOCK
    ]
    warnings = [
        _serialize_stage_rule_output(output)
        for output in outputs
        if output.get("effect") == ConditionEffectType.WARNING
    ]
    return 200, {
        "matched": bool(outputs),
        "outputs": [_serialize_stage_rule_output(output) for output in outputs],
        "blocking": blocking,
        "warnings": warnings,
    }


@router.get(
    "/records/{record_id}/active-stage-requirements",
    auth=django_auth,
    response={200: ActiveStageRequirementsOut, 403: ErrorOut, 404: ErrorOut},
)
def get_record_active_stage_requirements(request, record_id: str):
    try:
        require_permission(request, Permission.RECORD_VIEW)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    try:
        record = filter_records_qs(
            PipelineRecord.objects.filter(firm=request.firm),
            request,
        ).get(id=record_id)
    except PipelineRecord.DoesNotExist:
        return 404, {"detail": "Record not found."}

    _refresh_active_stage_scenario(record)
    extra_data = record.extra_data if isinstance(record.extra_data, dict) else {}
    requirements = extra_data.get("active_stage_requirements")
    if not isinstance(requirements, list):
        requirements = []
    active_stage_scenario_id = extra_data.get("active_stage_scenario_id")
    active_stage_scenario_name = None
    recommended_next_stage_id = None
    recommended_next_stage_name = None
    if active_stage_scenario_id:
        scenario = (
            StageScenario.objects.filter(
                id=active_stage_scenario_id,
                firm=request.firm,
                category_id=record.category_id,
                stage_id=record.current_stage_id,
                is_active=True,
            )
            .select_related("recommended_next_stage")
            .first()
        )
        if scenario:
            active_stage_scenario_name = scenario.name
            if scenario.recommended_next_stage_id:
                recommended_next_stage_id = str(scenario.recommended_next_stage_id)
                recommended_next_stage_name = scenario.recommended_next_stage.name
    return 200, {
        "record_id": str(record.id),
        "active_stage_scenario_id": active_stage_scenario_id,
        "active_stage_scenario_name": active_stage_scenario_name,
        "recommended_next_stage_id": recommended_next_stage_id,
        "recommended_next_stage_name": recommended_next_stage_name,
        "active_stage_requirements": requirements,
    }


@router.get(
    "/rule-evaluation-logs",
    auth=django_auth,
    response={200: List[RuleEvaluationLogOut], 403: ErrorOut},
)
def list_rule_evaluation_logs(
    request,
    trigger_type: str = "",
    result: str = "",
    record_id: str = "",
    rule_id: str = "",
    page: int = 1,
    page_size: int = 50,
):
    try:
        require_permission(request, Permission.CATEGORY_MANAGE)
    except (PermissionDenied, AuthenticationRequired, FirmNotFound) as exc:
        return 403, {"detail": str(exc)}

    page = max(1, int(page))
    page_size = max(1, min(200, int(page_size)))
    qs = RuleEvaluationLog.objects.filter(firm=request.firm).order_by("-evaluated_at", "-id")
    if trigger_type:
        qs = qs.filter(trigger_type=trigger_type)
    if result:
        qs = qs.filter(result=result)
    if record_id:
        qs = qs.filter(record_id=record_id)
    if rule_id:
        qs = qs.filter(rule_id=rule_id)

    offset = (page - 1) * page_size
    logs = qs[offset:offset + page_size]
    return 200, [_rule_evaluation_log_out(log) for log in logs]

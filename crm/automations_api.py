"""
Django Ninja router – Workflow Automation (v2.5)

Endpoints:
  GET    /crm/automations                    – list rules for the active firm
  POST   /crm/automations                    – create a new rule
  GET    /crm/automations/{rule_id}          – get a single rule
  PATCH  /crm/automations/{rule_id}          – update a rule (name, is_active, …)
  DELETE /crm/automations/{rule_id}          – delete a rule

  GET    /crm/automations/{rule_id}/runs     – last 20 execution runs for a rule

  GET    /crm/automations/templates          – list the 5 built-in templates
  POST   /crm/automations/from-template/{template_id}
                                             – create a rule from a template
"""

import logging
from typing import Any, Dict, List, Optional

from django.utils import timezone as tz
from ninja import Router, Schema
from ninja.security import django_auth

from crm.models import (
    AutomationRule,
    AutomationRun,
    AutomationRunStatus,
    AutomationTrigger,
)
from crm.soft_delete import perform_soft_delete
from firms.auth import InvitationRole, PermissionDenied, require_membership

logger = logging.getLogger(__name__)

automations_router = Router(tags=["automations"])

_auth = [django_auth]


# ---------------------------------------------------------------------------
# Built-in templates
# ---------------------------------------------------------------------------

AUTOMATION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "remind_assignee_before_task_due",
        "name": "Remind assignee 1 day before task due",
        "description": (
            "Sends an email reminder to the task assignee "
            "one day before a task is due."
        ),
        "trigger": AutomationTrigger.TASK_OVERDUE,
        "trigger_config": {"warning_days": 1},
        "conditions": [
            {"field": "days_until_due", "operator": "lte", "value": "1"},
        ],
        "actions": [
            {
                "type": "send_email",
                "to": "assignee",
                "subject": "Reminder: task due tomorrow — {{task_title}}",
                "body": (
                    "Hi {{assignee_name}},\n\n"
                    "This is a reminder that your task '{{task_title}}' "
                    "on record '{{record_title}}' is due tomorrow.\n\n"
                    "Log in to LeadLab to complete it."
                ),
            }
        ],
    },
    {
        "id": "notify_owner_record_won",
        "name": "Notify owner when record won",
        "description": (
            "Sends an email to the firm owner whenever a record "
            "is marked as Won."
        ),
        "trigger": AutomationTrigger.RECORD_STATUS_CHANGE,
        "trigger_config": {},
        "conditions": [
            {"field": "to_status", "operator": "eq", "value": "won"},
        ],
        "actions": [
            {
                "type": "send_email",
                "to": "owner",
                "subject": "🎉 PipelineRecord won: {{record_title}}",
                "body": (
                    "Great news!\n\n"
                    "PipelineRecord '{{record_title}}' has been marked as Won.\n\n"
                    "Log in to LeadLab for details."
                ),
            }
        ],
    },
    {
        "id": "welcome_email_record_created",
        "name": "Send welcome email when record created",
        "description": (
            "Automatically sends a welcome email to the customer "
            "when a new record is created."
        ),
        "trigger": AutomationTrigger.RECORD_CREATED,
        "trigger_config": {},
        "conditions": [],
        "actions": [
            {
                "type": "send_email",
                "to": "customer",
                "subject": "Welcome, {{customer_name}}!",
                "body": (
                    "Hi {{customer_name}},\n\n"
                    "Thank you for your interest. We have created a record "
                    "for you and will be in touch soon.\n\n"
                    "Best regards,\nThe Team"
                ),
            }
        ],
    },
    {
        "id": "mark_lost_30_days_inactive",
        "name": "Mark record as Lost after 30 days of inactivity",
        "description": (
            "Automatically updates a record's status to 'Lost' when there "
            "has been no recorded activity for 30 days."
        ),
        "trigger": AutomationTrigger.RECORD_INACTIVE,
        "trigger_config": {"inactive_days": 30},
        "conditions": [
            {"field": "record_status", "operator": "neq", "value": "won"},
            {"field": "record_status", "operator": "neq", "value": "lost"},
        ],
        "actions": [
            {"type": "update_field", "field": "status", "value": "lost"},
        ],
    },
    {
        "id": "followup_task_proposal_sent",
        "name": "Create follow-up task when proposal sent",
        "description": (
            "Creates a follow-up task on the record 3 days after a proposal "
            "is sent, so the assignee remembers to check in with the prospect."
        ),
        "trigger": AutomationTrigger.PROPOSAL_SENT,
        "trigger_config": {},
        "conditions": [],
        "actions": [
            {
                "type": "create_task",
                "title_template": "Follow up on sent proposal for {{record_title}}",
                "due_days_offset": 3,
                "priority": "medium",
                "assign_to_user_id": "inherit",
            }
        ],
    },
    {
        "id": "create_onboarding_task_proposal_accepted",
        "name": "Create onboarding task when proposal accepted",
        "description": (
            "Automatically creates a high-priority onboarding task "
            "when a proposal is accepted by the customer."
        ),
        "trigger": AutomationTrigger.PROPOSAL_ACCEPTED,
        "trigger_config": {},
        "conditions": [],
        "actions": [
            {
                "type": "create_task",
                "title_template": "Onboarding: {{customer_name}}",
                "due_days_offset": 7,
                "priority": "high",
                "assign_to_user_id": "inherit",
                "tags": ["onboarding"],
            }
        ],
    },
    {
        "id": "create_review_task_on_task_completed",
        "name": "Create review task when task completed",
        "description": (
            "Creates a review follow-up task 3 days after any task is completed, "
            "so nothing falls through the cracks."
        ),
        "trigger": AutomationTrigger.TASK_COMPLETED,
        "trigger_config": {},
        "conditions": [],
        "actions": [
            {
                "type": "create_task",
                "title_template": "Review: {{task_title}}",
                "due_days_offset": 3,
                "priority": "low",
                "assign_to_user_id": "inherit",
            }
        ],
    },
    {
        "id": "notify_owner_new_contact",
        "name": "Notify owner when new contact is created",
        "description": "Sends the firm owner an email whenever a new contact is added to the directory.",
        "trigger": AutomationTrigger.CONTACT_CREATED,
        "trigger_config": {},
        "conditions": [],
        "actions": [
            {
                "type": "send_email",
                "to": "owner",
                "subject": "Nový kontakt: {{customer_name}}",
                "body": (
                    "V adresáři byl přidán nový kontakt: {{customer_name}} ({{customer_email}}).\n\n"
                    "Přihlaste se do LeadLab pro zobrazení detailu."
                ),
            }
        ],
    },
]

_TEMPLATE_MAP: Dict[str, Dict[str, Any]] = {t["id"]: t for t in AUTOMATION_TEMPLATES}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AutomationRuleOut(Schema):
    id: str
    firm_id: str
    name: str
    is_active: bool
    trigger: str
    trigger_config: Dict[str, Any]
    conditions: List[Dict[str, Any]]
    condition_logic: str
    actions: List[Dict[str, Any]]
    created_at: str
    updated_at: str


class AutomationRuleIn(Schema):
    name: str
    is_active: bool = True
    trigger: str
    trigger_config: Dict[str, Any] = {}
    conditions: List[Dict[str, Any]] = []
    condition_logic: str = "and"
    actions: List[Dict[str, Any]] = []


class AutomationRulePatch(Schema):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    trigger: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    condition_logic: Optional[str] = None
    actions: Optional[List[Dict[str, Any]]] = None


class AutomationRunOut(Schema):
    id: str
    rule_id: str
    status: str
    triggered_at: str
    context: Dict[str, Any]
    error_message: str


class AutomationTemplateOut(Schema):
    id: str
    name: str
    description: str
    trigger: str
    trigger_config: Dict[str, Any]
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule_out(rule: AutomationRule) -> dict:
    return {
        "id": str(rule.id),
        "firm_id": str(rule.firm_id),
        "name": rule.name,
        "is_active": rule.is_active,
        "trigger": rule.trigger,
        "trigger_config": rule.trigger_config,
        "conditions": rule.conditions,
        "condition_logic": getattr(rule, "condition_logic", "and"),
        "actions": rule.actions,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
    }


def _run_out(run: AutomationRun) -> dict:
    return {
        "id": str(run.id),
        "rule_id": str(run.rule_id),
        "status": run.status,
        "triggered_at": run.triggered_at.isoformat(),
        "context": run.context,
        "error_message": run.error_message,
    }


# ---------------------------------------------------------------------------
# Built-in templates endpoints
# ---------------------------------------------------------------------------

@automations_router.get(
    "/automations/templates",
    auth=_auth,
    response={200: List[AutomationTemplateOut], 403: ErrorOut},
)
def list_automation_templates(request):
    """Return the 5 built-in automation templates."""
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    return 200, AUTOMATION_TEMPLATES


@automations_router.post(
    "/automations/from-template/{template_id}",
    auth=_auth,
    response={201: AutomationRuleOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_rule_from_template(request, template_id: str):
    """Create a new AutomationRule pre-populated from a built-in template."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    tmpl = _TEMPLATE_MAP.get(template_id)
    if not tmpl:
        return 404, {"detail": f"Template '{template_id}' not found."}

    rule = AutomationRule.objects.create(
        firm=request.firm,
        name=tmpl["name"],
        is_active=True,
        trigger=tmpl["trigger"],
        trigger_config=tmpl["trigger_config"],
        conditions=tmpl["conditions"],
        actions=tmpl["actions"],
    )
    return 201, _rule_out(rule)


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@automations_router.get(
    "/automations",
    auth=_auth,
    response={200: List[AutomationRuleOut], 403: ErrorOut},
)
def list_automation_rules(request):
    """List all AutomationRules for the active Firm."""
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    rules = AutomationRule.objects.filter(firm=request.firm).order_by("name")
    return 200, [_rule_out(r) for r in rules]


@automations_router.post(
    "/automations",
    auth=_auth,
    response={201: AutomationRuleOut, 400: ErrorOut, 403: ErrorOut},
)
def create_automation_rule(request, payload: AutomationRuleIn):
    """Create a new AutomationRule."""
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    valid_triggers = {t.value for t in AutomationTrigger}
    if payload.trigger not in valid_triggers:
        return 400, {
            "detail": f"Invalid trigger '{payload.trigger}'. "
                      f"Choose from: {', '.join(sorted(valid_triggers))}."
        }

    rule = AutomationRule.objects.create(
        firm=request.firm,
        name=payload.name,
        is_active=payload.is_active,
        trigger=payload.trigger,
        trigger_config=payload.trigger_config,
        conditions=payload.conditions,
        condition_logic=payload.condition_logic,
        actions=payload.actions,
    )
    return 201, _rule_out(rule)


@automations_router.get(
    "/automations/{rule_id}",
    auth=_auth,
    response={200: AutomationRuleOut, 403: ErrorOut, 404: ErrorOut},
)
def get_automation_rule(request, rule_id: str):
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = AutomationRule.objects.get(id=rule_id, firm=request.firm)
    except AutomationRule.DoesNotExist:
        return 404, {"detail": "Automation rule not found."}
    return 200, _rule_out(rule)


@automations_router.patch(
    "/automations/{rule_id}",
    auth=_auth,
    response={200: AutomationRuleOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def update_automation_rule(request, rule_id: str, payload: AutomationRulePatch):
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = AutomationRule.objects.get(id=rule_id, firm=request.firm)
    except AutomationRule.DoesNotExist:
        return 404, {"detail": "Automation rule not found."}

    update_data = payload.dict(exclude_none=True)

    if "trigger" in update_data:
        valid_triggers = {t.value for t in AutomationTrigger}
        if update_data["trigger"] not in valid_triggers:
            return 400, {"detail": f"Invalid trigger '{update_data['trigger']}'."}

    for field, value in update_data.items():
        setattr(rule, field, value)
    rule.save()
    return 200, _rule_out(rule)


@automations_router.delete(
    "/automations/{rule_id}",
    auth=_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_automation_rule(request, rule_id: str):
    try:
        require_membership(request, min_role=InvitationRole.ADMIN)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = AutomationRule.objects.get(id=rule_id, firm=request.firm)
    except AutomationRule.DoesNotExist:
        return 404, {"detail": "Automation rule not found."}
    perform_soft_delete(rule, request.user)
    return 204, None


@automations_router.get(
    "/automations/{rule_id}/runs",
    auth=_auth,
    response={200: List[AutomationRunOut], 403: ErrorOut, 404: ErrorOut},
)
def list_automation_runs(request, rule_id: str, limit: int = 20):
    """Return the most recent execution runs for a rule (default: 20)."""
    try:
        require_membership(request)
    except PermissionDenied as exc:
        return 403, {"detail": str(exc)}

    try:
        rule = AutomationRule.objects.get(id=rule_id, firm=request.firm)
    except AutomationRule.DoesNotExist:
        return 404, {"detail": "Automation rule not found."}

    runs = AutomationRun.objects.filter(rule=rule).order_by("-triggered_at")[: min(limit, 100)]
    return 200, [_run_out(r) for r in runs]

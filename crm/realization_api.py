"""
Realization API — Phase 4.1

Endpoints:
  /api/v1/crm/realizations          LIST + CREATE
  /api/v1/crm/realizations/{id}     GET / PATCH / DELETE
  /api/v1/crm/realizations/{id}/milestones          LIST + CREATE
  /api/v1/crm/realizations/{id}/milestones/{mid}    PATCH / DELETE
  /api/v1/crm/realizations/{id}/activities          LIST (timeline)
  /api/v1/crm/realizations/{id}/tasks               LIST (entity-scoped tasks)
"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from crm.models import (
    Activity,
    Customer,
    Lead,
    Milestone,
    Realization,
    RealizationStatus,
    Task,
)
from crm.api import _user_display_name, _activity_out as _shared_activity_out, _task_out as _shared_task_out, TaskOut as _SharedTaskOut
from crm.events import broadcast_event
from firms.auth import require_active_subscription, require_membership

realization_router = Router(tags=["realizations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _firm(request):
    return getattr(request, "firm", None)


# ---------------------------------------------------------------------------
# Schemas — Realization
# ---------------------------------------------------------------------------

class RealizationIn(Schema):
    title: str
    status: str = RealizationStatus.PLANNED
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_to_id: Optional[str] = None
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None


class RealizationPatch(Schema):
    title: Optional[str] = None
    status: Optional[str] = None
    lead_id: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_to_id: Optional[str] = None
    start_date: Optional[dt.date] = None
    end_date: Optional[dt.date] = None


class MilestoneOut(Schema):
    id: str
    realization_id: str
    name: str
    date: dt.date
    is_completed: bool
    description: str
    created_at: dt.datetime


class RealizationOut(Schema):
    id: str
    firm_id: str
    title: str
    status: str
    lead_id: Optional[str]
    lead_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    assigned_to_id: Optional[str]
    assigned_to_name: Optional[str]
    start_date: Optional[dt.date]
    end_date: Optional[dt.date]
    milestones: List[MilestoneOut]
    created_at: dt.datetime
    updated_at: dt.datetime

    @staticmethod
    def from_obj(obj: Realization) -> "RealizationOut":
        lead_title = None
        if obj.lead_id:
            try:
                lead_title = obj.lead.title
            except Exception:
                pass

        customer_name = None
        if obj.customer_id:
            try:
                c = obj.customer
                customer_name = f"{c.first_name} {c.last_name}".strip() or c.company_name
            except Exception:
                pass

        assigned_name = None
        if obj.assigned_to_id:
            try:
                u = obj.assigned_to
                assigned_name = f"{u.first_name} {u.last_name}".strip() or u.email
            except Exception:
                pass

        milestones = [
            MilestoneOut(
                id=str(m.id),
                realization_id=str(m.realization_id),
                name=m.name,
                date=m.date,
                is_completed=m.is_completed,
                description=m.description,
                created_at=m.created_at,
            )
            for m in obj.milestones.all()
        ]

        return RealizationOut(
            id=str(obj.id),
            firm_id=str(obj.firm_id),
            title=obj.title,
            status=obj.status,
            lead_id=str(obj.lead_id) if obj.lead_id else None,
            lead_title=lead_title,
            customer_id=str(obj.customer_id) if obj.customer_id else None,
            customer_name=customer_name,
            assigned_to_id=str(obj.assigned_to_id) if obj.assigned_to_id else None,
            assigned_to_name=assigned_name,
            start_date=obj.start_date,
            end_date=obj.end_date,
            milestones=milestones,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


# ---------------------------------------------------------------------------
# Schemas — Milestone
# ---------------------------------------------------------------------------

class MilestoneIn(Schema):
    name: str
    date: dt.date
    is_completed: bool = False
    description: str = ""


class MilestonePatch(Schema):
    name: Optional[str] = None
    date: Optional[dt.date] = None
    is_completed: Optional[bool] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Realization endpoints
# ---------------------------------------------------------------------------

@realization_router.get("/realizations", response=List[RealizationOut], auth=django_auth)
def list_realizations(
    request,
    status: Optional[str] = None,
    assigned_to_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    customer_id: Optional[str] = None,
):
    firm = _firm(request)
    require_membership(request)

    qs = (
        Realization.objects.filter(firm=firm)
        .select_related("lead", "customer", "assigned_to")
        .prefetch_related("milestones")
    )
    if status:
        qs = qs.filter(status=status)
    if assigned_to_id:
        qs = qs.filter(assigned_to_id=assigned_to_id)
    if lead_id:
        qs = qs.filter(lead_id=lead_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    return [RealizationOut.from_obj(r) for r in qs]


@realization_router.post("/realizations", response=RealizationOut, auth=django_auth)
def create_realization(request, payload: RealizationIn):
    firm = _firm(request)
    require_membership(request)
    require_active_subscription(firm)

    lead = None
    if payload.lead_id:
        lead = Lead.objects.filter(firm=firm, id=payload.lead_id).first()

    customer = None
    if payload.customer_id:
        customer = Customer.objects.filter(firm=firm, id=payload.customer_id).first()

    assigned_to = None
    if payload.assigned_to_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assigned_to = User.objects.filter(id=payload.assigned_to_id).first()

    realization = Realization.objects.create(
        firm=firm,
        title=payload.title,
        status=payload.status,
        lead=lead,
        customer=customer,
        assigned_to=assigned_to,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )

    out = RealizationOut.from_obj(realization)
    broadcast_event(firm=firm, event="realization.created", payload=out.dict())
    return out


@realization_router.get("/realizations/{realization_id}", response=RealizationOut, auth=django_auth)
def get_realization(request, realization_id: str):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).select_related(
        "lead", "customer", "assigned_to"
    ).prefetch_related("milestones").first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    return RealizationOut.from_obj(realization)


@realization_router.patch("/realizations/{realization_id}", response=RealizationOut, auth=django_auth)
def update_realization(request, realization_id: str, payload: RealizationPatch):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).select_related(
        "lead", "customer", "assigned_to"
    ).prefetch_related("milestones").first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    old_status = realization.status  # capture before save

    if payload.title is not None:
        realization.title = payload.title
    if payload.status is not None:
        realization.status = payload.status
    if payload.start_date is not None:
        realization.start_date = payload.start_date
    if payload.end_date is not None:
        realization.end_date = payload.end_date

    if payload.lead_id is not None:
        if payload.lead_id == "":
            realization.lead = None
        else:
            realization.lead = Lead.objects.filter(firm=firm, id=payload.lead_id).first()

    if payload.customer_id is not None:
        if payload.customer_id == "":
            realization.customer = None
        else:
            realization.customer = Customer.objects.filter(firm=firm, id=payload.customer_id).first()

    if payload.assigned_to_id is not None:
        if payload.assigned_to_id == "":
            realization.assigned_to = None
        else:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            realization.assigned_to = User.objects.filter(id=payload.assigned_to_id).first()

    realization.save()

    out = RealizationOut.from_obj(realization)
    broadcast_event(firm=firm, event="realization.updated", payload=out.dict())

    # Fire realization_status_change automation if status changed
    if payload.status is not None and payload.status != old_status:
        customer_name = ""
        customer_email = ""
        if realization.customer:
            customer_name = f"{realization.customer.first_name} {realization.customer.last_name}".strip()
            customer_email = realization.customer.email or ""
        _auto_ctx = {
            "realization_id": str(realization.id),
            "realization_title": realization.title,
            "from_status": old_status,
            "to_status": realization.status,
            "firm_id": str(firm.id),
            "assignee_email": realization.assigned_to.email if realization.assigned_to else "",
            "assignee_name": (
                f"{realization.assigned_to.first_name} {realization.assigned_to.last_name}".strip()
                if realization.assigned_to else ""
            ),
            "customer_name": customer_name,
            "customer_email": customer_email,
        }
        from crm.tasks import evaluate_automation_rules
        from django.db import transaction as db_tx
        db_tx.on_commit(
            lambda ctx=_auto_ctx: evaluate_automation_rules.delay(
                "realization_status_change", str(firm.id), ctx
            )
        )

    return out


@realization_router.delete("/realizations/{realization_id}", response={204: None}, auth=django_auth)
def delete_realization(request, realization_id: str):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    broadcast_event(firm=firm, event="realization.deleted", payload={"id": realization_id})
    realization.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Milestone endpoints
# ---------------------------------------------------------------------------

@realization_router.get(
    "/realizations/{realization_id}/milestones",
    response=List[MilestoneOut],
    auth=django_auth,
)
def list_milestones(request, realization_id: str):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    milestones = Milestone.objects.filter(realization=realization)
    return [
        MilestoneOut(
            id=str(m.id),
            realization_id=str(m.realization_id),
            name=m.name,
            date=m.date,
            is_completed=m.is_completed,
            description=m.description,
            created_at=m.created_at,
        )
        for m in milestones
    ]


@realization_router.post(
    "/realizations/{realization_id}/milestones",
    response=MilestoneOut,
    auth=django_auth,
)
def create_milestone(request, realization_id: str, payload: MilestoneIn):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    milestone = Milestone.objects.create(
        realization=realization,
        name=payload.name,
        date=payload.date,
        is_completed=payload.is_completed,
        description=payload.description,
    )

    return MilestoneOut(
        id=str(milestone.id),
        realization_id=str(milestone.realization_id),
        name=milestone.name,
        date=milestone.date,
        is_completed=milestone.is_completed,
        description=milestone.description,
        created_at=milestone.created_at,
    )


@realization_router.patch(
    "/realizations/{realization_id}/milestones/{milestone_id}",
    response=MilestoneOut,
    auth=django_auth,
)
def update_milestone(request, realization_id: str, milestone_id: str, payload: MilestonePatch):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    milestone = Milestone.objects.filter(realization=realization, id=milestone_id).first()
    if not milestone:
        from ninja import errors
        raise errors.HttpError(404, "Milestone not found")

    was_completed = milestone.is_completed

    if payload.name is not None:
        milestone.name = payload.name
    if payload.date is not None:
        milestone.date = payload.date
    if payload.is_completed is not None:
        milestone.is_completed = payload.is_completed
    if payload.description is not None:
        milestone.description = payload.description
    milestone.save()

    # Fire milestone_completed automation when milestone is just marked done
    if not was_completed and milestone.is_completed:
        _auto_ctx = {
            "milestone_id": str(milestone.id),
            "milestone_name": milestone.name,
            "milestone_date": milestone.date.isoformat(),
            "realization_id": str(realization.id),
            "realization_title": realization.title,
            "firm_id": str(firm.id),
        }
        from crm.tasks import evaluate_automation_rules
        from django.db import transaction as db_tx
        db_tx.on_commit(
            lambda ctx=_auto_ctx: evaluate_automation_rules.delay(
                "milestone_completed", str(firm.id), ctx
            )
        )

    return MilestoneOut(
        id=str(milestone.id),
        realization_id=str(milestone.realization_id),
        name=milestone.name,
        date=milestone.date,
        is_completed=milestone.is_completed,
        description=milestone.description,
        created_at=milestone.created_at,
    )


@realization_router.delete(
    "/realizations/{realization_id}/milestones/{milestone_id}",
    response={204: None},
    auth=django_auth,
)
def delete_milestone(request, realization_id: str, milestone_id: str):
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    milestone = Milestone.objects.filter(realization=realization, id=milestone_id).first()
    if not milestone:
        from ninja import errors
        raise errors.HttpError(404, "Milestone not found")

    milestone.delete()
    return 204, None


# ---------------------------------------------------------------------------
# Activity timeline endpoint
# ---------------------------------------------------------------------------

class _ActivityOut(Schema):
    id: str
    entity_type: str
    entity_id: str
    lead_id: Optional[str]
    user_id: Optional[str]
    user_name: Optional[str]
    user_avatar_url: Optional[str] = None
    type: str
    content_text: str
    metadata: dict
    created_at: dt.datetime
    tool_payload: Optional[dict] = None
    reactions: List[dict] = []


@realization_router.get(
    "/realizations/{realization_id}/activities",
    response=List[_ActivityOut],
    auth=django_auth,
)
def list_realization_activities(
    request,
    realization_id: str,
    page: int = 1,
    page_size: int = 20,
):
    """Return the activity timeline for a Realization, newest first (paginated)."""
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(realization=realization).select_related('user').prefetch_related('reactions').order_by("-created_at")[offset:offset + page_size]

    return [_shared_activity_out(a, request.user) for a in activities]


@realization_router.get(
    "/realizations/{realization_id}/tasks",
    response=List[_SharedTaskOut],
    auth=django_auth,
)
def list_realization_tasks(
    request,
    realization_id: str,
    page: int = 1,
    page_size: int = 20,
):
    """Return tasks linked to a Realization, newest first (paginated).

    Mirrors ``/realizations/{id}/activities``. Tenant-isolated via
    ``firm=request.firm`` filter on the Realization lookup, and the task
    queryset implicitly inherits that scope through the FK.
    """
    firm = _firm(request)
    require_membership(request)

    realization = Realization.objects.filter(firm=firm, id=realization_id).first()
    if not realization:
        from ninja import errors
        raise errors.HttpError(404, "Realization not found")

    offset = (page - 1) * page_size
    tasks = (
        Task.objects.filter(realization=realization)
        .select_related("assigned_to", "completed_by", "created_by", "lead", "proposal", "customer")
        .order_by("-created_at")[offset:offset + page_size]
    )
    return [_shared_task_out(t, request.user) for t in tasks]

"""
Management API — Phase 4.2

Endpoints:
  /api/v1/crm/management          LIST + CREATE
  /api/v1/crm/management/{id}     GET / PATCH / DELETE
  /api/v1/crm/management/{id}/activities  LIST (timeline)
"""
from __future__ import annotations

import datetime as dt
from typing import List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from crm.models import (
    Activity,
    Customer,
    Management,
    ManagementStatus,
    ManagementType,
    Realization,
)
from crm.api import _user_display_name
from crm.events import broadcast_event
from firms.auth import require_active_subscription, require_membership

management_router = Router(tags=["management"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _firm(request):
    return getattr(request, "firm", None)


def _sla_color(expires_at: Optional[dt.datetime]) -> Optional[str]:
    """Return 'green' | 'yellow' | 'red' based on how soon the SLA expires."""
    if not expires_at:
        return None
    now = dt.datetime.now(tz=expires_at.tzinfo)
    delta = expires_at - now
    days = delta.total_seconds() / 86400
    if days < 0:
        return "red"
    if days <= 7:
        return "yellow"
    return "green"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ManagementIn(Schema):
    title: str
    notes: str = ""
    type: str = ManagementType.CARE
    status: str = ManagementStatus.OPEN
    realization_id: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_to_id: Optional[str] = None
    expires_at: Optional[dt.datetime] = None


class ManagementPatch(Schema):
    title: Optional[str] = None
    notes: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    realization_id: Optional[str] = None
    customer_id: Optional[str] = None
    assigned_to_id: Optional[str] = None
    expires_at: Optional[dt.datetime] = None
    clear_expires_at: bool = False


class ManagementOut(Schema):
    id: str
    firm_id: str
    title: str
    notes: str
    type: str
    status: str
    realization_id: Optional[str]
    realization_title: Optional[str]
    customer_id: Optional[str]
    customer_name: Optional[str]
    assigned_to_id: Optional[str]
    assigned_to_name: Optional[str]
    expires_at: Optional[dt.datetime]
    sla_color: Optional[str]
    created_at: dt.datetime
    updated_at: dt.datetime

    @staticmethod
    def from_obj(obj: Management) -> "ManagementOut":
        realization_title = None
        if obj.realization_id:
            try:
                realization_title = obj.realization.title
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

        return ManagementOut(
            id=str(obj.id),
            firm_id=str(obj.firm_id),
            title=obj.title,
            notes=obj.notes,
            type=obj.type,
            status=obj.status,
            realization_id=str(obj.realization_id) if obj.realization_id else None,
            realization_title=realization_title,
            customer_id=str(obj.customer_id) if obj.customer_id else None,
            customer_name=customer_name,
            assigned_to_id=str(obj.assigned_to_id) if obj.assigned_to_id else None,
            assigned_to_name=assigned_name,
            expires_at=obj.expires_at,
            sla_color=_sla_color(obj.expires_at),
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@management_router.get("/management", response=List[ManagementOut], auth=django_auth)
def list_management(
    request,
    status: Optional[str] = None,
    type: Optional[str] = None,
    assigned_to_id: Optional[str] = None,
    realization_id: Optional[str] = None,
    customer_id: Optional[str] = None,
):
    firm = _firm(request)
    require_membership(request)

    qs = (
        Management.objects.filter(firm=firm)
        .select_related("realization", "customer", "assigned_to")
    )
    if status:
        qs = qs.filter(status=status)
    if type:
        qs = qs.filter(type=type)
    if assigned_to_id:
        qs = qs.filter(assigned_to_id=assigned_to_id)
    if realization_id:
        qs = qs.filter(realization_id=realization_id)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    return [ManagementOut.from_obj(m) for m in qs]


@management_router.post("/management", response=ManagementOut, auth=django_auth)
def create_management(request, payload: ManagementIn):
    firm = _firm(request)
    require_membership(request)
    require_active_subscription(firm)

    realization = None
    if payload.realization_id:
        realization = Realization.objects.filter(firm=firm, id=payload.realization_id).first()

    customer = None
    if payload.customer_id:
        customer = Customer.objects.filter(firm=firm, id=payload.customer_id).first()

    assigned_to = None
    if payload.assigned_to_id:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assigned_to = User.objects.filter(id=payload.assigned_to_id).first()

    management = Management.objects.create(
        firm=firm,
        title=payload.title,
        notes=payload.notes,
        type=payload.type,
        status=payload.status,
        realization=realization,
        customer=customer,
        assigned_to=assigned_to,
        expires_at=payload.expires_at,
    )

    out = ManagementOut.from_obj(management)
    broadcast_event(firm=firm, event="management.created", payload=out.dict())
    return out


@management_router.get("/management/{management_id}", response=ManagementOut, auth=django_auth)
def get_management(request, management_id: str):
    firm = _firm(request)
    require_membership(request)

    record = Management.objects.filter(firm=firm, id=management_id).select_related(
        "realization", "customer", "assigned_to"
    ).first()
    if not record:
        from ninja import errors
        raise errors.HttpError(404, "Management record not found")

    return ManagementOut.from_obj(record)


@management_router.patch("/management/{management_id}", response=ManagementOut, auth=django_auth)
def update_management(request, management_id: str, payload: ManagementPatch):
    firm = _firm(request)
    require_membership(request)

    record = Management.objects.filter(firm=firm, id=management_id).select_related(
        "realization", "customer", "assigned_to"
    ).first()
    if not record:
        from ninja import errors
        raise errors.HttpError(404, "Management record not found")

    if payload.title is not None:
        record.title = payload.title
    if payload.notes is not None:
        record.notes = payload.notes
    if payload.type is not None:
        record.type = payload.type
    if payload.status is not None:
        record.status = payload.status
    if payload.expires_at is not None:
        record.expires_at = payload.expires_at
    elif payload.clear_expires_at:
        record.expires_at = None

    if payload.realization_id is not None:
        if payload.realization_id == "":
            record.realization = None
        else:
            record.realization = Realization.objects.filter(firm=firm, id=payload.realization_id).first()

    if payload.customer_id is not None:
        if payload.customer_id == "":
            record.customer = None
        else:
            record.customer = Customer.objects.filter(firm=firm, id=payload.customer_id).first()

    if payload.assigned_to_id is not None:
        if payload.assigned_to_id == "":
            record.assigned_to = None
        else:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            record.assigned_to = User.objects.filter(id=payload.assigned_to_id).first()

    record.save()

    out = ManagementOut.from_obj(record)
    broadcast_event(firm=firm, event="management.updated", payload=out.dict())
    return out


@management_router.delete("/management/{management_id}", response={204: None}, auth=django_auth)
def delete_management(request, management_id: str):
    firm = _firm(request)
    require_membership(request)

    record = Management.objects.filter(firm=firm, id=management_id).first()
    if not record:
        from ninja import errors
        raise errors.HttpError(404, "Management record not found")

    broadcast_event(firm=firm, event="management.deleted", payload={"id": management_id})
    record.delete()
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
    type: str
    content_text: str
    metadata: dict
    created_at: dt.datetime


@management_router.get(
    "/management/{management_id}/activities",
    response=List[_ActivityOut],
    auth=django_auth,
)
def list_management_activities(
    request,
    management_id: str,
    page: int = 1,
    page_size: int = 20,
):
    """Return the activity timeline for a Management record, newest first (paginated)."""
    firm = _firm(request)
    require_membership(request)

    record = Management.objects.filter(firm=firm, id=management_id).first()
    if not record:
        from ninja import errors
        raise errors.HttpError(404, "Management record not found")

    offset = (page - 1) * page_size
    activities = Activity.objects.filter(management=record).select_related('user').order_by("-created_at")[offset:offset + page_size]

    return [
        {
            "id": str(a.id),
            "entity_type": a.entity_type,
            "entity_id": a.entity_id,
            "lead_id": str(a.lead_id) if a.lead_id else None,
            "user_id": str(a.user_id) if a.user_id else None,
            "user_name": _user_display_name(a.user),
            "type": a.type,
            "content_text": a.content_text,
            "metadata": a.metadata,
            "created_at": a.created_at,
        }
        for a in activities
    ]

"""
Django Ninja router – Outbound Webhooks

Endpoints for managing webhook endpoints and viewing delivery logs.
"""

from typing import List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import InvitationRole, require_membership
from firms.models import Firm, WebhookDelivery, WebhookEndpoint
from firms.token_auth import BearerTokenAuth

router = Router(tags=["webhooks"])

_auth = [django_auth, BearerTokenAuth()]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WebhookEndpointOut(Schema):
    id: str
    url: str
    events: List[str]
    is_active: bool
    created_at: str
    updated_at: str


class WebhookEndpointIn(Schema):
    url: str
    events: List[str] = []
    is_active: bool = True


class WebhookEndpointUpdateIn(Schema):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookDeliveryOut(Schema):
    id: str
    event: str
    status_code: Optional[int]
    success: bool
    error: str
    delivered_at: str
    duration_ms: int


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _endpoint_out(ep: WebhookEndpoint) -> dict:
    return {
        "id": str(ep.id),
        "url": ep.url,
        "events": ep.events,
        "is_active": ep.is_active,
        "created_at": ep.created_at.isoformat(),
        "updated_at": ep.updated_at.isoformat(),
    }


def _delivery_out(d: WebhookDelivery) -> dict:
    return {
        "id": str(d.id),
        "event": d.event,
        "status_code": d.status_code,
        "success": d.success,
        "error": d.error,
        "delivered_at": d.delivered_at.isoformat(),
        "duration_ms": d.duration_ms,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{firm_id}/webhooks",
    auth=_auth,
    response={200: List[WebhookEndpointOut], 403: ErrorOut},
)
def list_webhooks(request, firm_id: str):
    """List all webhook endpoints for a Firm (Admin/Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found."}

    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can manage webhooks."}

    endpoints = WebhookEndpoint.objects.filter(firm=firm)
    return 200, [_endpoint_out(ep) for ep in endpoints]


@router.post(
    "/{firm_id}/webhooks",
    auth=_auth,
    response={201: WebhookEndpointOut, 400: ErrorOut, 403: ErrorOut},
)
def create_webhook(request, firm_id: str, payload: WebhookEndpointIn):
    """Create a new webhook endpoint (Admin/Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 403, {"detail": "Firm not found."}

    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can manage webhooks."}

    if not payload.url.strip():
        return 400, {"detail": "URL is required."}

    ep = WebhookEndpoint.objects.create(
        firm=firm,
        url=payload.url.strip(),
        events=payload.events,
        is_active=payload.is_active,
    )
    return 201, _endpoint_out(ep)


@router.patch(
    "/{firm_id}/webhooks/{webhook_id}",
    auth=_auth,
    response={200: WebhookEndpointOut, 403: ErrorOut, 404: ErrorOut},
)
def update_webhook(request, firm_id: str, webhook_id: str, payload: WebhookEndpointUpdateIn):
    """Update a webhook endpoint (Admin/Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can manage webhooks."}

    try:
        ep = WebhookEndpoint.objects.get(id=webhook_id, firm=firm)
    except WebhookEndpoint.DoesNotExist:
        return 404, {"detail": "Webhook not found."}

    update_fields = []
    if payload.url is not None:
        ep.url = payload.url.strip()
        update_fields.append("url")
    if payload.events is not None:
        ep.events = payload.events
        update_fields.append("events")
    if payload.is_active is not None:
        ep.is_active = payload.is_active
        update_fields.append("is_active")
    if update_fields:
        ep.save(update_fields=update_fields + ["updated_at"])

    return 200, _endpoint_out(ep)


@router.delete(
    "/{firm_id}/webhooks/{webhook_id}",
    auth=_auth,
    response={204: None, 403: ErrorOut, 404: ErrorOut},
)
def delete_webhook(request, firm_id: str, webhook_id: str):
    """Delete a webhook endpoint (Admin/Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can manage webhooks."}

    try:
        ep = WebhookEndpoint.objects.get(id=webhook_id, firm=firm)
    except WebhookEndpoint.DoesNotExist:
        return 404, {"detail": "Webhook not found."}

    ep.delete()
    return 204, None


@router.get(
    "/{firm_id}/webhooks/{webhook_id}/deliveries",
    auth=_auth,
    response={200: List[WebhookDeliveryOut], 403: ErrorOut, 404: ErrorOut},
)
def list_deliveries(request, firm_id: str, webhook_id: str, page: int = 1, page_size: int = 20):
    """List recent delivery attempts for a webhook endpoint (Admin/Owner only)."""
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    try:
        membership = require_membership(request)
    except Exception as exc:
        return 403, {"detail": str(exc)}

    if str(request.firm.id) != str(firm.id):
        return 403, {"detail": "Firm mismatch."}

    if not membership.is_admin_or_above:
        return 403, {"detail": "Only Admins and Owners can view delivery logs."}

    try:
        ep = WebhookEndpoint.objects.get(id=webhook_id, firm=firm)
    except WebhookEndpoint.DoesNotExist:
        return 404, {"detail": "Webhook not found."}

    page_size = min(max(page_size, 1), 100)
    offset = (page - 1) * page_size
    deliveries = ep.deliveries.all()[offset: offset + page_size]
    return 200, [_delivery_out(d) for d in deliveries]

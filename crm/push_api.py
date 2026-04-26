"""
Push notification API — Web Push subscription management and VAPID public key endpoint.

Endpoints:
  GET  /api/v1/push/vapid-public-key   — return the server's VAPID public key
  POST /api/v1/push/subscribe          — register or update a push subscription
  POST /api/v1/push/unsubscribe        — remove a push subscription
"""
from typing import Optional

from django.conf import settings
from ninja import Router, Schema
from ninja.security import django_auth

from crm.models import PushSubscription
from firms.token_auth import BearerTokenAuth

router = Router(tags=["push"], auth=[django_auth, BearerTokenAuth()])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class VapidKeyOut(Schema):
    public_key: str


class PushSubscribeIn(Schema):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: Optional[str] = ""


class PushSubscribeOut(Schema):
    id: str
    endpoint: str
    push_enabled: bool


class PushUnsubscribeIn(Schema):
    endpoint: str


class MessageOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/vapid-public-key", response=VapidKeyOut, auth=None)
def vapid_public_key(request):
    """Return the server's VAPID public key (unauthenticated)."""
    return {"public_key": getattr(settings, "VAPID_PUBLIC_KEY", "")}


@router.post("/subscribe", response={200: PushSubscribeOut, 400: MessageOut})
def subscribe(request, payload: PushSubscribeIn):
    """
    Register (or update) a Web Push subscription for the authenticated user.

    If a subscription with the same endpoint already exists for any user it is
    re-assigned to the current user and re-enabled.
    """
    sub, _ = PushSubscription.objects.update_or_create(
        endpoint=payload.endpoint,
        defaults={
            "user": request.user,
            "p256dh": payload.p256dh,
            "auth": payload.auth,
            "user_agent": payload.user_agent or "",
            "push_enabled": True,
        },
    )
    return 200, {
        "id": str(sub.id),
        "endpoint": sub.endpoint,
        "push_enabled": sub.push_enabled,
    }


@router.post("/unsubscribe", response={200: MessageOut, 404: MessageOut})
def unsubscribe(request, payload: PushUnsubscribeIn):
    """Remove a push subscription belonging to the authenticated user."""
    deleted, _ = PushSubscription.objects.filter(
        user=request.user,
        endpoint=payload.endpoint,
    ).delete()
    if deleted:
        return 200, {"detail": "Unsubscribed."}
    return 404, {"detail": "Subscription not found."}

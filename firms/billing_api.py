"""
firms.billing_api
=================
Billing endpoints — Stripe Checkout session creation for upgrading to Pro.

Endpoint:
    POST /firms/{firm_id}/billing/checkout   — Owner only; returns Stripe Checkout URL.
"""
import logging

from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import MembershipRole, PermissionDenied, FirmNotFound, require_membership
from firms.models import Firm

logger = logging.getLogger(__name__)

billing_router = Router(tags=["billing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutOut(Schema):
    checkout_url: str


class ErrorOut(Schema):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@billing_router.post(
    "/{firm_id}/billing/checkout",
    auth=django_auth,
    response={200: CheckoutOut, 400: ErrorOut, 403: ErrorOut, 404: ErrorOut},
)
def create_checkout_session(request, firm_id: str):
    """
    Create a Stripe Checkout session to upgrade the Firm to Pro.

    Owner only.  Returns a ``checkout_url`` that the client should redirect the
    user to.  The Firm's Stripe fields are updated when Stripe sends the
    ``checkout.session.completed`` webhook.

    Gracefully returns ``400`` when Stripe credentials are not configured in
    the environment (``STRIPE_SECRET_KEY`` / ``STRIPE_PRICE_ID``).
    """
    import stripe
    from django.conf import settings

    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}

    # Require membership resolved by TenantMiddleware for this specific firm.
    # Because TenantMiddleware resolves the firm from the X-Firm-ID header we
    # must do a manual membership check against the URL-based firm_id.
    from firms.models import Membership
    try:
        caller_membership = Membership.objects.get(user=request.user, firm=firm)
    except Membership.DoesNotExist:
        return 403, {"detail": "You are not a member of this Firm."}

    if not caller_membership.is_owner:
        return 403, {"detail": "Only the Owner can manage billing."}

    if firm.subscription_tier == "pro" and firm.subscription_active:
        return 400, {"detail": "This Firm already has an active Pro subscription."}

    stripe_key = getattr(settings, "STRIPE_SECRET_KEY", "")
    price_id = getattr(settings, "STRIPE_PRICE_ID", "")

    if not stripe_key or not price_id:
        logger.warning(
            "create_checkout_session: Stripe is not configured "
            "(missing STRIPE_SECRET_KEY or STRIPE_PRICE_ID)."
        )
        return 400, {"detail": "Billing is not configured. Please contact support."}

    stripe.api_key = stripe_key

    frontend_url = getattr(settings, "FRONTEND_URL", "")
    success_url = f"{frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{frontend_url}/billing/cancel"

    session_kwargs = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "metadata": {"firm_id": str(firm.id)},
        "success_url": success_url,
        "cancel_url": cancel_url,
    }
    if firm.stripe_customer_id:
        session_kwargs["customer"] = firm.stripe_customer_id

    try:
        session = stripe.checkout.Session.create(**session_kwargs)
    except stripe.StripeError as exc:
        logger.error(
            "create_checkout_session: Stripe error for firm %s: %s", firm.id, exc
        )
        return 400, {"detail": "Failed to create checkout session. Please try again."}

    return 200, {"checkout_url": session.url}

"""
firms.stripe_webhook
====================
Public Django Ninja router that handles incoming Stripe webhook events.

Mounted at ``/api/v1/stripe/``.  The single endpoint:

    POST /stripe/webhook

verifies the Stripe-Signature header and processes the following events:

* ``checkout.session.completed``      — Upgrade Firm to Pro.
* ``customer.subscription.updated``   — Sync subscription status.
* ``customer.subscription.deleted``   — Downgrade Firm to Free.
* ``invoice.payment_failed``          — Mark subscription as inactive.

No Django authentication is required; the Stripe signature is the only
trust anchor.  Gracefully no-ops when ``STRIPE_WEBHOOK_SECRET`` is not
configured.
"""
import json
import logging

from ninja import Router

logger = logging.getLogger(__name__)

webhook_router = Router(tags=["stripe"])


@webhook_router.post(
    "/webhook",
    auth=None,
    response={200: dict, 400: dict},
)
def stripe_webhook(request):
    """
    Receive and process a Stripe webhook event.

    Verifies the ``Stripe-Signature`` header before processing any event.
    Returns ``200 {"received": true}`` on success, or ``400`` on signature
    or configuration errors.
    """
    import stripe
    from django.conf import settings

    from firms.models import Firm

    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    stripe_key = getattr(settings, "STRIPE_SECRET_KEY", "")

    if not stripe_key:
        logger.warning("stripe_webhook: STRIPE_SECRET_KEY is not configured.")
        return 400, {"detail": "Stripe is not configured."}

    stripe.api_key = stripe_key

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    # Parse the raw payload as a plain Python dict so all handlers can use
    # standard dict access (.get, [], etc.) regardless of the stripe library
    # version.
    try:
        event = json.loads(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("stripe_webhook: Failed to parse payload: %s", exc)
        return 400, {"detail": "Invalid payload."}

    # Verify the Stripe signature when a webhook secret is configured.
    if webhook_secret:
        try:
            stripe.WebhookSignature.verify_header(payload, sig_header, webhook_secret)
        except stripe.SignatureVerificationError as exc:
            logger.warning("stripe_webhook: Signature verification failed: %s", exc)
            return 400, {"detail": "Invalid Stripe signature."}
    else:
        logger.warning(
            "stripe_webhook: STRIPE_WEBHOOK_SECRET is not set — "
            "skipping signature verification."
        )

    event_type = event.get("type", "")
    data = (event.get("data") or {}).get("object") or {}

    logger.info("stripe_webhook: Received event '%s'.", event_type)

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(data, Firm)

        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data, Firm)

        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data, Firm)

        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data, Firm)

        else:
            logger.debug("stripe_webhook: Unhandled event type '%s'.", event_type)

    except Exception as exc:  # noqa: BLE001  # broad catch — never surface to Stripe
        logger.exception(
            "stripe_webhook: Unhandled error processing event '%s': %s",
            event_type,
            exc,
        )
        # Return 200 so Stripe does not keep retrying for transient errors.

    return 200, {"received": True}


# ---------------------------------------------------------------------------
# Private event handlers
# ---------------------------------------------------------------------------

def _handle_checkout_completed(session: dict, Firm) -> None:
    """Upgrade the Firm to Pro when a Checkout session completes."""
    firm_id = (session.get("metadata") or {}).get("firm_id")
    if not firm_id:
        logger.warning(
            "_handle_checkout_completed: No firm_id in session metadata. "
            "Session id=%s", session.get("id")
        )
        return

    customer_id = session.get("customer", "")
    subscription_id = session.get("subscription", "")

    updated = Firm.objects.filter(id=firm_id).update(
        stripe_customer_id=customer_id or "",
        stripe_subscription_id=subscription_id or "",
        subscription_tier="pro",
        subscription_active=True,
    )
    if updated:
        logger.info(
            "_handle_checkout_completed: Upgraded firm %s to Pro "
            "(customer=%s, subscription=%s).",
            firm_id, customer_id, subscription_id,
        )
    else:
        logger.warning(
            "_handle_checkout_completed: Firm %s not found.", firm_id
        )


def _handle_subscription_updated(subscription: dict, Firm) -> None:
    """Sync subscription status after an update event."""
    subscription_id = subscription.get("id", "")
    status = subscription.get("status", "")

    firm = Firm.objects.filter(stripe_subscription_id=subscription_id).first()
    if firm is None:
        logger.warning(
            "_handle_subscription_updated: No Firm found for subscription %s.",
            subscription_id,
        )
        return

    # Statuses that mean the subscription is healthy.
    active_statuses = {"active", "trialing"}
    subscription_active = status in active_statuses

    firm.subscription_active = subscription_active
    firm.save(update_fields=["subscription_active"])
    logger.info(
        "_handle_subscription_updated: Firm %s subscription status → '%s' "
        "(subscription_active=%s).",
        firm.id, status, subscription_active,
    )


def _handle_subscription_deleted(subscription: dict, Firm) -> None:
    """Downgrade the Firm to Free when their subscription is cancelled."""
    subscription_id = subscription.get("id", "")

    updated = Firm.objects.filter(stripe_subscription_id=subscription_id).update(
        stripe_subscription_id="",
        subscription_tier="free",
        subscription_active=True,
    )
    if updated:
        logger.info(
            "_handle_subscription_deleted: Downgraded firm with subscription %s to Free.",
            subscription_id,
        )
    else:
        logger.warning(
            "_handle_subscription_deleted: No Firm found for subscription %s.",
            subscription_id,
        )


def _handle_payment_failed(invoice: dict, Firm) -> None:
    """Mark the Firm's subscription as inactive when payment fails."""
    customer_id = invoice.get("customer", "")

    updated = Firm.objects.filter(stripe_customer_id=customer_id).update(
        subscription_active=False,
    )
    if updated:
        logger.info(
            "_handle_payment_failed: Marked firm with customer %s as subscription_active=False.",
            customer_id,
        )
    else:
        logger.warning(
            "_handle_payment_failed: No Firm found for customer %s.", customer_id
        )

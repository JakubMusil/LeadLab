"""
Helpers for broadcasting real-time CRM events via Django Channels and
persisting them as Notification records for all firm members.

Usage (sync context, e.g. inside a Django Ninja endpoint)::

    from crm.events import broadcast_event
    broadcast_event(firm=lead.firm, event="lead.created", payload=_lead_out(lead))

The function is fully fire-and-forget: any error (channel layer unavailable,
Redis down) is caught and logged so it never breaks the HTTP response.
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from crm.consumers import firm_group_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------

class _CRMEncoder(json.JSONEncoder):
    """Extend the default encoder to handle types common in CRM payloads."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, UUID):
            return str(o)
        return super().default(o)


def _make_json_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Round-trip the payload through JSON to make all values serializable."""
    return json.loads(json.dumps(payload, cls=_CRMEncoder))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def broadcast_event(firm, event: str, payload: Dict[str, Any]) -> None:
    """
    Broadcast *event* to all WebSocket connections in *firm*'s channel group
    and persist a Notification for every active firm member.
    Also dispatches outbound webhooks for any subscribed endpoints.

    Called from synchronous Django views / Ninja endpoints.
    Safe to call even when Channels / Redis are not configured.
    """
    safe_payload = _make_json_safe(payload)

    # Persist notifications inside the current transaction so they roll back if
    # the caller's DB transaction rolls back.
    _create_notifications(firm=firm, event=event, payload=safe_payload)

    # Send the channel-layer message after the DB transaction commits so that
    # connected clients can immediately query the API for the newly persisted data.
    transaction.on_commit(lambda: _send_channel_message(firm_id=str(firm.pk), event=event, payload=safe_payload))

    # Dispatch outbound webhooks after the transaction commits.
    transaction.on_commit(lambda: _dispatch_webhooks(firm=firm, event=event, payload=safe_payload))


def _create_notifications(firm, event: str, payload: Dict[str, Any]) -> None:
    """Create one Notification per firm member (best-effort)."""
    try:
        from crm.models import Notification
        from firms.models import Membership

        memberships = Membership.objects.filter(firm=firm).select_related('user')
        notifications = [
            Notification(firm=firm, user=m.user, event=event, payload=payload)
            for m in memberships
        ]
        if notifications:
            # ignore_conflicts=True silently skips if a race condition causes two
            # concurrent requests to insert the same notification (UUID primary key
            # makes true conflicts very unlikely, but it guards against test flakiness).
            Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    except Exception:
        logger.exception('Failed to persist notifications for event %s', event)


def _send_channel_message(firm_id: str, event: str, payload: Dict[str, Any]) -> None:
    """Push a message to the firm's channel group (best-effort)."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            firm_group_name(firm_id),
            {
                'type': 'crm.event',   # maps to FirmConsumer.crm_event()
                'event': event,
                'payload': payload,
            },
        )
    except Exception:
        logger.exception('Failed to broadcast WS event %s to firm %s', event, firm_id)


def _dispatch_webhooks(firm, event: str, payload: Dict[str, Any]) -> None:
    """Dispatch webhook deliveries to all active subscribed endpoints (best-effort)."""
    try:
        from firms.models import WebhookEndpoint
        from firms.tasks import deliver_webhook

        endpoints = WebhookEndpoint.objects.filter(firm=firm, is_active=True)
        for ep in endpoints:
            if ep.subscribes_to(event):
                try:
                    deliver_webhook.delay(str(ep.id), event, payload)
                except Exception:
                    logger.exception(
                        'Failed to enqueue webhook delivery for endpoint %s event %s',
                        ep.id,
                        event,
                    )
    except Exception:
        logger.exception('Failed to dispatch webhooks for event %s', event)

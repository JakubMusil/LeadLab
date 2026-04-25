"""
Django Channels WebSocket consumer for real-time CRM updates.

Each authenticated user connects to a firm-scoped group:
    firm_<firm_id>

Messages broadcast on that group follow this envelope:

    {
        "type": "crm.event",          # Channels routing key (dot → underscore dispatch)
        "event": "lead.created",      # Application-level event name
        "payload": { ... }            # Event-specific data
    }

Event names:
    lead.created   — a new lead was created
    lead.updated   — a lead was updated (status change included)
    lead.deleted   — a lead was deleted; payload contains {"id": "<uuid>"}
    activity.created — a new activity was logged on a lead
    task.completed — a task was marked as completed
"""

import json
import logging

from channels.exceptions import DenyConnection
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


def firm_group_name(firm_id: str) -> str:
    """Return the channel group name for a given Firm ID."""
    return f"firm_{firm_id}"


class FirmConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer that puts each connection into a firm-scoped channel group.

    Authentication relies on Django's session middleware (via AuthMiddlewareStack in
    asgi.py).  The Firm ID is taken from the URL route keyword argument ``firm_id``.
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.firm_id = self.scope['url_route']['kwargs']['firm_id']
        self.group_name = firm_group_name(self.firm_id)

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug('WS connect: user=%s firm=%s', user.pk, self.firm_id)

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug('WS disconnect: code=%s', close_code)

    async def receive(self, text_data=None, bytes_data=None):
        # Clients do not send messages to the server (read-only channel).
        pass

    # ------------------------------------------------------------------
    # Channel layer message handlers
    # ------------------------------------------------------------------

    async def crm_event(self, event):
        """Forward a ``crm.event`` channel message to the WebSocket client."""
        await self.send(
            text_data=json.dumps(
                {
                    'event': event['event'],
                    'payload': event['payload'],
                }
            )
        )

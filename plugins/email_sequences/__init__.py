"""
First-party plugin: Email Sequences (v2.4)

Multi-step drip campaign plugin.

A *Sequence* defines a series of timed emails that are automatically sent
when a lead transitions to a specific status. Each *SequenceStep* specifies
a delay (in days) after the previous step, a subject, and a body template.

When a lead changes status the CRM fires the ``sequence.enroll`` signal which
creates an *Enrollment* record. The Celery beat task
``send_sequence_emails`` processes pending steps and dispatches emails.

Activity type: ``SEQUENCE_EMAIL_SENT``

Configuration: no plugin-level config required (sequences are managed
per-firm in the Sequences UI).
"""
from __future__ import annotations

import logging

from leadlab.plugin_registry import LeadLabPlugin, register

logger = logging.getLogger(__name__)

SEQUENCE_EMAIL_SENT = "sequence_email_sent"


class EmailSequencesPlugin(LeadLabPlugin):
    manifest = {
        "name": "email-sequences",
        "version": "1.0.0",
        "description": (
            "Multi-step drip campaign plugin. Define timed email sequences "
            "triggered by lead status transitions. Celery beat schedules "
            "individual sends."
        ),
        "icon_url": "https://cdn.leadlab.io/plugins/email-sequences/icon.png",
        "permissions": ["records:read", "activities:write", "notifications:send"],
        "activity_types": [SEQUENCE_EMAIL_SENT],
        "webhook_event_types": ["sequence.email_sent"],
        "config_schema": {
            "type": "object",
            "properties": {
                "from_email": {
                    "type": "string",
                    "title": "From Email",
                    "description": "Sender address for sequence emails.",
                },
                "from_name": {
                    "type": "string",
                    "title": "From Name",
                    "description": "Display name for the sender.",
                },
            },
        },
    }

    def ready(self) -> None:
        logger.info("EmailSequencesPlugin ready")


plugin = EmailSequencesPlugin()
register(plugin)

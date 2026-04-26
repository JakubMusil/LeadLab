"""
First-party plugin: VoIP / Click-to-Call (v2.4)

Integrates with Twilio to place calls directly from a lead detail page.
Call duration and recording URL are logged as a ``CALL`` activity on the lead.

Configuration (stored in PluginConfig.config):
  twilio_account_sid  : str  — Twilio Account SID (secret)
  twilio_auth_token   : str  — Twilio Auth Token (secret)
  twilio_caller_id    : str  — Verified caller ID / phone number
"""
from __future__ import annotations

import logging

from leadlab.plugin_registry import LeadLabPlugin, register

logger = logging.getLogger(__name__)


class VoIPPlugin(LeadLabPlugin):
    manifest = {
        "name": "voip-click-to-call",
        "version": "1.0.0",
        "description": (
            "Integrates with Twilio to place calls directly from a lead detail "
            "page. Call duration and recording URL are logged as a CALL activity."
        ),
        "icon_url": "https://cdn.leadlab.io/plugins/voip/icon.png",
        "permissions": ["leads:read", "activities:write"],
        "activity_types": ["call"],
        "webhook_event_types": ["call.completed"],
        "config_schema": {
            "type": "object",
            "properties": {
                "twilio_account_sid": {
                    "type": "string",
                    "title": "Twilio Account SID",
                    "secret": True,
                },
                "twilio_auth_token": {
                    "type": "string",
                    "title": "Twilio Auth Token",
                    "secret": True,
                },
                "twilio_caller_id": {
                    "type": "string",
                    "title": "Caller ID",
                    "description": "Verified Twilio phone number (E.164 format, e.g. +14155552671).",
                },
            },
            "required": ["twilio_account_sid", "twilio_auth_token", "twilio_caller_id"],
        },
    }

    def ready(self) -> None:
        logger.info("VoIPPlugin ready")

    @staticmethod
    def get_twilio_config(firm_id: str) -> dict | None:
        """Return the Twilio config dict for *firm_id* or None if not configured."""
        try:
            from firms.models import PluginConfig
        except Exception:
            return None

        try:
            pc = PluginConfig.objects.get(
                firm_id=firm_id,
                plugin_name="voip-click-to-call",
                enabled=True,
            )
        except PluginConfig.DoesNotExist:
            return None

        cfg = pc.config or {}
        sid = cfg.get("twilio_account_sid", "").strip()
        token = cfg.get("twilio_auth_token", "").strip()
        caller_id = cfg.get("twilio_caller_id", "").strip()
        if not (sid and token and caller_id):
            return None
        return {"account_sid": sid, "auth_token": token, "caller_id": caller_id}

    @staticmethod
    def log_call_activity(
        firm_id: str,
        lead_id: str,
        user_id: str | None,
        duration_seconds: int,
        recording_url: str = "",
        notes: str = "",
    ) -> None:
        """Create a CALL activity on *lead_id* with the given call metadata."""
        try:
            from crm.models import Activity, ActivityType
        except Exception:
            return

        Activity.objects.create(
            lead_id=lead_id,
            user_id=user_id,
            type=ActivityType.CALL,
            content_text=notes,
            metadata={
                "duration_seconds": duration_seconds,
                "recording_url": recording_url,
                "provider": "twilio",
            },
        )


plugin = VoIPPlugin()
register(plugin)

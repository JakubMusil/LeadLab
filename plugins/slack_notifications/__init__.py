"""
First-party plugin: Slack Notifications (v2.4)

Sends a Slack message to a configurable channel when:
- New lead created
- PipelineRecord won / lost
- Task overdue
- Proposal accepted

Configuration (stored in PluginConfig.config):
  slack_webhook_url   : str   — Slack Incoming Webhook URL
  notify_lead_created : bool  — default True
  notify_lead_won     : bool  — default True
  notify_lead_lost    : bool  — default True
  notify_task_overdue : bool  — default True
  notify_proposal_accepted : bool — default True
"""
from __future__ import annotations

import logging

from leadlab.plugin_registry import LeadLabPlugin, register

logger = logging.getLogger(__name__)


class SlackNotificationsPlugin(LeadLabPlugin):
    manifest = {
        "name": "slack-notifications",
        "version": "1.0.0",
        "description": (
            "Send Slack messages to a configurable channel when key CRM events "
            "occur: new lead, lead won/lost, task overdue, proposal accepted."
        ),
        "icon_url": "https://cdn.leadlab.io/plugins/slack-notifications/icon.png",
        "permissions": ["notifications:send", "records:read"],
        "activity_types": [],
        "webhook_event_types": [
            "lead.created",
            "lead.won",
            "lead.lost",
            "task.overdue",
            "proposal.accepted",
        ],
        "config_schema": {
            "type": "object",
            "properties": {
                "slack_webhook_url": {
                    "type": "string",
                    "title": "Slack Incoming Webhook URL",
                    "description": "The Incoming Webhook URL from your Slack app configuration.",
                    "secret": True,
                },
                "notify_lead_created": {
                    "type": "boolean",
                    "title": "Notify on new lead",
                    "default": True,
                },
                "notify_lead_won": {
                    "type": "boolean",
                    "title": "Notify on lead won",
                    "default": True,
                },
                "notify_lead_lost": {
                    "type": "boolean",
                    "title": "Notify on lead lost",
                    "default": True,
                },
                "notify_task_overdue": {
                    "type": "boolean",
                    "title": "Notify on overdue task",
                    "default": True,
                },
                "notify_proposal_accepted": {
                    "type": "boolean",
                    "title": "Notify on proposal accepted",
                    "default": True,
                },
            },
            "required": ["slack_webhook_url"],
        },
    }

    def ready(self) -> None:
        logger.info("SlackNotificationsPlugin ready")

    # ------------------------------------------------------------------
    # Public helper — called from CRM signal handlers or Celery tasks
    # ------------------------------------------------------------------

    @staticmethod
    def send_notification(firm_id: str, event: str, text: str) -> None:
        """
        Look up the Slack config for *firm_id* and POST *text* to Slack.

        Silently no-ops when:
        - plugin is disabled for the firm
        - webhook URL is not configured
        - the ``requests`` library is unavailable
        """
        try:
            import requests
        except ImportError:
            logger.warning("SlackNotificationsPlugin: 'requests' is not installed.")
            return

        try:
            from firms.models import PluginConfig
        except Exception:
            return

        try:
            pc = PluginConfig.objects.get(
                firm_id=firm_id,
                plugin_name="slack-notifications",
                enabled=True,
            )
        except PluginConfig.DoesNotExist:
            return

        cfg = pc.config or {}

        # Check per-event toggles
        event_key_map = {
            "lead.created": "notify_lead_created",
            "lead.won": "notify_lead_won",
            "lead.lost": "notify_lead_lost",
            "task.overdue": "notify_task_overdue",
            "proposal.accepted": "notify_proposal_accepted",
        }
        toggle_key = event_key_map.get(event)
        if toggle_key and not cfg.get(toggle_key, True):
            return

        webhook_url = cfg.get("slack_webhook_url", "").strip()
        if not webhook_url:
            return

        try:
            resp = requests.post(
                webhook_url,
                json={"text": text},
                timeout=5,
            )
            if not resp.ok:
                logger.warning(
                    "SlackNotificationsPlugin: Slack returned %d for firm %s",
                    resp.status_code,
                    firm_id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "SlackNotificationsPlugin: Failed to send notification for firm %s: %s",
                firm_id,
                exc,
            )


plugin = SlackNotificationsPlugin()
register(plugin)

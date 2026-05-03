"""
First-party plugin: LinkedIn Enrichment (v2.4)

Given a LinkedIn profile URL stored in ``Customer.metadata['linkedin_url']``,
fetches public profile data via a configurable proxy API and updates the
customer record, then logs an ENRICHMENT activity on any associated lead.

Configuration (stored in PluginConfig.config):
  proxy_api_url : str  — Base URL of the LinkedIn proxy API (required)
  api_key       : str  — API key / Bearer token for the proxy (required, secret)

The proxy API must accept:
  POST {proxy_api_url}/profile
  Body: {"url": "<linkedin_profile_url>"}
  Response: {"name": "...", "title": "...", "company": "...", "avatar_url": "..."}
"""
from __future__ import annotations

import logging

from leadlab.plugin_registry import LeadLabPlugin, register

logger = logging.getLogger(__name__)

ENRICHMENT_ACTIVITY_TYPE = "enrichment"


class LinkedInEnrichmentPlugin(LeadLabPlugin):
    manifest = {
        "name": "linkedin-enrichment",
        "version": "1.0.0",
        "description": (
            "Given a LinkedIn profile URL on a customer record, fetches public "
            "profile data (name, title, company, avatar) via a proxy API and "
            "updates the customer fields."
        ),
        "icon_url": "https://cdn.leadlab.io/plugins/linkedin-enrichment/icon.png",
        "permissions": ["customers:read", "customers:write", "activities:write"],
        "activity_types": [ENRICHMENT_ACTIVITY_TYPE],
        "webhook_event_types": [],
        "config_schema": {
            "type": "object",
            "properties": {
                "proxy_api_url": {
                    "type": "string",
                    "title": "Proxy API URL",
                    "description": "Base URL of the LinkedIn enrichment proxy API.",
                },
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "Bearer token / API key for the proxy API.",
                    "secret": True,
                },
            },
            "required": ["proxy_api_url", "api_key"],
        },
    }

    def ready(self) -> None:
        logger.info("LinkedInEnrichmentPlugin ready")

    @staticmethod
    def enrich_customer(firm_id: str, customer_id: str) -> dict:
        """
        Enrich a customer record with LinkedIn profile data.

        Returns a dict with the enriched fields on success, or an empty dict
        when the plugin is not configured / the profile cannot be fetched.
        """
        try:
            import requests
        except ImportError:
            logger.warning("LinkedInEnrichmentPlugin: 'requests' is not installed.")
            return {}

        try:
            from firms.models import PluginConfig
            from crm.models import Activity, ActivityType, Customer
        except Exception:
            return {}

        try:
            pc = PluginConfig.objects.get(
                firm_id=firm_id,
                plugin_name="linkedin-enrichment",
                enabled=True,
            )
        except PluginConfig.DoesNotExist:
            return {}

        cfg = pc.config or {}
        proxy_url = cfg.get("proxy_api_url", "").rstrip("/")
        api_key = cfg.get("api_key", "").strip()
        if not proxy_url or not api_key:
            return {}

        try:
            customer = Customer.objects.get(id=customer_id, firm_id=firm_id)
        except Customer.DoesNotExist:
            return {}

        linkedin_url = (customer.metadata or {}).get("linkedin_url", "").strip()
        if not linkedin_url:
            logger.info(
                "LinkedInEnrichmentPlugin: customer %s has no linkedin_url in metadata",
                customer_id,
            )
            return {}

        try:
            resp = requests.post(
                f"{proxy_url}/profile",
                json={"url": linkedin_url},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "LinkedInEnrichmentPlugin: Proxy request failed for customer %s: %s",
                customer_id,
                exc,
            )
            return {}

        updates: dict = {}
        if data.get("name"):
            parts = data["name"].split(" ", 1)
            updates["first_name"] = parts[0]
            if len(parts) > 1:
                updates["last_name"] = parts[1]
        if data.get("company"):
            updates["company_name"] = data["company"]

        enrichment_meta: dict = {}
        if data.get("title"):
            enrichment_meta["title"] = data["title"]
        if data.get("avatar_url"):
            enrichment_meta["avatar_url"] = data["avatar_url"]
        if data.get("company"):
            enrichment_meta["company"] = data["company"]

        customer.metadata.update(enrichment_meta)
        if updates.get("first_name"):
            customer.first_name = updates["first_name"]
        if updates.get("last_name"):
            customer.last_name = updates["last_name"]
        if updates.get("company_name"):
            customer.company_name = updates["company_name"]
        customer.save()

        # Log an ENRICHMENT activity on the most recent associated lead (if any)
        from crm.models import PipelineRecord
        lead = (
            PipelineRecord.objects.filter(firm_id=firm_id, customer=customer)
            .order_by("-created_at")
            .first()
        )
        if lead:
            Activity.objects.create(
                lead=lead,
                type=ENRICHMENT_ACTIVITY_TYPE,
                content_text="LinkedIn profile enrichment completed.",
                metadata={
                    "source": "linkedin",
                    "linkedin_url": linkedin_url,
                    **enrichment_meta,
                },
            )

        return updates


plugin = LinkedInEnrichmentPlugin()
register(plugin)

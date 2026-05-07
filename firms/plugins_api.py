"""
Django Ninja router — Plugin Marketplace & Ecosystem (v2.4)

Endpoints
---------
GET    /api/v1/plugins/                                  List all registered plugins (global)
GET    /api/v1/plugins/marketplace/                      List plugins for the marketplace UI
GET    /api/v1/firms/{firm_id}/plugin-configs/           List per-firm plugin configs
PATCH  /api/v1/firms/{firm_id}/plugin-configs/{name}/   Update enabled flag + config values
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from firms.models import Firm, Membership, PluginConfig
from leadlab.plugin_registry import get_plugins, get_plugin

router = Router(tags=["plugins"])


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

class ConfigSchemaProperty(Schema):
    type: str
    title: Optional[str] = None
    description: Optional[str] = None
    default: Optional[Any] = None
    secret: Optional[bool] = None


class PluginOut(Schema):
    name: str
    version: str
    description: str
    icon_url: str
    permissions: List[str]
    activity_types: List[str]
    webhook_event_types: List[str]
    config_schema: Dict[str, Any]


class PluginConfigOut(Schema):
    plugin_name: str
    enabled: bool
    config: Dict[str, Any]
    plugin: Optional[PluginOut] = None


class PluginConfigIn(Schema):
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class ErrorOut(Schema):
    detail: str


class MarketplacePluginOut(Schema):
    name: str
    version: str
    description: str
    author: str
    icon_url: Optional[str] = None
    tags: List[str] = []
    install_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Global plugin list (no firm required — public within authenticated session)
# ---------------------------------------------------------------------------

@router.get("/", response=List[PluginOut], auth=django_auth)
def list_plugins(request):
    """Return all plugins registered in the LeadLab plugin registry."""
    plugins = get_plugins()
    return [
        PluginOut(
            name=p.name,
            version=p.version,
            description=p.description,
            icon_url=p.icon_url,
            permissions=p.permissions,
            activity_types=p.activity_types,
            webhook_event_types=p.webhook_event_types,
            config_schema=p.config_schema,
        )
        for p in plugins
    ]


# ---------------------------------------------------------------------------
# Marketplace listing — used by the "Marketplace" tab in PluginsView.
# Mirrors the in-process plugin registry but in the lightweight
# ``MarketplacePluginOut`` shape consumed by the SPA.
# ---------------------------------------------------------------------------

@router.get("/marketplace/", response=List[MarketplacePluginOut], auth=django_auth)
def list_marketplace_plugins(request):
    """Return all plugins available in the LeadLab marketplace."""
    items: List[MarketplacePluginOut] = []
    for p in get_plugins():
        manifest = getattr(p, "manifest", {}) or {}
        author = manifest.get("author") or getattr(p, "author", None) or "LeadLab"
        tags = manifest.get("tags")
        if not tags:
            tags = list(p.permissions or [])
        items.append(
            MarketplacePluginOut(
                name=p.name,
                version=p.version,
                description=p.description,
                author=author,
                icon_url=p.icon_url,
                tags=list(tags),
                install_url=manifest.get("install_url"),
            )
        )
    return items


# ---------------------------------------------------------------------------
# Per-firm plugin configs
# ---------------------------------------------------------------------------

@router.get("/{firm_id}/plugin-configs/", auth=django_auth, response={200: List[PluginConfigOut], 403: ErrorOut, 404: ErrorOut})
def list_plugin_configs(request, firm_id: str):
    """
    Return all plugin configs for the given firm.

    For each registered plugin that does NOT yet have a PluginConfig row the
    response includes a default entry with ``enabled=True`` and ``config={}``.
    """
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}
    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    existing: dict[str, PluginConfig] = {
        pc.plugin_name: pc
        for pc in PluginConfig.objects.filter(firm_id=firm_id)
    }

    result: list[PluginConfigOut] = []
    for plugin in get_plugins():
        pc = existing.get(plugin.name)
        plugin_out = PluginOut(
            name=plugin.name,
            version=plugin.version,
            description=plugin.description,
            icon_url=plugin.icon_url,
            permissions=plugin.permissions,
            activity_types=plugin.activity_types,
            webhook_event_types=plugin.webhook_event_types,
            config_schema=plugin.config_schema,
        )
        result.append(
            PluginConfigOut(
                plugin_name=plugin.name,
                enabled=pc.enabled if pc else True,
                config=pc.config if pc else {},
                plugin=plugin_out,
            )
        )
    return result


@router.patch("/{firm_id}/plugin-configs/{plugin_name}/", auth=django_auth, response={200: PluginConfigOut, 403: ErrorOut, 404: ErrorOut})
def update_plugin_config(request, firm_id: str, plugin_name: str, payload: PluginConfigIn):
    """
    Create or update the enabled flag and config values for a single plugin.

    Only firm members may call this endpoint.
    """
    try:
        firm = Firm.objects.get(id=firm_id, is_active=True)
    except Firm.DoesNotExist:
        return 404, {"detail": "Firm not found."}
    if not Membership.objects.filter(user=request.user, firm=firm).exists():
        return 403, {"detail": "You are not a member of this Firm."}

    plugin = get_plugin(plugin_name)
    if plugin is None:
        return 404, {"detail": f"Plugin '{plugin_name}' is not registered."}

    pc, _ = PluginConfig.objects.get_or_create(
        firm_id=firm_id,
        plugin_name=plugin_name,
        defaults={"enabled": True, "config": {}},
    )

    if payload.enabled is not None:
        pc.enabled = payload.enabled
    if payload.config is not None:
        pc.config = payload.config
    pc.save(update_fields=["enabled", "config", "updated_at"])

    plugin_out = PluginOut(
        name=plugin.name,
        version=plugin.version,
        description=plugin.description,
        icon_url=plugin.icon_url,
        permissions=plugin.permissions,
        activity_types=plugin.activity_types,
        webhook_event_types=plugin.webhook_event_types,
        config_schema=plugin.config_schema,
    )
    return PluginConfigOut(
        plugin_name=pc.plugin_name,
        enabled=pc.enabled,
        config=pc.config,
        plugin=plugin_out,
    )

"""
Django Ninja router — Plugin Marketplace & Ecosystem (v2.4)

Endpoints
---------
GET    /api/v1/plugins/                                  List all registered plugins (global)
GET    /api/v1/firms/{firm_id}/plugin-configs/           List per-firm plugin configs
PATCH  /api/v1/firms/{firm_id}/plugin-configs/{name}/   Update enabled flag + config values
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ninja import Router, Schema
from ninja.security import django_auth

from firms.auth import require_membership, require_active_subscription
from firms.models import PluginConfig
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
# Per-firm plugin configs
# ---------------------------------------------------------------------------

@router.get("/{firm_id}/plugin-configs/", response=List[PluginConfigOut])
def list_plugin_configs(request, firm_id: str):
    """
    Return all plugin configs for the given firm.

    For each registered plugin that does NOT yet have a PluginConfig row the
    response includes a default entry with ``enabled=True`` and ``config={}``.
    """
    require_membership(request, firm_id)

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


@router.patch("/{firm_id}/plugin-configs/{plugin_name}/", response=PluginConfigOut)
def update_plugin_config(request, firm_id: str, plugin_name: str, payload: PluginConfigIn):
    """
    Create or update the enabled flag and config values for a single plugin.

    Only firm members may call this endpoint.
    """
    require_membership(request, firm_id)

    plugin = get_plugin(plugin_name)
    if plugin is None:
        from ninja import errors as ninja_errors
        from django.http import Http404
        raise Http404(f"Plugin '{plugin_name}' is not registered.")

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

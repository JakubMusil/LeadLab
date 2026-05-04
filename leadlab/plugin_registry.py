"""
LeadLab Plugin Registry (v2.4)

Plugins self-register via ``register()``. Every plugin must expose a
``manifest`` dict that conforms to the leadlab-plugin.json schema.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Manifest schema (required keys)
# ---------------------------------------------------------------------------

MANIFEST_REQUIRED_KEYS: tuple[str, ...] = ("name", "version", "description")

VALID_PERMISSIONS: frozenset[str] = frozenset(
    {
        "activities:read",
        "activities:write",
        "records:read",
        "records:write",
        "customers:read",
        "customers:write",
        "notifications:send",
        "webhooks:send",
    }
)


class PluginManifestError(ValueError):
    """Raised when a plugin's manifest is invalid."""


def validate_manifest(manifest: dict[str, Any]) -> None:
    """
    Validate a plugin manifest dict.

    Raises ``PluginManifestError`` on the first validation failure.
    """
    if not isinstance(manifest, dict):
        raise PluginManifestError("manifest must be a dict")

    for key in MANIFEST_REQUIRED_KEYS:
        if not manifest.get(key):
            raise PluginManifestError(f"manifest is missing required key '{key}'")

    version = manifest["version"]
    # Accept semver strings like "1.0.0", "1.0", "1.0.0-beta.1", "1.0.0+build.1"
    # Strip build metadata and pre-release suffix before checking numeric parts.
    core = str(version).split("+")[0].split("-")[0]
    parts = core.split(".")
    if len(parts) < 2 or not all(p.isdigit() for p in parts):
        raise PluginManifestError(
            f"manifest 'version' must be a semver string (e.g. '1.0.0'), got '{version}'"
        )

    permissions = manifest.get("permissions", [])
    if not isinstance(permissions, list):
        raise PluginManifestError("manifest 'permissions' must be a list")
    unknown = set(permissions) - VALID_PERMISSIONS
    if unknown:
        raise PluginManifestError(
            f"manifest declares unknown permissions: {sorted(unknown)}"
        )

    config_schema = manifest.get("config_schema", {})
    if not isinstance(config_schema, dict):
        raise PluginManifestError("manifest 'config_schema' must be a dict (JSON Schema)")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class LeadLabPlugin:
    """
    Base class (not enforced — duck-typing is acceptable) for backend plugins.

    Attributes
    ----------
    manifest : dict
        Must conform to the leadlab-plugin.json schema.
    """

    manifest: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return self.manifest.get("name", "")

    @property
    def version(self) -> str:
        return self.manifest.get("version", "")

    @property
    def description(self) -> str:
        return self.manifest.get("description", "")

    @property
    def activity_types(self) -> list[str]:
        return self.manifest.get("activity_types", [])

    @property
    def webhook_event_types(self) -> list[str]:
        return self.manifest.get("webhook_event_types", [])

    @property
    def config_schema(self) -> dict[str, Any]:
        return self.manifest.get("config_schema", {})

    @property
    def permissions(self) -> list[str]:
        return self.manifest.get("permissions", [])

    @property
    def icon_url(self) -> str:
        return self.manifest.get("icon_url", "")

    def ready(self) -> None:
        """Called by Django AppConfig.ready() after all apps are loaded."""


_registry: list[LeadLabPlugin] = []


def register(plugin: Any) -> None:
    """
    Register a plugin instance.

    Validates the plugin's ``manifest`` and logs a warning (rather than
    raising) so a misconfigured plugin does not prevent the server from
    starting.
    """
    manifest = getattr(plugin, "manifest", {})
    try:
        validate_manifest(manifest)
    except PluginManifestError as exc:
        logger.warning(
            "Plugin registration failed for %r — invalid manifest: %s",
            getattr(plugin, "manifest", {}).get("name", repr(plugin)),
            exc,
        )
        return

    _registry.append(plugin)
    logger.info(
        "Plugin registered: %s v%s",
        manifest["name"],
        manifest["version"],
    )


def get_plugins() -> list[LeadLabPlugin]:
    return list(_registry)


def get_plugin(name: str) -> LeadLabPlugin | None:
    for plugin in _registry:
        if plugin.name == name:
            return plugin
    return None

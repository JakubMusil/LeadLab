"""
Streamline payload validation (F-3).

Each registered :class:`StreamlineTool` exposes a ``get_schema()`` returning a
JSON Schema that describes the *flattened* composer form for the SPA.  The
schema treats ``content_text`` as a top-level property and folds every
metadata key into the same flat namespace (e.g. ``new_status``,
``duration_minutes``).  This mirrors what the SPA composer produces.

This module bridges the gap between the inbound ``ActivityIn`` payload —
where ``content_text`` is its own field and structured data lives in
``metadata`` — and that flattened schema view.  It performs structural
validation (``type`` / ``required`` / ``enum`` / ``minimum`` / ``maximum``)
without enabling string ``format`` checking, which is intentionally lenient
to avoid breaking existing callers that pass non-strict URIs or UUIDs.

Unknown properties are accepted (JSON Schema's default
``additionalProperties: true``) so adding new metadata keys never requires
touching the schema first.

This module is the foundation for the inbound webhook router (F-6), which
will hand untrusted JSON straight to ``validate_payload`` before any
``Activity`` is persisted.
"""

from __future__ import annotations

import logging
from typing import Any

import jsonschema
from jsonschema.exceptions import SchemaError, ValidationError

from crm.streamline.registry import get_tool

logger = logging.getLogger(__name__)


class PayloadValidationError(ValueError):
    """Raised when an activity payload does not match its tool schema."""


def _flatten_payload(content_text: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Build the flattened composer-view dict the schema expects.

    Top-level ``content_text`` always wins over a colliding ``metadata`` key
    (callers are expected to use the dedicated field; we ignore stray
    duplicates rather than raising on them).
    """
    flat: dict[str, Any] = dict(metadata or {})
    flat["content_text"] = content_text
    return flat


def validate_payload(
    activity_type: str,
    content_text: str,
    metadata: dict[str, Any] | None,
) -> None:
    """Validate an inbound activity payload against its tool schema.

    Raises
    ------
    PayloadValidationError
        If the tool is registered but the payload fails schema validation.
        The message is short, human-readable, and safe to surface as an
        API ``detail`` field (does not echo arbitrary user content).

    Notes
    -----
    *   If no tool is registered for ``activity_type`` this function is a
        no-op — the caller is expected to reject unknown types separately
        (``create_activity`` already does so with a clearer error).
    *   If the tool's schema itself is invalid (author bug) we log a
        warning and treat the payload as valid, so a broken schema does
        not become a hard outage for a single activity type.
    """
    tool = get_tool(activity_type)
    if tool is None:
        return

    try:
        schema = tool.get_schema()
    except Exception:  # pragma: no cover — defensive against tool bugs
        logger.exception("StreamlineTool '%s' raised in get_schema(); skipping validation", activity_type)
        return

    flat = _flatten_payload(content_text, metadata)
    try:
        jsonschema.validate(instance=flat, schema=schema)
    except SchemaError:
        # Tool author bug — never fail user requests because of it.
        logger.exception("StreamlineTool '%s' has an invalid JSON Schema; skipping validation", activity_type)
        return
    except ValidationError as exc:
        # Build a short, deterministic message.  Use ``json_path`` (jsonschema
        # >= 4) which renders as ``$.field``, falling back to the dotted path
        # on older versions.
        location = getattr(exc, "json_path", None) or ".".join(str(p) for p in exc.absolute_path) or "(root)"
        raise PayloadValidationError(
            f"Invalid payload for activity type '{activity_type}' at {location}: {exc.message}"
        ) from exc

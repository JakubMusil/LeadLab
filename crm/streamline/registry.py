from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crm.streamline.base import StreamlineTool

logger = logging.getLogger(__name__)

_tool_registry: dict[str, "StreamlineTool"] = {}


def register_tool(tool: "StreamlineTool") -> None:
    """
    Register a ``StreamlineTool`` instance by its ``activity_type``.

    Logs a warning and skips registration if ``activity_type`` is missing.
    Overwrites any previously registered tool for the same ``activity_type``
    with a warning, so re-entrant calls (e.g. during testing) are safe.
    """
    activity_type = getattr(tool, "activity_type", None)
    if not activity_type:
        logger.warning(
            "StreamlineTool registration skipped: missing activity_type on %r", tool
        )
        return
    if activity_type in _tool_registry:
        logger.warning(
            "StreamlineTool '%s' already registered — overwriting with %r",
            activity_type,
            tool,
        )
    _tool_registry[activity_type] = tool
    logger.debug(
        "StreamlineTool registered: %s (%s)", activity_type, type(tool).__name__
    )


def get_tool(activity_type: str) -> "StreamlineTool | None":
    """Return the registered tool for *activity_type*, or ``None`` if not found."""
    return _tool_registry.get(activity_type)


def all_tools() -> list["StreamlineTool"]:
    """Return all registered tools in insertion order."""
    return list(_tool_registry.values())

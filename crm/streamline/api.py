"""
Streamline API router — exposes tool registry metadata to the SPA.
"""
from typing import Any, Dict, List, Optional

from django.utils.translation import gettext_lazy as _

from ninja import Router, Schema
from ninja.security import django_auth

from crm.streamline.registry import all_tools, get_tool

router = Router(tags=["streamline"])

# ---------------------------------------------------------------------------
# Per-entity-type toolbar registries
# These lists declare which tools (activity_type strings) appear in each
# entity's sidebar toolbar — the frontend renders them from this list rather
# than applying ad-hoc front-end filters.
# "task" is a pseudo-type handled separately on the frontend (creates a Task
# record, not an Activity).
# ---------------------------------------------------------------------------
_ENTITY_TOOLBAR: Dict[str, List[str]] = {}


def _build_entity_toolbar() -> None:
    """Populate ``_ENTITY_TOOLBAR`` from entity model class attributes."""
    global _ENTITY_TOOLBAR
    try:
        from crm.models import Lead, Realization, Management
        _ENTITY_TOOLBAR = {
            "lead": Lead.TOOLBAR_TOOLS,
            "realization": getattr(Realization, "TOOLBAR_TOOLS", ["comment", "task"]),
            "management": getattr(Management, "TOOLBAR_TOOLS", ["comment", "task"]),
            "customer": ["comment", "call", "meeting", "email_out", "task"],
            "proposal": ["comment", "task"],
            "task": [
                "comment",
                "file_upload",
                "voice_memo",
                "checklist_item_checked",
                "time_logged",
                "sub_task_added",
            ],
        }
    except Exception:
        pass


class ToolOut(Schema):
    activity_type: str
    label: str
    icon: str
    form_schema: Dict[str, Any]


class EntityToolbarOut(Schema):
    """Describes one toolbar item for a given entity type."""
    activity_type: str
    label: str
    icon: str
    form_schema: Dict[str, Any]


@router.get("/tools", auth=django_auth, response=List[ToolOut])
def list_tools(request):
    """
    Return all registered Streamline Tools with their form schemas.

    The SPA uses this endpoint to dynamically render the activity composer
    without hard-coding per-type UI logic.

    Example response item::

        {
            "activity_type": "comment",
            "label": "Comment",
            "icon": "ChatBubbleLeftIcon",
            "form_schema": {
                "type": "object",
                "properties": {
                    "content_text": {"type": "string", "format": "html", "title": "Comment"}
                },
                "required": ["content_text"]
            }
        }
    """
    # Note: `str(tool.label)` coerces Django's `gettext_lazy` `__proxy__`
    # to a real string for Pydantic — Pydantic's `isinstance(value, str)`
    # check rejects `__proxy__` even though it's string-like at runtime.
    return [
        {
            "activity_type": tool.activity_type,
            "label": str(tool.label),
            "icon": tool.icon,
            "form_schema": tool.get_schema(),
        }
        for tool in all_tools()
    ]


@router.get("/entity-toolbar/{entity_type}", auth=django_auth, response=List[EntityToolbarOut])
def get_entity_toolbar(request, entity_type: str):
    """
    Return the ordered list of toolbar tools for *entity_type*.

    The list is driven by the ``TOOLBAR_TOOLS`` class attribute on each entity
    model.  The frontend renders one button per item using the matching
    pre-registered tool element from the tool registry — no front-end
    hard-coding required.

    ``entity_type`` must be one of: ``lead``, ``realization``, ``management``,
    ``customer``, ``proposal``.

    The special pseudo-type ``task`` (which creates a Task record rather than
    an Activity) is included in the list with a synthetic descriptor so the
    frontend can treat it uniformly.
    """
    if not _ENTITY_TOOLBAR:
        _build_entity_toolbar()

    tool_types: List[str] = _ENTITY_TOOLBAR.get(entity_type, ["comment", "task"])
    result = []
    for activity_type in tool_types:
        if activity_type == "task":
            # Synthetic entry — handled specially by the frontend
            result.append({
                "activity_type": "task",
                "label": str(_("Task")),
                "icon": "ClipboardDocumentListIcon",
                "form_schema": {"type": "object", "properties": {}},
            })
        else:
            tool = get_tool(activity_type)
            if tool:
                result.append({
                    "activity_type": tool.activity_type,
                    "label": str(tool.label),
                    "icon": tool.icon,
                    "form_schema": tool.get_schema(),
                })
    return result

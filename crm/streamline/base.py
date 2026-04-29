from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from crm.models import Activity


class StreamlineTool(ABC):
    """
    Abstract base class for Streamline Tools.

    Each subclass handles one ``activity_type`` and encapsulates:

    * ``get_schema()``      — JSON Schema describing the composer form fields for
                             the SPA, so the frontend can render inputs dynamically.
    * ``process_action()``  — side-effects executed inside an ``atomic()`` block
                             immediately after the ``Activity`` record is created.
    * ``render_payload()``  — tool-specific data included as ``tool_payload`` in
                             every ``ActivityOut`` serialization.

    Class attributes
    ----------------
    activity_type : str
        Unique identifier matching an ``ActivityType`` choice value, e.g. ``"comment"``.
    label : str
        Human-readable display name used by the SPA.
    icon : str
        Icon key (maps to a Heroicons component name on the frontend).
    """

    activity_type: str
    label: str
    icon: str

    @abstractmethod
    def get_schema(self) -> dict:
        """
        Return a JSON Schema object describing the tool's form fields.

        The SPA uses this schema to render the composer input dynamically
        without hard-coding per-type UI logic.

        Example for CommentTool::

            {
                "type": "object",
                "properties": {
                    "content_text": {"type": "string", "format": "html", "title": "Comment"},
                    "mentions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["content_text"],
            }
        """

    @abstractmethod
    def process_action(
        self,
        activity: "Activity",
        entity: Any,
        payload: dict,
        context: dict,
    ) -> None:
        """
        Execute side-effects after the Activity record has been saved.

        Called inside a ``transaction.atomic()`` block in ``create_activity``.

        Parameters
        ----------
        activity : Activity
            The freshly created ``Activity`` instance.
        entity : Lead | Realization | Management
            The CRM entity this activity is attached to.
        payload : dict
            Raw request payload dict (from ``ActivityIn``).
        context : dict
            Extra request context with keys:

            * ``"firm"``         — the active ``Firm`` instance
            * ``"user"``         — the authenticated ``User`` instance
            * ``"entity_title"`` — display title of the linked entity
        """

    @abstractmethod
    def render_payload(self, activity: "Activity") -> dict:
        """
        Return tool-specific data for JSON serialization in the activity feed.

        The returned dict is included as ``tool_payload`` in ``ActivityOut``.

        Example for TaskTool::

            {
                "task_id": "...",
                "task_title": "...",
                "due_date": "2024-01-15",
            }
        """

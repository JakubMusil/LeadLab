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
    category : str
        Group used by the SPA filter dropdown to organise activity types.
        One of: ``"communication"``, ``"task"``, ``"commerce"``, ``"system"``,
        ``"ai"``, ``"meta"``.  Defaults to ``"system"``.
    default_visibility : str
        Whether this activity type is shown by default in the streamline.
        ``"important"`` types are visible to a fresh user; ``"secondary"``
        types are hidden until the user opts in via the filter dropdown.
        Defaults to ``"secondary"`` so noisy logs do not overwhelm the UI.
    channel : str
        Communication channel this tool represents.  Used by the unified
        "Message" composer to collapse the 6 separate email / SMS /
        WhatsApp buttons into a single entry whose channel is selected
        in-form.  One of: ``"email"``, ``"sms"``, ``"whatsapp"``,
        ``"chat"``, ``"none"``.  Defaults to ``"none"`` for non-messaging
        tools.
    direction : str
        Whether the activity is outbound, inbound, or has no direction
        semantics.  Pairs with ``channel`` so the SPA can map a
        ``(channel, direction)`` selection back to a concrete
        ``activity_type``.  One of: ``"out"``, ``"in"``, ``"none"``.
        Defaults to ``"none"``.
    """

    activity_type: str
    label: str
    icon: str
    category: str = "system"
    default_visibility: str = "secondary"
    channel: str = "none"
    direction: str = "none"

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

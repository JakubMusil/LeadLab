"""
Streamline API router — exposes tool registry metadata to the SPA.
"""
from typing import Any, Dict, List

from ninja import Router, Schema
from ninja.security import django_auth

from crm.streamline.registry import all_tools

router = Router(tags=["streamline"])


class ToolOut(Schema):
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
    return [
        {
            "activity_type": tool.activity_type,
            "label": tool.label,
            "icon": tool.icon,
            "form_schema": tool.get_schema(),
        }
        for tool in all_tools()
    ]

"""
Streamline Tool Registry — plugin-based architecture for CRM activity types.

Each activity type is handled by a registered StreamlineTool that defines:
- get_schema()       → JSON Schema for the SPA form renderer
- process_action()   → side-effects executed inside atomic() after Activity creation
- render_payload()   → tool-specific data serialized into the ActivityOut feed
"""
from crm.streamline.base import StreamlineTool
from crm.streamline.registry import all_tools, get_tool, register_tool

__all__ = ["StreamlineTool", "register_tool", "get_tool", "all_tools"]

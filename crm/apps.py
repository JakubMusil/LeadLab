from django.apps import AppConfig


class CrmConfig(AppConfig):
    name = 'crm'

    def ready(self) -> None:
        from crm.streamline.registry import register_tool
        from crm.streamline.tools import BUILTIN_TOOLS

        for tool in BUILTIN_TOOLS:
            register_tool(tool)

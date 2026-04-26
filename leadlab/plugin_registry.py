from typing import Protocol, runtime_checkable

@runtime_checkable
class LeadLabPlugin(Protocol):
    name: str
    activity_types: list
    webhook_event_types: list
    
    def ready(self) -> None: ...

_registry: list = []

def register(plugin) -> None:
    _registry.append(plugin)

def get_plugins() -> list:
    return list(_registry)

# Plugin Authoring

LeadLab supports a lightweight plugin system for both the Python backend and the Vue 3 frontend.

## Backend plugin

Register a plugin in `leadlab/plugin_registry.py`:

```python
from leadlab.plugin_registry import register

class MyPlugin:
    name = "my_plugin"
    activity_types = ["call", "demo"]
    webhook_event_types = ["call.completed"]

    def ready(self):
        # called at app startup
        pass

register(MyPlugin())
```

## Frontend plugin

Add a plugin object to `frontend-spa/src/plugins/index.ts`:

```ts
import type { App } from 'vue'

export const myPlugin = {
  install(app: App) {
    // register global components, provide values, etc.
  },
  navItems: [
    { key: 'calls', label: 'Calls', to: '/app/calls', icon: '📞' },
  ],
}

export const pluginRegistry = [myPlugin]
```

The `navItems` array is merged into the AppShell navigation sidebar automatically.

## Plugin lifecycle

1. `install(app)` is called at Vue app bootstrap (`main.ts`).
2. `navItems` are injected into the sidebar in `AppShell.vue`.
3. Backend `ready()` is called from `AppConfig.ready()` in your Django app.

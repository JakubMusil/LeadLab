# Plugin Authoring

LeadLab supports a lightweight plugin system for both the Python backend and the Vue 3 frontend.
Starting with **v2.4** every plugin must declare a **manifest** (`leadlab-plugin.json`) that is
validated at registration time.

---

## Plugin manifest (`leadlab-plugin.json`)

Every plugin must expose a manifest that conforms to the following schema:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Short human-readable description shown in Settings → Plugins.",
  "icon_url": "https://example.com/icon.png",
  "permissions": ["leads:read", "activities:write"],
  "activity_types": ["my_activity_type"],
  "webhook_event_types": ["my.event"],
  "config_schema": {
    "type": "object",
    "properties": {
      "api_key": {
        "type": "string",
        "title": "API Key",
        "description": "Your API key.",
        "secret": true
      },
      "enabled": {
        "type": "boolean",
        "title": "Enable feature X",
        "default": true
      }
    },
    "required": ["api_key"]
  }
}
```

### Manifest fields

| Field | Required | Description |
|---|---|---|
| `name` | ✅ | Unique kebab-case identifier (e.g. `"slack-notifications"`) |
| `version` | ✅ | Semver string (e.g. `"1.0.0"`) |
| `description` | ✅ | Short description displayed in the plugin manager |
| `icon_url` | — | URL of a square icon image |
| `permissions` | — | List of permissions the plugin requires (see below) |
| `activity_types` | — | Custom activity type keys the plugin introduces |
| `webhook_event_types` | — | Webhook events the plugin emits |
| `config_schema` | — | JSON Schema `object` describing the plugin's configuration |

### Available permissions

| Permission | Description |
|---|---|
| `activities:read` | Read activities on leads |
| `activities:write` | Create activities on leads |
| `leads:read` | Read lead data |
| `leads:write` | Create / update leads |
| `customers:read` | Read customer records |
| `customers:write` | Create / update customer records |
| `notifications:send` | Send notifications (email, push, Slack, …) |
| `webhooks:send` | Emit webhook events |

### Config schema property fields

| Field | Description |
|---|---|
| `type` | `"string"`, `"number"`, or `"boolean"` |
| `title` | Human-readable label rendered in Settings → Plugins |
| `description` | Optional helper text rendered below the input |
| `default` | Default value |
| `secret` | When `true` the Settings UI renders a password input |

---

## Backend plugin

Register a plugin in your Django app:

```python
from leadlab.plugin_registry import LeadLabPlugin, register

class MyPlugin(LeadLabPlugin):
    manifest = {
        "name": "my-plugin",
        "version": "1.0.0",
        "description": "My first LeadLab plugin.",
        "permissions": ["leads:read"],
        "activity_types": ["my_custom_event"],
        "webhook_event_types": [],
        "config_schema": {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "secret": True,
                }
            },
            "required": ["api_key"],
        },
    }

    def ready(self):
        # Called at app startup after all apps are loaded
        pass

register(MyPlugin())
```

Import your plugin module during Django startup. The recommended place is in your app's
`AppConfig.ready()` method, or by listing the module path in your `settings.py` alongside
the built-in plugins.

### Reading plugin config at runtime

```python
from firms.models import PluginConfig

def get_config(firm_id: str) -> dict:
    try:
        pc = PluginConfig.objects.get(firm_id=firm_id, plugin_name="my-plugin", enabled=True)
        return pc.config
    except PluginConfig.DoesNotExist:
        return {}
```

---

## Frontend plugin

Create a TypeScript file and call `registerPlugin()`:

```ts
import type { App } from 'vue'
import { registerPlugin } from '@/plugins'

registerPlugin({
  manifest: {
    name: 'my-plugin',
    version: '1.0.0',
    description: 'My first LeadLab plugin.',
    permissions: ['leads:read'],
    configSchema: {
      type: 'object',
      properties: {
        api_key: {
          type: 'string',
          title: 'API Key',
          secret: true,
        },
      },
      required: ['api_key'],
    },
  },
  activityTypes: [
    { type: 'my_custom_event', label: 'Custom Event', icon: '⚡' },
  ],
  navItems: [
    { label: 'My Feature', icon: '🔌', path: '/app/my-feature' },
  ],
  install(app: App) {
    // Register global components, directives, etc.
  },
})
```

Import your plugin file in `main.ts` (or your app entry point) so that `registerPlugin()` is
called before `app.mount()`:

```ts
import './plugins/myPlugin'
```

### Plugin API sandbox (`usePlugin`)

Inside plugin components you can use `usePlugin()` to access a scoped API:

```ts
import { usePlugin } from '@/composables/usePlugin'

const api = usePlugin('my-plugin')

api.toast.success('Hello from my plugin!')
api.navigate('/app/leads')
const firm = api.useFirm()
const auth = api.useAuth()
```

Access is gated by the permissions declared in the manifest. Attempting to use functionality
that requires a permission not listed in `manifest.permissions` throws a `PluginPermissionError`.

---

## Plugin lifecycle

1. `registerPlugin()` validates the manifest and adds the plugin to the registry.
2. `install(app)` is called at Vue app bootstrap (`main.ts`).
3. `navItems` are merged into the AppShell navigation sidebar.
4. `activityTypes` are available to the activity timeline renderer.
5. Backend `ready()` is called from Django settings startup.
6. Plugin configuration is stored per-firm in `PluginConfig` and surfaced in Settings → Plugins.

---

## Public plugin registry

Community plugins are listed in the
[public plugin registry](https://github.com/JakubMusil/LeadLab/blob/main/frontend-spa/public/plugin-registry.json).
To add your plugin, submit a pull request adding an entry to `plugin-registry.json`.

The registry is linked from the in-app plugin manager in Settings → Plugins.

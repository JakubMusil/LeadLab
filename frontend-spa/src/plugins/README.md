# LeadLab Plugin System

Plugins allow you to extend LeadLab with custom activity types, nav items, and webhook event types.

## Creating a Plugin

```typescript
import { registerPlugin, type LeadLabPlugin } from '@/plugins'
import type { App } from 'vue'

const myPlugin: LeadLabPlugin = {
  name: 'my-plugin',
  version: '1.0.0',
  navItems: [
    { label: 'My Feature', icon: '🔌', path: '/app/my-feature' },
  ],
  activityTypes: [
    { type: 'my_activity', label: 'My Activity', icon: '📌' },
  ],
  webhookEventTypes: ['my_plugin.event'],
  install(app: App) {
    // Register Vue components, directives, etc.
    // app.component('MyComponent', MyComponent)
  },
}

registerPlugin(myPlugin)
```

## Plugin Interface

| Property | Type | Description |
|---|---|---|
| `name` | `string` | Unique plugin identifier |
| `version` | `string` | Semver version string |
| `navItems` | `NavItemDefinition[]` | Navigation items to add to the sidebar |
| `activityTypes` | `ActivityTypeDefinition[]` | Custom activity types for the timeline |
| `webhookEventTypes` | `string[]` | Event type names emitted by this plugin |
| `install` | `(app: App) => void` | Vue app installation hook |

## Registering Plugins

Call `registerPlugin()` before `app.mount()`. The easiest way is to import your plugin file in `main.ts`.

```typescript
import './plugins/my-plugin' // side-effect import that calls registerPlugin
```

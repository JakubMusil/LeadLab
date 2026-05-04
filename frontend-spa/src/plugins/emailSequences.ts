/**
 * First-party plugin: Email Sequences (frontend, v2.4)
 */
import type { App } from 'vue'
import { registerPlugin } from './index'

registerPlugin({
  manifest: {
    name: 'email-sequences',
    version: '1.0.0',
    description:
      'Multi-step drip campaign plugin. Define timed email sequences triggered by lead status transitions. Celery beat schedules individual sends.',
    iconUrl: 'https://cdn.leadlab.io/plugins/email-sequences/icon.png',
    permissions: ['records:read', 'activities:write', 'notifications:send'],
    configSchema: {
      type: 'object',
      properties: {
        from_email: {
          type: 'string',
          title: 'From Email',
          description: 'Sender address for sequence emails.',
        },
        from_name: {
          type: 'string',
          title: 'From Name',
          description: 'Display name for the sender.',
        },
      },
    },
  },
  activityTypes: [
    {
      type: 'sequence_email_sent',
      label: 'Sequence Email Sent',
      icon: '✉️',
    },
  ],
  navItems: [
    {
      label: 'Sequences',
      icon: '📧',
      path: '/app/sequences',
    },
  ],
  install(_app: App) {
    // No global components registered by this plugin
  },
})

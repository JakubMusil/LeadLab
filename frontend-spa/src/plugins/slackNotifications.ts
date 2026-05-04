/**
 * First-party plugin: Slack Notifications (frontend, v2.4)
 */
import type { App } from 'vue'
import { registerPlugin } from './index'

registerPlugin({
  manifest: {
    name: 'slack-notifications',
    version: '1.0.0',
    description:
      'Send Slack messages to a configurable channel when key CRM events occur: new record, record won/lost, task overdue, proposal accepted.',
    iconUrl: 'https://cdn.leadlab.io/plugins/slack-notifications/icon.png',
    permissions: ['notifications:send', 'records:read'],
    configSchema: {
      type: 'object',
      properties: {
        slack_webhook_url: {
          type: 'string',
          title: 'Slack Incoming Webhook URL',
          description: 'The Incoming Webhook URL from your Slack app configuration.',
          secret: true,
        },
        notify_record_created: { type: 'boolean', title: 'Notify on new record', default: true },
        notify_record_won: { type: 'boolean', title: 'Notify on record won', default: true },
        notify_record_lost: { type: 'boolean', title: 'Notify on record lost', default: true },
        notify_task_overdue: { type: 'boolean', title: 'Notify on overdue task', default: true },
        notify_proposal_accepted: {
          type: 'boolean',
          title: 'Notify on proposal accepted',
          default: true,
        },
      },
      required: ['slack_webhook_url'],
    },
  },
  install(_app: App) {
    // No global components registered by this plugin
  },
})

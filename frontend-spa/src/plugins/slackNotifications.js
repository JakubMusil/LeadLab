import { registerPlugin } from './index';
registerPlugin({
    manifest: {
        name: 'slack-notifications',
        version: '1.0.0',
        description: 'Send Slack messages to a configurable channel when key CRM events occur: new lead, lead won/lost, task overdue, proposal accepted.',
        iconUrl: 'https://cdn.leadlab.io/plugins/slack-notifications/icon.png',
        permissions: ['notifications:send', 'leads:read'],
        configSchema: {
            type: 'object',
            properties: {
                slack_webhook_url: {
                    type: 'string',
                    title: 'Slack Incoming Webhook URL',
                    description: 'The Incoming Webhook URL from your Slack app configuration.',
                    secret: true,
                },
                notify_lead_created: { type: 'boolean', title: 'Notify on new lead', default: true },
                notify_lead_won: { type: 'boolean', title: 'Notify on lead won', default: true },
                notify_lead_lost: { type: 'boolean', title: 'Notify on lead lost', default: true },
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
    install(_app) {
        // No global components registered by this plugin
    },
});

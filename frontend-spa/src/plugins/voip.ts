/**
 * First-party plugin: VoIP / Click-to-Call (frontend, v2.4)
 */
import type { App } from 'vue'
import { registerPlugin } from './index'

registerPlugin({
  manifest: {
    name: 'voip-click-to-call',
    version: '1.0.0',
    description:
      'Integrates with Twilio to place calls directly from a record detail page. Call duration and recording URL are logged as a CALL activity.',
    iconUrl: 'https://cdn.leadlab.io/plugins/voip/icon.png',
    permissions: ['records:read', 'activities:write'],
    configSchema: {
      type: 'object',
      properties: {
        twilio_account_sid: {
          type: 'string',
          title: 'Twilio Account SID',
          secret: true,
        },
        twilio_auth_token: {
          type: 'string',
          title: 'Twilio Auth Token',
          secret: true,
        },
        twilio_caller_id: {
          type: 'string',
          title: 'Caller ID',
          description: 'Verified Twilio phone number (E.164 format, e.g. +14155552671).',
        },
      },
      required: ['twilio_account_sid', 'twilio_auth_token', 'twilio_caller_id'],
    },
  },
  activityTypes: [
    {
      type: 'call',
      label: 'Call',
      icon: '📞',
    },
  ],
  install(_app: App) {
    // No global components registered by this plugin
  },
})

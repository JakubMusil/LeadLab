import { registerPlugin } from './index';
registerPlugin({
    manifest: {
        name: 'linkedin-enrichment',
        version: '1.0.0',
        description: 'Given a LinkedIn profile URL on a customer record, fetches public profile data (name, title, company, avatar) via a proxy API and updates the customer fields.',
        iconUrl: 'https://cdn.leadlab.io/plugins/linkedin-enrichment/icon.png',
        permissions: ['customers:read', 'customers:write', 'activities:write'],
        configSchema: {
            type: 'object',
            properties: {
                proxy_api_url: {
                    type: 'string',
                    title: 'Proxy API URL',
                    description: 'Base URL of the LinkedIn enrichment proxy API.',
                },
                api_key: {
                    type: 'string',
                    title: 'API Key',
                    description: 'Bearer token / API key for the proxy API.',
                    secret: true,
                },
            },
            required: ['proxy_api_url', 'api_key'],
        },
    },
    install(_app) {
        // No global components registered by this plugin
    },
});

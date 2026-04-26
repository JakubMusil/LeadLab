import Badge from './Badge.vue';
const meta = {
    component: Badge,
    tags: ['autodocs'],
    argTypes: {
        variant: { control: 'select', options: ['gray', 'blue', 'green', 'yellow', 'red', 'orange'] },
        size: { control: 'select', options: ['sm', 'md'] },
    },
};
export default meta;
export const Gray = {
    render: (args) => ({
        components: { Badge },
        setup: () => ({ args }),
        template: '<Badge v-bind="args">Draft</Badge>',
    }),
    args: { variant: 'gray' },
};
export const Blue = {
    render: (args) => ({
        components: { Badge },
        setup: () => ({ args }),
        template: '<Badge v-bind="args">Contacted</Badge>',
    }),
    args: { variant: 'blue' },
};
export const Green = {
    render: (args) => ({
        components: { Badge },
        setup: () => ({ args }),
        template: '<Badge v-bind="args">Won</Badge>',
    }),
    args: { variant: 'green' },
};
export const Yellow = {
    render: (args) => ({
        components: { Badge },
        setup: () => ({ args }),
        template: '<Badge v-bind="args">Pending</Badge>',
    }),
    args: { variant: 'yellow' },
};
export const Red = {
    render: (args) => ({
        components: { Badge },
        setup: () => ({ args }),
        template: '<Badge v-bind="args">Lost</Badge>',
    }),
    args: { variant: 'red' },
};
export const Orange = {
    render: (args) => ({
        components: { Badge },
        setup: () => ({ args }),
        template: '<Badge v-bind="args">Negotiation</Badge>',
    }),
    args: { variant: 'orange' },
};

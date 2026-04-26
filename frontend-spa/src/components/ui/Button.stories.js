import Button from './Button.vue';
const meta = {
    component: Button,
    tags: ['autodocs'],
    argTypes: {
        variant: { control: 'select', options: ['primary', 'secondary', 'ghost', 'danger'] },
        size: { control: 'select', options: ['sm', 'md', 'lg'] },
    },
};
export default meta;
export const Primary = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Save changes</Button>',
    }),
    args: { variant: 'primary' },
};
export const Secondary = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Cancel</Button>',
    }),
    args: { variant: 'secondary' },
};
export const Ghost = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Ghost</Button>',
    }),
    args: { variant: 'ghost' },
};
export const Danger = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Delete</Button>',
    }),
    args: { variant: 'danger' },
};
export const Loading = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Saving…</Button>',
    }),
    args: { variant: 'primary', loading: true },
};
export const Small = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Small</Button>',
    }),
    args: { size: 'sm' },
};
export const Large = {
    render: (args) => ({
        components: { Button },
        setup: () => ({ args }),
        template: '<Button v-bind="args">Large</Button>',
    }),
    args: { size: 'lg' },
};

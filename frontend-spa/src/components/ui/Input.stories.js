import Input from './Input.vue';
const meta = {
    component: Input,
    tags: ['autodocs'],
};
export default meta;
export const Default = {
    args: { label: 'Email', placeholder: 'you@example.com', type: 'email' },
};
export const WithError = {
    args: { label: 'Email', placeholder: 'you@example.com', error: 'Email is required', modelValue: '' },
};
export const Disabled = {
    args: { label: 'Email', placeholder: 'you@example.com', disabled: true },
};
export const Required = {
    args: { label: 'Email', placeholder: 'you@example.com', required: true },
};

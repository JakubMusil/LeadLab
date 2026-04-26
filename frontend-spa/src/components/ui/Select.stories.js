import Select from './Select.vue';
const meta = {
    component: Select,
    tags: ['autodocs'],
};
export default meta;
const options = [
    { value: 'new', label: 'New' },
    { value: 'contacted', label: 'Contacted' },
    { value: 'proposal', label: 'Proposal' },
    { value: 'won', label: 'Won' },
    { value: 'lost', label: 'Lost' },
];
export const Default = {
    args: { label: 'Status', options, placeholder: 'Select status' },
};
export const WithError = {
    args: { label: 'Status', options, error: 'Status is required' },
};
export const Disabled = {
    args: { label: 'Status', options, disabled: true, modelValue: 'new' },
};

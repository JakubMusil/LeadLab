import Avatar from './Avatar.vue';
const meta = {
    component: Avatar,
    tags: ['autodocs'],
    argTypes: {
        size: { control: 'select', options: ['xs', 'sm', 'md', 'lg'] },
    },
};
export default meta;
export const Initials = {
    args: { name: 'Jane Doe', size: 'md' },
};
export const SingleName = {
    args: { name: 'Alice', size: 'md' },
};
export const Small = {
    args: { name: 'John Smith', size: 'sm' },
};
export const Large = {
    args: { name: 'Alice Bob', size: 'lg' },
};
export const ExtraSmall = {
    args: { name: 'Tom Hardy', size: 'xs' },
};

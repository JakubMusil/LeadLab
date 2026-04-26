import ToastContainer from './ToastContainer.vue';
const meta = {
    component: ToastContainer,
    tags: ['autodocs'],
};
export default meta;
export const Default = {
    render: () => ({
        components: { ToastContainer },
        template: `<ToastContainer />`,
    }),
};

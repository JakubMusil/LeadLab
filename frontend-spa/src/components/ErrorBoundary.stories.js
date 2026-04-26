import ErrorBoundary from './ErrorBoundary.vue';
const meta = {
    component: ErrorBoundary,
    tags: ['autodocs'],
};
export default meta;
export const Default = {
    render: () => ({
        components: { ErrorBoundary },
        template: `
      <ErrorBoundary>
        <p class="text-sm text-gray-600">No error — content renders here.</p>
      </ErrorBoundary>
    `,
    }),
};

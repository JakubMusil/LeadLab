import type { Meta, StoryObj } from '@storybook/vue3'
import ErrorBoundary from './ErrorBoundary.vue'

const meta: Meta<typeof ErrorBoundary> = {
  component: ErrorBoundary,
  tags: ['autodocs'],
}
export default meta

type Story = StoryObj<typeof ErrorBoundary>

export const Default: Story = {
  render: () => ({
    components: { ErrorBoundary },
    template: `
      <ErrorBoundary>
        <p class="text-sm text-gray-600">No error — content renders here.</p>
      </ErrorBoundary>
    `,
  }),
}

import type { Meta, StoryObj } from '@storybook/vue3'
import ToastContainer from './ToastContainer.vue'

const meta: Meta<typeof ToastContainer> = {
  component: ToastContainer,
  tags: ['autodocs'],
}
export default meta

type Story = StoryObj<typeof ToastContainer>

export const Default: Story = {
  render: () => ({
    components: { ToastContainer },
    template: `<ToastContainer />`,
  }),
}

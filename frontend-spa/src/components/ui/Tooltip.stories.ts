import type { Meta, StoryObj } from '@storybook/vue3'
import Tooltip from './Tooltip.vue'

const meta: Meta<typeof Tooltip> = {
  component: Tooltip,
  tags: ['autodocs'],
  argTypes: {
    placement: { control: 'select', options: ['top', 'bottom', 'left', 'right'] },
  },
}
export default meta

type Story = StoryObj<typeof Tooltip>

export const Top: Story = {
  render: (args) => ({
    components: { Tooltip },
    setup: () => ({ args }),
    template: `
      <div class="flex items-center justify-center h-32">
        <Tooltip v-bind="args">
          <button class="px-3 py-2 bg-gray-100 rounded-lg text-sm">Hover me</button>
        </Tooltip>
      </div>
    `,
  }),
  args: { content: 'This is a tooltip', placement: 'top' },
}

export const Bottom: Story = {
  render: (args) => ({
    components: { Tooltip },
    setup: () => ({ args }),
    template: `
      <div class="flex items-center justify-center h-32">
        <Tooltip v-bind="args">
          <button class="px-3 py-2 bg-gray-100 rounded-lg text-sm">Hover me</button>
        </Tooltip>
      </div>
    `,
  }),
  args: { content: 'Tooltip below', placement: 'bottom' },
}

export const Right: Story = {
  render: (args) => ({
    components: { Tooltip },
    setup: () => ({ args }),
    template: `
      <div class="flex items-center justify-center h-32">
        <Tooltip v-bind="args">
          <button class="px-3 py-2 bg-gray-100 rounded-lg text-sm">Hover me</button>
        </Tooltip>
      </div>
    `,
  }),
  args: { content: 'Tooltip right', placement: 'right' },
}

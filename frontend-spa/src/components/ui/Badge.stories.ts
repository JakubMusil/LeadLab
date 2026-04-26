import type { Meta, StoryObj } from '@storybook/vue3'
import Badge from './Badge.vue'

const meta: Meta<typeof Badge> = {
  component: Badge,
  tags: ['autodocs'],
  argTypes: {
    variant: { control: 'select', options: ['gray', 'blue', 'green', 'yellow', 'red', 'orange'] },
    size: { control: 'select', options: ['sm', 'md'] },
  },
}
export default meta

type Story = StoryObj<typeof Badge>

export const Gray: Story = {
  render: (args) => ({
    components: { Badge },
    setup: () => ({ args }),
    template: '<Badge v-bind="args">Draft</Badge>',
  }),
  args: { variant: 'gray' },
}

export const Blue: Story = {
  render: (args) => ({
    components: { Badge },
    setup: () => ({ args }),
    template: '<Badge v-bind="args">Contacted</Badge>',
  }),
  args: { variant: 'blue' },
}

export const Green: Story = {
  render: (args) => ({
    components: { Badge },
    setup: () => ({ args }),
    template: '<Badge v-bind="args">Won</Badge>',
  }),
  args: { variant: 'green' },
}

export const Yellow: Story = {
  render: (args) => ({
    components: { Badge },
    setup: () => ({ args }),
    template: '<Badge v-bind="args">Pending</Badge>',
  }),
  args: { variant: 'yellow' },
}

export const Red: Story = {
  render: (args) => ({
    components: { Badge },
    setup: () => ({ args }),
    template: '<Badge v-bind="args">Lost</Badge>',
  }),
  args: { variant: 'red' },
}

export const Orange: Story = {
  render: (args) => ({
    components: { Badge },
    setup: () => ({ args }),
    template: '<Badge v-bind="args">Negotiation</Badge>',
  }),
  args: { variant: 'orange' },
}

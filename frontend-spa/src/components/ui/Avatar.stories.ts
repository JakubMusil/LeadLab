import type { Meta, StoryObj } from '@storybook/vue3'
import Avatar from './Avatar.vue'

const meta: Meta<typeof Avatar> = {
  component: Avatar,
  tags: ['autodocs'],
  argTypes: {
    size: { control: 'select', options: ['xs', 'sm', 'md', 'lg'] },
  },
}
export default meta

type Story = StoryObj<typeof Avatar>

export const Initials: Story = {
  args: { name: 'Jane Doe', size: 'md' },
}

export const SingleName: Story = {
  args: { name: 'Alice', size: 'md' },
}

export const Small: Story = {
  args: { name: 'John Smith', size: 'sm' },
}

export const Large: Story = {
  args: { name: 'Alice Bob', size: 'lg' },
}

export const ExtraSmall: Story = {
  args: { name: 'Tom Hardy', size: 'xs' },
}

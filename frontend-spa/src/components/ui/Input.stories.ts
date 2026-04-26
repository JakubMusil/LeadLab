import type { Meta, StoryObj } from '@storybook/vue3'
import Input from './Input.vue'

const meta: Meta<typeof Input> = {
  component: Input,
  tags: ['autodocs'],
}
export default meta

type Story = StoryObj<typeof Input>

export const Default: Story = {
  args: { label: 'Email', placeholder: 'you@example.com', type: 'email' },
}

export const WithError: Story = {
  args: { label: 'Email', placeholder: 'you@example.com', error: 'Email is required', modelValue: '' },
}

export const Disabled: Story = {
  args: { label: 'Email', placeholder: 'you@example.com', disabled: true },
}

export const Required: Story = {
  args: { label: 'Email', placeholder: 'you@example.com', required: true },
}

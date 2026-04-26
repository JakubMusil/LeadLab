import type { Meta, StoryObj } from '@storybook/vue3'
import Select from './Select.vue'

const meta: Meta<typeof Select> = {
  component: Select,
  tags: ['autodocs'],
}
export default meta

type Story = StoryObj<typeof Select>

const options = [
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

export const Default: Story = {
  args: { label: 'Status', options, placeholder: 'Select status' },
}

export const WithError: Story = {
  args: { label: 'Status', options, error: 'Status is required' },
}

export const Disabled: Story = {
  args: { label: 'Status', options, disabled: true, modelValue: 'new' },
}

import type { Meta, StoryObj } from '@storybook/vue3'
import Dropdown from './Dropdown.vue'
import Button from './Button.vue'

const meta: Meta<typeof Dropdown> = {
  component: Dropdown,
  tags: ['autodocs'],
}
export default meta

type Story = StoryObj<typeof Dropdown>

export const Default: Story = {
  render: () => ({
    components: { Dropdown, Button },
    setup() {
      const items = [
        { label: 'Edit', onClick: () => alert('Edit') },
        { label: 'Duplicate', onClick: () => alert('Duplicate') },
        { label: 'Delete', danger: true, onClick: () => alert('Delete') },
      ]
      return { items }
    },
    template: `
      <div class="flex justify-center pt-12">
        <Dropdown :items="items">
          <Button variant="secondary">Actions ▾</Button>
        </Dropdown>
      </div>
    `,
  }),
}

export const LeftAligned: Story = {
  render: () => ({
    components: { Dropdown, Button },
    setup() {
      const items = [
        { label: 'View profile', onClick: () => {} },
        { label: 'Settings', onClick: () => {} },
        { label: 'Sign out', danger: true, onClick: () => {} },
      ]
      return { items }
    },
    template: `
      <div class="flex justify-end pr-4 pt-12">
        <Dropdown :items="items" placement="left">
          <Button variant="secondary">User ▾</Button>
        </Dropdown>
      </div>
    `,
  }),
}

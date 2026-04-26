import type { Meta, StoryObj } from '@storybook/vue3'
import SkeletonLoader from './SkeletonLoader.vue'

const meta: Meta<typeof SkeletonLoader> = {
  component: SkeletonLoader,
  tags: ['autodocs'],
}
export default meta

type Story = StoryObj<typeof SkeletonLoader>

export const ThreeLines: Story = {
  args: { lines: 3 },
}

export const FiveLines: Story = {
  args: { lines: 5 },
}

export const TenLines: Story = {
  args: { lines: 10 },
}

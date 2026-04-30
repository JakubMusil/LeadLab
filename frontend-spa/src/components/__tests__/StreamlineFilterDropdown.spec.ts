import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StreamlineFilterDropdown from '../StreamlineFilterDropdown.vue'

const TOOLS = [
  { activity_type: 'comment', label: 'Comment', category: 'communication', default_visibility: 'important' as const },
  { activity_type: 'email_in', label: 'Email (Inbound)', category: 'communication', default_visibility: 'important' as const },
  { activity_type: 'system_note', label: 'System Note', category: 'system', default_visibility: 'secondary' as const },
  { activity_type: 'ai_summary', label: 'AI Summary', category: 'ai', default_visibility: 'secondary' as const },
]

function makeWrapper(modelValue: Set<string>, isCustomised = false) {
  return mount(StreamlineFilterDropdown, {
    props: {
      tools: TOOLS,
      modelValue,
      isCustomised,
    },
  })
}

describe('StreamlineFilterDropdown', () => {
  it('renders the trigger button with the hidden-count badge', async () => {
    const wrapper = makeWrapper(new Set(['comment', 'email_in']))
    const btn = wrapper.find('[data-testid="streamline-filter-dropdown-button"]')
    expect(btn.exists()).toBe(true)
    // 4 tools registered, 2 hidden → badge shows "2"
    const badge = wrapper.find('[data-testid="streamline-filter-hidden-count"]')
    expect(badge.text()).toBe('2')
  })

  it('omits the badge when no types are hidden', () => {
    const wrapper = makeWrapper(new Set(['comment', 'email_in', 'system_note', 'ai_summary']))
    expect(wrapper.find('[data-testid="streamline-filter-hidden-count"]').exists()).toBe(false)
  })

  it('opens the panel on click and groups items by category', async () => {
    const wrapper = makeWrapper(new Set(['comment']))
    await wrapper.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    expect(wrapper.find('[data-testid="streamline-filter-dropdown-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="streamline-filter-group-communication"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="streamline-filter-group-system"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="streamline-filter-group-ai"]').exists()).toBe(true)
  })

  it('emits update:visible when toggling an item', async () => {
    const wrapper = makeWrapper(new Set(['comment']))
    await wrapper.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    const item = wrapper.find('[data-testid="streamline-filter-item"][data-activity-type="email_in"]')
    await item.trigger('click')
    const events = wrapper.emitted('update:visible')!
    expect(events.length).toBe(1)
    expect(new Set(events[0]![0] as string[])).toEqual(new Set(['comment', 'email_in']))
  })

  it('"Important only" emits the set of important tool types', async () => {
    const wrapper = makeWrapper(new Set(['comment', 'system_note']))
    await wrapper.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    await wrapper.find('[data-testid="streamline-filter-action-important"]').trigger('click')
    const events = wrapper.emitted('update:visible')!
    expect(new Set(events[0]![0] as string[])).toEqual(new Set(['comment', 'email_in']))
  })

  it('"All" emits every registered activity type', async () => {
    const wrapper = makeWrapper(new Set())
    await wrapper.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    await wrapper.find('[data-testid="streamline-filter-action-all"]').trigger('click')
    const events = wrapper.emitted('update:visible')!
    expect(new Set(events[0]![0] as string[])).toEqual(
      new Set(['comment', 'email_in', 'system_note', 'ai_summary']),
    )
  })

  it('"None" emits an empty array', async () => {
    const wrapper = makeWrapper(new Set(['comment']))
    await wrapper.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    await wrapper.find('[data-testid="streamline-filter-action-none"]').trigger('click')
    const events = wrapper.emitted('update:visible')!
    expect(events[0]![0]).toEqual([])
  })

  it('shows "Reset to defaults" only when customised, and emits null', async () => {
    const wrapperPristine = makeWrapper(new Set(['comment']), false)
    await wrapperPristine.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    expect(wrapperPristine.find('[data-testid="streamline-filter-action-reset"]').exists()).toBe(false)

    const wrapper = makeWrapper(new Set(['comment']), true)
    await wrapper.find('[data-testid="streamline-filter-dropdown-button"]').trigger('click')
    const reset = wrapper.find('[data-testid="streamline-filter-action-reset"]')
    expect(reset.exists()).toBe(true)
    await reset.trigger('click')
    const events = wrapper.emitted('update:visible')!
    expect(events[0]![0]).toBeNull()
  })
})

/**
 * Component tests for TeamView.vue
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import TeamView from '../TeamView.vue'

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

vi.mock('@/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
    postForm: vi.fn(),
  },
}))

vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({
    activeFirm: { id: '1', name: 'Test Firm', slug: 'test-firm', subscription_tier: 'free', subscription_active: true, is_active: true },
    firms: [],
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: '1', email: 'owner@example.com', first_name: 'Owner', last_name: 'User', full_name: 'Owner User', timezone: 'UTC' },
  }),
}))

import { api } from '@/api'

const mockMembers = [
  { id: 'mem-1', user_email: 'owner@example.com', user_full_name: 'Owner User', role: 'owner', firm_id: '1' },
  { id: 'mem-2', user_email: 'worker@example.com', user_full_name: 'Worker User', role: 'worker', firm_id: '1' },
]

describe('TeamView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders the Team heading', () => {
    vi.mocked(api.get).mockResolvedValue({ ok: true, status: 200, data: [] })
    const wrapper = mount(TeamView, { global: { stubs: { Teleport: true } } })
    expect(wrapper.text()).toContain('Team')
  })

  it('shows members after load', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ ok: true, status: 200, data: mockMembers }) // members
      .mockResolvedValueOnce({ ok: true, status: 200, data: [] }) // invitations

    const wrapper = mount(TeamView, { global: { stubs: { Teleport: true } } })
    await wrapper.vm.$nextTick()
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('owner@example.com')
    expect(wrapper.text()).toContain('worker@example.com')
  })

  it('shows role badges', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ ok: true, status: 200, data: mockMembers })
      .mockResolvedValueOnce({ ok: true, status: 200, data: [] })

    const wrapper = mount(TeamView, { global: { stubs: { Teleport: true } } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('owner')
    expect(wrapper.text()).toContain('worker')
  })

  it('shows invite form for admin/owner users', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ ok: true, status: 200, data: mockMembers })
      .mockResolvedValueOnce({ ok: true, status: 200, data: [] })

    const wrapper = mount(TeamView, { global: { stubs: { Teleport: true } } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Invite member')
    expect(wrapper.text()).toContain('Send Invite')
  })

  it('shows member count', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ ok: true, status: 200, data: mockMembers })
      .mockResolvedValueOnce({ ok: true, status: 200, data: [] })

    const wrapper = mount(TeamView, { global: { stubs: { Teleport: true } } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('2 members')
  })
})

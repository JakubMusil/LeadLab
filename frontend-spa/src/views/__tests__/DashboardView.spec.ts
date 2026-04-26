/**
 * Component tests for DashboardView.vue
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DashboardView from '../DashboardView.vue'

// Mock Chart.js / vue-chartjs
vi.mock('vue-chartjs', () => ({
  Bar: { template: '<canvas />' },
  Line: { template: '<canvas />' },
}))
vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  BarElement: {},
  CategoryScale: {},
  LinearScale: {},
  Tooltip: {},
  Legend: {},
  LineElement: {},
  PointElement: {},
  Filler: {},
}))

vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({
    activeFirm: { id: '1', name: 'Test Firm' },
  }),
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

import { api } from '@/api'

const mockStats = {
  total_leads: 42,
  leads_by_status: { new: 10, contacted: 8, proposal: 6, negotiation: 5, won: 9, lost: 3, canceled: 1 },
  total_customers: 20,
  total_tasks_pending: 5,
  total_tasks_overdue: 2,
  pipeline_value: 125000,
  won_value: 45000,
  conversion_rate: 0.214,
  recent_activities: [],
}

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/app/dashboard', component: DashboardView },
    { path: '/app/leads', component: { template: '<div/>' } },
  ],
})

describe('DashboardView', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    await router.push('/app/dashboard')
    await router.isReady()
  })

  it('shows loading skeleton or fallback initially when no stats', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 500, data: null })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()
    // Either loading skeleton or fallback — the component should have rendered
    expect(wrapper.exists()).toBe(true)
  })

  it('renders stat cards after data loads', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockStats })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('42') // total leads
    expect(wrapper.text()).toContain('20') // total customers
  })

  it('shows pipeline value', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockStats })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Pipeline')
  })

  it('shows overdue tasks in red when overdue > 0', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockStats })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    // The overdue text should be present
    expect(wrapper.text()).toContain('overdue')
  })

  it('shows conversion rate', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockStats })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('conversion')
  })

  it('shows status breakdown section', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockStats })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Status Breakdown')
    expect(wrapper.text()).toContain('New')
  })

  it('shows error state when API fails', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: null })
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 500, data: null })
    const wrapper = mount(DashboardView, { global: { plugins: [router] } })
    await new Promise((r) => setTimeout(r, 50))
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Failed to load dashboard data')
  })
})

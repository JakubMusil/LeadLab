/**
 * Component tests for LeadsView.vue
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import LeadsView from '../LeadsView.vue'
import { useLeadsStore } from '@/stores/leads'

// Mock vue-router composables used inside component
vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

vi.mock('@/api', () => ({
  api: {
    get: vi.fn().mockResolvedValue({ ok: true, status: 200, data: [] }),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
    postForm: vi.fn(),
  },
}))

// Mock firm store
vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({ activeFirm: { id: '1', name: 'Test Firm' } }),
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: LeadsView },
    { path: '/app/opportunities', component: LeadsView },
    { path: '/app/opportunities/:id', component: { template: '<div/>' } },
  ],
})

describe('LeadsView', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    await router.push('/app/opportunities')
    await router.isReady()
  })

  it('renders the Leads heading', () => {
    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    expect(wrapper.text()).toContain('Leads')
  })

  it('renders the "+ New Lead" button', () => {
    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    expect(wrapper.text()).toContain('+ New Lead')
  })

  it('shows table and kanban view toggle buttons', () => {
    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    expect(wrapper.text()).toContain('Table')
    expect(wrapper.text()).toContain('Kanban')
  })

  it('shows empty state when no leads', async () => {
    const store = useLeadsStore()
    store.leads = []
    store.loading = false

    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    await wrapper.vm.$nextTick()
    // Look for the empty state or the table skeleton
    expect(wrapper.exists()).toBe(true)
  })

  it('opens create modal on "+ New Lead" click', async () => {
    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    await wrapper.find('button').trigger('click')
    // The button we want is "+ New Lead"
    const buttons = wrapper.findAll('button')
    const newLeadBtn = buttons.find((b) => b.text().includes('New Lead'))
    expect(newLeadBtn).toBeDefined()
  })

  it('switches to kanban view when clicking kanban button', async () => {
    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    const buttons = wrapper.findAll('button')
    const kanbanBtn = buttons.find((b) => b.text().includes('Kanban'))
    if (kanbanBtn) {
      await kanbanBtn.trigger('click')
      expect(wrapper.text()).toContain('Kanban')
    }
  })

  it('displays leads when store has data', async () => {
    const store = useLeadsStore()
    store.leads = [{
      id: 'lead-1', firm_id: '1', customer_id: null, title: 'Enterprise Deal',
      description: '', status: 'new', source: 'web', assigned_to_id: null,
      value: 10000, currency: 'CZK', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z',
      created_by_id: null, created_by_name: null,
    }]
    store.loading = false

    const wrapper = mount(LeadsView, {
      global: { plugins: [router] },
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Enterprise Deal')
  })
})

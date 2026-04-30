/**
 * Component tests for SettingsView.vue
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import SettingsView from '../SettingsView.vue'

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

vi.mock('@/composables/useI18n', async () => {
  const actual = await vi.importActual<typeof import('@/composables/useI18n')>('@/composables/useI18n')
  return {
    ...actual,
    // Stub setLocale to avoid `window.location.reload()` during tests; keep
    // the real `useI18n` so the global i18n plugin (registered in
    // src/test/setup.ts) provides a working `t` function.
    setLocale: vi.fn(),
  }
})

vi.mock('@/composables/usePushNotifications', () => ({
  usePushNotifications: () => ({
    isSupported: false,
    isSubscribed: { value: false },
    isLoading: { value: false },
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
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

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: { id: '1', email: 'user@example.com', first_name: 'John', last_name: 'Doe', full_name: 'John Doe', timezone: 'UTC' },
  }),
}))

vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({
    activeFirm: { id: '1', name: 'My Workspace', slug: 'my-workspace', subscription_tier: 'free', subscription_active: true, is_active: true },
    firms: [],
    fetchFirms: vi.fn().mockResolvedValue(undefined),
    setActiveFirm: vi.fn(),
  }),
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/app/settings', component: SettingsView },
    { path: '/app/onboarding', component: { template: '<div/>' } },
  ],
})

describe('SettingsView', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    await router.push('/app/settings')
    await router.isReady()
  })

  it('renders Profile section', () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    expect(wrapper.text()).toContain('Profile')
  })

  it('renders Workspace section', () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    expect(wrapper.text()).toContain('Workspace')
  })

  it('renders Danger Zone section', () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    expect(wrapper.text()).toContain('Danger Zone')
  })

  it('pre-fills profile form with user data', async () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    await wrapper.vm.$nextTick()
    const inputs = wrapper.findAll('input')
    const firstNameInput = inputs.find((i) => (i.element as HTMLInputElement).value === 'John')
    expect(firstNameInput).toBeDefined()
  })

  it('pre-fills workspace name input', async () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    await wrapper.vm.$nextTick()
    const inputs = wrapper.findAll('input')
    const workspaceInput = inputs.find((i) => (i.element as HTMLInputElement).value === 'My Workspace')
    expect(workspaceInput).toBeDefined()
  })

  it('shows delete workspace button', async () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    expect(wrapper.text()).toContain('Delete Workspace')
  })

  it('shows confirmation input after clicking delete workspace', async () => {
    const wrapper = mount(SettingsView, { global: { plugins: [router], stubs: { Teleport: true } } })
    const deleteBtn = wrapper.findAll('button').find((b) => b.text().includes('Delete Workspace'))
    if (deleteBtn) {
      await deleteBtn.trigger('click')
      expect(wrapper.text()).toContain('Type the workspace name')
    }
  })
})

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../auth'

// Mock the api module
vi.mock('@/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    postForm: vi.fn(),
  },
}))

// Mock the router
vi.mock('@/router', () => ({
  default: { push: vi.fn() },
}))

import { api } from '@/api'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initialises with no user and not initialized', () => {
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.initialized).toBe(false)
  })

  it('init() sets initialized=true and calls fetchMe', async () => {
    const mockUser = { id: 1, email: 'test@example.com', first_name: 'Test', last_name: 'User', timezone: 'UTC', full_name: 'Test User' }
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockUser })

    const store = useAuthStore()
    await store.init()

    expect(store.initialized).toBe(true)
    expect(store.user).toEqual(mockUser)
    expect(api.get).toHaveBeenCalledWith('/api/v1/users/me')
  })

  it('init() is idempotent — second call does nothing', async () => {
    vi.mocked(api.get).mockResolvedValue({ ok: true, status: 200, data: { id: 1, email: 'a@b.com', first_name: '', last_name: '', timezone: 'UTC', full_name: '' } })

    const store = useAuthStore()
    await store.init()
    await store.init()

    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('fetchMe() sets user to null on 401', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 401, data: { detail: 'Not authenticated' } })

    const store = useAuthStore()
    await store.fetchMe()

    expect(store.user).toBeNull()
  })

  it('login() stores user on success', async () => {
    const mockUser = { id: 2, email: 'user@test.com', first_name: 'Jane', last_name: 'Doe', timezone: 'UTC', full_name: 'Jane Doe' }
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 200, data: mockUser })

    const store = useAuthStore()
    const result = await store.login('user@test.com', 'password123')

    expect(result.ok).toBe(true)
    expect(store.user).toEqual(mockUser)
  })

  it('login() returns error on failure', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: false, status: 401, data: { detail: 'Invalid credentials.' } })

    const store = useAuthStore()
    const result = await store.login('bad@test.com', 'wrongpass')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Invalid credentials.')
    expect(store.user).toBeNull()
  })

  it('register() calls login after successful registration', async () => {
    const mockUser = { id: 3, email: 'new@test.com', first_name: 'New', last_name: 'User', timezone: 'UTC', full_name: 'New User' }
    vi.mocked(api.post)
      .mockResolvedValueOnce({ ok: true, status: 201, data: mockUser }) // register
      .mockResolvedValueOnce({ ok: true, status: 200, data: mockUser }) // login

    const store = useAuthStore()
    const result = await store.register('new@test.com', 'pass', 'New', 'User')

    expect(result.ok).toBe(true)
    expect(api.post).toHaveBeenCalledTimes(2)
  })

  it('logout() clears user', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 200, data: { detail: 'Logged out successfully.' } })

    const store = useAuthStore()
    store.user = { id: 1, email: 'x@y.com', first_name: '', last_name: '', timezone: 'UTC', number_locale: '', full_name: '', is_staff: false, is_superuser: false }
    await store.logout()

    expect(store.user).toBeNull()
  })
})

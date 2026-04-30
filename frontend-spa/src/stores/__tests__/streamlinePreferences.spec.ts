import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStreamlinePreferencesStore } from '../streamlinePreferences'

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

import { api } from '@/api'

const TOOLS = [
  { activity_type: 'comment', category: 'communication', default_visibility: 'important' as const },
  { activity_type: 'email_in', category: 'communication', default_visibility: 'important' as const },
  { activity_type: 'system_note', category: 'system', default_visibility: 'secondary' as const },
  { activity_type: 'tag_added', category: 'system', default_visibility: 'secondary' as const },
]

describe('useStreamlinePreferencesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('falls back to per-tool defaults when nothing is saved', () => {
    const store = useStreamlinePreferencesStore()
    const visible = store.effectiveVisible(TOOLS)
    expect(visible.has('comment')).toBe(true)
    expect(visible.has('email_in')).toBe(true)
    expect(visible.has('system_note')).toBe(false)
    expect(visible.has('tag_added')).toBe(false)
    expect(store.isCustomised).toBe(false)
  })

  it('uses the saved set verbatim once customised', () => {
    const store = useStreamlinePreferencesStore()
    store.savedVisible = ['system_note']
    const visible = store.effectiveVisible(TOOLS)
    // Defaults are completely ignored once savedVisible is set.
    expect(visible.has('system_note')).toBe(true)
    expect(visible.has('comment')).toBe(false)
    expect(store.isCustomised).toBe(true)
  })

  it('treats an empty saved list as "show nothing" (not as defaults)', () => {
    const store = useStreamlinePreferencesStore()
    store.savedVisible = []
    const visible = store.effectiveVisible(TOOLS)
    expect(visible.size).toBe(0)
    expect(store.isCustomised).toBe(true)
  })

  it('load() populates from the API exactly once', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: { visible_activity_types: ['comment'] },
    })
    const store = useStreamlinePreferencesStore()
    await store.load()
    expect(store.savedVisible).toEqual(['comment'])
    expect(store.loaded).toBe(true)

    // Second call short-circuits.
    await store.load()
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('save(null) resets to defaults', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: { visible_activity_types: null },
    })
    const store = useStreamlinePreferencesStore()
    store.savedVisible = ['comment']
    const ok = await store.save(null)
    expect(ok).toBe(true)
    expect(store.savedVisible).toBeNull()
    expect(store.isCustomised).toBe(false)
  })

  it('save([...]) persists the explicit set', async () => {
    vi.mocked(api.put).mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: { visible_activity_types: ['comment', 'system_note'] },
    })
    const store = useStreamlinePreferencesStore()
    const ok = await store.save(['comment', 'system_note'])
    expect(ok).toBe(true)
    expect(store.savedVisible).toEqual(['comment', 'system_note'])
    expect(api.put).toHaveBeenCalledWith(
      '/api/v1/users/me/streamline-preferences',
      { visible_activity_types: ['comment', 'system_note'] },
    )
  })
})

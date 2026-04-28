/**
 * Phase 4.0 — useTimer composable + timerStore tests
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
  }
})()
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock, writable: true })

// Mock @/api
vi.mock('@/api', () => ({
  api: {
    post: vi.fn(),
  },
}))

vi.mock('@/api/errors', () => ({
  extractErrorMessage: (data: unknown, fallback: string) => fallback,
}))

import { api } from '@/api'
import { useTimerStore } from '../timer'
import { useTimer } from '@/composables/useTimer'

describe('timerStore', () => {
  beforeEach(() => {
    localStorageMock.clear()
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('starts with running=false', () => {
    const store = useTimerStore()
    expect(store.running).toBe(false)
    expect(store.elapsedSeconds).toBe(0)
  })

  it('start() sets running=true and persists to localStorage', () => {
    const store = useTimerStore()
    store.start({ entityType: null, entityId: null, entityLabel: null })
    expect(store.running).toBe(true)
    expect(store.startedAt).not.toBeNull()
    expect(localStorageMock.getItem('ll_timer')).not.toBeNull()
  })

  it('start() with context stores entity info', () => {
    const store = useTimerStore()
    store.start({ entityType: 'lead', entityId: 'lead-123', entityLabel: 'Big Deal' }, 'Work desc', true)
    expect(store.context.entityType).toBe('lead')
    expect(store.context.entityId).toBe('lead-123')
    expect(store.description).toBe('Work desc')
    expect(store.isBillable).toBe(true)
  })

  it('reset() stops timer and clears localStorage', () => {
    const store = useTimerStore()
    store.start({ entityType: null, entityId: null, entityLabel: null })
    store.reset()
    expect(store.running).toBe(false)
    expect(store.startedAt).toBeNull()
    expect(localStorageMock.getItem('ll_timer')).toBeNull()
  })

  it('elapsedSeconds increases after time passes', () => {
    const store = useTimerStore()
    store.start({ entityType: null, entityId: null, entityLabel: null })
    vi.advanceTimersByTime(5000)
    expect(store.elapsedSeconds).toBeGreaterThanOrEqual(5)
  })

  it('displayTime formats correctly as HH:MM:SS', () => {
    const store = useTimerStore()
    store.start({ entityType: null, entityId: null, entityLabel: null })
    vi.advanceTimersByTime(3661 * 1000)
    // Should be 01:01:01 (approximately)
    expect(store.displayTime).toMatch(/^\d{2}:\d{2}:\d{2}$/)
  })

  it('stop() calls API and returns entry on success', async () => {
    const mockEntry = {
      id: 'entry-1',
      duration_minutes: 1,
      description: '',
      is_billable: true,
    }
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true, status: 200, data: mockEntry })

    const store = useTimerStore()
    store.start({ entityType: 'lead', entityId: 'lead-1', entityLabel: 'Deal' }, 'Dev work', true)
    vi.advanceTimersByTime(90 * 1000) // 90 seconds = 1.5 minutes → rounds to 2

    const result = await store.stop()
    expect(result.ok).toBe(true)
    expect(result.entry).toEqual(mockEntry)
    expect(store.running).toBe(false)
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/erp/time-entries',
      expect.objectContaining({
        description: 'Dev work',
        is_billable: true,
        lead_id: 'lead-1',
        customer_id: null,
        task_id: null,
      }),
    )
  })

  it('stop() returns error when not running', async () => {
    const store = useTimerStore()
    const result = await store.stop()
    expect(result.ok).toBe(false)
    expect(result.error).toBeTruthy()
  })

  it('stop() resets store on API failure', async () => {
    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: false, status: 500, data: {} })
    const store = useTimerStore()
    store.start({ entityType: null, entityId: null, entityLabel: null })
    vi.advanceTimersByTime(60_000)
    const result = await store.stop()
    expect(result.ok).toBe(false)
    expect(store.running).toBe(false)
  })
})

describe('useTimer composable', () => {
  beforeEach(() => {
    localStorageMock.clear()
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('exposes running, displayTime and startTimer/stopTimer/resetTimer', () => {
    const timer = useTimer()
    // running and displayTime are Refs (from storeToRefs)
    expect(typeof timer.running.value).toBe('boolean')
    expect(typeof timer.displayTime.value).toBe('string')
    expect(typeof timer.startTimer).toBe('function')
    expect(typeof timer.stopTimer).toBe('function')
    expect(typeof timer.resetTimer).toBe('function')
  })

  it('startTimer sets running to true', () => {
    const timer = useTimer()
    timer.startTimer()
    expect(timer.running.value).toBe(true)
  })

  it('resetTimer stops running', () => {
    const timer = useTimer()
    timer.startTimer()
    timer.resetTimer()
    expect(timer.running.value).toBe(false)
  })
})

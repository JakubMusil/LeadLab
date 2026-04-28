/**
 * Phase 4.0 — Sitewide Timer Store
 *
 * Persists the running timer state in localStorage so it survives page
 * refreshes.  The elapsed time is computed from `startedAt` (a timestamp
 * stored in the store) rather than from a simple counter, which avoids
 * drift when the tab is hidden or the browser throttles timers.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface TimerContext {
  entityType: 'lead' | 'customer' | 'task' | 'realization' | null
  entityId: string | null
  entityLabel: string | null
}

export interface TimeEntryOut {
  id: string
  firm_id: string
  user_id: string | null
  user_name: string | null
  lead_id: string | null
  lead_title: string | null
  customer_id: string | null
  customer_name: string | null
  task_id: string | null
  task_title: string | null
  duration_minutes: number
  description: string
  is_billable: boolean
  started_at: string | null
  ended_at: string | null
  created_at: string
  updated_at: string
}

export interface TimeEntryIn {
  duration_minutes: number
  description?: string
  is_billable?: boolean
  started_at?: string | null
  ended_at?: string | null
  lead_id?: string | null
  customer_id?: string | null
  task_id?: string | null
  realization_id?: string | null
}

const STORAGE_KEY = 'll_timer'

interface PersistedTimer {
  startedAt: number        // unix ms
  context: TimerContext
  description: string
  isBillable: boolean
}

function loadPersisted(): PersistedTimer | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as PersistedTimer) : null
  } catch {
    return null
  }
}

function savePersisted(data: PersistedTimer | null) {
  if (data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

export const useTimerStore = defineStore('timer', () => {
  const persisted = loadPersisted()

  const running = ref(persisted !== null)
  const startedAt = ref<number | null>(persisted?.startedAt ?? null)
  const context = ref<TimerContext>(
    persisted?.context ?? { entityType: null, entityId: null, entityLabel: null },
  )
  const description = ref<string>(persisted?.description ?? '')
  const isBillable = ref<boolean>(persisted?.isBillable ?? true)

  // Elapsed seconds computed live
  const elapsedSeconds = ref<number>(
    persisted ? Math.floor((Date.now() - persisted.startedAt) / 1000) : 0,
  )

  let _interval: ReturnType<typeof setInterval> | null = null

  function _startTick() {
    if (_interval) return
    _interval = setInterval(() => {
      if (startedAt.value !== null) {
        elapsedSeconds.value = Math.floor((Date.now() - startedAt.value) / 1000)
      }
    }, 1000)
  }

  function _stopTick() {
    if (_interval !== null) {
      clearInterval(_interval)
      _interval = null
    }
  }

  // Resume tick if was running on load
  if (running.value) {
    _startTick()
  }

  function start(ctx: TimerContext, desc = '', billable = true) {
    const now = Date.now()
    running.value = true
    startedAt.value = now
    context.value = ctx
    description.value = desc
    isBillable.value = billable
    elapsedSeconds.value = 0
    savePersisted({ startedAt: now, context: ctx, description: desc, isBillable: billable })
    _startTick()
  }

  function reset() {
    _stopTick()
    running.value = false
    startedAt.value = null
    elapsedSeconds.value = 0
    context.value = { entityType: null, entityId: null, entityLabel: null }
    description.value = ''
    isBillable.value = true
    savePersisted(null)
  }

  /**
   * Stop the timer and save a TimeEntry via the API.
   * Returns the created entry or null on error.
   */
  async function stop(): Promise<{ ok: boolean; entry?: TimeEntryOut; error?: string }> {
    if (!running.value || startedAt.value === null) {
      return { ok: false, error: 'Timer is not running' }
    }

    const endedAt = new Date()
    const durationMinutes = Math.max(1, Math.round(elapsedSeconds.value / 60))

    const payload: TimeEntryIn = {
      duration_minutes: durationMinutes,
      description: description.value,
      is_billable: isBillable.value,
      started_at: new Date(startedAt.value).toISOString(),
      ended_at: endedAt.toISOString(),
      lead_id: context.value.entityType === 'lead' ? context.value.entityId : null,
      customer_id: context.value.entityType === 'customer' ? context.value.entityId : null,
      task_id: context.value.entityType === 'task' ? context.value.entityId : null,
      realization_id: context.value.entityType === 'realization' ? context.value.entityId : null,
    }

    const res = await api.post<TimeEntryOut>('/api/v1/erp/time-entries', payload)
    reset()
    if (res.ok) {
      return { ok: true, entry: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to save time entry') }
  }

  /** Formatted elapsed time as HH:MM:SS */
  const displayTime = computed(() => {
    const s = elapsedSeconds.value
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    return [h, m, sec].map((v) => String(v).padStart(2, '0')).join(':')
  })

  return {
    running,
    startedAt,
    context,
    description,
    isBillable,
    elapsedSeconds,
    displayTime,
    start,
    stop,
    reset,
  }
})

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRuleEvaluationLogsStore } from '../ruleEvaluationLogs'

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

const mockLog = {
  id: 'log-1',
  firm_id: 'firm-1',
  record_id: 'record-1',
  rule_id: 'rule-1',
  scenario_id: null,
  requirement_id: null,
  trigger_type: 'record.stage_change_requested',
  result: 'blocked',
  messages: [],
  recommendations: [],
  error_message: '',
  input_context: {},
  evaluated_by_id: null,
  evaluated_at: '2026-01-01T00:00:00Z',
}

describe('useRuleEvaluationLogsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads logs with filters and updates pagination state', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockLog] })
    const store = useRuleEvaluationLogsStore()

    const result = await store.fetchLogs({
      triggerType: 'record.stage_change_requested',
      result: 'blocked',
      ruleId: 'rule-1',
      page: 2,
      pageSize: 1,
    })

    expect(result.ok).toBe(true)
    expect(api.get).toHaveBeenCalledWith(
      '/api/v1/crm/rule-evaluation-logs?page=2&page_size=1&trigger_type=record.stage_change_requested&result=blocked&rule_id=rule-1',
    )
    expect(store.logs).toEqual([mockLog])
    expect(store.page).toBe(2)
    expect(store.pageSize).toBe(1)
    expect(store.hasMore).toBe(true)
  })

  it('stores error and clears logs when fetch fails', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 403, data: { detail: 'Forbidden' } })
    const store = useRuleEvaluationLogsStore()
    store.logs = [mockLog]

    const result = await store.fetchLogs()

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Forbidden')
    expect(store.logs).toEqual([])
    expect(store.error).toBe('Forbidden')
    expect(store.hasMore).toBe(false)
  })

  it('clears state', () => {
    const store = useRuleEvaluationLogsStore()
    store.logs = [mockLog]
    store.page = 3
    store.hasMore = true
    store.error = 'x'

    store.clear()

    expect(store.logs).toEqual([])
    expect(store.page).toBe(1)
    expect(store.hasMore).toBe(false)
    expect(store.error).toBeNull()
  })
})

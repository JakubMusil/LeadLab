import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRecordsStore, normalizeStageChangeIssues } from '../records'

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
    activeFirm: { id: 'firm-1' },
  }),
}))

import { api } from '@/api'

const mockRecord = {
  id: 'record-1',
  firm_id: 'firm-1',
  customer_id: null,
  title: 'Record',
  status: 'new',
  source: 'web',
  assigned_to_id: null,
  assigned_to_name: null,
  value: null,
  currency: 'CZK',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  created_by_id: null,
  created_by_name: null,
  company_id: null,
  company_name: null,
  contact_person_id: null,
  contact_person_name: null,
  category_id: 'cat-1',
  current_stage_id: 'stage-1',
  current_stage_name: 'Stage 1',
  parent_id: null,
  start_date: null,
  end_date: null,
  expires_at: null,
  notes: '',
  extra_data: {},
}

describe('useRecordsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('normalizeStageChangeIssues merges requested blocking and warnings', () => {
    const result = normalizeStageChangeIssues({
      requested: {
        blocking: [{ rule_id: 'r1', name: 'Block', effect: 'block_stage_change', severity: 'error', message: 'blocked' }],
        warnings: [{ rule_id: 'r2', name: 'Warn', effect: 'warn', severity: 'warning', message: 'warn' }],
      },
      changed: {
        blocking: [],
        warnings: [{ rule_id: 'r3', name: 'Changed warn', effect: 'warn', severity: 'warning', message: 'changed' }],
      },
    })

    expect(result.blocking).toHaveLength(1)
    expect(result.blocking[0]?.source).toBe('requested')
    expect(result.warnings).toHaveLength(2)
    expect(result.warnings.map((item) => item.source)).toEqual(['requested', 'changed'])
  })

  it('patchStage returns stageChangeEvaluation on blocked response and rolls stage back', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      ok: false,
      status: 400,
      data: {
        code: 'stage_change_blocked',
        detail: 'Blocked',
        stage_change_evaluation: {
          requested: {
            blocking: [{ rule_id: 'r1', name: 'Block', effect: 'block_stage_change', severity: 'error', message: 'blocked' }],
            warnings: [],
          },
          changed: { blocking: [], warnings: [] },
        },
      },
    })
    const store = useRecordsStore()
    store.records = [{ ...mockRecord }]

    const result = await store.patchStage('record-1', 'stage-2', 'Stage 2')

    expect(result.ok).toBe(false)
    expect(result.code).toBe('stage_change_blocked')
    expect(result.stageChangeEvaluation?.requested?.blocking).toHaveLength(1)
    expect(store.records[0]?.current_stage_id).toBe('stage-1')
    expect(store.records[0]?.current_stage_name).toBe('Stage 1')
  })

  it('updateRecord returns stageChangeEvaluation on warning response', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      data: {
        ...mockRecord,
        stage_change_evaluation: {
          requested: { blocking: [], warnings: [{ rule_id: 'r2', name: 'Warn', effect: 'warn', severity: 'warning', message: 'warn' }] },
          changed: { blocking: [], warnings: [] },
        },
      },
    })
    const store = useRecordsStore()
    store.records = [{ ...mockRecord }]

    const result = await store.updateRecord('record-1', { current_stage_id: 'stage-1' })

    expect(result.ok).toBe(true)
    expect(result.stageChangeEvaluation?.requested?.warnings).toHaveLength(1)
  })
})

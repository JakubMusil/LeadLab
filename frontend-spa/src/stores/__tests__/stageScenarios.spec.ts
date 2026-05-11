import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStageScenariosStore } from '../stageScenarios'

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

const mockScenario = {
  id: 'scenario-1',
  firm_id: 'firm-1',
  category_id: 'cat-1',
  stage_id: 'stage-1',
  name: 'Scenario',
  description: '',
  activation_condition: {},
  completion_condition: {},
  recommended_next_stage_id: null,
  priority: 100,
  is_active: true,
  created_by_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const mockRequirement = {
  id: 'req-1',
  firm_id: 'firm-1',
  scenario_id: 'scenario-1',
  name: 'Requirement',
  description: '',
  requirement_type: 'custom',
  condition: {},
  blocking: true,
  visible_to_user: true,
  sort_order: 0,
  next_step_on_met_id: 'req-2',
  next_step_on_unmet_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('useStageScenariosStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initialises empty state', () => {
    const store = useStageScenariosStore()
    expect(store.scenarios).toEqual([])
    expect(store.requirements).toEqual([])
    expect(store.error).toBeNull()
  })

  it('fetchScenarios populates scenarios on success', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockScenario] })
    const store = useStageScenariosStore()

    const result = await store.fetchScenarios('cat-1', 'stage-1')

    expect(result.ok).toBe(true)
    expect(store.scenarios).toEqual([mockScenario])
    expect(store.error).toBeNull()
  })

  it('fetchScenarios stores error on failure', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 403, data: { detail: 'Forbidden' } })
    const store = useStageScenariosStore()

    const result = await store.fetchScenarios('cat-1', 'stage-1')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Forbidden')
    expect(store.scenarios).toEqual([])
    expect(store.error).toBe('Forbidden')
  })

  it('create/update/delete scenario mutate state', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 201, data: mockScenario })
    vi.mocked(api.patch).mockResolvedValueOnce({ ok: true, status: 200, data: { ...mockScenario, name: 'Updated' } })
    vi.mocked(api.delete).mockResolvedValueOnce({ ok: true, status: 204, data: null })
    const store = useStageScenariosStore()

    const created = await store.createScenario('cat-1', 'stage-1', { name: 'Scenario' })
    const updated = await store.updateScenario('cat-1', 'stage-1', 'scenario-1', { name: 'Updated' })
    store.requirements = [mockRequirement]
    const deleted = await store.deleteScenario('cat-1', 'stage-1', 'scenario-1')

    expect(created.ok).toBe(true)
    expect(updated.ok).toBe(true)
    expect(deleted.ok).toBe(true)
    expect(store.scenarios).toEqual([])
    expect(store.requirements).toEqual([])
  })

  it('fetchRequirements and previewForRecord return expected payloads', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ ok: true, status: 200, data: [mockRequirement] })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        data: {
          record_id: 'record-1',
          active_stage_scenario_id: 'scenario-1',
          active_stage_scenario_name: 'Scenario',
          recommended_next_stage_id: null,
          recommended_next_stage_name: null,
          active_stage_requirements: [],
        },
      })
    const store = useStageScenariosStore()

    const reqResult = await store.fetchRequirements('scenario-1')
    const previewResult = await store.previewForRecord('record-1')

    expect(reqResult.ok).toBe(true)
    expect(store.requirements).toEqual([mockRequirement])
    expect(store.requirements[0]?.next_step_on_met_id).toBe('req-2')
    expect(previewResult.ok).toBe(true)
    expect(previewResult.data?.active_stage_scenario_id).toBe('scenario-1')
  })
})

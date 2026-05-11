import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import RecordDetailView from '../RecordDetailView.vue'

const { recordsStoreMock, pipelineStoreMock, apiGetMock } = vi.hoisted(() => ({
  recordsStoreMock: {
    loadingDetail: false,
    currentRecord: {
      id: 'rec-1',
      title: 'Record A',
      source: 'manual',
      value: 1000,
      currency: 'CZK',
      created_at: '2026-01-01T00:00:00Z',
      category_id: 'cat-1',
      current_stage_id: 'stage-1',
      notes: '',
      expires_at: null,
      start_date: null,
      end_date: null,
      status: 'new',
      company_name: null,
      company_id: null,
      contact_person_name: null,
      contact_person_id: null,
      parent_id: null,
    },
    fetchRecord: vi.fn().mockResolvedValue({ ok: true }),
    updateRecord: vi.fn().mockResolvedValue({ ok: true }),
    deleteRecord: vi.fn().mockResolvedValue({ ok: true }),
  },
  pipelineStoreMock: {
    categories: [{ id: 'cat-1', fields: [] }],
    fetchCategories: vi.fn().mockResolvedValue({ ok: true }),
    getCategoryById: vi.fn().mockReturnValue({ id: 'cat-1', fields: [] }),
    getStagesForCategory: vi.fn().mockReturnValue([
      { id: 'stage-1', name: 'Stage 1', color: '#f59e0b', is_terminal: false, is_won: false },
      { id: 'stage-2', name: 'Stage 2', color: '#10b981', is_terminal: true, is_won: true },
    ]),
    getStageProgress: vi.fn().mockReturnValue(50),
  },
  apiGetMock: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'rec-1' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/stores/records', () => ({
  RECORD_STATUSES: [{ value: 'new', label: 'New' }],
  normalizeStageChangeIssues: () => ({ blocking: [], warnings: [] }),
  useRecordsStore: () => recordsStoreMock,
}))

vi.mock('@/stores/pipeline', () => ({
  usePipelineStore: () => pipelineStoreMock,
}))

vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({ activeFirm: { id: '1' } }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ user: { id: 'u-1' } }),
}))

vi.mock('@/stores/members', () => ({
  useMembersStore: () => ({ fetchMembers: vi.fn(), displayNameById: vi.fn().mockReturnValue('') }),
}))

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({ on: vi.fn(), off: vi.fn() }),
}))

vi.mock('@/api', () => ({
  api: {
    get: apiGetMock,
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
    postForm: vi.fn(),
  },
}))

describe('RecordDetailView - stage requirements panel', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    apiGetMock.mockImplementation((url: string) => {
      if (url.includes('/active-stage-requirements')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          data: {
            record_id: 'rec-1',
            active_stage_scenario_id: null,
            active_stage_scenario_name: null,
            scenario_activated_by_activity_id: null,
            recommended_next_stage_id: null,
            recommended_next_stage_name: null,
            active_stage_requirements: [],
          },
        })
      }
      return Promise.resolve({ ok: true, status: 200, data: [] })
    })
  })

  it('renders stage requirements panel with empty-state message', async () => {
    const wrapper = shallowMount(RecordDetailView)
    await flushPromises()

    expect(wrapper.text()).toContain('Stage requirements')
    expect(wrapper.text()).toContain('No requirements for the active scenario.')
  })

  it('renders unmet and met requirements in separate sections', async () => {
    apiGetMock.mockImplementation((url: string) => {
      if (url.includes('/active-stage-requirements')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          data: {
            record_id: 'rec-1',
            active_stage_scenario_id: 'scenario-1',
            active_stage_scenario_name: 'Scenario A',
            scenario_activated_by_activity_id: null,
            recommended_next_stage_id: null,
            recommended_next_stage_name: null,
            active_stage_requirements: [
              {
                id: 'req-1',
                name: 'Missing handover protocol',
                requirement_type: 'field',
                blocking: true,
                visible_to_user: true,
                is_met: false,
              },
              {
                id: 'req-2',
                name: 'Add service note',
                requirement_type: 'field',
                blocking: false,
                visible_to_user: true,
                is_met: false,
              },
              {
                id: 'req-3',
                name: 'Upload photo',
                requirement_type: 'activity',
                blocking: false,
                visible_to_user: true,
                is_met: true,
                satisfied_by_activity_id: 'act-99',
              },
            ],
          },
        })
      }
      return Promise.resolve({ ok: true, status: 200, data: [] })
    })

    const wrapper = shallowMount(RecordDetailView)
    await flushPromises()

    expect(wrapper.text()).toContain('Unmet requirements')
    expect(wrapper.text()).toContain('Met requirements')
    expect(wrapper.text()).toContain('Missing handover protocol')
    expect(wrapper.text()).toContain('Add service note')
    expect(wrapper.text()).toContain('Upload photo')
    expect(wrapper.text()).toContain('Blocking')
    expect(wrapper.text()).toContain('Warning')
    expect(wrapper.text()).toContain('Satisfied by activity: act-99')
  })
})

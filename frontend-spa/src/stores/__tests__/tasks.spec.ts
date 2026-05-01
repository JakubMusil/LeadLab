import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTasksStore } from '../tasks'

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

const mockTask = {
  id: 'task-1',
  firm_id: '1',
  lead_id: 'lead-1',
  lead_title: null,
  proposal_id: null,
  proposal_title: null,
  customer_id: null,
  customer_name: null,
  project_ids: [],
  assigned_to_id: null,
  assigned_to_name: null,
  completed_by_id: null,
  completed_by_name: null,
  watcher_ids: [],
  title: 'Follow up call',
  description: '',
  description_html: '',
  description_added_at: null,
  priority: 'medium' as const,
  status: 'todo' as const,
  kind: 'generic' as const,
  tags: [],
  due_date: '2025-06-01T10:00:00Z',
  due_date_end: null,
  location: '',
  attendees: [],
  auto_close_on_expiry: false,
  outcome_prompted_at: null,
  is_completed: false,
  completed_at: null,
  is_pinned: false,
  is_archived: false,
  is_favourite: false,
  created_at: '2025-01-01T00:00:00Z',
  created_by_id: null,
  created_by_name: null,
  streamline_count: 0,
  streamline_resolved: 0,
  estimated_minutes: null,
  total_logged_minutes: 0,
  my_active_timer_started_at: null,
  recurrence: null,
  recurrence_parent_id: null,
  approval_required: false,
  approval_status: 'none' as const,
  approval_requested_from_id: null,
  approval_requested_from_name: null,
  approval_note: '',
  custom_fields: [],
}

describe('useTasksStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initialises empty', () => {
    const store = useTasksStore()
    expect(store.tasks).toEqual([])
    expect(store.loading).toBe(false)
  })

  it('fetchTasks() populates tasks', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockTask] })

    const store = useTasksStore()
    const result = await store.fetchTasks()

    expect(result.ok).toBe(true)
    expect(store.tasks).toEqual([mockTask])
  })

  it('fetchTasks() passes completed filter in query', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [] })

    const store = useTasksStore()
    await store.fetchTasks({ completed: false })

    expect(api.get).toHaveBeenCalledWith(expect.stringContaining('completed=false'))
  })

  it('createTask() appends new task', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 201, data: mockTask })

    const store = useTasksStore()
    const result = await store.createTask({ lead_id: 'lead-1', title: 'Follow up call' })

    expect(result.ok).toBe(true)
    expect(store.tasks).toHaveLength(1)
    expect(store.tasks[0]).toEqual(mockTask)
  })

  it('createTask() returns error on failure', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: false, status: 400, data: { detail: 'Lead not found.' } })

    const store = useTasksStore()
    const result = await store.createTask({ lead_id: 'bad', title: 'Task' })

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Lead not found.')
  })

  it('completeTask() updates task in list', async () => {
    const completedTask = { ...mockTask, is_completed: true, completed_at: '2025-06-02T12:00:00Z' }
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 200, data: completedTask })

    const store = useTasksStore()
    store.tasks = [mockTask]
    const result = await store.completeTask('task-1')

    expect(result.ok).toBe(true)
    expect(store.tasks[0]!.is_completed).toBe(true)
  })

  it('completeTask() returns error on failure', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: false, status: 404, data: { detail: 'Task not found.' } })

    const store = useTasksStore()
    store.tasks = [mockTask]
    const result = await store.completeTask('nonexistent')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Task not found.')
  })

  it('fetchTasks() returns error on failure', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 403, data: { detail: 'Forbidden.' } })

    const store = useTasksStore()
    const result = await store.fetchTasks()

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Forbidden.')
  })

  // ---------------------------------------------------------------------------
  // PR4: recordTaskOutcome — held / rescheduled / no_show
  // ---------------------------------------------------------------------------

  it('recordTaskOutcome(held) marks task done locally', async () => {
    const completed = { ...mockTask, is_completed: true, status: 'done' as const, completed_at: '2025-06-02T12:00:00Z' }
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 200, data: completed })

    const store = useTasksStore()
    store.tasks = [{ ...mockTask, kind: 'call', outcome_prompted_at: '2025-06-02T11:00:00Z' }]
    const r = await store.recordTaskOutcome('task-1', { action: 'held', note: 'Talked to client.' })

    expect(r.ok).toBe(true)
    expect(api.post).toHaveBeenCalledWith(
      '/api/v1/crm/tasks/task-1/outcome',
      { action: 'held', note: 'Talked to client.' },
    )
    expect(store.tasks[0]!.is_completed).toBe(true)
    expect(store.tasks[0]!.status).toBe('done')
  })

  it('recordTaskOutcome(rescheduled) updates due_date and clears prompt', async () => {
    const rescheduled = {
      ...mockTask,
      due_date: '2025-06-10T14:00:00Z',
      due_date_end: '2025-06-10T15:00:00Z',
      outcome_prompted_at: null,
      status: 'todo' as const,
    }
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 200, data: rescheduled })

    const store = useTasksStore()
    store.tasks = [{ ...mockTask, kind: 'meeting', outcome_prompted_at: '2025-06-02T11:00:00Z' }]
    const r = await store.recordTaskOutcome('task-1', {
      action: 'rescheduled',
      new_due_date: '2025-06-10T14:00:00Z',
      new_due_date_end: '2025-06-10T15:00:00Z',
    })

    expect(r.ok).toBe(true)
    expect(store.tasks[0]!.due_date).toBe('2025-06-10T14:00:00Z')
    expect(store.tasks[0]!.outcome_prompted_at).toBeNull()
  })

  it('recordTaskOutcome(no_show) flips status to expired', async () => {
    const expired = { ...mockTask, status: 'expired' as const }
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 200, data: expired })

    const store = useTasksStore()
    store.tasks = [{ ...mockTask, kind: 'call', outcome_prompted_at: '2025-06-02T11:00:00Z' }]
    const r = await store.recordTaskOutcome('task-1', { action: 'no_show' })

    expect(r.ok).toBe(true)
    expect(store.tasks[0]!.status).toBe('expired')
  })

  it('recordTaskOutcome() returns error on backend failure', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      ok: false,
      status: 400,
      data: { detail: 'new_due_date is required for rescheduled.' },
    })

    const store = useTasksStore()
    store.tasks = [mockTask]
    const r = await store.recordTaskOutcome('task-1', { action: 'rescheduled' })

    expect(r.ok).toBe(false)
    expect(r.error).toBe('new_due_date is required for rescheduled.')
  })
})

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
  assigned_to_id: null,
  title: 'Follow up call',
  due_date: '2025-06-01T10:00:00Z',
  is_completed: false,
  completed_at: null,
  created_at: '2025-01-01T00:00:00Z',
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
})

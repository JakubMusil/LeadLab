import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface TaskOut {
  id: string
  firm_id: string
  lead_id: string
  assigned_to_id: string | null
  title: string
  due_date: string | null
  is_completed: boolean
  completed_at: string | null
  created_at: string
}

export interface TaskIn {
  lead_id: string
  title: string
  assigned_to_id?: string | null
  due_date?: string | null
}

export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref<TaskOut[]>([])
  const loading = ref(false)

  async function fetchTasks(opts: { completed?: boolean; page?: number; page_size?: number } = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (opts.completed !== undefined) params.set('completed', String(opts.completed))
      params.set('page', String(opts.page ?? 1))
      params.set('page_size', String(opts.page_size ?? 100))
      const res = await api.get<TaskOut[]>(`/api/v1/crm/tasks?${params}`)
      if (res.ok) {
        tasks.value = res.data
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Failed to load tasks.') }
    } finally {
      loading.value = false
    }
  }

  async function createTask(payload: TaskIn): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>('/api/v1/crm/tasks', payload)
    if (res.ok) {
      tasks.value.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create task.') }
  }

  async function completeTask(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/complete`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to complete task.') }
  }

  return { tasks, loading, fetchTasks, createTask, completeTask }
})

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface TaskOut {
  id: string
  firm_id: string
  lead_id: string
  lead_title: string
  assigned_to_id: string | null
  assigned_to_name: string | null
  watcher_ids: string[]
  title: string
  description: string
  due_date: string | null
  is_completed: boolean
  completed_at: string | null
  created_at: string
  created_by_id: string | null
  created_by_name: string | null
}

export interface TaskIn {
  lead_id: string
  title: string
  description?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
}

export interface TaskUpdateIn {
  title?: string
  description?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
  clear_due_date?: boolean
}

export interface FollowUpTaskIn {
  title: string
  description?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
}

export interface TaskCommentOut {
  id: string
  task_id: string
  author_id: string | null
  author_name: string | null
  content_html: string
  created_at: string
  updated_at: string
}

export interface TaskAttachmentOut {
  id: string
  task_id: string
  uploaded_by_id: string | null
  original_filename: string
  content_type: string
  size_bytes: number
  url: string
  created_at: string
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

  async function fetchTasksForView(opts: {
    assignedToId?: string | 'all'
    completed?: boolean
    page?: number
    page_size?: number
  } = {}): Promise<{ ok: boolean; data?: TaskOut[]; error?: string }> {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (opts.assignedToId !== undefined) params.set('assigned_to_id', opts.assignedToId)
      if (opts.completed !== undefined) params.set('completed', String(opts.completed))
      params.set('page', String(opts.page ?? 1))
      params.set('page_size', String(opts.page_size ?? 100))
      const res = await api.get<TaskOut[]>(`/api/v1/crm/tasks?${params}`)
      if (res.ok) {
        tasks.value = res.data
        return { ok: true, data: res.data }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Failed to load tasks.') }
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(id: string): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.get<TaskOut>(`/api/v1/crm/tasks/${id}`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load task.') }
  }

  async function createTask(payload: TaskIn): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>('/api/v1/crm/tasks', payload)
    if (res.ok) {
      tasks.value.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create task.') }
  }

  async function updateTask(id: string, payload: TaskUpdateIn): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.patch<TaskOut>(`/api/v1/crm/tasks/${id}`, payload)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update task.') }
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

  async function completeTaskWithFollowUp(
    id: string,
    followUp?: FollowUpTaskIn,
  ): Promise<{ ok: boolean; error?: string }> {
    const body: Record<string, unknown> = {}
    if (followUp) body.follow_up = followUp
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/complete`, body)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to complete task.') }
  }

  // ---------------------------------------------------------------------------
  // Task comments
  // ---------------------------------------------------------------------------

  async function fetchTaskComments(taskId: string): Promise<{ ok: boolean; data?: TaskCommentOut[]; error?: string }> {
    const res = await api.get<TaskCommentOut[]>(`/api/v1/crm/tasks/${taskId}/comments`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load comments.') }
  }

  async function createTaskComment(taskId: string, contentHtml: string): Promise<{ ok: boolean; data?: TaskCommentOut; error?: string }> {
    const res = await api.post<TaskCommentOut>(`/api/v1/crm/tasks/${taskId}/comments`, { content_html: contentHtml })
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to post comment.') }
  }

  async function updateTaskComment(taskId: string, commentId: string, contentHtml: string): Promise<{ ok: boolean; data?: TaskCommentOut; error?: string }> {
    const res = await api.patch<TaskCommentOut>(`/api/v1/crm/tasks/${taskId}/comments/${commentId}`, { content_html: contentHtml })
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update comment.') }
  }

  async function deleteTaskComment(taskId: string, commentId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${taskId}/comments/${commentId}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete comment.') }
  }

  // ---------------------------------------------------------------------------
  // Task attachments
  // ---------------------------------------------------------------------------

  async function fetchTaskAttachments(taskId: string): Promise<{ ok: boolean; data?: TaskAttachmentOut[]; error?: string }> {
    const res = await api.get<TaskAttachmentOut[]>(`/api/v1/crm/tasks/${taskId}/attachments`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load attachments.') }
  }

  async function uploadTaskAttachment(taskId: string, file: File): Promise<{ ok: boolean; data?: TaskAttachmentOut; error?: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.postForm<TaskAttachmentOut>(`/api/v1/crm/tasks/${taskId}/attachments`, formData)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to upload file.') }
  }

  async function deleteTaskAttachment(taskId: string, attachmentId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${taskId}/attachments/${attachmentId}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete attachment.') }
  }

  return {
    tasks,
    loading,
    fetchTasks,
    fetchTasksForView,
    fetchTask,
    createTask,
    updateTask,
    completeTask,
    completeTaskWithFollowUp,
    fetchTaskComments,
    createTaskComment,
    updateTaskComment,
    deleteTaskComment,
    fetchTaskAttachments,
    uploadTaskAttachment,
    deleteTaskAttachment,
  }
})


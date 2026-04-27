import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface TaskOut {
  id: string
  firm_id: string
  // Entity links
  lead_id: string | null
  lead_title: string | null
  proposal_id: string | null
  proposal_title: string | null
  customer_id: string | null
  customer_name: string | null
  parent_task_id: string | null
  project_ids: string[]
  // Authorship
  assigned_to_id: string | null
  assigned_to_name: string | null
  completed_by_id: string | null
  completed_by_name: string | null
  watcher_ids: string[]
  // Content
  title: string
  description: string
  description_html: string
  description_added_at: string | null
  // Classification
  priority: 'none' | 'low' | 'medium' | 'high' | 'critical'
  status: 'todo' | 'in_progress' | 'blocked' | 'done' | 'cancelled'
  tags: string[]
  // Dates
  due_date: string | null
  due_date_end: string | null
  // Flags
  is_completed: boolean
  completed_at: string | null
  is_pinned: boolean
  is_archived: boolean
  is_favourite: boolean
  created_at: string
  created_by_id: string | null
  created_by_name: string | null
}

export interface TaskIn {
  lead_id?: string | null
  proposal_id?: string | null
  customer_id?: string | null
  title: string
  description?: string
  description_html?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
  due_date_end?: string | null
  priority?: string
  status?: string
  tags?: string[]
  project_ids?: string[]
}

export interface TaskUpdateIn {
  title?: string
  description?: string
  description_html?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
  due_date_end?: string | null
  clear_due_date?: boolean
  clear_due_date_end?: boolean
  priority?: string
  status?: string
  tags?: string[]
  is_pinned?: boolean
  is_archived?: boolean
  project_ids?: string[]
}

export interface FollowUpTaskIn {
  title: string
  description?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
  lead_id?: string | null
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

export interface TaskFetchOpts {
  assignedToId?: string | 'all'
  completed?: boolean
  status?: string
  priority?: string
  isArchived?: boolean
  isPinned?: boolean
  isFavourite?: boolean
  leadId?: string
  proposalId?: string
  customerId?: string
  projectId?: string
  tag?: string
  page?: number
  page_size?: number
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

  async function fetchTasksForView(opts: TaskFetchOpts = {}): Promise<{ ok: boolean; data?: TaskOut[]; error?: string }> {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (opts.assignedToId !== undefined) params.set('assigned_to_id', opts.assignedToId)
      if (opts.completed !== undefined) params.set('completed', String(opts.completed))
      if (opts.status !== undefined) params.set('status', opts.status)
      if (opts.priority !== undefined) params.set('priority', opts.priority)
      if (opts.isArchived !== undefined) params.set('is_archived', String(opts.isArchived))
      if (opts.isPinned !== undefined) params.set('is_pinned', String(opts.isPinned))
      if (opts.isFavourite !== undefined) params.set('is_favourite', String(opts.isFavourite))
      if (opts.leadId !== undefined) params.set('lead_id', opts.leadId)
      if (opts.proposalId !== undefined) params.set('proposal_id', opts.proposalId)
      if (opts.customerId !== undefined) params.set('customer_id', opts.customerId)
      if (opts.projectId !== undefined) params.set('project_id', opts.projectId)
      if (opts.tag !== undefined) params.set('tag', opts.tag)
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

  async function toggleFavourite(id: string): Promise<{ ok: boolean; is_favourite?: boolean; error?: string }> {
    const res = await api.post<{ task_id: string; is_favourite: boolean }>(`/api/v1/crm/tasks/${id}/favourite`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = { ...tasks.value[idx], is_favourite: res.data.is_favourite }
      return { ok: true, is_favourite: res.data.is_favourite }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to toggle favourite.') }
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
    toggleFavourite,
    fetchTaskComments,
    createTaskComment,
    updateTaskComment,
    deleteTaskComment,
    fetchTaskAttachments,
    uploadTaskAttachment,
    deleteTaskAttachment,
  }
})

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


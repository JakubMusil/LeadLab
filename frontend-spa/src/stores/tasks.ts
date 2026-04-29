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
  parent_task_title: string | null
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
  // Phase 3: subtask counters
  subtask_count: number
  subtasks_completed: number
  // Phase 3: checklist counters
  checklist_count: number
  checklist_checked: number
  // Phase 6: time tracking
  estimated_minutes: number | null
  total_logged_minutes: number
  my_active_timer_started_at: string | null
  // Phase 7: recurrence
  recurrence: Record<string, unknown> | null
  recurrence_parent_id: string | null
  // Phase 7: approval
  approval_required: boolean
  approval_status: 'none' | 'pending' | 'approved' | 'rejected'
  approval_requested_from_id: string | null
  approval_requested_from_name: string | null
  approval_note: string
  // Phase 8: custom fields
  custom_fields: Array<{
    field_id: string
    name: string
    field_type: 'text' | 'number' | 'date' | 'dropdown' | 'checkbox' | 'url'
    options: string[]
    is_required: boolean
    position: number
    value: string | number | boolean | null
  }>
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
  estimated_minutes?: number | null
  clear_estimated_minutes?: boolean
  // Phase 7: recurrence
  recurrence?: Record<string, unknown> | null
  clear_recurrence?: boolean
  // Phase 7: approval
  approval_required?: boolean
}

export interface FollowUpTaskIn {
  title: string
  description?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
  lead_id?: string | null
}

export interface TaskDocumentOut {
  id: string
  task_id: string
  uploaded_by_id: string | null
  original_filename: string
  content_type: string
  size_bytes: number
  url: string
  created_at: string
}

/** @deprecated Kept as an alias of TaskDocumentOut for backward-compat. */
export type TaskAttachmentOut = TaskDocumentOut

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

// ---------------------------------------------------------------------------
// Phase 3 types
// ---------------------------------------------------------------------------

export interface SubtaskIn {
  title: string
  description?: string
  description_html?: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
  priority?: string
  status?: string
  tags?: string[]
}

export interface ChecklistItemOut {
  id: string
  task_id: string
  text: string
  is_checked: boolean
  position: number
  created_by_id: string | null
  created_at: string
}

export interface ChecklistItemIn {
  text: string
  position?: number
}

export interface ChecklistItemUpdateIn {
  text?: string
  is_checked?: boolean
  position?: number
}

export interface TaskDependencyOut {
  id: string
  from_task_id: string
  from_task_title: string
  to_task_id: string
  to_task_title: string
  type: 'blocks' | 'related_to'
  created_by_id: string | null
  created_at: string
}

export interface TaskDependencyIn {
  to_task_id: string
  type?: 'blocks' | 'related_to'
}

// ---------------------------------------------------------------------------
// Phase 2: Unified timeline types
// ---------------------------------------------------------------------------

export interface ReactionSummaryOut {
  emoji: string
  count: number
  user_ids: string[]
  reacted_by_me: boolean
}

export interface TimelineAttachmentOut {
  id: string
  original_filename: string
  content_type: string
  size_bytes: number
  url: string
  uploaded_by_id: string | null
  created_at: string
}

export interface TaskTimelineEntryOut {
  id: string
  /** 'activity' (always — legacy 'timeline_entry'/'legacy_*' sources removed) */
  source: string
  /** 'comment' | 'file_upload' | 'status_change' | 'priority_change' | ... */
  event_type: string
  author_id: string | null
  author_name: string | null
  content_text: string
  metadata: Record<string, unknown>
  parent_entry_id: string | null
  reactions: ReactionSummaryOut[]
  reply_count: number
  attachment: TimelineAttachmentOut | null
  created_at: string
}

export interface TaskTimelinePostIn {
  content_text: string
  parent_entry_id?: string | null
  // Action toggles
  change_assignee_to?: string | null
  log_time_minutes?: number | null
  log_time_description?: string
  set_due_date?: string | null
}

// ---------------------------------------------------------------------------
// Phase 6: Time tracking types
// ---------------------------------------------------------------------------

export interface TaskTimeLogOut {
  id: string
  task_id: string
  user_id: string | null
  user_name: string | null
  logged_at: string
  duration_minutes: number
  description: string
  created_at: string
}

export interface TaskTimeLogIn {
  duration_minutes: number
  description?: string
  logged_at?: string | null
}

export interface TaskTimerOut {
  id: string
  task_id: string
  user_id: string
  started_at: string
  stopped_at: string | null
  is_running: boolean
}

// ---------------------------------------------------------------------------
// Phase 7: Task Templates
// ---------------------------------------------------------------------------

export interface TaskTemplateOut {
  id: string
  firm_id: string
  name: string
  description_html: string
  priority: 'none' | 'low' | 'medium' | 'high' | 'critical'
  estimated_minutes: number | null
  checklist_items: Array<{ text: string; position: number }>
  tags: string[]
  created_by_id: string | null
  created_by_name: string | null
  created_at: string
  updated_at: string
}

export interface TaskTemplateIn {
  name: string
  description_html?: string
  priority?: string
  estimated_minutes?: number | null
  checklist_items?: Array<{ text: string; position: number }>
  tags?: string[]
}

export interface TaskTemplateUpdateIn {
  name?: string
  description_html?: string
  priority?: string
  estimated_minutes?: number | null
  clear_estimated_minutes?: boolean
  checklist_items?: Array<{ text: string; position: number }>
  tags?: string[]
}

export interface TaskTemplateApplyIn {
  title: string
  lead_id?: string | null
  proposal_id?: string | null
  customer_id?: string | null
  assigned_to_id?: string | null
  watcher_ids?: string[]
  due_date?: string | null
}

// ---------------------------------------------------------------------------
// Phase 8: Custom Fields types
// ---------------------------------------------------------------------------

export interface TaskCustomFieldOut {
  id: string
  firm_id: string
  name: string
  field_type: 'text' | 'number' | 'date' | 'dropdown' | 'checkbox' | 'url'
  options: string[]
  is_required: boolean
  position: number
  created_at: string
}

export interface TaskCustomFieldIn {
  name: string
  field_type?: string
  options?: string[]
  is_required?: boolean
  position?: number
}

export interface TaskCustomFieldUpdateIn {
  name?: string
  field_type?: string
  options?: string[]
  is_required?: boolean
  position?: number
}

export interface TaskCustomFieldValueIn {
  field_id: string
  value_text?: string | null
  value_number?: number | null
  value_date?: string | null
  value_bool?: boolean | null
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
      if (idx !== -1) tasks.value[idx] = { ...tasks.value[idx], is_favourite: res.data.is_favourite } as TaskOut
      return { ok: true, is_favourite: res.data.is_favourite }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to toggle favourite.') }
  }

  // ---------------------------------------------------------------------------
  // Task documents (replaces legacy /tasks/:id/attachments — Document-backed)
  // ---------------------------------------------------------------------------

  async function fetchTaskAttachments(taskId: string): Promise<{ ok: boolean; data?: TaskDocumentOut[]; error?: string }> {
    const res = await api.get<TaskDocumentOut[]>(`/api/v1/crm/tasks/${taskId}/documents`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load attachments.') }
  }

  async function uploadTaskAttachment(taskId: string, file: File): Promise<{ ok: boolean; data?: TaskDocumentOut; error?: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const res = await api.postForm<TaskDocumentOut>(`/api/v1/crm/tasks/${taskId}/documents`, formData)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to upload file.') }
  }

  async function deleteTaskAttachment(taskId: string, attachmentId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${taskId}/documents/${attachmentId}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete attachment.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 3: Subtasks
  // ---------------------------------------------------------------------------

  async function fetchSubtasks(taskId: string): Promise<{ ok: boolean; data?: TaskOut[]; error?: string }> {
    const res = await api.get<TaskOut[]>(`/api/v1/crm/tasks/${taskId}/subtasks`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load subtasks.') }
  }

  async function createSubtask(taskId: string, payload: SubtaskIn): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${taskId}/subtasks`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create subtask.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 3: Checklist
  // ---------------------------------------------------------------------------

  async function fetchChecklist(taskId: string): Promise<{ ok: boolean; data?: ChecklistItemOut[]; error?: string }> {
    const res = await api.get<ChecklistItemOut[]>(`/api/v1/crm/tasks/${taskId}/checklist`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load checklist.') }
  }

  async function createChecklistItem(taskId: string, payload: ChecklistItemIn): Promise<{ ok: boolean; data?: ChecklistItemOut; error?: string }> {
    const res = await api.post<ChecklistItemOut>(`/api/v1/crm/tasks/${taskId}/checklist`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create checklist item.') }
  }

  async function updateChecklistItem(taskId: string, itemId: string, payload: ChecklistItemUpdateIn): Promise<{ ok: boolean; data?: ChecklistItemOut; error?: string }> {
    const res = await api.patch<ChecklistItemOut>(`/api/v1/crm/tasks/${taskId}/checklist/${itemId}`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update checklist item.') }
  }

  async function deleteChecklistItem(taskId: string, itemId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${taskId}/checklist/${itemId}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete checklist item.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 3: Dependencies
  // ---------------------------------------------------------------------------

  async function fetchDependencies(taskId: string): Promise<{ ok: boolean; data?: TaskDependencyOut[]; error?: string }> {
    const res = await api.get<TaskDependencyOut[]>(`/api/v1/crm/tasks/${taskId}/dependencies`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load dependencies.') }
  }

  async function createDependency(taskId: string, payload: TaskDependencyIn): Promise<{ ok: boolean; data?: TaskDependencyOut; error?: string }> {
    const res = await api.post<TaskDependencyOut>(`/api/v1/crm/tasks/${taskId}/dependencies`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create dependency.') }
  }

  async function deleteDependency(taskId: string, dependencyId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${taskId}/dependencies/${dependencyId}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete dependency.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 2: Unified timeline
  // ---------------------------------------------------------------------------

  async function fetchTimeline(
    taskId: string,
    opts: { eventType?: string; order?: 'asc' | 'desc'; page?: number; pageSize?: number } = {},
  ): Promise<{ ok: boolean; data?: TaskTimelineEntryOut[]; error?: string }> {
    const params = new URLSearchParams()
    if (opts.eventType) params.set('event_type', opts.eventType)
    if (opts.order) params.set('order', opts.order)
    params.set('page', String(opts.page ?? 1))
    params.set('page_size', String(opts.pageSize ?? 100))
    const res = await api.get<TaskTimelineEntryOut[]>(`/api/v1/crm/tasks/${taskId}/timeline?${params}`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load timeline.') }
  }

  async function createTimelineEntry(
    taskId: string,
    payload: TaskTimelinePostIn,
  ): Promise<{ ok: boolean; data?: TaskTimelineEntryOut; error?: string }> {
    const res = await api.post<TaskTimelineEntryOut>(`/api/v1/crm/tasks/${taskId}/timeline`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to post comment.') }
  }

  async function toggleTimelineReaction(
    taskId: string,
    entryId: string,
    emoji: string,
  ): Promise<{ ok: boolean; data?: ReactionSummaryOut; error?: string }> {
    const res = await api.post<ReactionSummaryOut>(
      `/api/v1/crm/tasks/${taskId}/timeline/${entryId}/reactions`,
      { emoji },
    )
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to toggle reaction.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 5: Task operations
  // ---------------------------------------------------------------------------

  async function deleteTask(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${id}`)
    if (res.ok) {
      tasks.value = tasks.value.filter((t) => t.id !== id)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete task.') }
  }

  async function archiveTask(id: string): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/archive`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to archive task.') }
  }

  async function unarchiveTask(id: string): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/unarchive`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to unarchive task.') }
  }

  async function pinTask(id: string): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/pin`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to pin task.') }
  }

  async function unpinTask(id: string): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/unpin`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to unpin task.') }
  }

  async function copyTask(
    id: string,
    opts: { title?: string; include_subtasks?: boolean; include_checklist?: boolean },
  ): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/copy`, opts)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to copy task.') }
  }

  async function moveTask(
    id: string,
    opts: { lead_id?: string | null; proposal_id?: string | null; customer_id?: string | null },
  ): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${id}/move`, opts)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === id)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to move task.') }
  }

  async function getPublicLink(id: string): Promise<{ ok: boolean; data?: { token: string; url: string }; error?: string }> {
    const res = await api.get<{ token: string; url: string }>(`/api/v1/crm/tasks/${id}/public-link`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to get public link.') }
  }

  async function batchAction(
    taskIds: string[],
    action: string,
    opts: { assigned_to_id?: string } = {},
  ): Promise<{ ok: boolean; data?: { processed: number; failed: number }; error?: string }> {
    const res = await api.post<{ processed: number; failed: number }>(`/api/v1/crm/tasks/batch`, {
      task_ids: taskIds,
      action,
      ...opts,
    })
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to perform batch action.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 6: Time tracking
  // ---------------------------------------------------------------------------

  async function fetchTimeLogs(taskId: string): Promise<{ ok: boolean; data?: TaskTimeLogOut[]; error?: string }> {
    const res = await api.get<TaskTimeLogOut[]>(`/api/v1/crm/tasks/${taskId}/time-logs`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load time logs.') }
  }

  async function createTimeLog(taskId: string, payload: TaskTimeLogIn): Promise<{ ok: boolean; data?: TaskTimeLogOut; error?: string }> {
    const res = await api.post<TaskTimeLogOut>(`/api/v1/crm/tasks/${taskId}/time-logs`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create time log.') }
  }

  async function deleteTimeLog(taskId: string, logId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/tasks/${taskId}/time-logs/${logId}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete time log.') }
  }

  async function startTimer(taskId: string): Promise<{ ok: boolean; data?: TaskTimerOut; error?: string }> {
    const res = await api.post<TaskTimerOut>(`/api/v1/crm/tasks/${taskId}/timer/start`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to start timer.') }
  }

  async function stopTimer(taskId: string): Promise<{ ok: boolean; data?: TaskTimerOut; error?: string }> {
    const res = await api.post<TaskTimerOut>(`/api/v1/crm/tasks/${taskId}/timer/stop`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to stop timer.') }
  }

  async function getActiveTimer(taskId: string): Promise<{ ok: boolean; data?: TaskTimerOut | null; error?: string }> {
    const res = await api.get<TaskTimerOut | null>(`/api/v1/crm/tasks/${taskId}/timer/active`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to get active timer.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 7: Approval workflow
  // ---------------------------------------------------------------------------

  async function requestApproval(
    taskId: string,
    approverId: string,
  ): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${taskId}/request-approval`, {
      approver_id: approverId,
    })
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === taskId)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to request approval.') }
  }

  async function approveTask(taskId: string): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${taskId}/approve`)
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === taskId)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to approve task.') }
  }

  async function rejectTask(taskId: string, note = ''): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/tasks/${taskId}/reject`, { note })
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === taskId)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to reject task.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 7: Task Templates
  // ---------------------------------------------------------------------------

  async function fetchTaskTemplates(): Promise<{ ok: boolean; data?: TaskTemplateOut[]; error?: string }> {
    const res = await api.get<TaskTemplateOut[]>('/api/v1/crm/task-templates')
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load task templates.') }
  }

  async function fetchTaskTemplate(id: string): Promise<{ ok: boolean; data?: TaskTemplateOut; error?: string }> {
    const res = await api.get<TaskTemplateOut>(`/api/v1/crm/task-templates/${id}`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load task template.') }
  }

  async function createTaskTemplate(payload: TaskTemplateIn): Promise<{ ok: boolean; data?: TaskTemplateOut; error?: string }> {
    const res = await api.post<TaskTemplateOut>('/api/v1/crm/task-templates', payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create task template.') }
  }

  async function updateTaskTemplate(
    id: string,
    payload: TaskTemplateUpdateIn,
  ): Promise<{ ok: boolean; data?: TaskTemplateOut; error?: string }> {
    const res = await api.patch<TaskTemplateOut>(`/api/v1/crm/task-templates/${id}`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update task template.') }
  }

  async function deleteTaskTemplate(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/task-templates/${id}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete task template.') }
  }

  async function applyTaskTemplate(
    templateId: string,
    payload: TaskTemplateApplyIn,
  ): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.post<TaskOut>(`/api/v1/crm/task-templates/${templateId}/apply`, payload)
    if (res.ok) {
      tasks.value.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to apply task template.') }
  }

  // ---------------------------------------------------------------------------
  // Phase 8: Custom Fields
  // ---------------------------------------------------------------------------

  async function fetchCustomFields(): Promise<{ ok: boolean; data?: TaskCustomFieldOut[]; error?: string }> {
    const res = await api.get<TaskCustomFieldOut[]>('/api/v1/crm/custom-fields')
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load custom fields.') }
  }

  async function createCustomField(payload: TaskCustomFieldIn): Promise<{ ok: boolean; data?: TaskCustomFieldOut; error?: string }> {
    const res = await api.post<TaskCustomFieldOut>('/api/v1/crm/custom-fields', payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create custom field.') }
  }

  async function updateCustomField(id: string, payload: TaskCustomFieldUpdateIn): Promise<{ ok: boolean; data?: TaskCustomFieldOut; error?: string }> {
    const res = await api.patch<TaskCustomFieldOut>(`/api/v1/crm/custom-fields/${id}`, payload)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update custom field.') }
  }

  async function deleteCustomField(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/custom-fields/${id}`)
    if (res.ok) return { ok: true }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete custom field.') }
  }

  async function upsertTaskCustomFields(
    taskId: string,
    values: TaskCustomFieldValueIn[],
  ): Promise<{ ok: boolean; data?: TaskOut; error?: string }> {
    const res = await api.patch<TaskOut>(`/api/v1/crm/tasks/${taskId}/custom-fields`, { values })
    if (res.ok) {
      const idx = tasks.value.findIndex((t) => t.id === taskId)
      if (idx !== -1) tasks.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to save custom field values.') }
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
    fetchTaskAttachments,
    uploadTaskAttachment,
    deleteTaskAttachment,
    // Phase 3
    fetchSubtasks,
    createSubtask,
    fetchChecklist,
    createChecklistItem,
    updateChecklistItem,
    deleteChecklistItem,
    fetchDependencies,
    createDependency,
    deleteDependency,
    // Phase 2: timeline
    fetchTimeline,
    createTimelineEntry,
    toggleTimelineReaction,
    // Phase 5
    deleteTask,
    archiveTask,
    unarchiveTask,
    pinTask,
    unpinTask,
    copyTask,
    moveTask,
    getPublicLink,
    batchAction,
    // Phase 6: time tracking
    fetchTimeLogs,
    createTimeLog,
    deleteTimeLog,
    startTimer,
    stopTimer,
    getActiveTimer,
    // Phase 7: approval
    requestApproval,
    approveTask,
    rejectTask,
    // Phase 7: task templates
    fetchTaskTemplates,
    fetchTaskTemplate,
    createTaskTemplate,
    updateTaskTemplate,
    deleteTaskTemplate,
    applyTaskTemplate,
    // Phase 8: custom fields
    fetchCustomFields,
    createCustomField,
    updateCustomField,
    deleteCustomField,
    upsertTaskCustomFields,
  }
})

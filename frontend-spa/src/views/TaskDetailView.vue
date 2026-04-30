<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useTasksStore, type TaskOut, type ChecklistItemOut, type TaskDependencyOut, type TaskTimeLogOut, type TaskTimerOut, type TaskCustomFieldValueIn } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import TaskOutcomeModal from '@/components/TaskOutcomeModal.vue'
import DOMPurify from 'dompurify'

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const tasksStore = useTasksStore()
const toast = useToast()
const { t } = useI18n()

const taskId = computed(() => route.params.id as string)

// ---------------------------------------------------------------------------
// Priority / Status constants
// ---------------------------------------------------------------------------
const PRIORITY_LABELS: Record<string, string> = {
  none: '—',
  low: t('tasks.priorityLow'),
  medium: t('tasks.priorityMedium'),
  high: t('tasks.priorityHigh'),
  critical: t('tasks.priorityCritical'),
}
const PRIORITY_COLORS: Record<string, string> = {
  none: 'text-gray-400',
  low: 'text-blue-500',
  medium: 'text-yellow-500',
  high: 'text-orange-500',
  critical: 'text-red-600',
}
const STATUS_LABELS: Record<string, string> = {
  todo: t('tasks.statusTodo'),
  in_progress: t('tasks.statusInProgress'),
  blocked: t('tasks.statusBlocked'),
  done: t('tasks.statusDone'),
  cancelled: t('tasks.statusCancelled'),
}
const STATUS_COLORS: Record<string, string> = {
  todo: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
  in_progress: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  blocked: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
  done: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  cancelled: 'bg-gray-200 text-gray-500 dark:bg-gray-800 dark:text-gray-400 line-through',
}

// ---------------------------------------------------------------------------
// Team members (for @mention and assignee selectors)
// ---------------------------------------------------------------------------
interface Member {
  id: string
  user_id: string
  user_email: string
  user_full_name: string
  role: string
}
const members = ref<Member[]>([])
const teamMembers = ref<MentionUser[]>([])

async function loadMembers() {
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (!firmId) return
  const res = await api.get<Member[]>(`/api/v1/firms/${firmId}/members`)
  if (res.ok) {
    members.value = res.data
    teamMembers.value = res.data.map((m) => ({
      id: m.user_id,
      label: m.user_full_name?.trim() || m.user_email,
    }))
  }
}

function memberLabel(m: Member) {
  return m.user_full_name?.trim() || m.user_email
}

const currentMember = computed(() =>
  members.value.find((m) => m.user_email === authStore.user?.email),
)
const isAdmin = computed(() =>
  currentMember.value?.role === 'admin' || currentMember.value?.role === 'owner',
)

// ---------------------------------------------------------------------------
// Task
// ---------------------------------------------------------------------------
const task = ref<TaskOut | null>(null)
const taskLoading = ref(false)
const taskError = ref('')

async function loadTask() {
  taskLoading.value = true
  taskError.value = ''
  const result = await tasksStore.fetchTask(taskId.value)
  taskLoading.value = false
  if (result.ok && result.data) {
    task.value = result.data
  } else {
    taskError.value = result.error ?? t('tasks.loadFailed')
  }
}

function isOverdue(t: TaskOut) {
  return !t.is_completed && t.due_date && new Date(t.due_date) < new Date()
}

function formatDate(ds: string | null) {
  if (!ds) return '—'
  return new Date(ds).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDateTime(ds: string) {
  return new Date(ds).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// Inline title editing
// ---------------------------------------------------------------------------
const editingTitle = ref(false)
const inlineTitle = ref('')
const titleInputRef = ref<HTMLInputElement | null>(null)
const titleSaving = ref(false)

function startInlineEditTitle() {
  if (!task.value || task.value.is_completed) return
  inlineTitle.value = task.value.title
  editingTitle.value = true
  setTimeout(() => titleInputRef.value?.focus(), 0)
}

async function saveInlineTitle() {
  if (!task.value || !inlineTitle.value.trim()) {
    editingTitle.value = false
    return
  }
  if (inlineTitle.value.trim() === task.value.title) {
    editingTitle.value = false
    return
  }
  titleSaving.value = true
  const result = await tasksStore.updateTask(task.value.id, { title: inlineTitle.value.trim() })
  titleSaving.value = false
  editingTitle.value = false
  if (result.ok && result.data) {
    task.value = result.data
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

function cancelInlineEditTitle() {
  editingTitle.value = false
}

// ---------------------------------------------------------------------------
// Edit task modal
// ---------------------------------------------------------------------------
const showEditTask = ref(false)
const editTitle = ref('')
const editDescription = ref('')
const editDescriptionHtml = ref('')
const editDueDate = ref('')
const editDueDateEnd = ref('')
const editAssigneeId = ref('')
const editWatcherIds = ref<string[]>([])
const editPriority = ref('medium')
const editStatus = ref('todo')
const editTags = ref('')
const editSubmitting = ref(false)
const editError = ref('')

function openEditTask() {
  if (!task.value) return
  editTitle.value = task.value.title
  editDescription.value = task.value.description
  editDescriptionHtml.value = task.value.description_html
  editDueDate.value = task.value.due_date ? (task.value.due_date.split('T')[0] ?? '') : ''
  editDueDateEnd.value = task.value.due_date_end ? (task.value.due_date_end.split('T')[0] ?? '') : ''
  editAssigneeId.value = task.value.assigned_to_id ?? ''
  editWatcherIds.value = [...task.value.watcher_ids]
  editPriority.value = task.value.priority
  editStatus.value = task.value.status
  editTags.value = (task.value.tags ?? []).join(', ')
  editError.value = ''
  showEditTask.value = true
}

async function submitEditTask() {
  if (!editTitle.value.trim()) { editError.value = t('tasks.titleRequired'); return }
  if (!task.value) return
  editSubmitting.value = true
  editError.value = ''
  const tagsArray = editTags.value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const result = await tasksStore.updateTask(task.value.id, {
    title: editTitle.value.trim(),
    description: editDescription.value,
    description_html: editDescriptionHtml.value,
    assigned_to_id: editAssigneeId.value || null,
    watcher_ids: editWatcherIds.value,
    due_date: editDueDate.value ? new Date(editDueDate.value).toISOString() : null,
    due_date_end: editDueDateEnd.value ? new Date(editDueDateEnd.value).toISOString() : null,
    clear_due_date: !editDueDate.value,
    clear_due_date_end: !editDueDateEnd.value,
    priority: editPriority.value,
    status: editStatus.value,
    tags: tagsArray,
  })
  editSubmitting.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showEditTask.value = false
    toast.success(t('tasks.taskUpdated'))
  } else {
    editError.value = result.error ?? t('tasks.updateFailed')
  }
}

function toggleWatcher(watcherIds: string[], userId: string) {
  const idx = watcherIds.indexOf(userId)
  if (idx !== -1) watcherIds.splice(idx, 1)
  else watcherIds.push(userId)
}

// ---------------------------------------------------------------------------
// Leads (for move modal)
// ---------------------------------------------------------------------------
interface LeadOption { id: string; title: string }
const leads = ref<LeadOption[]>([])

async function loadLeads() {
  const res = await api.get<LeadOption[]>('/api/v1/crm/opportunities?page_size=200')
  if (res.ok) leads.value = res.data as LeadOption[]
}

// ---------------------------------------------------------------------------
// Favourite
// ---------------------------------------------------------------------------
const togglingFavourite = ref(false)

async function toggleFavourite() {
  if (!task.value) return
  togglingFavourite.value = true
  const result = await tasksStore.toggleFavourite(task.value.id)
  togglingFavourite.value = false
  if (result.ok) {
    task.value = { ...task.value, is_favourite: result.is_favourite ?? false }
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

// ---------------------------------------------------------------------------
// Phase 5: Action menu (⋮)
// ---------------------------------------------------------------------------
const showActionMenu = ref(false)

// Copy task
const showCopyModal = ref(false)
const copyTitle = ref('')
const copyIncludeSubtasks = ref(false)
const copyIncludeChecklist = ref(true)
const copySubmitting = ref(false)

async function submitCopyTask() {
  if (!task.value) return
  copySubmitting.value = true
  const result = await tasksStore.copyTask(task.value.id, {
    title: copyTitle.value || undefined,
    include_subtasks: copyIncludeSubtasks.value,
    include_checklist: copyIncludeChecklist.value,
  })
  copySubmitting.value = false
  if (result.ok && result.data) {
    showCopyModal.value = false
    toast.success(t('tasks.taskCopied'))
    router.push(`/app/tasks/${result.data.id}`)
  } else {
    toast.error(result.error ?? t('tasks.copyFailed'))
  }
}

function openCopyModal() {
  if (!task.value) return
  copyTitle.value = task.value.title + ' ' + t('tasks.copySuffix')
  copyIncludeSubtasks.value = false
  copyIncludeChecklist.value = true
  showCopyModal.value = true
  showActionMenu.value = false
}

// Move task
const showMoveModal = ref(false)
const moveLeadId = ref('')
const moveCustomerId = ref('')
const moveSubmitting = ref(false)
const customers = ref<{ id: string; display: string }[]>([])

async function loadCustomers() {
  const res = await api.get<{ id: string; first_name: string; last_name: string; company_name: string }[]>('/api/v1/crm/directory?page_size=200')
  if (res.ok) {
    customers.value = (res.data as any[]).map((c) => ({
      id: c.id,
      display: `${c.first_name} ${c.last_name}`.trim() || c.company_name || c.id,
    }))
  }
}

function openMoveModal() {
  if (!task.value) return
  moveLeadId.value = task.value.lead_id ?? ''
  moveCustomerId.value = task.value.customer_id ?? ''
  showMoveModal.value = true
  showActionMenu.value = false
  loadCustomers()
}

async function submitMoveTask() {
  if (!task.value) return
  moveSubmitting.value = true
  const result = await tasksStore.moveTask(task.value.id, {
    lead_id: moveLeadId.value || null,
    customer_id: moveCustomerId.value || null,
  })
  moveSubmitting.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showMoveModal.value = false
    toast.success(t('tasks.taskMoved'))
  } else {
    toast.error(result.error ?? t('tasks.moveFailed'))
  }
}

// Archive / Unarchive
const archiving = ref(false)

async function toggleArchive() {
  if (!task.value) return
  archiving.value = true
  showActionMenu.value = false
  const result = task.value.is_archived
    ? await tasksStore.unarchiveTask(task.value.id)
    : await tasksStore.archiveTask(task.value.id)
  archiving.value = false
  if (result.ok && result.data) {
    task.value = result.data
    toast.success(task.value.is_archived ? t('tasks.taskArchived') : t('tasks.taskUnarchived'))
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

// Pin / Unpin
const pinning = ref(false)

async function togglePin() {
  if (!task.value) return
  pinning.value = true
  showActionMenu.value = false
  const result = task.value.is_pinned
    ? await tasksStore.unpinTask(task.value.id)
    : await tasksStore.pinTask(task.value.id)
  pinning.value = false
  if (result.ok && result.data) {
    task.value = result.data
    toast.success(task.value.is_pinned ? t('tasks.taskPinned') : t('tasks.taskUnpinned'))
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

// Share (public link)
async function sharePublicLink() {
  if (!task.value) return
  showActionMenu.value = false
  const result = await tasksStore.getPublicLink(task.value.id)
  if (result.ok && result.data) {
    const fullUrl = window.location.origin + '/app/tasks/public/' + result.data.token
    try {
      await navigator.clipboard.writeText(fullUrl)
      toast.success(t('tasks.linkCopied'))
    } catch {
      toast.error(t('tasks.copyLinkFailed'))
    }
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

// Export to PDF (browser print)
function exportPdf() {
  showActionMenu.value = false
  window.print()
}

// Delete task
const showDeleteConfirm = ref(false)
const deleting = ref(false)

async function confirmDelete() {
  if (!task.value) return
  deleting.value = true
  const result = await tasksStore.deleteTask(task.value.id)
  deleting.value = false
  if (result.ok) {
    showDeleteConfirm.value = false
    toast.success(t('tasks.taskDeleted'))
    router.push('/app/tasks')
  } else {
    toast.error(result.error ?? t('tasks.deleteFailed'))
  }
}

// ---------------------------------------------------------------------------
// Description HTML inline editor
// ---------------------------------------------------------------------------
const editingDescription = ref(false)
const editDescHtml = ref('')
const descSaving = ref(false)

function startEditDescription() {
  if (!task.value) return
  editDescHtml.value = task.value.description_html
  editingDescription.value = true
}

async function saveDescription() {
  if (!task.value) return
  descSaving.value = true
  const result = await tasksStore.updateTask(task.value.id, { description_html: editDescHtml.value })
  descSaving.value = false
  if (result.ok && result.data) {
    task.value = result.data
    editingDescription.value = false
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

function cancelEditDescription() {
  editingDescription.value = false
}

// ---------------------------------------------------------------------------
// Complete task
// ---------------------------------------------------------------------------
const completing = ref(false)

async function completeTask() {
  if (!task.value || task.value.is_completed) return
  completing.value = true
  const result = await tasksStore.completeTask(task.value.id)
  completing.value = false
  if (result.ok) {
    toast.success(t('tasks.taskCompleted'))
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.completeFailed'))
  }
}

// ---------------------------------------------------------------------------
// PR4: outcome prompt for calendar-bound tasks (kind=call/meeting)
// ---------------------------------------------------------------------------
const showOutcomeModal = ref(false)

/**
 * True iff the auto-expire job has already prompted us for the outcome of
 * this calendar task and the user hasn't resolved it yet (held / rescheduled
 * / no_show). Drives both the inline banner and the "Log outcome" CTA.
 */
const needsOutcome = computed(() => {
  const tt = task.value
  if (!tt) return false
  if (tt.is_completed || tt.is_archived) return false
  if (tt.status === 'expired' || tt.status === 'done' || tt.status === 'cancelled') return false
  if (!tt.outcome_prompted_at) return false
  return tt.kind === 'call' || tt.kind === 'meeting'
})

function openOutcomeModal() {
  if (!task.value) return
  showOutcomeModal.value = true
}

async function onOutcomeResolved() {
  // Refresh from API so timeline + counters reflect the new state.
  await loadTask()
}

// ---------------------------------------------------------------------------
// Phase 3: Subtasks
// ---------------------------------------------------------------------------
const subtasks = ref<TaskOut[]>([])
const subtasksLoading = ref(false)
const showAddSubtaskDropdown = ref(false)
const showNewSubtaskForm = ref(false)
const newSubtaskTitle = ref('')
const newSubtaskAssigneeId = ref('')
const newSubtaskPriority = ref('medium')
const subtaskSubmitting = ref(false)

async function loadSubtasks() {
  if (!taskId.value) return
  subtasksLoading.value = true
  const result = await tasksStore.fetchSubtasks(taskId.value)
  subtasksLoading.value = false
  if (result.ok && result.data) subtasks.value = result.data
}

async function submitNewSubtask() {
  if (!newSubtaskTitle.value.trim()) return
  subtaskSubmitting.value = true
  const result = await tasksStore.createSubtask(taskId.value, {
    title: newSubtaskTitle.value.trim(),
    assigned_to_id: newSubtaskAssigneeId.value || null,
    priority: newSubtaskPriority.value,
  })
  subtaskSubmitting.value = false
  if (result.ok && result.data) {
    subtasks.value.push(result.data)
    newSubtaskTitle.value = ''
    newSubtaskAssigneeId.value = ''
    newSubtaskPriority.value = 'medium'
    showNewSubtaskForm.value = false
    showAddSubtaskDropdown.value = false
    toast.success(t('tasks.subtaskCreated'))
    // Reload task to refresh counters
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.subtaskCreateFailed'))
  }
}

async function completeSubtask(subtask: TaskOut) {
  if (subtask.is_completed) return
  const result = await tasksStore.completeTask(subtask.id)
  if (result.ok) {
    await loadSubtasks()
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.completeFailed'))
  }
}

// ---------------------------------------------------------------------------
// Phase 3: Checklist
// ---------------------------------------------------------------------------
const checklistItems = ref<ChecklistItemOut[]>([])
const checklistLoading = ref(false)
const newChecklistText = ref('')
const checklistSubmitting = ref(false)

async function loadChecklist() {
  if (!taskId.value) return
  checklistLoading.value = true
  const result = await tasksStore.fetchChecklist(taskId.value)
  checklistLoading.value = false
  if (result.ok && result.data) checklistItems.value = result.data
}

async function addChecklistItem() {
  if (!newChecklistText.value.trim()) return
  checklistSubmitting.value = true
  const result = await tasksStore.createChecklistItem(taskId.value, {
    text: newChecklistText.value.trim(),
    position: checklistItems.value.length,
  })
  checklistSubmitting.value = false
  if (result.ok && result.data) {
    checklistItems.value.push(result.data)
    newChecklistText.value = ''
    toast.success(t('tasks.checklistItemCreated'))
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.checklistItemCreateFailed'))
  }
}

async function toggleChecklistItem(item: ChecklistItemOut) {
  const result = await tasksStore.updateChecklistItem(taskId.value, item.id, {
    is_checked: !item.is_checked,
  })
  if (result.ok && result.data) {
    const idx = checklistItems.value.findIndex((i) => i.id === item.id)
    if (idx !== -1) checklistItems.value[idx] = result.data
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.checklistItemUpdateFailed'))
  }
}

async function deleteChecklistItem(itemId: string) {
  const result = await tasksStore.deleteChecklistItem(taskId.value, itemId)
  if (result.ok) {
    checklistItems.value = checklistItems.value.filter((i) => i.id !== itemId)
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.checklistItemDeleteFailed'))
  }
}

// ---------------------------------------------------------------------------
// Phase 3: Dependencies
// ---------------------------------------------------------------------------
const dependencies = ref<TaskDependencyOut[]>([])
const dependenciesLoading = ref(false)
const showAddDepForm = ref(false)
const depSearchQuery = ref('')
const depSearchResults = ref<TaskOut[]>([])
const depSearchLoading = ref(false)
const selectedDepTaskId = ref('')
const selectedDepType = ref<'blocks' | 'related_to'>('blocks')
const depSubmitting = ref(false)

async function loadDependencies() {
  if (!taskId.value) return
  dependenciesLoading.value = true
  const result = await tasksStore.fetchDependencies(taskId.value)
  dependenciesLoading.value = false
  if (result.ok && result.data) dependencies.value = result.data
}

const blocksOthers = computed(() =>
  dependencies.value.filter((d) => d.type === 'blocks' && d.from_task_id === taskId.value)
)
const blockedBy = computed(() =>
  dependencies.value.filter((d) => d.type === 'blocks' && d.to_task_id === taskId.value)
)
const relatedTo = computed(() =>
  dependencies.value.filter((d) => d.type === 'related_to')
)

let depSearchTimer: ReturnType<typeof setTimeout> | null = null

async function searchTasksForDep() {
  if (!depSearchQuery.value.trim() || depSearchQuery.value.length < 2) {
    depSearchResults.value = []
    return
  }
  if (depSearchTimer) clearTimeout(depSearchTimer)
  depSearchTimer = setTimeout(async () => {
    depSearchLoading.value = true
    const res = await api.get<TaskOut[]>(`/api/v1/crm/tasks?page_size=20`)
    depSearchLoading.value = false
    if (res.ok && res.data) {
      const q = depSearchQuery.value.toLowerCase()
      depSearchResults.value = (res.data as TaskOut[]).filter(
        (t) => t.id !== taskId.value && t.title.toLowerCase().includes(q)
      )
    }
  }, 300)
}

async function submitDependency() {
  if (!selectedDepTaskId.value) return
  depSubmitting.value = true
  const result = await tasksStore.createDependency(taskId.value, {
    to_task_id: selectedDepTaskId.value,
    type: selectedDepType.value,
  })
  depSubmitting.value = false
  if (result.ok) {
    await loadDependencies()
    showAddDepForm.value = false
    selectedDepTaskId.value = ''
    depSearchQuery.value = ''
    depSearchResults.value = []
    toast.success(t('tasks.dependencyCreated'))
  } else {
    toast.error(result.error ?? t('tasks.dependencyCreateFailed'))
  }
}

async function removeDependency(depId: string) {
  const result = await tasksStore.deleteDependency(taskId.value, depId)
  if (result.ok) {
    dependencies.value = dependencies.value.filter((d) => d.id !== depId)
  } else {
    toast.error(result.error ?? t('tasks.dependencyDeleteFailed'))
  }
}

// ---------------------------------------------------------------------------
// Activity timeline (unified ActivityTimeline component)
// ---------------------------------------------------------------------------
const activityTimelineRef = ref<InstanceType<typeof ActivityTimeline> | null>(null)
function reloadTimeline() { activityTimelineRef.value?.load() }

// ---------------------------------------------------------------------------
// Phase 6: Time Tracking
// ---------------------------------------------------------------------------
const timeLogs = ref<TaskTimeLogOut[]>([])
const timeLogsLoading = ref(false)
const activeTimer = ref<TaskTimerOut | null>(null)
const timerTick = ref(0)   // incremented every second while timer runs
let timerInterval: ReturnType<typeof setInterval> | null = null

// Manual log form
const showLogForm = ref(false)
const logFormMinutes = ref<number | null>(null)
const logFormDescription = ref('')
const logFormDate = ref('')
const logFormSubmitting = ref(false)

// Estimate edit
const showEstimateEdit = ref(false)
const estimateHours = ref<number | null>(null)
const estimateMinutes = ref<number | null>(null)
const estimateSaving = ref(false)

// Timer start/stop
const timerActionLoading = ref(false)

function formatMinutesHuman(mins: number): string {
  if (!mins) return '0 min'
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h === 0) return `${m} min`
  if (m === 0) return `${h} h`
  return `${h} h ${m} min`
}

function elapsedFromTimer(timer: TaskTimerOut | null): number {
  // Returns elapsed seconds (updated reactively via timerTick)
  if (!timer || !timer.is_running) return 0
  void timerTick.value  // reactive dependency
  return Math.floor((Date.now() - new Date(timer.started_at).getTime()) / 1000)
}

function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

function startTickInterval() {
  if (timerInterval) return
  timerInterval = setInterval(() => { timerTick.value++ }, 1000)
}

function stopTickInterval() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null }
}

async function loadTimeLogs() {
  timeLogsLoading.value = true
  const result = await tasksStore.fetchTimeLogs(taskId.value)
  timeLogsLoading.value = false
  if (result.ok && result.data) timeLogs.value = result.data
}

async function loadActiveTimer() {
  const result = await tasksStore.getActiveTimer(taskId.value)
  if (result.ok) {
    activeTimer.value = result.data ?? null
    if (activeTimer.value?.is_running) {
      startTickInterval()
    } else {
      stopTickInterval()
    }
  }
}

async function handleStartTimer() {
  timerActionLoading.value = true
  const result = await tasksStore.startTimer(taskId.value)
  timerActionLoading.value = false
  if (result.ok && result.data) {
    activeTimer.value = result.data
    timerTick.value = 0
    startTickInterval()
    // Update task to reflect my_active_timer_started_at
    await loadTask()
    toast.success(t('tasks.timerStarted'))
  } else {
    toast.error(result.error ?? t('tasks.timerStartFailed'))
  }
}

async function handleStopTimer() {
  timerActionLoading.value = true
  const result = await tasksStore.stopTimer(taskId.value)
  timerActionLoading.value = false
  if (result.ok) {
    stopTickInterval()
    activeTimer.value = null
    await Promise.all([loadTimeLogs(), loadTask(), reloadTimeline()])
    toast.success(t('tasks.timerStopped'))
  } else {
    toast.error(result.error ?? t('tasks.timerStopFailed'))
  }
}

function openLogForm() {
  const now = new Date()
  logFormDate.value = now.toISOString().split('T')[0] ?? ''
  logFormMinutes.value = null
  logFormDescription.value = ''
  showLogForm.value = true
}

async function submitLogForm() {
  const mins = Number(logFormMinutes.value)
  if (!mins || mins <= 0) {
    toast.error(t('tasks.durationMinutes') + ' > 0')
    return
  }
  logFormSubmitting.value = true
  const loggedAt = logFormDate.value
    ? new Date(logFormDate.value + 'T12:00:00').toISOString()
    : new Date().toISOString()
  const result = await tasksStore.createTimeLog(taskId.value, {
    duration_minutes: mins,
    description: logFormDescription.value,
    logged_at: loggedAt,
  })
  logFormSubmitting.value = false
  if (result.ok && result.data) {
    timeLogs.value.unshift(result.data)
    showLogForm.value = false
    logFormMinutes.value = null
    logFormDescription.value = ''
    await Promise.all([loadTask(), reloadTimeline()])
    toast.success(t('tasks.logTime'))
  } else {
    toast.error(result.error ?? t('tasks.logTimeFailed'))
  }
}

async function removeTimeLog(logId: string) {
  const result = await tasksStore.deleteTimeLog(taskId.value, logId)
  if (result.ok) {
    timeLogs.value = timeLogs.value.filter((l) => l.id !== logId)
    await loadTask()
    toast.success(t('tasks.timeLogDeleted'))
  } else {
    toast.error(result.error ?? t('tasks.timeLogDeleteFailed'))
  }
}

function openEstimateEdit() {
  if (!task.value) return
  const total = task.value.estimated_minutes ?? 0
  estimateHours.value = Math.floor(total / 60) || null
  estimateMinutes.value = total % 60 || null
  showEstimateEdit.value = true
}

async function saveEstimate() {
  const totalMins = (Number(estimateHours.value || 0) * 60) + Number(estimateMinutes.value || 0)
  estimateSaving.value = true
  const result = totalMins > 0
    ? await tasksStore.updateTask(taskId.value, { estimated_minutes: totalMins })
    : await tasksStore.updateTask(taskId.value, { clear_estimated_minutes: true })
  estimateSaving.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showEstimateEdit.value = false
    toast.success(t('tasks.estimateSaved'))
  } else {
    toast.error(result.error ?? t('tasks.estimateSaveFailed'))
  }
}

const timePercent = computed(() => {
  if (!task.value || !task.value.estimated_minutes) return null
  return Math.min(100, Math.round((task.value.total_logged_minutes / task.value.estimated_minutes) * 100))
})

const estimateButtonLabel = computed(() => {
  if (!task.value?.estimated_minutes) return t('tasks.setEstimate')
  return `${t('tasks.estimate')}: ${formatMinutesHuman(task.value.estimated_minutes)}`
})

// ---------------------------------------------------------------------------
// Phase 7: Recurrence
// ---------------------------------------------------------------------------
const showRecurrenceModal = ref(false)
const recurrenceType = ref('daily')
const recurrenceInterval = ref(1)
const recurrenceDayOfWeek = ref<number[]>([])
const recurrenceEndsAt = ref('')
const recurrenceSaving = ref(false)

function openRecurrenceModal() {
  if (!task.value) return
  const rec = task.value.recurrence
  if (rec) {
    recurrenceType.value = String(rec.type ?? 'daily')
    recurrenceInterval.value = Number(rec.interval ?? 1)
    recurrenceDayOfWeek.value = Array.isArray(rec.day_of_week) ? rec.day_of_week.map(Number) : []
    recurrenceEndsAt.value = rec.ends_at ? (String(rec.ends_at).split('T')[0] ?? '') : ''
  } else {
    recurrenceType.value = 'daily'
    recurrenceInterval.value = 1
    recurrenceDayOfWeek.value = []
    recurrenceEndsAt.value = ''
  }
  showRecurrenceModal.value = true
}

function toggleRecurrenceDow(day: number) {
  const idx = recurrenceDayOfWeek.value.indexOf(day)
  if (idx !== -1) recurrenceDayOfWeek.value.splice(idx, 1)
  else recurrenceDayOfWeek.value.push(day)
}

async function saveRecurrence() {
  if (!task.value) return
  recurrenceSaving.value = true
  const recurrencePayload = {
    type: recurrenceType.value,
    interval: recurrenceInterval.value,
    ...(recurrenceType.value === 'weekly' && recurrenceDayOfWeek.value.length > 0
      ? { day_of_week: recurrenceDayOfWeek.value }
      : {}),
    ...(recurrenceEndsAt.value ? { ends_at: new Date(recurrenceEndsAt.value).toISOString() } : { ends_at: null }),
  }
  const result = await tasksStore.updateTask(task.value.id, { recurrence: recurrencePayload })
  recurrenceSaving.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showRecurrenceModal.value = false
    toast.success(t('tasks.recurrenceSaved'))
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

async function clearRecurrence() {
  if (!task.value) return
  recurrenceSaving.value = true
  const result = await tasksStore.updateTask(task.value.id, { clear_recurrence: true })
  recurrenceSaving.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showRecurrenceModal.value = false
    toast.success(t('tasks.recurrenceCleared'))
  } else {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
}

function recurrenceLabel(rec: Record<string, unknown> | null): string {
  if (!rec) return t('tasks.noRecurrence')
  const type = String(rec.type ?? '')
  const interval = Number(rec.interval ?? 1)
  const labelMap: Record<string, string> = {
    daily: t('tasks.recurrenceDaily'),
    weekly: t('tasks.recurrenceWeekly'),
    monthly: t('tasks.recurrenceMonthly'),
    custom: t('tasks.recurrenceCustom'),
  }
  const base = labelMap[type] ?? type
  if (interval > 1) return `${t('tasks.recurrenceEvery')} ${interval} ${base.toLowerCase()}`
  return base
}

// ---------------------------------------------------------------------------
// Phase 7: Approval
// ---------------------------------------------------------------------------
const showApprovalRequestModal = ref(false)
const approvalRequestApproverId = ref('')
const approvalRequestSubmitting = ref(false)
const showApprovalRejectModal = ref(false)
const approvalRejectNote = ref('')
const approvalRejectSubmitting = ref(false)
const approvalActionLoading = ref(false)

async function submitApprovalRequest() {
  if (!task.value || !approvalRequestApproverId.value) return
  approvalRequestSubmitting.value = true
  const result = await tasksStore.requestApproval(task.value.id, approvalRequestApproverId.value)
  approvalRequestSubmitting.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showApprovalRequestModal.value = false
    toast.success(t('tasks.approvalRequested'))
  } else {
    toast.error(result.error ?? t('tasks.approvalRequestFailed'))
  }
}

async function handleApproveTask() {
  if (!task.value) return
  approvalActionLoading.value = true
  const result = await tasksStore.approveTask(task.value.id)
  approvalActionLoading.value = false
  if (result.ok && result.data) {
    task.value = result.data
    toast.success(t('tasks.taskApproved'))
  } else {
    toast.error(result.error ?? t('tasks.approveFailed'))
  }
}

async function submitReject() {
  if (!task.value) return
  approvalRejectSubmitting.value = true
  const result = await tasksStore.rejectTask(task.value.id, approvalRejectNote.value)
  approvalRejectSubmitting.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showApprovalRejectModal.value = false
    approvalRejectNote.value = ''
    toast.success(t('tasks.taskRejected'))
  } else {
    toast.error(result.error ?? t('tasks.rejectFailed'))
  }
}

const approvalStatusColor = computed(() => {
  if (!task.value) return ''
  const map: Record<string, string> = {
    none: 'text-gray-400',
    pending: 'text-yellow-600 dark:text-yellow-400',
    approved: 'text-green-600 dark:text-green-400',
    rejected: 'text-red-600 dark:text-red-400',
  }
  return map[task.value.approval_status] ?? 'text-gray-400'
})

const approvalStatusIcon = computed(() => {
  const map: Record<string, string> = {
    none: '○',
    pending: '⏳',
    approved: '✅',
    rejected: '❌',
  }
  return map[task.value?.approval_status ?? 'none'] ?? '○'
})

// ---------------------------------------------------------------------------
// Phase 8: Custom Fields
// ---------------------------------------------------------------------------
const customFields = ref<TaskOut['custom_fields']>([])

function loadCustomFieldsFromTask() {
  if (task.value) {
    customFields.value = task.value.custom_fields ?? []
  }
}

watch(task, loadCustomFieldsFromTask, { immediate: true })

const savingCustomFieldId = ref<string | null>(null)

async function saveCustomFieldValue(fieldId: string, newValue: unknown) {
  if (!task.value) return
  savingCustomFieldId.value = fieldId
  const cf = customFields.value.find((f) => f.field_id === fieldId)
  if (!cf) { savingCustomFieldId.value = null; return }

  const valueIn: TaskCustomFieldValueIn = { field_id: fieldId }
  if (cf.field_type === 'text' || cf.field_type === 'dropdown' || cf.field_type === 'url') {
    valueIn.value_text = String(newValue ?? '')
  } else if (cf.field_type === 'number') {
    valueIn.value_number = (newValue !== '' && newValue !== null && newValue !== undefined) ? Number(newValue) : null
  } else if (cf.field_type === 'date') {
    valueIn.value_date = newValue ? String(newValue) : null
  } else if (cf.field_type === 'checkbox') {
    valueIn.value_bool = Boolean(newValue)
  }

  const result = await tasksStore.upsertTaskCustomFields(task.value.id, [valueIn])
  if (result.ok && result.data) {
    task.value = result.data
    customFields.value = result.data.custom_fields ?? []
  } else if (!result.ok) {
    toast.error(result.error ?? t('tasks.updateFailed'))
  }
  savingCustomFieldId.value = null
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
onMounted(async () => {
  await Promise.all([loadMembers(), loadLeads(), loadTask(), loadSubtasks(), loadChecklist(), loadDependencies(), loadTimeLogs(), loadActiveTimer()])
})

onUnmounted(() => {
  stopTickInterval()
})
</script>

<template>
  <div class="p-6">
    <!-- Back button -->
    <button
      class="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 mb-4 flex items-center gap-1"
      @click="router.push('/app/tasks')"
    >
      ← {{ t('tasks.backToTasks') }}
    </button>

    <!-- Loading -->
    <div v-if="taskLoading" class="space-y-4 animate-pulse">
      <div class="h-8 bg-gray-200 dark:bg-gray-700 rounded-xl w-2/3" />
      <div class="h-4 bg-gray-100 dark:bg-gray-800 rounded-xl w-1/2" />
    </div>

    <!-- Error -->
    <div v-else-if="taskError" class="text-red-500 text-sm py-8 text-center">{{ taskError }}</div>

    <!-- Content -->
    <template v-else-if="task">
      <!-- ===================== TASK HEADER ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">

        <!-- Breadcrumb -->
        <nav class="flex items-center gap-1.5 text-xs text-gray-400 mb-3">
          <span>{{ t('tasks.title') }}</span>
          <span>›</span>
          <template v-if="task.lead_id">
            <RouterLink :to="`/app/opportunities/${task.lead_id}`" class="hover:text-blue-500 truncate max-w-[160px]">
              {{ task.lead_title || task.lead_id }}
            </RouterLink>
            <span>›</span>
          </template>
          <template v-else-if="task.customer_id">
            <RouterLink :to="`/app/directory/${task.customer_id}`" class="hover:text-blue-500 truncate max-w-[160px]">
              {{ task.customer_name || task.customer_id }}
            </RouterLink>
            <span>›</span>
          </template>
          <template v-else-if="task.proposal_id">
            <span class="truncate max-w-[160px]">{{ task.proposal_title || task.proposal_id }}</span>
            <span>›</span>
          </template>
          <template v-else>
            <span>{{ t('tasks.standalone') }}</span>
            <span>›</span>
          </template>
          <!-- Parent task breadcrumb -->
          <template v-if="task.parent_task_id">
            <RouterLink
              :to="`/app/tasks/${task.parent_task_id}`"
              class="hover:text-blue-500 truncate max-w-[200px]"
            >
              {{ task.parent_task_title || task.parent_task_id }}
            </RouterLink>
            <span>›</span>
          </template>
          <span class="text-gray-600 dark:text-gray-300 truncate max-w-[200px]">{{ task.title }}</span>
        </nav>

        <!-- Metadata bar -->
        <div class="flex flex-wrap gap-3 text-xs text-gray-400 dark:text-gray-500 mb-4 pb-3 border-b border-gray-100 dark:border-gray-700">
          <span v-if="task.created_by_name">
            {{ t('tasks.createdBy') }} <span class="font-medium text-gray-600 dark:text-gray-300">{{ task.created_by_name }}</span>
            {{ formatDate(task.created_at) }}
          </span>
          <span v-if="task.is_completed && task.completed_by_name" class="flex items-center gap-1">
            <span class="text-green-500">✓</span>
            {{ t('tasks.completedBy') }} <span class="font-medium text-gray-600 dark:text-gray-300">{{ task.completed_by_name }}</span>
            {{ formatDate(task.completed_at) }}
          </span>
          <span v-if="task.is_pinned" class="text-yellow-500">📌 {{ t('tasks.pinned') }}</span>
          <span v-if="task.is_archived" class="text-gray-400">🗄 {{ t('tasks.archived') }}</span>
        </div>

        <!-- PR4: outcome prompt banner for calendar tasks -->
        <div
          v-if="needsOutcome"
          class="rounded-2xl border border-amber-200 dark:border-amber-700/50 bg-amber-50 dark:bg-amber-900/20 px-4 py-3 mb-4 flex items-start gap-3"
          role="status"
        >
          <span class="text-2xl flex-shrink-0" aria-hidden="true">⏰</span>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-semibold text-amber-800 dark:text-amber-300">
              {{ t('taskOutcome.headerPicker') }}
            </p>
            <p class="text-xs text-amber-700/90 dark:text-amber-400/80 mt-0.5">
              {{ t('taskOutcome.prompt') }}
            </p>
          </div>
          <button
            class="flex-shrink-0 inline-flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-2 rounded-xl transition-colors"
            @click="openOutcomeModal"
          >
            {{ t('calendar.logOutcome') }}
          </button>
        </div>

        <div class="flex items-start gap-4">
          <!-- Completion checkbox -->
          <button
            class="w-6 h-6 rounded border flex-shrink-0 flex items-center justify-center transition-colors mt-0.5"
            :class="task.is_completed
              ? 'bg-blue-500 border-blue-500 text-white cursor-default'
              : 'border-gray-300 hover:border-blue-400'"
            :disabled="task.is_completed || completing"
            :title="task.is_completed ? '' : t('tasks.complete')"
            @click="!task.is_completed && completeTask()"
          >
            <span v-if="task.is_completed" class="text-sm">✓</span>
          </button>

          <div class="flex-1 min-w-0">
            <!-- Title row (inline editable) -->
            <div class="flex items-start justify-between gap-3">
              <!-- Inline title edit -->
              <div class="flex-1 min-w-0">
                <div v-if="editingTitle" class="flex items-center gap-2">
                  <input
                    ref="titleInputRef"
                    v-model="inlineTitle"
                    type="text"
                    class="flex-1 text-xl font-bold bg-transparent border-b-2 border-blue-400 outline-none text-gray-900 dark:text-gray-100 py-0.5"
                    @keydown.enter="saveInlineTitle"
                    @keydown.escape="cancelInlineEditTitle"
                    @blur="saveInlineTitle"
                  />
                  <span v-if="titleSaving" class="text-xs text-gray-400">…</span>
                </div>
                <h1
                  v-else
                  class="text-xl font-bold text-gray-900 dark:text-gray-100 cursor-text"
                  :class="task.is_completed ? 'line-through text-gray-400' : ''"
                  :title="task.is_completed ? '' : t('tasks.clickToEdit')"
                  @click="startInlineEditTitle"
                >
                  {{ task.title }}
                </h1>
              </div>

              <!-- Action buttons -->
              <div class="flex gap-2 flex-shrink-0 items-center">
                <!-- Favourite -->
                <button
                  class="text-lg leading-none transition-colors"
                  :class="task.is_favourite ? 'text-yellow-400' : 'text-gray-300 hover:text-yellow-400'"
                  :title="task.is_favourite ? t('tasks.unfavourite') : t('tasks.favourite')"
                  :disabled="togglingFavourite"
                  @click="toggleFavourite"
                >⭐</button>

                <button
                  v-if="!task.is_completed"
                  class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                  @click="openEditTask"
                >
                  {{ t('tasks.edit') }}
                </button>
                <button
                  v-if="!task.is_completed"
                  class="px-3 py-1.5 rounded-xl border border-green-200 text-xs text-green-600 hover:bg-green-50"
                  :disabled="completing"
                  @click="completeTask"
                >
                  {{ completing ? '…' : t('tasks.complete') }}
                </button>
                <span v-if="task.is_completed" class="px-3 py-1.5 rounded-xl bg-green-50 text-xs text-green-600 font-medium">
                  ✓ {{ t('tasks.done') }}
                </span>

                <!-- Action menu -->
                <div class="relative">
                  <button
                    class="px-2.5 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                    :title="t('tasks.moreActions')"
                    @click.stop="showActionMenu = !showActionMenu"
                  >⋮</button>
                  <div
                    v-if="showActionMenu"
                    class="absolute right-0 top-full mt-1 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg z-30 min-w-[200px] py-1"
                  >
                    <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2" @click="togglePin">
                      <span>📌</span>
                      {{ task.is_pinned ? t('tasks.unpin') : t('tasks.pin') }}
                    </button>
                    <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2" @click="openCopyModal">
                      <span>📋</span> {{ t('tasks.copyTask') }}
                    </button>
                    <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2" @click="openMoveModal">
                      <span>↗️</span> {{ t('tasks.moveTask') }}
                    </button>
                    <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2" @click="toggleArchive">
                      <span>🗄</span> {{ task.is_archived ? t('tasks.unarchive') : t('tasks.archive') }}
                    </button>
                    <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2" @click="sharePublicLink">
                      <span>🔗</span> {{ t('tasks.sharePublicLink') }}
                    </button>
                    <button class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2" @click="exportPdf">
                      <span>📄</span> {{ t('tasks.exportPdf') }}
                    </button>
                    <div class="border-t border-gray-100 dark:border-gray-700 my-1" />
                    <button class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2" @click="showDeleteConfirm = true; showActionMenu = false">
                      <span>🗑</span> {{ t('tasks.deleteTask') }}
                    </button>
                  </div>
                  <!-- Click outside overlay -->
                  <div v-if="showActionMenu" class="fixed inset-0 z-20" @click="showActionMenu = false" />
                </div>
              </div>
            </div>

            <!-- Status / Priority / Tags row -->
            <div class="flex flex-wrap items-center gap-2 mt-2">
              <!-- Status badge -->
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="STATUS_COLORS[task.status] ?? STATUS_COLORS['todo']"
              >
                {{ STATUS_LABELS[task.status] ?? task.status }}
              </span>
              <!-- Priority badge -->
              <span
                v-if="task.priority && task.priority !== 'none'"
                class="inline-flex items-center gap-0.5 text-xs font-medium"
                :class="PRIORITY_COLORS[task.priority] ?? ''"
              >
                ⚠ {{ PRIORITY_LABELS[task.priority] ?? task.priority }}
              </span>
              <!-- Tags -->
              <span
                v-for="tag in task.tags"
                :key="tag"
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
              >
                🏷 {{ tag }}
              </span>
            </div>

            <!-- Meta grid -->
            <div class="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 text-xs text-gray-500 dark:text-gray-400">
              <!-- Lead (if linked) -->
              <div v-if="task.lead_id" class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.lead') }}</span>
                <RouterLink
                  :to="`/app/opportunities/${task.lead_id}`"
                  class="text-blue-500 hover:underline truncate"
                >
                  {{ task.lead_title || task.lead_id }}
                </RouterLink>
              </div>
              <!-- Customer (if linked) -->
              <div v-if="task.customer_id" class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.customer') }}</span>
                <RouterLink
                  :to="`/app/directory/${task.customer_id}`"
                  class="text-blue-500 hover:underline truncate"
                >
                  {{ task.customer_name || task.customer_id }}
                </RouterLink>
              </div>
              <!-- Proposal (if linked) -->
              <div v-if="task.proposal_id" class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.proposal') }}</span>
                <span class="truncate">{{ task.proposal_title || task.proposal_id }}</span>
              </div>
              <!-- Assignee -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.assignee') }}</span>
                <span>{{ task.assigned_to_name || t('tasks.noAssignee') }}</span>
              </div>
              <!-- Due date -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.deadline') }}</span>
                <span :class="isOverdue(task) ? 'text-red-500 font-semibold' : ''">
                  {{ formatDate(task.due_date) }}
                  <template v-if="task.due_date_end"> – {{ formatDate(task.due_date_end) }}</template>
                  <span v-if="isOverdue(task)">({{ t('tasks.overdue') }})</span>
                </span>
              </div>
              <!-- Watchers -->
              <div v-if="task.watcher_ids.length" class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.watchers') }}</span>
                <span>🔔 {{ task.watcher_ids.length }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===================== ADD SUBTASK BUTTON ===================== -->
      <div class="mb-4 relative">
        <div class="flex items-center gap-2">
          <button
            class="inline-flex items-center gap-1 px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors"
            @click="showAddSubtaskDropdown = !showAddSubtaskDropdown"
          >
            {{ t('tasks.addSubtask') }}
          </button>
        </div>
        <!-- Dropdown -->
        <div
          v-if="showAddSubtaskDropdown"
          class="absolute left-0 top-full mt-1 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg z-20 min-w-[180px]"
        >
          <button
            class="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-xl"
            @click="showNewSubtaskForm = true; showAddSubtaskDropdown = false"
          >
            {{ t('tasks.addEmptySubtask') }}
          </button>
        </div>
        <!-- Click outside to close -->
        <div
          v-if="showAddSubtaskDropdown"
          class="fixed inset-0 z-10"
          @click="showAddSubtaskDropdown = false"
        />
      </div>

      <!-- ===================== SUBTASKS ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          📋 {{ t('tasks.subtasks') }}
          <span v-if="task.subtask_count > 0" class="text-sm font-normal text-gray-400 ml-1">
            ({{ task.subtasks_completed }}/{{ task.subtask_count }})
          </span>
        </h2>

        <!-- Progress bar -->
        <div v-if="task.subtask_count > 0" class="mb-4">
          <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>{{ t('tasks.subtasksProgress').replace('{done}', String(task.subtasks_completed)).replace('{total}', String(task.subtask_count)) }}</span>
            <span>{{ Math.round((task.subtasks_completed / task.subtask_count) * 100) }}%</span>
          </div>
          <div class="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-green-500 rounded-full transition-all"
              :style="{ width: `${Math.round((task.subtasks_completed / task.subtask_count) * 100)}%` }"
            />
          </div>
        </div>

        <!-- Loading -->
        <div v-if="subtasksLoading" class="space-y-2 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-9 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <!-- Subtask list -->
        <div v-else-if="subtasks.length === 0 && !showNewSubtaskForm" class="text-sm text-gray-400 dark:text-gray-500">
          {{ t('tasks.noSubtasks') }}
        </div>

        <ul v-else class="space-y-2 mb-3">
          <li
            v-for="sub in subtasks"
            :key="sub.id"
            class="flex items-center gap-3 p-2.5 rounded-xl border border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 group"
          >
            <!-- Completion toggle -->
            <button
              class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors"
              :class="sub.is_completed
                ? 'bg-green-500 border-green-500 text-white cursor-default'
                : 'border-gray-300 hover:border-green-400'"
              :disabled="sub.is_completed"
              @click="!sub.is_completed && completeSubtask(sub)"
            >
              <span v-if="sub.is_completed" class="text-xs">✓</span>
            </button>

            <!-- Title + link -->
            <RouterLink
              :to="`/app/tasks/${sub.id}`"
              class="flex-1 text-sm text-gray-700 dark:text-gray-200 hover:text-blue-500 truncate"
              :class="sub.is_completed ? 'line-through text-gray-400' : ''"
            >
              {{ sub.title }}
            </RouterLink>

            <!-- Assignee + priority badge -->
            <div class="flex items-center gap-1.5 flex-shrink-0">
              <span
                v-if="sub.priority && sub.priority !== 'none'"
                class="text-xs px-1.5 py-0.5 rounded-full"
                :class="PRIORITY_COLORS[sub.priority] ?? ''"
              >⚠</span>
              <span v-if="sub.assigned_to_name" class="text-xs text-gray-400 truncate max-w-[80px]">
                {{ sub.assigned_to_name }}
              </span>
            </div>
          </li>
        </ul>

        <!-- New subtask inline form -->
        <div v-if="showNewSubtaskForm" class="border border-green-200 dark:border-green-800 rounded-xl p-3 space-y-2 mt-2">
          <input
            v-model="newSubtaskTitle"
            type="text"
            :placeholder="t('tasks.taskTitle')"
            class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-green-400"
            @keydown.enter="submitNewSubtask"
            @keydown.escape="showNewSubtaskForm = false"
          />
          <div class="flex gap-2 items-center">
            <select
              v-model="newSubtaskAssigneeId"
              class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-2 py-1.5 focus:outline-none focus:border-green-400"
            >
              <option value="">{{ t('tasks.noAssignee') }}</option>
              <option v-for="m in members" :key="m.user_id" :value="m.user_id">{{ memberLabel(m) }}</option>
            </select>
            <select
              v-model="newSubtaskPriority"
              class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-2 py-1.5 focus:outline-none focus:border-green-400"
            >
              <option value="none">{{ t('tasks.priorityNone') }}</option>
              <option value="low">{{ t('tasks.priorityLow') }}</option>
              <option value="medium">{{ t('tasks.priorityMedium') }}</option>
              <option value="high">{{ t('tasks.priorityHigh') }}</option>
              <option value="critical">{{ t('tasks.priorityCritical') }}</option>
            </select>
          </div>
          <div class="flex justify-end gap-2">
            <button
              class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50"
              @click="showNewSubtaskForm = false; newSubtaskTitle = ''"
            >{{ t('tasks.cancel') }}</button>
            <button
              :disabled="subtaskSubmitting || !newSubtaskTitle.trim()"
              class="px-3 py-1.5 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50"
              @click="submitNewSubtask"
            >{{ subtaskSubmitting ? '…' : t('tasks.create') }}</button>
          </div>
        </div>
      </div>

      <!-- ===================== CHECKLIST ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          ☑️ {{ t('tasks.checklist') }}
          <span v-if="task.checklist_count > 0" class="text-sm font-normal text-gray-400 ml-1">
            ({{ task.checklist_checked }}/{{ task.checklist_count }})
          </span>
        </h2>

        <!-- Progress bar -->
        <div v-if="task.checklist_count > 0" class="mb-4">
          <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
            <span>{{ t('tasks.checklistProgress').replace('{done}', String(task.checklist_checked)).replace('{total}', String(task.checklist_count)) }}</span>
            <span>{{ Math.round((task.checklist_checked / task.checklist_count) * 100) }}%</span>
          </div>
          <div class="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full bg-blue-500 rounded-full transition-all"
              :style="{ width: `${Math.round((task.checklist_checked / task.checklist_count) * 100)}%` }"
            />
          </div>
        </div>

        <!-- Loading -->
        <div v-if="checklistLoading" class="space-y-2 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-8 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <!-- Checklist items -->
        <div v-else>
          <div v-if="checklistItems.length === 0" class="text-sm text-gray-400 dark:text-gray-500 mb-3">
            {{ t('tasks.noChecklist') }}
          </div>
          <ul v-else class="space-y-1.5 mb-3">
            <li
              v-for="item in checklistItems"
              :key="item.id"
              class="flex items-center gap-2.5 group"
            >
              <button
                class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors"
                :class="item.is_checked
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'border-gray-300 hover:border-blue-400'"
                @click="toggleChecklistItem(item)"
              >
                <span v-if="item.is_checked" class="text-xs">✓</span>
              </button>
              <span
                class="flex-1 text-sm text-gray-700 dark:text-gray-200"
                :class="item.is_checked ? 'line-through text-gray-400' : ''"
              >{{ item.text }}</span>
              <button
                class="text-xs text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
                @click="deleteChecklistItem(item.id)"
              >🗑</button>
            </li>
          </ul>

          <!-- Add new item input -->
          <div class="flex items-center gap-2">
            <input
              v-model="newChecklistText"
              type="text"
              :placeholder="t('tasks.checklistPlaceholder')"
              class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
              @keydown.enter="addChecklistItem"
            />
            <button
              :disabled="checklistSubmitting || !newChecklistText.trim()"
              class="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
              @click="addChecklistItem"
            >{{ checklistSubmitting ? '…' : '+' }}</button>
          </div>
        </div>
      </div>

      <!-- ===================== ZÁVISLOSTI ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">
            🔗 {{ t('tasks.dependencies') }}
          </h2>
          <button
            class="text-xs text-blue-500 hover:text-blue-600 font-medium"
            @click="showAddDepForm = !showAddDepForm"
          >{{ t('tasks.addDependency') }}</button>
        </div>

        <!-- Loading -->
        <div v-if="dependenciesLoading" class="space-y-2 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-8 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <div v-else>
          <!-- No deps -->
          <div
            v-if="dependencies.length === 0 && !showAddDepForm"
            class="text-sm text-gray-400 dark:text-gray-500"
          >
            {{ t('tasks.noDependencies') }}
          </div>

          <!-- Blocks others -->
          <div v-if="blocksOthers.length" class="mb-3">
            <p class="text-xs font-semibold text-orange-600 dark:text-orange-400 uppercase tracking-wide mb-1.5">
              🚫 {{ t('tasks.dependencyBlocks') }}
            </p>
            <ul class="space-y-1.5">
              <li
                v-for="dep in blocksOthers"
                :key="dep.id"
                class="flex items-center gap-2 group"
              >
                <RouterLink
                  :to="`/app/tasks/${dep.to_task_id}`"
                  class="flex-1 text-sm text-gray-700 dark:text-gray-200 hover:text-blue-500 truncate"
                >
                  {{ dep.to_task_title }}
                </RouterLink>
                <button
                  class="text-xs text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click="removeDependency(dep.id)"
                >✕</button>
              </li>
            </ul>
          </div>

          <!-- Blocked by -->
          <div v-if="blockedBy.length" class="mb-3">
            <p class="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-1.5">
              ⛔ {{ t('tasks.dependencyBlockedBy') }}
            </p>
            <ul class="space-y-1.5">
              <li
                v-for="dep in blockedBy"
                :key="dep.id"
                class="flex items-center gap-2 group"
              >
                <RouterLink
                  :to="`/app/tasks/${dep.from_task_id}`"
                  class="flex-1 text-sm text-gray-700 dark:text-gray-200 hover:text-blue-500 truncate"
                >
                  {{ dep.from_task_title }}
                </RouterLink>
                <button
                  class="text-xs text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click="removeDependency(dep.id)"
                >✕</button>
              </li>
            </ul>
          </div>

          <!-- Related to -->
          <div v-if="relatedTo.length" class="mb-3">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
              ↔ {{ t('tasks.dependencyRelatedTo') }}
            </p>
            <ul class="space-y-1.5">
              <li
                v-for="dep in relatedTo"
                :key="dep.id"
                class="flex items-center gap-2 group"
              >
                <RouterLink
                  :to="`/app/tasks/${dep.from_task_id === taskId ? dep.to_task_id : dep.from_task_id}`"
                  class="flex-1 text-sm text-gray-700 dark:text-gray-200 hover:text-blue-500 truncate"
                >
                  {{ dep.from_task_id === taskId ? dep.to_task_title : dep.from_task_title }}
                </RouterLink>
                <button
                  class="text-xs text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  @click="removeDependency(dep.id)"
                >✕</button>
              </li>
            </ul>
          </div>

          <!-- Add dependency form -->
          <div v-if="showAddDepForm" class="mt-3 border border-blue-200 dark:border-blue-800 rounded-xl p-3 space-y-2">
            <!-- Type selector -->
            <div class="flex gap-2">
              <button
                class="flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors"
                :class="selectedDepType === 'blocks'
                  ? 'bg-orange-100 border-orange-400 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
                @click="selectedDepType = 'blocks'"
              >🚫 {{ t('tasks.dependencyTypeBlocks') }}</button>
              <button
                class="flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors"
                :class="selectedDepType === 'related_to'
                  ? 'bg-blue-100 border-blue-400 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
                @click="selectedDepType = 'related_to'"
              >↔ {{ t('tasks.dependencyTypeRelatedTo') }}</button>
            </div>

            <!-- Task search -->
            <div class="relative">
              <input
                v-model="depSearchQuery"
                type="text"
                :placeholder="t('tasks.selectTask')"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
                @input="searchTasksForDep"
              />
              <div
                v-if="depSearchResults.length"
                class="absolute left-0 top-full mt-1 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg z-20 w-full max-h-48 overflow-y-auto"
              >
                <button
                  v-for="searchTask in depSearchResults"
                  :key="searchTask.id"
                  class="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  @click="selectedDepTaskId = searchTask.id; depSearchQuery = searchTask.title; depSearchResults = []"
                >
                  {{ searchTask.title }}
                </button>
              </div>
            </div>

            <div class="flex justify-end gap-2">
              <button
                class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50"
                @click="showAddDepForm = false; depSearchQuery = ''; selectedDepTaskId = ''"
              >{{ t('tasks.cancel') }}</button>
              <button
                :disabled="depSubmitting || !selectedDepTaskId"
                class="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
                @click="submitDependency"
              >{{ depSubmitting ? '…' : t('tasks.create') }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- ===================== TIME TRACKING ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <!-- Header -->
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            ⏱ {{ t('tasks.timeTracking') }}
          </h2>
          <div class="flex items-center gap-2">
            <!-- Estimate edit -->
            <button
              class="text-xs text-gray-500 dark:text-gray-400 hover:text-blue-500 px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-600 hover:border-blue-400 transition-colors"
              @click="openEstimateEdit"
            >
              {{ estimateButtonLabel }}
            </button>
          </div>
        </div>

        <!-- Progress bar (logged vs estimate) -->
        <div v-if="task!.estimated_minutes" class="mb-5">
          <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1.5">
            <span>
              <span class="font-medium text-gray-700 dark:text-gray-200">{{ formatMinutesHuman(task!.total_logged_minutes) }}</span>
              {{ ' ' + t('tasks.logged').toLowerCase() }}
            </span>
            <span class="text-gray-400">
              {{ t('tasks.timeProgress')
                  .replace('{logged}', formatMinutesHuman(task!.total_logged_minutes))
                  .replace('{estimated}', formatMinutesHuman(task!.estimated_minutes)) }}
              <span
                v-if="timePercent !== null"
                class="ml-1.5 font-semibold"
                :class="timePercent >= 100 ? 'text-red-500' : timePercent >= 80 ? 'text-orange-500' : 'text-green-600 dark:text-green-400'"
              >{{ timePercent }}%</span>
            </span>
          </div>
          <div class="w-full h-2.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500"
              :class="timePercent !== null && timePercent >= 100 ? 'bg-red-500' : timePercent !== null && timePercent >= 80 ? 'bg-orange-400' : 'bg-blue-500'"
              :style="{ width: `${Math.min(100, timePercent ?? 0)}%` }"
            />
          </div>
        </div>

        <!-- Summary row (no estimate) -->
        <div v-else-if="task!.total_logged_minutes > 0" class="mb-5 text-sm text-gray-500 dark:text-gray-400">
          {{ t('tasks.logged') }}: <span class="font-semibold text-gray-700 dark:text-gray-200">{{ formatMinutesHuman(task!.total_logged_minutes) }}</span>
        </div>

        <!-- ======= STOPWATCH WIDGET ======= -->
        <div
          class="flex items-center gap-4 p-4 rounded-xl mb-5 transition-all duration-300"
          :class="activeTimer?.is_running
            ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700'
            : 'bg-gray-50 dark:bg-gray-700/30 border border-gray-200 dark:border-gray-600'"
        >
          <!-- Elapsed time display -->
          <div class="flex-1 min-w-0">
            <div
              class="text-2xl font-mono font-bold tabular-nums tracking-wider transition-colors"
              :class="activeTimer?.is_running ? 'text-blue-600 dark:text-blue-400' : 'text-gray-400 dark:text-gray-500'"
            >
              {{ formatElapsed(elapsedFromTimer(activeTimer)) }}
            </div>
            <div class="text-xs mt-0.5 transition-colors" :class="activeTimer?.is_running ? 'text-blue-400 dark:text-blue-500' : 'text-gray-400'">
              {{ activeTimer?.is_running ? t('tasks.timerRunning') : t('tasks.elapsed') }}
            </div>
          </div>

          <!-- Start / Stop button -->
          <button
            :disabled="timerActionLoading"
            class="flex items-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 disabled:opacity-50 flex-shrink-0"
            :class="activeTimer?.is_running
              ? 'bg-red-500 hover:bg-red-600 text-white shadow-md shadow-red-200 dark:shadow-red-900/30'
              : 'bg-blue-500 hover:bg-blue-600 text-white shadow-md shadow-blue-200 dark:shadow-blue-900/30'"
            @click="activeTimer?.is_running ? handleStopTimer() : handleStartTimer()"
          >
            <span class="text-base">{{ activeTimer?.is_running ? '⏹' : '▶' }}</span>
            <span>{{ activeTimer?.is_running ? t('tasks.stopTimer') : t('tasks.startTimer') }}</span>
          </button>
        </div>

        <!-- ======= TIME LOG LIST ======= -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
              {{ t('tasks.logged') }}
              <span v-if="timeLogs.length" class="font-normal normal-case text-gray-400">({{ timeLogs.length }})</span>
            </span>
            <button
              class="text-xs px-3 py-1.5 rounded-lg bg-blue-500 text-white hover:bg-blue-600 font-medium transition-colors"
              @click="openLogForm"
            >
              + {{ t('tasks.logTimeManually') }}
            </button>
          </div>

          <!-- Manual log form (inline) -->
          <div
            v-if="showLogForm"
            class="mb-3 p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl border border-blue-200 dark:border-blue-700 space-y-3"
          >
            <div class="grid grid-cols-2 gap-3">
              <!-- Duration -->
              <div>
                <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('tasks.durationMinutes') }}</label>
                <input
                  v-model.number="logFormMinutes"
                  type="number"
                  min="1"
                  class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
                  :placeholder="t('tasks.minutesShort')"
                />
              </div>
              <!-- Date -->
              <div>
                <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('tasks.logDate') }}</label>
                <input
                  v-model="logFormDate"
                  type="date"
                  class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
                />
              </div>
            </div>
            <!-- Description -->
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('tasks.logDescription') }}</label>
              <input
                v-model="logFormDescription"
                type="text"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
                :placeholder="t('tasks.logDescription')"
              />
            </div>
            <div class="flex justify-end gap-2">
              <button
                class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                @click="showLogForm = false"
              >{{ t('tasks.cancelLog') }}</button>
              <button
                :disabled="logFormSubmitting || !logFormMinutes || logFormMinutes <= 0"
                class="px-4 py-1.5 rounded-lg bg-blue-500 text-white text-xs font-semibold hover:bg-blue-600 disabled:opacity-50"
                @click="submitLogForm"
              >{{ logFormSubmitting ? '…' : t('tasks.logTime') }}</button>
            </div>
          </div>

          <!-- Logs list -->
          <div v-if="timeLogsLoading" class="py-4 text-center text-xs text-gray-400 animate-pulse">…</div>
          <div v-else-if="timeLogs.length === 0" class="text-sm text-gray-400 dark:text-gray-500 py-2">
            {{ t('tasks.noTimeLogs') }}
          </div>
          <div v-else class="divide-y divide-gray-100 dark:divide-gray-700">
            <div
              v-for="log in timeLogs"
              :key="log.id"
              class="flex items-start justify-between py-2.5 group"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-semibold text-sm text-gray-800 dark:text-gray-100">
                    {{ formatMinutesHuman(log.duration_minutes) }}
                  </span>
                  <span class="text-xs text-gray-400">·</span>
                  <span class="text-xs text-gray-500 dark:text-gray-400">{{ log.user_name || '?' }}</span>
                  <span class="text-xs text-gray-400">·</span>
                  <span class="text-xs text-gray-400">{{ formatDate(log.logged_at) }}</span>
                </div>
                <p v-if="log.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">{{ log.description }}</p>
              </div>
              <button
                class="opacity-0 group-hover:opacity-100 transition-opacity ml-2 text-xs text-red-400 hover:text-red-600 flex-shrink-0 px-1.5 py-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20"
                :title="t('tasks.deleteTimeLog')"
                @click="removeTimeLog(log.id)"
              >🗑</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Estimate edit modal -->
      <div v-if="showEstimateEdit" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-600 p-6 w-full max-w-sm mx-4">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
            ⏱ {{ t('tasks.setEstimate') }}
          </h3>
          <div class="flex gap-3 mb-4">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('tasks.hoursShort') }}</label>
              <input
                v-model.number="estimateHours"
                type="number"
                min="0"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
                placeholder="0"
              />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('tasks.minutesShort') }}</label>
              <input
                v-model.number="estimateMinutes"
                type="number"
                min="0"
                max="59"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
                placeholder="0"
              />
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <button
              class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="showEstimateEdit = false"
            >{{ t('tasks.cancel') }}</button>
            <button
              :disabled="estimateSaving"
              class="px-4 py-2 rounded-xl bg-blue-500 text-white text-sm font-semibold hover:bg-blue-600 disabled:opacity-50"
              @click="saveEstimate"
            >{{ estimateSaving ? '…' : t('tasks.save') }}</button>
          </div>
        </div>
        <!-- Backdrop -->
        <div class="fixed inset-0 z-[-1]" @click="showEstimateEdit = false" />
      </div>

      <!-- ===================== PHASE 7: RECURRENCE ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            🔁 {{ t('tasks.recurrence') }}
          </h2>
          <button
            class="text-xs px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
            @click="openRecurrenceModal"
          >
            {{ task!.recurrence ? t('tasks.editRecurrence') : t('tasks.setRecurrence') }}
          </button>
        </div>

        <div v-if="task!.recurrence" class="flex items-center gap-3">
          <span class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/20 rounded-xl text-sm font-medium text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-700">
            🔁 {{ recurrenceLabel(task!.recurrence) }}
          </span>
          <span v-if="task!.recurrence_parent_id" class="text-xs text-gray-400 dark:text-gray-500">
            {{ t('tasks.recurrenceInstance') }}
            <RouterLink :to="`/app/tasks/${task!.recurrence_parent_id}`" class="text-blue-500 hover:underline ml-1">
              {{ t('tasks.viewParent') }}
            </RouterLink>
          </span>
          <span v-if="task!.recurrence?.ends_at" class="text-xs text-gray-400">
            · {{ t('tasks.recurrenceEndsAt') }}: {{ formatDate(String(task!.recurrence.ends_at)) }}
          </span>
        </div>
        <div v-else class="text-sm text-gray-400 dark:text-gray-500">
          {{ t('tasks.noRecurrence') }}
        </div>
      </div>

      <!-- ===================== PHASE 7: APPROVAL ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            ✅ {{ t('tasks.approval') }}
          </h2>
          <!-- Request approval button (only when not yet pending/approved) -->
          <button
            v-if="task!.approval_status === 'none' || task!.approval_status === 'rejected'"
            class="text-xs px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
            @click="showApprovalRequestModal = true; approvalRequestApproverId = ''"
          >
            {{ t('tasks.requestApproval') }}
          </button>
        </div>

        <!-- Status badge row -->
        <div class="flex flex-wrap items-center gap-3 mb-3">
          <span :class="['text-sm font-semibold', approvalStatusColor]">
            {{ approvalStatusIcon }} {{ t(`tasks.approvalStatus_${task!.approval_status}`) }}
          </span>
          <span v-if="task!.approval_requested_from_name" class="text-sm text-gray-500 dark:text-gray-400">
            → {{ task!.approval_requested_from_name }}
          </span>
        </div>

        <!-- Rejection note -->
        <div
          v-if="task!.approval_status === 'rejected' && task!.approval_note"
          class="mb-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-xl text-sm text-red-700 dark:text-red-300"
        >
          <span class="font-medium">{{ t('tasks.approvalNote') }}:</span> {{ task!.approval_note }}
        </div>

        <!-- Approve / Reject buttons (shown when pending) -->
        <div v-if="task!.approval_status === 'pending'" class="flex gap-3">
          <button
            :disabled="approvalActionLoading"
            class="px-4 py-2 rounded-xl bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
            @click="handleApproveTask"
          >
            {{ approvalActionLoading ? '…' : t('tasks.approve') }}
          </button>
          <button
            :disabled="approvalActionLoading"
            class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50 transition-colors"
            @click="showApprovalRejectModal = true; approvalRejectNote = ''"
          >
            {{ t('tasks.reject') }}
          </button>
        </div>
        <div v-else-if="task!.approval_status === 'none'" class="text-sm text-gray-400 dark:text-gray-500">
          {{ t('tasks.approvalNotRequired') }}
        </div>
      </div>

      <!-- ===================== PHASE 8: CUSTOM FIELDS ===================== -->
      <div
        v-if="customFields.length > 0"
        class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6"
      >
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          🔧 {{ t('tasks.customFields') }}
        </h2>
        <div class="space-y-4">
          <div v-for="cf in customFields" :key="cf.field_id">
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
              {{ cf.name }}
              <span v-if="cf.is_required" class="text-red-400 ml-0.5">*</span>
            </label>

            <!-- Text -->
            <input
              v-if="cf.field_type === 'text'"
              :value="(cf.value as string) ?? ''"
              type="text"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400"
              :placeholder="cf.name"
              :disabled="savingCustomFieldId === cf.field_id"
              @blur="saveCustomFieldValue(cf.field_id, ($event.target as HTMLInputElement).value)"
            />

            <!-- Number -->
            <input
              v-else-if="cf.field_type === 'number'"
              :value="(cf.value as number) ?? ''"
              type="number"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400"
              :placeholder="cf.name"
              :disabled="savingCustomFieldId === cf.field_id"
              @blur="saveCustomFieldValue(cf.field_id, ($event.target as HTMLInputElement).value)"
            />

            <!-- Date -->
            <input
              v-else-if="cf.field_type === 'date'"
              :value="(cf.value as string) ?? ''"
              type="date"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400"
              :disabled="savingCustomFieldId === cf.field_id"
              @change="saveCustomFieldValue(cf.field_id, ($event.target as HTMLInputElement).value)"
            />

            <!-- Dropdown -->
            <select
              v-else-if="cf.field_type === 'dropdown'"
              :value="(cf.value as string) ?? ''"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400"
              :disabled="savingCustomFieldId === cf.field_id"
              @change="saveCustomFieldValue(cf.field_id, ($event.target as HTMLSelectElement).value)"
            >
              <option value="">—</option>
              <option v-for="opt in cf.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>

            <!-- Checkbox -->
            <label v-else-if="cf.field_type === 'checkbox'" class="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                :checked="Boolean(cf.value)"
                class="rounded"
                :disabled="savingCustomFieldId === cf.field_id"
                @change="saveCustomFieldValue(cf.field_id, ($event.target as HTMLInputElement).checked)"
              />
              <span class="text-sm text-gray-600 dark:text-gray-400">{{ cf.name }}</span>
            </label>

            <!-- URL -->
            <div v-else-if="cf.field_type === 'url'" class="flex gap-1.5">
              <input
                :value="(cf.value as string) ?? ''"
                type="url"
                class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400"
                placeholder="https://..."
                :disabled="savingCustomFieldId === cf.field_id"
                @blur="saveCustomFieldValue(cf.field_id, ($event.target as HTMLInputElement).value)"
              />
              <a
                v-if="cf.value"
                :href="(cf.value as string)"
                target="_blank"
                rel="noopener noreferrer"
                class="px-2 py-1.5 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 text-xs hover:bg-blue-100 dark:hover:bg-blue-900/30 flex items-center"
              >↗</a>
            </div>
          </div>
        </div>
      </div>

      <!-- ===================== DESCRIPTION ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">
            📝 {{ t('tasks.descriptionSection') }}
          </h2>
          <button
            v-if="!editingDescription"
            class="text-xs text-gray-400 hover:text-blue-500"
            @click="startEditDescription"
          >{{ t('tasks.edit') }}</button>
        </div>
        <!-- View mode -->
        <template v-if="!editingDescription">
          <div
            v-if="task!.description_html"
            class="prose prose-sm dark:prose-invert max-w-none"
            v-html="sanitizeHtml(task!.description_html)"
          />
          <p
            v-else-if="task!.description"
            class="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap"
          >{{ task!.description }}</p>
          <p v-else class="text-sm text-gray-400 italic">{{ t('tasks.noDescription') }}</p>
          <p v-if="task!.description_added_at" class="text-xs text-gray-400 mt-2">
            {{ t('tasks.descriptionAddedAt') }} {{ formatDateTime(task!.description_added_at) }}
          </p>
        </template>
        <!-- Edit mode -->
        <div v-else class="space-y-2 mt-2">
          <RichTextEditor v-model="editDescHtml" :members="teamMembers" :placeholder="t('tasks.descriptionPlaceholder')" />
          <div class="flex justify-end gap-2">
            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 hover:bg-gray-50"
              @click="cancelEditDescription"
            >{{ t('tasks.cancel') }}</button>
            <button
              :disabled="descSaving"
              class="px-3 py-1.5 rounded-xl bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
              @click="saveDescription"
            >{{ descSaving ? '…' : t('tasks.save') }}</button>
          </div>
        </div>
      </div>

      <!-- ===================== UNIFIED ACTIVITY TIMELINE (Streamline) ===================== -->
      <!-- Replaces the legacy task-specific timeline.  The shared ActivityTimeline component
           handles rendering of comments, system events, file uploads, reactions, real-time
           updates and provides the action-picker composer for any registered Streamline tool. -->
      <ActivityTimeline
        ref="activityTimelineRef"
        entity-type="task"
        :entity-id="taskId"
        class="mb-6"
      />

      <!-- Watchers row (kept here for context, was previously inside the timeline footer) -->
      <div
        v-if="task!.watcher_ids.length"
        class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 mb-6 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400"
      >
        <span class="font-medium">🔔 {{ t('tasks.watchersSection') }}</span>
        <div class="flex flex-wrap gap-1">
          <span
            v-for="wid in task!.watcher_ids"
            :key="wid"
            class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-xs font-medium"
            :title="members.find((m) => m.user_id === wid)?.user_full_name ?? wid"
          >
            {{ (members.find((m) => m.user_id === wid)?.user_full_name ?? '?').charAt(0).toUpperCase() }}
          </span>
        </div>
      </div>
    </template>

    <!-- ===================== EDIT TASK MODAL ===================== -->
    <Teleport to="body">
      <div
        v-if="showEditTask"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="showEditTask = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4 overflow-y-auto max-h-[90vh]">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.editTask') }}</h2>

          <div v-if="editError" class="text-sm text-red-600 bg-red-50 dark:bg-red-900/30 rounded-xl px-3 py-2">
            {{ editError }}
          </div>

          <!-- Title -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.taskTitle') }}</label>
            <input
              v-model="editTitle"
              type="text"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Description (plain) -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.description') }}</label>
            <textarea
              v-model="editDescription"
              rows="2"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
            />
          </div>

          <!-- Priority + Status row -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.priority') }}</label>
              <select
                v-model="editPriority"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              >
                <option value="none">{{ t('tasks.priorityNone') }}</option>
                <option value="low">{{ t('tasks.priorityLow') }}</option>
                <option value="medium">{{ t('tasks.priorityMedium') }}</option>
                <option value="high">{{ t('tasks.priorityHigh') }}</option>
                <option value="critical">{{ t('tasks.priorityCritical') }}</option>
              </select>
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.status') }}</label>
              <select
                v-model="editStatus"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              >
                <option value="todo">{{ t('tasks.statusTodo') }}</option>
                <option value="in_progress">{{ t('tasks.statusInProgress') }}</option>
                <option value="blocked">{{ t('tasks.statusBlocked') }}</option>
                <option value="done">{{ t('tasks.statusDone') }}</option>
                <option value="cancelled">{{ t('tasks.statusCancelled') }}</option>
              </select>
            </div>
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.tags') }} <span class="text-gray-400">({{ t('tasks.tagsHint') }})</span></label>
            <input
              v-model="editTags"
              type="text"
              :placeholder="t('tasks.tagsPlaceholder')"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Due date range row -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.deadline') }}</label>
              <input
                v-model="editDueDate"
                type="date"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.deadlineEnd') }}</label>
              <input
                v-model="editDueDateEnd"
                type="date"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
          </div>

          <!-- Assignee -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.assignee') }}</label>
            <select
              v-model="editAssigneeId"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
            >
              <option value="">{{ t('tasks.noAssignee') }}</option>
              <option v-for="m in members" :key="m.user_id" :value="m.user_id">
                {{ memberLabel(m) }}
              </option>
            </select>
          </div>

          <!-- Watchers -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.watchers') }}</label>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="m in members"
                :key="m.user_id"
                class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
                :class="editWatcherIds.includes(m.user_id)
                  ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
              >
                <input
                  type="checkbox"
                  class="hidden"
                  :checked="editWatcherIds.includes(m.user_id)"
                  @change="toggleWatcher(editWatcherIds, m.user_id)"
                />
                🔔 {{ memberLabel(m) }}
              </label>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="showEditTask = false"
            >
              {{ t('tasks.cancel') }}
            </button>
            <button
              :disabled="editSubmitting"
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="submitEditTask"
            >
              {{ editSubmitting ? t('tasks.saving') : t('tasks.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
    <!-- Copy Task Modal -->
    <Teleport to="body">
      <div v-if="showCopyModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showCopyModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.copyTask') }}</h2>
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.taskTitle') }}</label>
            <input v-model="copyTitle" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div class="space-y-2">
            <label class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input type="checkbox" v-model="copyIncludeChecklist" class="rounded" />
              {{ t('tasks.copyChecklist') }}
            </label>
            <label class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input type="checkbox" v-model="copyIncludeSubtasks" class="rounded" />
              {{ t('tasks.copySubtasks') }}
            </label>
          </div>
          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showCopyModal = false">{{ t('tasks.cancel') }}</button>
            <button class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-60" :disabled="copySubmitting" @click="submitCopyTask">
              {{ copySubmitting ? '…' : t('tasks.copyTask') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Move Task Modal -->
    <Teleport to="body">
      <div v-if="showMoveModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showMoveModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.moveTask') }}</h2>
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.lead') }} <span class="text-gray-400">({{ t('tasks.optional') }})</span></label>
            <select v-model="moveLeadId" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400">
              <option value="">{{ t('tasks.noLead') }}</option>
              <option v-for="l in leads" :key="l.id" :value="l.id">{{ l.title }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.customer') }} <span class="text-gray-400">({{ t('tasks.optional') }})</span></label>
            <select v-model="moveCustomerId" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400">
              <option value="">{{ t('tasks.noCustomer') }}</option>
              <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.display }}</option>
            </select>
          </div>
          <p class="text-xs text-gray-400">{{ t('tasks.moveHint') }}</p>
          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showMoveModal = false">{{ t('tasks.cancel') }}</button>
            <button class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-60" :disabled="moveSubmitting" @click="submitMoveTask">
              {{ moveSubmitting ? '…' : t('tasks.moveTask') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete Confirm Modal -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showDeleteConfirm = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.deleteTask') }}</h2>
          <p class="text-sm text-gray-600 dark:text-gray-400">{{ t('tasks.deleteConfirm') }}</p>
          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showDeleteConfirm = false">{{ t('tasks.cancel') }}</button>
            <button class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-60" :disabled="deleting" @click="confirmDelete">
              {{ deleting ? '…' : t('tasks.deleteTask') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Phase 7: Recurrence Modal -->
    <Teleport to="body">
      <div v-if="showRecurrenceModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showRecurrenceModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">🔁 {{ t('tasks.recurrence') }}</h2>

          <!-- Type -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.recurrenceType') }}</label>
            <select
              v-model="recurrenceType"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
            >
              <option value="daily">{{ t('tasks.recurrenceDaily') }}</option>
              <option value="weekly">{{ t('tasks.recurrenceWeekly') }}</option>
              <option value="monthly">{{ t('tasks.recurrenceMonthly') }}</option>
              <option value="custom">{{ t('tasks.recurrenceCustom') }}</option>
            </select>
          </div>

          <!-- Interval -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.recurrenceInterval') }}</label>
            <input
              v-model.number="recurrenceInterval"
              type="number"
              min="1"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
            />
          </div>

          <!-- Day of week (only for weekly) -->
          <div v-if="recurrenceType === 'weekly'">
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">{{ t('tasks.recurrenceDaysOfWeek') }}</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="(day, idx) in [t('tasks.dowMon'), t('tasks.dowTue'), t('tasks.dowWed'), t('tasks.dowThu'), t('tasks.dowFri'), t('tasks.dowSat'), t('tasks.dowSun')]"
                :key="idx"
                type="button"
                class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors"
                :class="recurrenceDayOfWeek.includes(idx)
                  ? 'bg-blue-500 border-blue-500 text-white'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-blue-400'"
                @click="toggleRecurrenceDow(idx)"
              >{{ day }}</button>
            </div>
          </div>

          <!-- Ends at -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.recurrenceEndsAt') }} <span class="text-gray-400">({{ t('tasks.optional') }})</span></label>
            <input
              v-model="recurrenceEndsAt"
              type="date"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
            />
          </div>

          <div class="flex justify-between pt-2">
            <button
              v-if="task!.recurrence"
              :disabled="recurrenceSaving"
              class="px-4 py-2 rounded-xl border border-red-200 dark:border-red-700 text-red-600 dark:text-red-400 text-sm hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
              @click="clearRecurrence"
            >{{ t('tasks.clearRecurrence') }}</button>
            <div v-else />
            <div class="flex gap-2">
              <button
                class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                @click="showRecurrenceModal = false"
              >{{ t('tasks.cancel') }}</button>
              <button
                :disabled="recurrenceSaving"
                class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                @click="saveRecurrence"
              >{{ recurrenceSaving ? '…' : t('tasks.save') }}</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Phase 7: Approval Request Modal -->
    <Teleport to="body">
      <div v-if="showApprovalRequestModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showApprovalRequestModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">✅ {{ t('tasks.requestApproval') }}</h2>
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.approver') }}</label>
            <select
              v-model="approvalRequestApproverId"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
            >
              <option value="">{{ t('tasks.selectApprover') }}</option>
              <option v-for="m in members" :key="m.user_id" :value="m.user_id">
                {{ memberLabel(m) }}
              </option>
            </select>
          </div>
          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showApprovalRequestModal = false">{{ t('tasks.cancel') }}</button>
            <button
              :disabled="approvalRequestSubmitting || !approvalRequestApproverId"
              class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              @click="submitApprovalRequest"
            >{{ approvalRequestSubmitting ? '…' : t('tasks.sendApprovalRequest') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Phase 7: Approval Reject Modal -->
    <Teleport to="body">
      <div v-if="showApprovalRejectModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showApprovalRejectModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">❌ {{ t('tasks.rejectApproval') }}</h2>
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.rejectionNote') }} <span class="text-gray-400">({{ t('tasks.optional') }})</span></label>
            <textarea
              v-model="approvalRejectNote"
              rows="3"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              :placeholder="t('tasks.rejectionNotePlaceholder')"
            />
          </div>
          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showApprovalRejectModal = false">{{ t('tasks.cancel') }}</button>
            <button
              :disabled="approvalRejectSubmitting"
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="submitReject"
            >{{ approvalRejectSubmitting ? '…' : t('tasks.confirmReject') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- PR4: outcome prompt modal for calendar tasks -->
    <TaskOutcomeModal
      v-if="showOutcomeModal && task"
      :task="task"
      @close="showOutcomeModal = false"
      @resolved="onOutcomeResolved"
    />
  </div>
</template>

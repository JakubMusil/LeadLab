<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useTasksStore, type TaskOut, type TaskCommentOut, type TaskAttachmentOut, type ChecklistItemOut, type TaskDependencyOut } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import DOMPurify from 'dompurify'

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

function hasPlainText(html: string): boolean {
  const div = document.createElement('div')
  div.innerHTML = DOMPurify.sanitize(html)
  return Boolean(div.textContent?.trim())
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
  editDueDate.value = task.value.due_date ? task.value.due_date.split('T')[0] : ''
  editDueDateEnd.value = task.value.due_date_end ? task.value.due_date_end.split('T')[0] : ''
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
// Comments
// ---------------------------------------------------------------------------
const comments = ref<TaskCommentOut[]>([])
const commentsLoading = ref(false)
const commentEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const newCommentHtml = ref('')
const commentSubmitting = ref(false)

// Per-comment editing state
const editingCommentId = ref<string | null>(null)
const editCommentHtml = ref('')
const editCommentEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const editCommentSubmitting = ref(false)

async function loadComments() {
  commentsLoading.value = true
  const result = await tasksStore.fetchTaskComments(taskId.value)
  commentsLoading.value = false
  if (result.ok && result.data) comments.value = result.data
}

async function submitComment() {
  if (!hasPlainText(newCommentHtml.value)) return
  commentSubmitting.value = true
  const result = await tasksStore.createTaskComment(taskId.value, newCommentHtml.value)
  commentSubmitting.value = false
  if (result.ok && result.data) {
    comments.value.push(result.data)
    newCommentHtml.value = ''
  } else {
    toast.error(result.error ?? t('tasks.commentFailed'))
  }
}

function startEditComment(comment: TaskCommentOut) {
  editingCommentId.value = comment.id
  editCommentHtml.value = comment.content_html
}

function cancelEditComment() {
  editingCommentId.value = null
  editCommentHtml.value = ''
}

async function submitEditComment(commentId: string) {
  if (!hasPlainText(editCommentHtml.value)) return
  editCommentSubmitting.value = true
  const result = await tasksStore.updateTaskComment(taskId.value, commentId, editCommentHtml.value)
  editCommentSubmitting.value = false
  if (result.ok && result.data) {
    const idx = comments.value.findIndex((c) => c.id === commentId)
    if (idx !== -1) comments.value[idx] = result.data
    editingCommentId.value = null
    editCommentHtml.value = ''
  } else {
    toast.error(result.error ?? t('tasks.commentUpdateFailed'))
  }
}

async function deleteComment(commentId: string) {
  const result = await tasksStore.deleteTaskComment(taskId.value, commentId)
  if (result.ok) {
    comments.value = comments.value.filter((c) => c.id !== commentId)
  } else {
    toast.error(result.error ?? t('tasks.commentDeleteFailed'))
  }
}

function canEditComment(comment: TaskCommentOut): boolean {
  return isAdmin.value || String(comment.author_id) === String(authStore.user?.id)
}

// ---------------------------------------------------------------------------
// Attachments
// ---------------------------------------------------------------------------
const attachments = ref<TaskAttachmentOut[]>([])
const attachmentsLoading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadingFile = ref(false)
const isDraggingOver = ref(false)

async function loadAttachments() {
  attachmentsLoading.value = true
  const result = await tasksStore.fetchTaskAttachments(taskId.value)
  attachmentsLoading.value = false
  if (result.ok && result.data) attachments.value = result.data
}

async function uploadFile(file: File) {
  uploadingFile.value = true
  const result = await tasksStore.uploadTaskAttachment(taskId.value, file)
  uploadingFile.value = false
  if (result.ok && result.data) {
    attachments.value.unshift(result.data)
    toast.success(t('tasks.fileUploaded'))
  } else {
    toast.error(result.error ?? t('tasks.fileUploadFailed'))
  }
}

async function deleteAttachment(attachmentId: string) {
  const result = await tasksStore.deleteTaskAttachment(taskId.value, attachmentId)
  if (result.ok) {
    attachments.value = attachments.value.filter((a) => a.id !== attachmentId)
    toast.success(t('tasks.fileDeleted'))
  } else {
    toast.error(result.error ?? t('tasks.fileDeleteFailed'))
  }
}

function onFileSelected(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files?.length) uploadFile(files[0])
}

function onDrop(e: DragEvent) {
  isDraggingOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) uploadFile(file)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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
// Init
// ---------------------------------------------------------------------------
onMounted(async () => {
  await Promise.all([loadMembers(), loadTask(), loadComments(), loadAttachments(), loadSubtasks(), loadChecklist(), loadDependencies()])
})
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto">
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
            <RouterLink :to="`/app/leads/${task.lead_id}`" class="hover:text-blue-500 truncate max-w-[160px]">
              {{ task.lead_title || task.lead_id }}
            </RouterLink>
            <span>›</span>
          </template>
          <template v-else-if="task.customer_id">
            <RouterLink :to="`/app/customers/${task.customer_id}`" class="hover:text-blue-500 truncate max-w-[160px]">
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
                  :to="`/app/leads/${task.lead_id}`"
                  class="text-blue-500 hover:underline truncate"
                >
                  {{ task.lead_title || task.lead_id }}
                </RouterLink>
              </div>
              <!-- Customer (if linked) -->
              <div v-if="task.customer_id" class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.customer') }}</span>
                <RouterLink
                  :to="`/app/customers/${task.customer_id}`"
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

      <!-- ===================== POPIS ÚKOLU ===================== -->
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
            v-if="task.description_html"
            class="prose prose-sm dark:prose-invert max-w-none"
            v-html="sanitizeHtml(task.description_html)"
          />
          <p
            v-else-if="task.description"
            class="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap"
          >{{ task.description }}</p>
          <p v-else class="text-sm text-gray-400 dark:text-gray-500 italic">
            {{ t('tasks.noDescription') }}
          </p>
          <p v-if="task.description_added_at" class="text-xs text-gray-400 mt-2">
            {{ t('tasks.descriptionAddedAt') }} {{ formatDateTime(task.description_added_at) }}
          </p>
        </template>

        <!-- Edit mode -->
        <div v-else class="space-y-2">
          <RichTextEditor
            v-model="editDescHtml"
            :members="teamMembers"
            :placeholder="t('tasks.descriptionPlaceholder')"
          />
          <div class="flex justify-end gap-2">
            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
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

      <!-- ===================== COMMENTS ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          💬 {{ t('tasks.comments') }}
          <span v-if="comments.length" class="text-sm font-normal text-gray-400">({{ comments.length }})</span>
        </h2>

        <!-- Comment list -->
        <div v-if="commentsLoading" class="space-y-3 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-16 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <div v-else-if="comments.length === 0" class="text-sm text-gray-400 dark:text-gray-500 mb-4">
          {{ t('tasks.noComments') }}
        </div>

        <div v-else class="space-y-4 mb-6">
          <div
            v-for="comment in comments"
            :key="comment.id"
            class="group border border-gray-100 dark:border-gray-700 rounded-xl p-4"
          >
            <!-- Comment header -->
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                  {{ (comment.author_name || '?').charAt(0).toUpperCase() }}
                </span>
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ comment.author_name || t('tasks.unknownAuthor') }}</span>
                <span>·</span>
                <span :title="formatDateTime(comment.updated_at)">
                  {{ formatDateTime(comment.created_at) }}
                  <span v-if="comment.updated_at !== comment.created_at" class="italic ml-1">({{ t('tasks.edited') }})</span>
                </span>
              </div>
              <!-- Actions (author or admin) -->
              <div v-if="canEditComment(comment)" class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  class="text-xs text-gray-400 hover:text-blue-500 px-2 py-0.5 rounded"
                  @click="startEditComment(comment)"
                >
                  {{ t('tasks.editComment') }}
                </button>
                <button
                  class="text-xs text-gray-400 hover:text-red-500 px-2 py-0.5 rounded"
                  @click="deleteComment(comment.id)"
                >
                  {{ t('tasks.deleteComment') }}
                </button>
              </div>
            </div>

            <!-- Comment content (view or edit mode) -->
            <div v-if="editingCommentId !== comment.id">
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="prose prose-sm dark:prose-invert max-w-none" v-html="sanitizeHtml(comment.content_html)" />
            </div>
            <div v-else class="space-y-2">
              <RichTextEditor
                ref="editCommentEditorRef"
                v-model="editCommentHtml"
                :members="teamMembers"
                :placeholder="t('tasks.editCommentPlaceholder')"
              />
              <div class="flex justify-end gap-2">
                <button
                  class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                  @click="cancelEditComment"
                >
                  {{ t('tasks.cancel') }}
                </button>
                <button
                  :disabled="editCommentSubmitting || !hasPlainText(editCommentHtml)"
                  class="px-3 py-1.5 rounded-xl bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                  @click="submitEditComment(comment.id)"
                >
                  {{ editCommentSubmitting ? t('tasks.saving') : t('tasks.save') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- New comment composer -->
        <div class="space-y-2">
          <RichTextEditor
            ref="commentEditorRef"
            v-model="newCommentHtml"
            :members="teamMembers"
            :placeholder="t('tasks.commentPlaceholder')"
          />
          <div class="flex justify-end">
            <button
              :disabled="commentSubmitting || !hasPlainText(newCommentHtml)"
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="submitComment"
            >
              {{ commentSubmitting ? t('tasks.saving') : t('tasks.addComment') }}
            </button>
          </div>
        </div>
      </div>

      <!-- ===================== ATTACHMENTS ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          📎 {{ t('tasks.attachments') }}
          <span v-if="attachments.length" class="text-sm font-normal text-gray-400">({{ attachments.length }})</span>
        </h2>

        <!-- Drop zone -->
        <div
          class="relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors mb-4"
          :class="isDraggingOver
            ? 'border-red-400 bg-red-50 dark:bg-red-900/20'
            : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'"
          @click="fileInput?.click()"
          @dragover.prevent="isDraggingOver = true"
          @dragleave="isDraggingOver = false"
          @drop.prevent="onDrop"
        >
          <input ref="fileInput" type="file" class="hidden" @change="onFileSelected" />
          <p v-if="uploadingFile" class="text-sm text-gray-500 dark:text-gray-400">{{ t('leadDetail.uploading') }}</p>
          <template v-else>
            <p v-if="isDraggingOver" class="text-sm font-medium text-red-500">{{ t('leadDetail.dropToUpload') }}</p>
            <template v-else>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('leadDetail.clickOrDrop') }}</p>
              <p class="text-xs text-gray-400 mt-1">{{ t('leadDetail.maxSize') }}</p>
            </template>
          </template>
        </div>

        <!-- Attachment list -->
        <div v-if="attachmentsLoading" class="space-y-2 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <div v-else-if="attachments.length === 0" class="text-sm text-gray-400 dark:text-gray-500 text-center py-2">
          {{ t('tasks.noAttachments') }}
        </div>

        <ul v-else class="space-y-2">
          <li
            v-for="att in attachments"
            :key="att.id"
            class="flex items-center gap-3 p-3 rounded-xl border border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 group"
          >
            <span class="text-lg flex-shrink-0">📄</span>
            <div class="flex-1 min-w-0">
              <a
                :href="att.url"
                target="_blank"
                rel="noopener"
                class="text-sm font-medium text-blue-500 hover:underline truncate block"
              >
                {{ att.original_filename }}
              </a>
              <p class="text-xs text-gray-400">{{ formatFileSize(att.size_bytes) }} · {{ formatDateTime(att.created_at) }}</p>
            </div>
            <button
              class="text-xs text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
              :title="t('tasks.deleteAttachment')"
              @click="deleteAttachment(att.id)"
            >
              🗑
            </button>
          </li>
        </ul>
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
  </div>
</template>

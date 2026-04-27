<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useTasksStore, type TaskOut, type FollowUpTaskIn } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import GanttView from '@/components/GanttView.vue'
import TaskTableView from '@/components/TaskTableView.vue'

const router = useRouter()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const tasksStore = useTasksStore()
const toast = useToast()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// Team members (for assignee / watcher selectors)
// ---------------------------------------------------------------------------
interface Member {
  id: string
  user_id: string
  user_email: string
  user_full_name: string
  role: string
}

const members = ref<Member[]>([])

async function loadMembers() {
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (!firmId) return
  const res = await api.get<Member[]>(`/api/v1/firms/${firmId}/members`)
  if (res.ok) members.value = res.data
}

function memberLabel(m: Member) {
  return m.user_full_name?.trim() || m.user_email
}

// ---------------------------------------------------------------------------
// Leads (for the "new task" lead selector)
// ---------------------------------------------------------------------------
interface LeadOption { id: string; title: string }
const leads = ref<LeadOption[]>([])

async function loadLeads() {
  const res = await api.get<LeadOption[]>('/api/v1/crm/leads?page_size=200')
  if (res.ok) leads.value = (res.data as LeadOption[])
}

// ---------------------------------------------------------------------------
// Role/permissions
// ---------------------------------------------------------------------------
const currentMember = computed(() =>
  members.value.find((m) => m.user_email === authStore.user?.email),
)
const isAdmin = computed(() =>
  currentMember.value?.role === 'admin' || currentMember.value?.role === 'owner',
)

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------
type ViewMode = 'mine' | 'all' | 'user'
const viewMode = ref<ViewMode>('mine')
const selectedUserId = ref<string>('')
const showCompleted = ref(false)
const filterStatus = ref<string>('')
const filterPriority = ref<string>('')
const filterTag = ref<string>('')
const showFavourites = ref(false)
const showArchived = ref(false)
const showPinned = ref(false)

async function loadTasks() {
  let assignedToId: string | undefined
  if (viewMode.value === 'all') {
    assignedToId = 'all'
  } else if (viewMode.value === 'user' && selectedUserId.value) {
    assignedToId = selectedUserId.value
  }
  await tasksStore.fetchTasksForView({
    assignedToId,
    completed: showCompleted.value ? undefined : false,
    status: filterStatus.value || undefined,
    priority: filterPriority.value || undefined,
    tag: filterTag.value || undefined,
    isFavourite: showFavourites.value ? true : undefined,
    isArchived: showArchived.value ? true : undefined,
    isPinned: showPinned.value ? true : undefined,
  })
}

watch([viewMode, selectedUserId, showCompleted, filterStatus, filterPriority, filterTag, showFavourites, showArchived, showPinned], () => loadTasks())

// ---------------------------------------------------------------------------
// Task list helpers
// ---------------------------------------------------------------------------
const tasks = computed(() => tasksStore.tasks)

function isOverdue(task: TaskOut) {
  return !task.is_completed && task.due_date && new Date(task.due_date) < new Date()
}

function formatDate(ds: string | null) {
  if (!ds) return '—'
  return new Date(ds).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

// ---------------------------------------------------------------------------
// New Task modal
// ---------------------------------------------------------------------------
const showNewTask = ref(false)
const newTaskLeadId = ref('')
const newTaskTitle = ref('')
const newTaskDescription = ref('')
const newTaskDueDate = ref('')
const newTaskAssigneeId = ref('')
const newTaskWatcherIds = ref<string[]>([])
const newTaskPriority = ref('medium')
const newTaskStatus = ref('todo')
const newTaskTags = ref('')
const newTaskSubmitting = ref(false)
const newTaskError = ref('')

function openNewTask() {
  newTaskLeadId.value = ''
  newTaskTitle.value = ''
  newTaskDescription.value = ''
  newTaskDueDate.value = ''
  newTaskAssigneeId.value = authStore.user ? String(authStore.user.id) : ''
  newTaskWatcherIds.value = []
  newTaskPriority.value = 'medium'
  newTaskStatus.value = 'todo'
  newTaskTags.value = ''
  newTaskError.value = ''
  showNewTask.value = true
}

async function submitNewTask() {
  if (!newTaskTitle.value.trim()) { newTaskError.value = t('tasks.titleRequired'); return }
  newTaskSubmitting.value = true
  newTaskError.value = ''
  const tagsArray = newTaskTags.value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const result = await tasksStore.createTask({
    lead_id: newTaskLeadId.value || null,
    title: newTaskTitle.value.trim(),
    description: newTaskDescription.value,
    assigned_to_id: newTaskAssigneeId.value || null,
    watcher_ids: newTaskWatcherIds.value,
    due_date: newTaskDueDate.value ? new Date(newTaskDueDate.value).toISOString() : null,
    priority: newTaskPriority.value,
    status: newTaskStatus.value,
    tags: tagsArray,
  })
  newTaskSubmitting.value = false
  if (result.ok) {
    showNewTask.value = false
    toast.success(t('tasks.taskCreated'))
    await loadTasks()
  } else {
    newTaskError.value = result.error ?? t('tasks.createFailed')
  }
}

// ---------------------------------------------------------------------------
// Edit Task modal
// ---------------------------------------------------------------------------
const showEditTask = ref(false)
const editingTask = ref<TaskOut | null>(null)
const editTitle = ref('')
const editDescription = ref('')
const editDueDate = ref('')
const editAssigneeId = ref('')
const editWatcherIds = ref<string[]>([])
const editPriority = ref('medium')
const editStatus = ref('todo')
const editTags = ref('')
const editSubmitting = ref(false)
const editError = ref('')

function openEditTask(task: TaskOut) {
  editingTask.value = task
  editTitle.value = task.title
  editDescription.value = task.description
  editDueDate.value = task.due_date ? task.due_date.split('T')[0] : ''
  editAssigneeId.value = task.assigned_to_id ?? ''
  editWatcherIds.value = [...task.watcher_ids]
  editPriority.value = task.priority
  editStatus.value = task.status
  editTags.value = (task.tags ?? []).join(', ')
  editError.value = ''
  showEditTask.value = true
}

async function submitEditTask() {
  if (!editTitle.value.trim()) { editError.value = t('tasks.titleRequired'); return }
  if (!editingTask.value) return
  editSubmitting.value = true
  editError.value = ''
  const tagsArray = editTags.value
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const result = await tasksStore.updateTask(editingTask.value.id, {
    title: editTitle.value.trim(),
    description: editDescription.value,
    assigned_to_id: editAssigneeId.value || null,
    watcher_ids: editWatcherIds.value,
    due_date: editDueDate.value ? new Date(editDueDate.value).toISOString() : null,
    priority: editPriority.value,
    status: editStatus.value,
    tags: tagsArray,
  })
  editSubmitting.value = false
  if (result.ok) {
    showEditTask.value = false
    toast.success(t('tasks.taskUpdated'))
    await loadTasks()
  } else {
    editError.value = result.error ?? t('tasks.updateFailed')
  }
}

// ---------------------------------------------------------------------------
// Complete + follow-up
// ---------------------------------------------------------------------------
const showFollowUp = ref(false)
const completingTaskId = ref<string | null>(null)
const followUpTitle = ref('')
const followUpDescription = ref('')
const followUpDueDate = ref('')
const followUpAssigneeId = ref('')
const followUpWatcherIds = ref<string[]>([])
const followUpSubmitting = ref(false)

async function startComplete(task: TaskOut) {
  completingTaskId.value = task.id
  // Pre-fill follow-up from completed task
  followUpTitle.value = task.title
  followUpDescription.value = task.description
  followUpDueDate.value = ''
  followUpAssigneeId.value = task.assigned_to_id ?? ''
  followUpWatcherIds.value = [...task.watcher_ids]
  showFollowUp.value = true
}

async function completeWithoutFollowUp() {
  if (!completingTaskId.value) return
  followUpSubmitting.value = true
  const result = await tasksStore.completeTaskWithFollowUp(completingTaskId.value)
  followUpSubmitting.value = false
  if (result.ok) {
    showFollowUp.value = false
    completingTaskId.value = null
    toast.success(t('tasks.taskCompleted'))
    await loadTasks()
  } else {
    toast.error(result.error ?? t('tasks.completeFailed'))
  }
}

async function completeWithFollowUp() {
  if (!completingTaskId.value || !followUpTitle.value.trim()) {
    toast.error(t('tasks.followUpTitleRequired'))
    return
  }
  followUpSubmitting.value = true
  const followUp: FollowUpTaskIn = {
    title: followUpTitle.value.trim(),
    description: followUpDescription.value,
    assigned_to_id: followUpAssigneeId.value || null,
    watcher_ids: followUpWatcherIds.value,
    due_date: followUpDueDate.value ? new Date(followUpDueDate.value).toISOString() : null,
  }
  const result = await tasksStore.completeTaskWithFollowUp(completingTaskId.value, followUp)
  followUpSubmitting.value = false
  if (result.ok) {
    showFollowUp.value = false
    completingTaskId.value = null
    toast.success(t('tasks.taskCompletedWithFollowUp'))
    await loadTasks()
  } else {
    toast.error(result.error ?? t('tasks.completeFailed'))
  }
}

// ---------------------------------------------------------------------------
// View mode (List / Kanban)
// ---------------------------------------------------------------------------
type DisplayMode = 'list' | 'kanban' | 'gantt' | 'table'
const displayMode = ref<DisplayMode>('list')

// ---------------------------------------------------------------------------
// Kanban — drag & drop
// ---------------------------------------------------------------------------
const KANBAN_COLUMNS = [
  { key: 'todo', label: 'To Do' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'blocked', label: 'Blocked' },
  { key: 'done', label: 'Done' },
  { key: 'cancelled', label: 'Cancelled' },
] as const

function tasksByStatus(status: string) {
  return tasks.value.filter((t) => t.status === status)
}

const dragTaskId = ref<string | null>(null)
const dragOverStatus = ref<string | null>(null)

function onDragStart(task: TaskOut) {
  dragTaskId.value = task.id
}

function onDragOver(e: DragEvent, status: string) {
  e.preventDefault()
  dragOverStatus.value = status
}

function onDragLeave() {
  dragOverStatus.value = null
}

async function onDrop(e: DragEvent, status: string) {
  e.preventDefault()
  dragOverStatus.value = null
  if (!dragTaskId.value) return
  const task = tasks.value.find((t) => t.id === dragTaskId.value)
  if (!task || task.status === status) {
    dragTaskId.value = null
    return
  }
  // Optimistic update
  const idx = tasks.value.findIndex((t) => t.id === dragTaskId.value)
  if (idx !== -1) tasks.value[idx] = { ...tasks.value[idx], status: status as TaskOut['status'] } as TaskOut
  const result = await tasksStore.updateTask(dragTaskId.value, { status })
  dragTaskId.value = null
  if (!result.ok) {
    toast.error(result.error ?? t('tasks.updateFailed'))
    await loadTasks()
  }
}

// ---------------------------------------------------------------------------
// Batch actions
// ---------------------------------------------------------------------------
const selectedTaskIds = ref<Set<string>>(new Set())
const batchAction_submitting = ref(false)

function toggleSelectTask(id: string) {
  if (selectedTaskIds.value.has(id)) {
    selectedTaskIds.value.delete(id)
  } else {
    selectedTaskIds.value.add(id)
  }
}

function selectAll() {
  tasks.value.forEach((t) => selectedTaskIds.value.add(t.id))
}

function clearSelection() {
  selectedTaskIds.value.clear()
}

async function doBatchAction(action: string) {
  if (selectedTaskIds.value.size === 0) return
  batchAction_submitting.value = true
  const result = await tasksStore.batchAction([...selectedTaskIds.value], action)
  batchAction_submitting.value = false
  if (result.ok && result.data) {
    toast.success(t('tasks.batchDone').replace('{n}', String(result.data.processed)))
    clearSelection()
    await loadTasks()
  } else {
    toast.error(result.error ?? t('tasks.batchFailed'))
  }
}

// ---------------------------------------------------------------------------
// Archive tab
// ---------------------------------------------------------------------------
type TabMode = 'active' | 'archived'
const tabMode = ref<TabMode>('active')

watch(tabMode, () => {
  showArchived.value = tabMode.value === 'archived'
  loadTasks()
})

// ---------------------------------------------------------------------------
// Watcher toggle helpers
// ---------------------------------------------------------------------------
function toggleWatcher(watcherIds: string[], userId: string) {
  const idx = watcherIds.indexOf(userId)
  if (idx !== -1) watcherIds.splice(idx, 1)
  else watcherIds.push(userId)
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
onMounted(async () => {
  await Promise.all([loadMembers(), loadLeads()])
  await loadTasks()
})
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Page header -->
    <div class="flex items-center justify-between mb-6 flex-wrap gap-3">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ t('tasks.title') }}</h1>
      <button
        class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700"
        @click="openNewTask"
      >
        {{ t('tasks.newTask') }}
      </button>
    </div>

    <!-- Tabs: Active / Archived -->
    <div class="flex gap-1 mb-4 bg-gray-100 dark:bg-gray-800 rounded-xl p-1 w-fit">
      <button
        v-for="tab in (['active', 'archived'] as const)"
        :key="tab"
        class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
        :class="tabMode === tab
          ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
          : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
        @click="tabMode = tab"
      >
        {{ tab === 'active' ? t('tasks.active') : t('tasks.archiveTab') }}
      </button>
    </div>

    <!-- Display mode toggle — only on active tab -->
    <div v-if="tabMode === 'active'" class="flex gap-1 mb-4 bg-gray-100 dark:bg-gray-800 rounded-xl p-1 w-fit">
      <button
        v-for="mode in (['list', 'kanban', 'gantt', 'table'] as const)"
        :key="mode"
        class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
        :class="displayMode === mode
          ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
          : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
        @click="displayMode = mode"
      >
        {{ ({ list: '☰ ' + t('tasks.viewList'), kanban: '⬛ ' + t('tasks.viewKanban'), gantt: '📊 ' + t('tasks.viewGantt'), table: '⊞ ' + t('tasks.viewTable') } as Record<string, string>)[mode] }}
      </button>
    </div>

    <!-- Filter bar -->
    <div class="flex flex-wrap gap-3 mb-5 items-center">
      <!-- View mode tabs (admin/owner only) -->
      <div v-if="isAdmin" class="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1">
        <button
          v-for="mode in (['mine', 'all', 'user'] as const)"
          :key="mode"
          class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          :class="viewMode === mode
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
          @click="viewMode = mode"
        >
          {{
            mode === 'mine' ? t('tasks.myTasks') :
            mode === 'all'  ? t('tasks.allTasks') :
                               t('tasks.byUser')
          }}
        </button>
      </div>

      <!-- Per-user dropdown (admin only) -->
      <select
        v-if="isAdmin && viewMode === 'user'"
        v-model="selectedUserId"
        class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
      >
        <option value="">{{ t('tasks.selectUser') }}</option>
        <option v-for="m in members" :key="m.user_id" :value="m.user_id">
          {{ memberLabel(m) }}
        </option>
      </select>

      <!-- Status filter -->
      <select
        v-model="filterStatus"
        class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
      >
        <option value="">{{ t('tasks.allStatuses') }}</option>
        <option value="todo">{{ t('tasks.statusTodo') }}</option>
        <option value="in_progress">{{ t('tasks.statusInProgress') }}</option>
        <option value="blocked">{{ t('tasks.statusBlocked') }}</option>
        <option value="done">{{ t('tasks.statusDone') }}</option>
        <option value="cancelled">{{ t('tasks.statusCancelled') }}</option>
      </select>

      <!-- Priority filter -->
      <select
        v-model="filterPriority"
        class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
      >
        <option value="">{{ t('tasks.allPriorities') }}</option>
        <option value="critical">{{ t('tasks.priorityCritical') }}</option>
        <option value="high">{{ t('tasks.priorityHigh') }}</option>
        <option value="medium">{{ t('tasks.priorityMedium') }}</option>
        <option value="low">{{ t('tasks.priorityLow') }}</option>
        <option value="none">{{ t('tasks.priorityNone') }}</option>
      </select>

      <!-- Tag filter -->
      <input
        v-model="filterTag"
        type="text"
        :placeholder="t('tasks.filterByTag')"
        class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400 w-32"
      />

      <!-- Flags row -->
      <div class="flex items-center gap-3 ml-auto flex-wrap">
        <label class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
          <input type="checkbox" v-model="showFavourites" class="rounded" />
          ⭐ {{ t('tasks.favourites') }}
        </label>
        <label class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
          <input type="checkbox" v-model="showPinned" class="rounded" />
          📌 {{ t('tasks.pinned') }}
        </label>
        <label class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
          <input type="checkbox" v-model="showArchived" class="rounded" />
          🗄 {{ t('tasks.archived') }}
        </label>
        <label class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
          <input type="checkbox" v-model="showCompleted" class="rounded" />
          {{ t('tasks.showCompleted') }}
        </label>
      </div>
    </div>

    <!-- Batch actions toolbar -->
    <div
      v-if="selectedTaskIds.size > 0"
      class="flex items-center gap-3 mb-4 px-4 py-2.5 bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-200 dark:border-blue-800"
    >
      <span class="text-sm font-medium text-blue-700 dark:text-blue-300">{{ selectedTaskIds.size }} {{ t('tasks.selected') }}</span>
      <button class="px-3 py-1 rounded-lg bg-green-500 text-white text-xs hover:bg-green-600" :disabled="batchAction_submitting" @click="doBatchAction('complete')">✓ {{ t('tasks.complete') }}</button>
      <button class="px-3 py-1 rounded-lg bg-gray-500 text-white text-xs hover:bg-gray-600" :disabled="batchAction_submitting" @click="doBatchAction('archive')">🗄 {{ t('tasks.archive') }}</button>
      <button class="px-3 py-1 rounded-lg bg-red-500 text-white text-xs hover:bg-red-600" :disabled="batchAction_submitting" @click="doBatchAction('delete')">🗑 {{ t('tasks.deleteTask') }}</button>
      <button class="ml-auto text-xs text-gray-500 hover:text-gray-700" @click="clearSelection">✕ {{ t('tasks.clearSelection') }}</button>
    </div>

    <!-- Loading state -->
    <div v-if="tasksStore.loading" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-16 bg-gray-100 dark:bg-gray-800 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="tasks.length === 0"
      class="text-center py-16 text-gray-400 dark:text-gray-500 text-sm"
    >
      {{ t('tasks.noTasks') }}
    </div>

    <!-- Task list -->
    <div v-else-if="displayMode === 'list'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="flex items-start gap-3 p-4"
        :class="task.is_completed ? 'opacity-60' : ''"
      >
        <!-- Selection checkbox -->
        <input
          type="checkbox"
          :checked="selectedTaskIds.has(task.id)"
          class="rounded flex-shrink-0 mt-0.5"
          @change="toggleSelectTask(task.id)"
        />

        <!-- Complete checkbox -->
        <button
          class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors mt-0.5"
          :class="task.is_completed
            ? 'bg-blue-500 border-blue-500 text-white cursor-default'
            : 'border-gray-300 hover:border-blue-400'"
          :disabled="task.is_completed"
          :title="task.is_completed ? '' : t('tasks.complete')"
          @click="!task.is_completed && startComplete(task)"
        >
          <span v-if="task.is_completed" class="text-xs">✓</span>
        </button>

        <!-- Task info -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span v-if="task.is_favourite" class="text-yellow-400 text-sm">⭐</span>
            <span v-if="task.is_pinned" class="text-yellow-500 text-sm">📌</span>
            <RouterLink
              :to="`/app/tasks/${task.id}`"
              class="text-sm font-medium hover:underline"
              :class="task.is_completed ? 'line-through text-gray-400' : 'text-gray-900 dark:text-gray-100'"
            >
              {{ task.title }}
            </RouterLink>
          </div>
          <div class="flex flex-wrap items-center gap-2 mt-1">
            <!-- Status badge -->
            <span
              class="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium"
              :class="{
                'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300': task.status === 'todo',
                'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300': task.status === 'in_progress',
                'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300': task.status === 'blocked',
                'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300': task.status === 'done',
                'bg-gray-200 text-gray-500 dark:bg-gray-800 dark:text-gray-400': task.status === 'cancelled',
              }"
            >
              {{ { todo: t('tasks.statusTodo'), in_progress: t('tasks.statusInProgress'), blocked: t('tasks.statusBlocked'), done: t('tasks.statusDone'), cancelled: t('tasks.statusCancelled') }[task.status] ?? task.status }}
            </span>
            <!-- Priority -->
            <span
              v-if="task.priority && task.priority !== 'none'"
              class="text-xs font-medium"
              :class="{
                'text-blue-500': task.priority === 'low',
                'text-yellow-500': task.priority === 'medium',
                'text-orange-500': task.priority === 'high',
                'text-red-600': task.priority === 'critical',
              }"
            >
              ⚠ {{ { low: t('tasks.priorityLow'), medium: t('tasks.priorityMedium'), high: t('tasks.priorityHigh'), critical: t('tasks.priorityCritical') }[task.priority] ?? task.priority }}
            </span>
            <!-- Lead link -->
            <RouterLink
              v-if="task.lead_id"
              :to="`/app/leads/${task.lead_id}`"
              class="text-xs text-blue-500 hover:underline truncate max-w-[160px]"
            >
              {{ task.lead_title || task.lead_id }}
            </RouterLink>
            <!-- Tags -->
            <span
              v-for="tag in (task.tags ?? []).slice(0, 3)"
              :key="tag"
              class="text-xs px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
            >🏷 {{ tag }}</span>
            <!-- Assignee -->
            <span v-if="task.assigned_to_name" class="text-xs text-gray-500 dark:text-gray-400">
              👤 {{ task.assigned_to_name }}
            </span>
            <!-- Due date -->
            <span
              v-if="task.due_date"
              class="text-xs"
              :class="isOverdue(task) ? 'text-red-500 font-semibold' : 'text-gray-400'"
            >
              📅 {{ formatDate(task.due_date) }}
              <template v-if="task.due_date_end"> – {{ formatDate(task.due_date_end) }}</template>
              <span v-if="isOverdue(task)" class="ml-1">({{ t('tasks.overdue') }})</span>
            </span>
          </div>
        </div>

        <!-- Actions -->
        <div v-if="!task.is_completed" class="flex gap-2 flex-shrink-0">
          <button
            class="px-2.5 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
            @click="openEditTask(task)"
          >
            {{ t('tasks.edit') }}
          </button>
          <button
            class="px-2.5 py-1 rounded-lg border border-green-200 text-xs text-green-600 hover:bg-green-50"
            @click="startComplete(task)"
          >
            {{ t('tasks.complete') }}
          </button>
        </div>
        <div v-else class="text-xs text-gray-400 flex-shrink-0">
          {{ t('tasks.done') }}
        </div>
      </div>
    </div>

    <!-- Kanban board -->
    <div v-else-if="displayMode === 'kanban' && tabMode === 'active'" class="flex gap-4 overflow-x-auto pb-4">
      <div
        v-for="col in KANBAN_COLUMNS"
        :key="col.key"
        class="flex-shrink-0 w-72 flex flex-col"
        @dragover.prevent="onDragOver($event, col.key)"
        @dragleave="onDragLeave"
        @drop="onDrop($event, col.key)"
      >
        <!-- Column header -->
        <div
          class="flex items-center justify-between px-3 py-2 rounded-t-xl font-semibold text-sm"
          :class="{
            'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300': col.key === 'todo',
            'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300': col.key === 'in_progress',
            'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300': col.key === 'blocked',
            'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300': col.key === 'done',
            'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400': col.key === 'cancelled',
          }"
        >
          <span>{{ { todo: t('tasks.statusTodo'), in_progress: t('tasks.statusInProgress'), blocked: t('tasks.statusBlocked'), done: t('tasks.statusDone'), cancelled: t('tasks.statusCancelled') }[col.key] }}</span>
          <span class="ml-2 text-xs opacity-60">{{ tasksByStatus(col.key).length }}</span>
        </div>
        <!-- Drop zone -->
        <div
          class="flex-1 min-h-[120px] rounded-b-xl p-2 space-y-2 transition-colors"
          :class="dragOverStatus === col.key
            ? 'bg-blue-50 dark:bg-blue-900/10 border-2 border-dashed border-blue-400'
            : 'bg-gray-50 dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700'"
        >
          <!-- Task cards -->
          <div
            v-for="task in tasksByStatus(col.key)"
            :key="task.id"
            class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-3 cursor-grab active:cursor-grabbing shadow-sm hover:shadow-md transition-shadow"
            :class="task.id === dragTaskId ? 'opacity-50' : ''"
            draggable="true"
            @dragstart="onDragStart(task)"
          >
            <div class="flex items-start gap-2 mb-2">
              <input
                type="checkbox"
                :checked="selectedTaskIds.has(task.id)"
                class="mt-0.5 rounded flex-shrink-0"
                @change="toggleSelectTask(task.id)"
                @click.stop
              />
              <RouterLink
                :to="`/app/tasks/${task.id}`"
                class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:underline flex-1 min-w-0 line-clamp-2"
                :class="task.is_completed ? 'line-through text-gray-400' : ''"
              >
                {{ task.title }}
              </RouterLink>
            </div>
            <div class="flex flex-wrap items-center gap-1.5 text-xs">
              <span v-if="task.is_favourite" class="text-yellow-400">⭐</span>
              <span v-if="task.is_pinned" class="text-yellow-500">📌</span>
              <span
                v-if="task.priority && task.priority !== 'none'"
                :class="{
                  'text-blue-500': task.priority === 'low',
                  'text-yellow-500': task.priority === 'medium',
                  'text-orange-500': task.priority === 'high',
                  'text-red-600': task.priority === 'critical',
                }"
              >⚠ {{ { low: t('tasks.priorityLow'), medium: t('tasks.priorityMedium'), high: t('tasks.priorityHigh'), critical: t('tasks.priorityCritical') }[task.priority] ?? task.priority }}</span>
              <span v-if="task.due_date" class="text-gray-400" :class="isOverdue(task) ? 'text-red-500 font-semibold' : ''">
                📅 {{ formatDate(task.due_date) }}
              </span>
              <span v-if="task.assigned_to_name" class="text-gray-400">👤 {{ task.assigned_to_name }}</span>
            </div>
            <div v-if="(task.tags ?? []).length > 0" class="flex flex-wrap gap-1 mt-1.5">
              <span v-for="tag in (task.tags ?? []).slice(0, 2)" :key="tag" class="px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-xs">🏷 {{ tag }}</span>
            </div>
          </div>
          <!-- Empty state -->
          <div v-if="tasksByStatus(col.key).length === 0" class="text-center py-6 text-xs text-gray-400">
            {{ t('tasks.dropHere') }}
          </div>
        </div>
      </div>
    </div>

    <!-- ======================================================= -->
    <!-- GANTT VIEW                                               -->
    <!-- ======================================================= -->
    <div v-if="displayMode === 'gantt' && tabMode === 'active'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
      <GanttView
        :tasks="tasks"
        @task-date-change="(id, start, end) => tasksStore.updateTask(id, { due_date: start + 'T00:00:00Z', due_date_end: end + 'T00:00:00Z' })"
      />
    </div>

    <!-- ======================================================= -->
    <!-- TABLE VIEW                                               -->
    <!-- ======================================================= -->
    <div v-if="displayMode === 'table' && tabMode === 'active'">
      <TaskTableView
        :tasks="tasks"
        :on-update-task="(id, payload) => tasksStore.updateTask(id, payload)"
        @refresh="loadTasks"
      />
    </div>

    <!-- ======================================================= -->
    <!-- NEW TASK MODAL                                           -->
    <!-- ======================================================= -->
    <Teleport to="body">
      <div
        v-if="showNewTask"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="showNewTask = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4 overflow-y-auto max-h-[90vh]">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.newTask') }}</h2>

          <div v-if="newTaskError" class="text-sm text-red-600 bg-red-50 dark:bg-red-900/30 rounded-xl px-3 py-2">
            {{ newTaskError }}
          </div>

          <!-- Lead (optional) -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.lead') }} <span class="text-gray-400">({{ t('tasks.optional') }})</span></label>
            <select
              v-model="newTaskLeadId"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
            >
              <option value="">{{ t('tasks.selectLead') }}</option>
              <option v-for="l in leads" :key="l.id" :value="l.id">{{ l.title }}</option>
            </select>
          </div>

          <!-- Title -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.taskTitle') }}</label>
            <input
              v-model="newTaskTitle"
              type="text"
              :placeholder="t('tasks.taskTitle')"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.description') }}</label>
            <textarea
              v-model="newTaskDescription"
              rows="2"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
            />
          </div>

          <!-- Priority + Status row -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.priority') }}</label>
              <select
                v-model="newTaskPriority"
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
                v-model="newTaskStatus"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              >
                <option value="todo">{{ t('tasks.statusTodo') }}</option>
                <option value="in_progress">{{ t('tasks.statusInProgress') }}</option>
                <option value="blocked">{{ t('tasks.statusBlocked') }}</option>
              </select>
            </div>
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.tags') }} <span class="text-gray-400">({{ t('tasks.tagsHint') }})</span></label>
            <input
              v-model="newTaskTags"
              type="text"
              :placeholder="t('tasks.tagsPlaceholder')"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Due date + Assignee row -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.deadline') }}</label>
              <input
                v-model="newTaskDueDate"
                type="date"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.assignee') }}</label>
              <select
                v-model="newTaskAssigneeId"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              >
                <option value="">{{ t('tasks.noAssignee') }}</option>
                <option v-for="m in members" :key="m.user_id" :value="m.user_id">
                  {{ memberLabel(m) }}
                </option>
              </select>
            </div>
          </div>

          <!-- Watchers -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.watchers') }}</label>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="m in members"
                :key="m.user_id"
                class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
                :class="newTaskWatcherIds.includes(m.user_id)
                  ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
              >
                <input
                  type="checkbox"
                  class="hidden"
                  :checked="newTaskWatcherIds.includes(m.user_id)"
                  @change="toggleWatcher(newTaskWatcherIds, m.user_id)"
                />
                🔔 {{ memberLabel(m) }}
              </label>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="showNewTask = false"
            >
              {{ t('tasks.cancel') }}
            </button>
            <button
              :disabled="newTaskSubmitting"
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="submitNewTask"
            >
              {{ newTaskSubmitting ? t('tasks.creating') : t('tasks.create') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ======================================================= -->
    <!-- EDIT TASK MODAL                                          -->
    <!-- ======================================================= -->
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

          <!-- Description -->
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

          <!-- Due date + Assignee -->
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

    <!-- ======================================================= -->
    <!-- FOLLOW-UP MODAL                                          -->
    <!-- ======================================================= -->
    <Teleport to="body">
      <div
        v-if="showFollowUp"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="showFollowUp = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.completeTask') }}</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('tasks.followUpPrompt') }}</p>

          <!-- Follow-up title -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.followUpTitle') }}</label>
            <input
              v-model="followUpTitle"
              type="text"
              :placeholder="t('tasks.followUpTitlePlaceholder')"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Follow-up description -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.description') }}</label>
            <textarea
              v-model="followUpDescription"
              rows="2"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
            />
          </div>

          <!-- Due date + Assignee -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.deadline') }}</label>
              <input
                v-model="followUpDueDate"
                type="date"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.assignee') }}</label>
              <select
                v-model="followUpAssigneeId"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              >
                <option value="">{{ t('tasks.noAssignee') }}</option>
                <option v-for="m in members" :key="m.user_id" :value="m.user_id">
                  {{ memberLabel(m) }}
                </option>
              </select>
            </div>
          </div>

          <!-- Watchers -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.watchers') }}</label>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="m in members"
                :key="m.user_id"
                class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
                :class="followUpWatcherIds.includes(m.user_id)
                  ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
              >
                <input
                  type="checkbox"
                  class="hidden"
                  :checked="followUpWatcherIds.includes(m.user_id)"
                  @change="toggleWatcher(followUpWatcherIds, m.user_id)"
                />
                🔔 {{ memberLabel(m) }}
              </label>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex justify-between gap-2 pt-2 flex-wrap">
            <button
              class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
              :disabled="followUpSubmitting"
              @click="completeWithoutFollowUp"
            >
              {{ t('tasks.completeOnly') }}
            </button>
            <div class="flex gap-2">
              <button
                class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                @click="showFollowUp = false"
              >
                {{ t('tasks.cancel') }}
              </button>
              <button
                :disabled="followUpSubmitting || !followUpTitle.trim()"
                class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                @click="completeWithFollowUp"
              >
                {{ followUpSubmitting ? t('tasks.creating') : t('tasks.createFollowUp') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

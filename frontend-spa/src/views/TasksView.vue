<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useTasksStore, type TaskOut, type FollowUpTaskIn } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

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
  })
}

watch([viewMode, selectedUserId, showCompleted], () => loadTasks())

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
const newTaskSubmitting = ref(false)
const newTaskError = ref('')

function openNewTask() {
  newTaskLeadId.value = ''
  newTaskTitle.value = ''
  newTaskDescription.value = ''
  newTaskDueDate.value = ''
  newTaskAssigneeId.value = authStore.user ? String(authStore.user.id) : ''
  newTaskWatcherIds.value = []
  newTaskError.value = ''
  showNewTask.value = true
}

async function submitNewTask() {
  if (!newTaskLeadId.value) { newTaskError.value = 'Please select a lead.'; return }
  if (!newTaskTitle.value.trim()) { newTaskError.value = 'Title is required.'; return }
  newTaskSubmitting.value = true
  newTaskError.value = ''
  const result = await tasksStore.createTask({
    lead_id: newTaskLeadId.value,
    title: newTaskTitle.value.trim(),
    description: newTaskDescription.value,
    assigned_to_id: newTaskAssigneeId.value || null,
    watcher_ids: newTaskWatcherIds.value,
    due_date: newTaskDueDate.value ? new Date(newTaskDueDate.value).toISOString() : null,
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
const editSubmitting = ref(false)
const editError = ref('')

function openEditTask(task: TaskOut) {
  editingTask.value = task
  editTitle.value = task.title
  editDescription.value = task.description
  editDueDate.value = task.due_date ? task.due_date.split('T')[0] : ''
  editAssigneeId.value = task.assigned_to_id ?? ''
  editWatcherIds.value = [...task.watcher_ids]
  editError.value = ''
  showEditTask.value = true
}

async function submitEditTask() {
  if (!editTitle.value.trim()) { editError.value = 'Title is required.'; return }
  if (!editingTask.value) return
  editSubmitting.value = true
  editError.value = ''
  const result = await tasksStore.updateTask(editingTask.value.id, {
    title: editTitle.value.trim(),
    description: editDescription.value,
    assigned_to_id: editAssigneeId.value || null,
    watcher_ids: editWatcherIds.value,
    due_date: editDueDate.value ? new Date(editDueDate.value).toISOString() : null,
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

      <!-- Show completed toggle -->
      <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer ml-auto">
        <input type="checkbox" v-model="showCompleted" class="rounded" />
        {{ t('tasks.showCompleted') }}
      </label>
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
    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="flex items-start gap-3 p-4"
        :class="task.is_completed ? 'opacity-60' : ''"
      >
        <!-- Complete checkbox -->
        <button
          class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors mt-0.5"
          :class="task.is_completed
            ? 'bg-green-500 border-green-500 text-white cursor-default'
            : 'border-gray-300 hover:border-green-400'"
          :disabled="task.is_completed"
          :title="task.is_completed ? '' : t('tasks.complete')"
          @click="!task.is_completed && startComplete(task)"
        >
          <span v-if="task.is_completed" class="text-xs">✓</span>
        </button>

        <!-- Task info -->
        <div class="flex-1 min-w-0">
          <p
            class="text-sm font-medium text-gray-900 dark:text-gray-100"
            :class="task.is_completed ? 'line-through text-gray-400' : ''"
          >
            {{ task.title }}
          </p>
          <p v-if="task.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
            {{ task.description }}
          </p>
          <div class="flex flex-wrap gap-3 mt-1 text-xs">
            <!-- Lead link -->
            <RouterLink
              :to="`/app/leads/${task.lead_id}`"
              class="text-blue-500 hover:underline truncate max-w-[200px]"
            >
              {{ task.lead_title || task.lead_id }}
            </RouterLink>
            <!-- Assignee -->
            <span v-if="task.assigned_to_name" class="text-gray-500 dark:text-gray-400">
              👤 {{ task.assigned_to_name }}
            </span>
            <!-- Due date -->
            <span
              v-if="task.due_date"
              :class="isOverdue(task) ? 'text-red-500 font-semibold' : 'text-gray-400'"
            >
              📅 {{ formatDate(task.due_date) }}
              <span v-if="isOverdue(task)" class="ml-1">({{ t('tasks.overdue') }})</span>
            </span>
            <!-- Watchers -->
            <span v-if="task.watcher_ids.length" class="text-gray-400 dark:text-gray-500">
              🔔 {{ task.watcher_ids.length }}
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

    <!-- ======================================================= -->
    <!-- NEW TASK MODAL                                           -->
    <!-- ======================================================= -->
    <Teleport to="body">
      <div
        v-if="showNewTask"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="showNewTask = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.newTask') }}</h2>

          <div v-if="newTaskError" class="text-sm text-red-600 bg-red-50 dark:bg-red-900/30 rounded-xl px-3 py-2">
            {{ newTaskError }}
          </div>

          <!-- Lead -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.lead') }}</label>
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
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4">
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

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import listPlugin from '@fullcalendar/list'
import interactionPlugin from '@fullcalendar/interaction'
import type { CalendarOptions, EventInput, DateSelectArg, EventClickArg } from '@fullcalendar/core'
import { useTasksStore } from '@/stores/tasks'
import { useLeadsStore } from '@/stores/leads'
import { useFirmStore } from '@/stores/firm'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'

const tasksStore = useTasksStore()
const leadsStore = useLeadsStore()
const firmStore = useFirmStore()
const toast = useToast()

// New task form (triggered by clicking a date)
const showNewTaskModal = ref(false)
const newTaskTitle = ref('')
const newTaskDueDate = ref('')
const newTaskLeadId = ref('')
const taskFormLoading = ref(false)
const taskFormError = ref('')

interface LeadOption { id: string; title: string }
const leadOptions = ref<LeadOption[]>([])

// User filter
interface MemberOption { id: string; label: string }
const members = ref<MemberOption[]>([])
const filterUserId = ref<string>('')

const filteredTasks = computed(() => {
  if (!filterUserId.value) return tasksStore.tasks
  return tasksStore.tasks.filter((t) => t.assigned_to_id === filterUserId.value)
})

const events = computed<EventInput[]>(() => {
  return filteredTasks.value
    .filter((t) => t.due_date)
    .map((t) => ({
      id: t.id,
      title: t.title,
      start: t.due_date!,
      allDay: true,
      backgroundColor: t.is_completed ? '#22c55e' : (new Date(t.due_date!) < new Date() ? '#ef4444' : '#3b82f6'),
      borderColor: 'transparent',
      textColor: '#fff',
      extendedProps: { task: t },
    }))
})

const calendarOptions = computed<CalendarOptions>(() => ({
  plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,listWeek',
  },
  events: events.value,
  selectable: true,
  select: handleDateSelect,
  eventClick: handleEventClick,
  height: 'auto',
}))

function handleDateSelect(info: DateSelectArg) {
  newTaskDueDate.value = info.startStr
  newTaskTitle.value = ''
  newTaskLeadId.value = ''
  taskFormError.value = ''
  showNewTaskModal.value = true
}

function handleEventClick(info: EventClickArg) {
  const task = info.event.extendedProps['task'] as { is_completed: boolean } | undefined
  if (task && !task.is_completed) {
    tasksStore.completeTask(info.event.id).then((r) => {
      if (!r.ok) toast.error(r.error ?? 'Failed to complete task.')
      else toast.success('Task marked complete!')
    })
  }
}

async function submitNewTask() {
  if (!newTaskTitle.value.trim()) { taskFormError.value = 'Title is required.'; return }
  if (!newTaskLeadId.value) { taskFormError.value = 'Please select a lead.'; return }
  taskFormLoading.value = true
  taskFormError.value = ''
  const result = await tasksStore.createTask({
    lead_id: newTaskLeadId.value,
    title: newTaskTitle.value.trim(),
    due_date: newTaskDueDate.value ? new Date(newTaskDueDate.value).toISOString() : null,
  })
  taskFormLoading.value = false
  if (result.ok) {
    showNewTaskModal.value = false
    toast.success('Task created.')
  } else {
    taskFormError.value = result.error ?? 'Failed to create task.'
  }
}

const overdueCount = computed(() => filteredTasks.value.filter((t) => !t.is_completed && t.due_date && new Date(t.due_date) < new Date()).length)
const upcomingTasks = computed(() => {
  const now = new Date()
  const next7 = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  return filteredTasks.value.filter((t) => !t.is_completed && t.due_date && new Date(t.due_date) >= now && new Date(t.due_date) <= next7)
})

onMounted(async () => {
  await tasksStore.fetchTasks({ completed: false })
  // Load leads for the task creation form
  const res = await api.get<LeadOption[]>('/api/v1/crm/leads?page_size=100')
  if (res.ok) leadOptions.value = res.data
  // Load team members for user filter
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (firmId) {
    const mRes = await api.get<{ id: string; user_id: string; user_full_name: string }[]>(`/api/v1/firms/${firmId}/members`)
    if (mRes.ok) {
      members.value = mRes.data.map((m) => ({ id: m.user_id, label: m.user_full_name || m.user_id }))
    }
  }
})
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Stats row -->
    <div class="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-5">
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Overdue Tasks</div>
        <div class="text-2xl font-bold" :class="overdueCount > 0 ? 'text-red-600' : 'text-gray-400 dark:text-gray-500'">{{ overdueCount }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Due This Week</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ upcomingTasks.length }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 col-span-2 lg:col-span-1">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Open</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ filteredTasks.filter(t => !t.is_completed).length }}</div>
      </div>
    </div>

    <!-- User filter -->
    <div v-if="members.length > 1" class="flex items-center gap-2 mb-4">
      <label class="text-xs font-medium text-gray-500 dark:text-gray-400 flex-shrink-0">Filter by user:</label>
      <select
        v-model="filterUserId"
        class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400"
      >
        <option value="">All users</option>
        <option v-for="m in members" :key="m.id" :value="m.id">{{ m.label }}</option>
      </select>
    </div>

    <!-- Calendar -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
      <div v-if="tasksStore.loading" class="animate-pulse h-64 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      <FullCalendar v-else :options="calendarOptions" />
    </div>

    <!-- Upcoming tasks panel -->
    <div v-if="upcomingTasks.length > 0" class="mt-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Upcoming (next 7 days)</h3>
      <div class="space-y-2">
        <div v-for="task in upcomingTasks" :key="task.id" class="flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50">
          <button
            class="w-5 h-5 rounded border border-gray-300 dark:border-gray-600 hover:border-green-400 flex-shrink-0 flex items-center justify-center"
            :aria-label="`Complete task: ${task.title}`"
            @click="tasksStore.completeTask(task.id)"
          >
            <span class="text-xs text-transparent hover:text-green-500" aria-hidden="true">✓</span>
          </button>
          <span class="text-sm text-gray-800 dark:text-gray-200 flex-1">{{ task.title }}</span>
          <span class="text-xs text-gray-400 dark:text-gray-500">{{ task.due_date ? new Date(task.due_date).toLocaleDateString() : '' }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- New Task Modal -->
  <Teleport to="body">
    <div v-if="showNewTaskModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showNewTaskModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6" role="dialog" aria-modal="true" aria-labelledby="new-task-title">
        <h3 id="new-task-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">New Task</h3>
        <div v-if="taskFormError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ taskFormError }}</div>
        <form class="space-y-3" @submit.prevent="submitNewTask">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Title *</label>
            <input v-model="newTaskTitle" type="text" required autofocus class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Lead *</label>
            <select v-model="newTaskLeadId" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
              <option value="">Select a lead…</option>
              <option v-for="l in leadOptions" :key="l.id" :value="l.id">{{ l.title }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Due Date</label>
            <input v-model="newTaskDueDate" type="date" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300" @click="showNewTaskModal = false">Cancel</button>
            <button type="submit" :disabled="taskFormLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ taskFormLoading ? 'Creating…' : 'Create' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

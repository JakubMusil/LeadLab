<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import listPlugin from '@fullcalendar/list'
import interactionPlugin from '@fullcalendar/interaction'
import type { CalendarOptions, EventInput, DateSelectArg, EventClickArg } from '@fullcalendar/core'
import { useTasksStore, type TaskOut } from '@/stores/tasks'
import { useFirmStore } from '@/stores/firm'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import TaskOutcomeModal from '@/components/TaskOutcomeModal.vue'

const router = useRouter()
const tasksStore = useTasksStore()
const firmStore = useFirmStore()
const toast = useToast()
const { t } = useI18n()

// ── Constants ─────────────────────────────────────────────────────────────────
const TOOLTIP_WIDTH = 272

// ── User color palette (Google Calendar–inspired) ─────────────────────────────
const USER_COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#f59e0b', // amber
  '#10b981', // emerald
  '#ef4444', // red
  '#06b6d4', // cyan
  '#f97316', // orange
]

// ── Team members ──────────────────────────────────────────────────────────────
interface MemberOption { id: string; label: string }
const members = ref<MemberOption[]>([])
// Empty set = show all users; non-empty = show only selected users
const activeUserIds = ref<Set<string>>(new Set())

const userColorMap = computed(() => {
  const map = new Map<string, string>()
  members.value.forEach((m, i) => map.set(m.id, USER_COLORS[i % USER_COLORS.length] ?? '#6b7280'))
  return map
})

function getUserColor(userId: string | null): string {
  if (!userId) return '#6b7280'
  return userColorMap.value.get(userId) ?? '#6b7280'
}

function toggleUser(id: string) {
  const next = new Set(activeUserIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  activeUserIds.value = next
}

function isUserActive(id: string): boolean {
  return activeUserIds.value.size === 0 || activeUserIds.value.has(id)
}

function showAllUsers() {
  activeUserIds.value = new Set()
}

// ── Task visibility ───────────────────────────────────────────────────────────
const showCompleted = ref(false)

const filteredTasks = computed(() => {
  let list = tasksStore.tasks
  if (!showCompleted.value) list = list.filter((t) => !t.is_completed)
  if (activeUserIds.value.size > 0) {
    list = list.filter((t) => t.assigned_to_id && activeUserIds.value.has(t.assigned_to_id))
  }
  return list
})

// ── Calendar events ───────────────────────────────────────────────────────────
const events = computed<EventInput[]>(() =>
  filteredTasks.value
    .filter((t) => t.due_date)
    .map((t) => {
      const isoStr = t.due_date!
      const endIso = t.due_date_end ?? null
      // Treat as all-day if the time component is midnight UTC or absent
      const isAllDay = /T00:00:00/.test(isoStr) || !isoStr.includes('T')
      // PR4: visual differentiation for expired / prompted tasks so the
      // user spots overdue calendar items at a glance.
      const isExpired = t.status === 'expired'
      const isPrompted = !t.is_completed && !!t.outcome_prompted_at && !isExpired
      let color: string
      const classNames: string[] = []
      if (t.is_completed) {
        color = '#22c55e'
        classNames.push('fc-event-completed')
      } else if (isExpired) {
        color = '#9ca3af' // gray-400
        classNames.push('fc-event-expired')
      } else if (isPrompted) {
        color = '#f59e0b' // amber-500
        classNames.push('fc-event-prompted')
      } else {
        color = getUserColor(t.assigned_to_id)
      }
      return {
        id: t.id,
        title: t.title,
        start: isoStr,
        // FullCalendar treats events with no end as point-in-time; using
        // ``due_date_end`` lets meeting/call slots span their actual length.
        end: endIso ?? undefined,
        allDay: isAllDay,
        backgroundColor: color,
        borderColor: color,
        textColor: '#fff',
        classNames,
        extendedProps: { task: t },
      }
    }),
)

// ── FullCalendar options ──────────────────────────────────────────────────────
const calendarOptions = computed<CalendarOptions>(() => ({
  plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
  initialView: 'timeGridWeek',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay,listWeek',
  },
  buttonText: {
    today: t('calendar.today'),
    month: t('calendar.viewMonth'),
    week: t('calendar.viewWeek'),
    day: t('calendar.viewDay'),
    list: t('calendar.viewList'),
  },
  events: events.value,
  selectable: true,
  select: handleDateSelect,
  eventClick: handleEventClick,
  eventMouseEnter: handleEventMouseEnter,
  eventMouseLeave: handleEventMouseLeave,
  height: 'auto',
  slotMinTime: '07:00:00',
  slotMaxTime: '21:00:00',
  nowIndicator: true,
  allDaySlot: true,
  eventClassNames: 'cursor-pointer',
}))

// ── Hover tooltip ─────────────────────────────────────────────────────────────
const tooltipTask = ref<TaskOut | null>(null)
const tooltipTop = ref(0)
const tooltipLeft = ref(0)
const showTooltip = ref(false)

function handleEventMouseEnter(info: { event: { extendedProps: Record<string, unknown> }; el: HTMLElement }) {
  const task = info.event.extendedProps['task'] as TaskOut
  tooltipTask.value = task
  const rect = info.el.getBoundingClientRect()
  tooltipTop.value = rect.bottom + 8
  tooltipLeft.value = Math.min(rect.left, window.innerWidth - TOOLTIP_WIDTH)
  showTooltip.value = true
}

function handleEventMouseLeave() {
  showTooltip.value = false
}

// ── Task detail modal ─────────────────────────────────────────────────────────
const selectedTask = ref<TaskOut | null>(null)
const showTaskDetail = ref(false)
const completeLoading = ref(false)

function handleEventClick(info: EventClickArg) {
  selectedTask.value = info.event.extendedProps['task'] as TaskOut
  showTaskDetail.value = true
  showTooltip.value = false
}

async function completeSelectedTask() {
  if (!selectedTask.value) return
  completeLoading.value = true
  const r = await tasksStore.completeTask(selectedTask.value.id)
  completeLoading.value = false
  if (r.ok) {
    toast.success(t('calendar.taskComplete'))
    showTaskDetail.value = false
  } else {
    toast.error(r.error ?? t('calendar.failedToComplete'))
  }
}

// ── PR4: outcome prompt for calendar tasks ───────────────────────────────────
const showOutcomeModal = ref(false)

/** True iff the open modal's task is awaiting outcome resolution
 *  (calendar kind, prompted by the auto-expire job, not yet resolved). */
const selectedNeedsOutcome = computed(() => {
  const tt = selectedTask.value
  if (!tt) return false
  if (tt.is_completed || tt.status === 'expired' || tt.status === 'done' || tt.status === 'cancelled') return false
  if (!tt.outcome_prompted_at) return false
  return tt.kind === 'call' || tt.kind === 'meeting'
})

function isExpired(task: TaskOut): boolean {
  return task.status === 'expired'
}

function openOutcomeModal() {
  if (!selectedTask.value) return
  showOutcomeModal.value = true
}

function onOutcomeResolved(updated: TaskOut) {
  selectedTask.value = updated
  showOutcomeModal.value = false
  showTaskDetail.value = false
}

function goToTaskDetail() {
  if (!selectedTask.value) return
  router.push(`/app/tasks/${selectedTask.value.id}`)
}

function formatDateTime(isoStr: string | null): string {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  const isAllDay = /T00:00:00/.test(isoStr) || !isoStr.includes('T')
  if (isAllDay) {
    return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
  }
  return d.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function isOverdue(task: TaskOut): boolean {
  return !task.is_completed && !!task.due_date && new Date(task.due_date) < new Date()
}

// ── New task modal ────────────────────────────────────────────────────────────
const showNewTaskModal = ref(false)
const newTaskTitle = ref('')
const newTaskDate = ref('')
const newTaskTime = ref('')
const newTaskLeadId = ref('')
const newTaskAssigneeId = ref('')
const newTaskDescription = ref('')
const taskFormLoading = ref(false)
const taskFormError = ref('')

interface LeadOption { id: string; title: string }
const leadOptions = ref<LeadOption[]>([])

function openNewTaskModal(dateStr?: string, timeStr?: string) {
  newTaskDate.value = dateStr ?? new Date().toISOString().slice(0, 10)
  newTaskTime.value = timeStr ?? ''
  newTaskTitle.value = ''
  newTaskLeadId.value = ''
  newTaskAssigneeId.value = ''
  newTaskDescription.value = ''
  taskFormError.value = ''
  showNewTaskModal.value = true
}

function handleDateSelect(info: DateSelectArg) {
  const start = new Date(info.startStr)
  const dateStr = start.toISOString().slice(0, 10)
  const h = start.getHours()
  const m = start.getMinutes()
  const timeStr = info.allDay ? '' : `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
  openNewTaskModal(dateStr, timeStr)
}

async function submitNewTask() {
  if (!newTaskTitle.value.trim()) { taskFormError.value = t('calendar.titleRequired'); return }
  if (!newTaskLeadId.value) { taskFormError.value = t('calendar.leadRequired'); return }
  taskFormLoading.value = true
  taskFormError.value = ''

  let dueDate: string | null = null
  if (newTaskDate.value) {
    const dt = newTaskTime.value
      ? new Date(`${newTaskDate.value}T${newTaskTime.value}:00`)
      : new Date(newTaskDate.value)
    dueDate = dt.toISOString()
  }

  const result = await tasksStore.createTask({
    lead_id: newTaskLeadId.value,
    title: newTaskTitle.value.trim(),
    description: newTaskDescription.value.trim() || undefined,
    assigned_to_id: newTaskAssigneeId.value || null,
    due_date: dueDate,
  })
  taskFormLoading.value = false
  if (result.ok) {
    showNewTaskModal.value = false
    toast.success(t('calendar.taskCreated'))
  } else {
    taskFormError.value = result.error ?? t('calendar.failedToCreate')
  }
}

// ── Stats ─────────────────────────────────────────────────────────────────────
const overdueCount = computed(() =>
  tasksStore.tasks.filter((t) => !t.is_completed && t.due_date && new Date(t.due_date) < new Date()).length,
)
const upcomingCount = computed(() => {
  const now = new Date()
  const next7 = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  return tasksStore.tasks.filter(
    (t) => !t.is_completed && t.due_date && new Date(t.due_date) >= now && new Date(t.due_date) <= next7,
  ).length
})
const openCount = computed(() => tasksStore.tasks.filter((t) => !t.is_completed).length)

// ── Mount ─────────────────────────────────────────────────────────────────────
onMounted(async () => {
  // Load all tasks (completed + open) so the calendar is complete
  await tasksStore.fetchTasks({})
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  const [leadsRes, membersRes] = await Promise.all([
    api.get<LeadOption[]>('/api/v1/crm/opportunities?page_size=100'),
    firmId
      ? api.get<{ id: string; user_id: string; user_full_name: string }[]>(`/api/v1/firms/${firmId}/members`)
      : Promise.resolve({ ok: false as const, data: [] }),
  ])
  if (leadsRes.ok) leadOptions.value = leadsRes.data
  if (membersRes.ok && Array.isArray(membersRes.data)) {
    members.value = (
      membersRes.data as { id: string; user_id: string; user_full_name: string }[]
    ).map((m) => ({ id: m.user_id, label: m.user_full_name || m.user_id }))
  }
})
</script>

<template>
  <div class="p-4 lg:p-6">
    <!-- Header row: title + Add Task button -->
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ t('calendar.title') }}</h1>
      <button
        class="inline-flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-xl transition-colors"
        @click="openNewTaskModal()"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        {{ t('calendar.addTask') }}
      </button>
    </div>

    <!-- Stats row -->
    <div class="grid grid-cols-3 gap-3 mb-5">
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('calendar.overdueTasks') }}</div>
        <div class="text-2xl font-bold" :class="overdueCount > 0 ? 'text-red-600' : 'text-gray-400 dark:text-gray-500'">{{ overdueCount }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('calendar.dueThisWeek') }}</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ upcomingCount }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
        <div class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('calendar.totalOpen') }}</div>
        <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ openCount }}</div>
      </div>
    </div>

    <!-- People filter chips + show-completed toggle -->
    <div class="flex flex-wrap items-center gap-2 mb-4">
      <!-- "All" chip -->
      <button
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
        :class="activeUserIds.size === 0
          ? 'bg-gray-800 text-white border-gray-800 dark:bg-gray-200 dark:text-gray-900 dark:border-gray-200'
          : 'bg-white text-gray-600 border-gray-200 hover:border-gray-400 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600'"
        @click="showAllUsers"
      >
        {{ t('calendar.allUsers') }}
      </button>

      <!-- Per-user chips -->
      <button
        v-for="m in members"
        :key="m.id"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
        :style="isUserActive(m.id)
          ? { backgroundColor: getUserColor(m.id), borderColor: getUserColor(m.id), color: '#fff' }
          : { backgroundColor: 'transparent', borderColor: getUserColor(m.id), color: getUserColor(m.id) }"
        @click="toggleUser(m.id)"
      >
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :style="{ backgroundColor: isUserActive(m.id) ? '#fff' : getUserColor(m.id) }"
        />
        {{ m.label }}
      </button>

      <div class="h-5 w-px bg-gray-200 dark:bg-gray-600 mx-1" />

      <!-- Show/hide completed toggle -->
      <button
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
        :class="showCompleted
          ? 'bg-emerald-600 text-white border-emerald-600'
          : 'bg-white text-gray-500 border-gray-200 hover:border-gray-400 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-600'"
        @click="showCompleted = !showCompleted"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        {{ showCompleted ? t('calendar.hideCompleted') : t('calendar.showCompleted') }}
      </button>
    </div>

    <!-- Calendar -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
      <div v-if="tasksStore.loading" class="animate-pulse h-[600px] bg-gray-100 dark:bg-gray-700 rounded-xl m-4" />
      <FullCalendar v-else :options="calendarOptions" class="fc-leadlab" />
    </div>
  </div>

  <!-- ── Hover tooltip ─────────────────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="showTooltip && tooltipTask"
      class="fixed z-[9999] pointer-events-none w-64 bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 p-3 text-sm"
      :style="{ top: tooltipTop + 'px', left: tooltipLeft + 'px' }"
    >
      <p class="font-semibold text-gray-900 dark:text-gray-100 mb-1.5 leading-snug">{{ tooltipTask.title }}</p>
      <div class="space-y-1 text-xs text-gray-500 dark:text-gray-400">
        <div v-if="tooltipTask.lead_title" class="flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {{ tooltipTask.lead_title }}
        </div>
        <div v-if="tooltipTask.assigned_to_name" class="flex items-center gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          {{ tooltipTask.assigned_to_name }}
        </div>
        <div v-if="tooltipTask.due_date" class="flex items-center gap-1.5" :class="isOverdue(tooltipTask) ? 'text-red-500' : ''">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          {{ formatDateTime(tooltipTask.due_date) }}
        </div>
        <div class="flex items-center gap-1.5 mt-1.5 pt-1.5 border-t border-gray-100 dark:border-gray-700">
          <span
            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
            :class="tooltipTask.is_completed
              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400'
              : isOverdue(tooltipTask)
                ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
                : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400'"
          >
            {{ tooltipTask.is_completed ? t('calendar.statusCompleted') : isOverdue(tooltipTask) ? t('calendar.overdueTasks') : t('calendar.statusOpen') }}
          </span>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── Task detail modal ──────────────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="showTaskDetail && selectedTask"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      @click.self="showTaskDetail = false"
    >
      <div
        class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
        role="dialog"
        aria-modal="true"
      >
        <!-- Modal header -->
        <div class="flex items-start justify-between p-5 pb-3">
          <div class="flex-1 min-w-0 pr-3">
            <div class="flex items-center gap-2 mb-1">
              <span
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                :class="selectedTask.is_completed
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400'
                  : isExpired(selectedTask)
                    ? 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                    : selectedNeedsOutcome
                      ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400'
                      : isOverdue(selectedTask)
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
                        : 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400'"
              >
                {{ selectedTask.is_completed
                  ? t('calendar.statusCompleted')
                  : isExpired(selectedTask)
                    ? t('calendar.statusExpired')
                    : selectedNeedsOutcome
                      ? t('calendar.outcomePending')
                      : isOverdue(selectedTask)
                        ? t('calendar.overdueTasks')
                        : t('calendar.statusOpen') }}
              </span>
              <span
                v-if="selectedTask.kind === 'call' || selectedTask.kind === 'meeting'"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300"
              >
                {{ selectedTask.kind === 'call' ? t('calendar.kindCall') : t('calendar.kindMeeting') }}
              </span>
            </div>
            <h2 class="text-lg font-bold text-gray-900 dark:text-gray-100 leading-tight">{{ selectedTask.title }}</h2>
          </div>
          <button
            class="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1 rounded-lg"
            :aria-label="t('calendar.cancel')"
            @click="showTaskDetail = false"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Task meta -->
        <div class="px-5 pb-4 space-y-2.5">
          <div v-if="selectedTask.lead_title" class="flex items-center gap-3 text-sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span class="text-gray-500 dark:text-gray-400 w-20 flex-shrink-0">{{ t('calendar.lead') }}</span>
            <span class="text-gray-900 dark:text-gray-100 font-medium">{{ selectedTask.lead_title }}</span>
          </div>
          <div class="flex items-center gap-3 text-sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span class="text-gray-500 dark:text-gray-400 w-20 flex-shrink-0">{{ t('calendar.assignee') }}</span>
            <span class="text-gray-900 dark:text-gray-100">{{ selectedTask.assigned_to_name ?? t('calendar.unassigned') }}</span>
          </div>
          <div v-if="selectedTask.due_date" class="flex items-center gap-3 text-sm">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span class="text-gray-500 dark:text-gray-400 w-20 flex-shrink-0">{{ t('calendar.dueDate') }}</span>
            <span
              class="font-medium"
              :class="isOverdue(selectedTask) ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'"
            >{{ formatDateTime(selectedTask.due_date) }}</span>
          </div>
          <div v-if="selectedTask.description" class="flex items-start gap-3 text-sm pt-1">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h7" />
            </svg>
            <span class="text-gray-500 dark:text-gray-400 w-20 flex-shrink-0">{{ t('calendar.description') }}</span>
            <span class="text-gray-700 dark:text-gray-300 leading-relaxed">{{ selectedTask.description }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex gap-2 px-5 pb-5">
          <button
            v-if="selectedNeedsOutcome"
            class="flex-1 inline-flex items-center justify-center gap-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
            @click="openOutcomeModal"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {{ t('calendar.logOutcome') }}
          </button>
          <button
            v-else-if="!selectedTask.is_completed && !isExpired(selectedTask)"
            :disabled="completeLoading"
            class="flex-1 inline-flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
            @click="completeSelectedTask"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            {{ completeLoading ? t('calendar.markingComplete') : t('calendar.markComplete') }}
          </button>
          <button
            class="flex-1 inline-flex items-center justify-center gap-2 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 text-sm font-medium px-4 py-2.5 rounded-xl transition-colors"
            @click="goToTaskDetail"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            {{ t('calendar.viewFullDetail') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- ── New Task Modal ──────────────────────────────────────────────────────── -->
  <Teleport to="body">
    <div
      v-if="showNewTaskModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      @click.self="showNewTaskModal = false"
    >
      <div
        class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-sm p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-task-dialog-title"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 id="new-task-dialog-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('calendar.newTask') }}</h3>
          <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1 rounded-lg" @click="showNewTaskModal = false">
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div
          v-if="taskFormError"
          class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400"
          role="alert"
        >
          {{ taskFormError }}
        </div>

        <form class="space-y-3" @submit.prevent="submitNewTask">
          <!-- Title -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('calendar.titleField') }}</label>
            <!-- eslint-disable-next-line vuejs-accessibility/no-autofocus -->
            <input
              v-model="newTaskTitle"
              type="text"
              required
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Lead -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('calendar.leadField') }}</label>
            <select
              v-model="newTaskLeadId"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            >
              <option value="">{{ t('calendar.selectLead') }}</option>
              <option v-for="l in leadOptions" :key="l.id" :value="l.id">{{ l.title }}</option>
            </select>
          </div>

          <!-- Assignee -->
          <div v-if="members.length > 0">
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('calendar.assigneeField') }}</label>
            <select
              v-model="newTaskAssigneeId"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            >
              <option value="">{{ t('calendar.unassigned') }}</option>
              <option v-for="m in members" :key="m.id" :value="m.id">{{ m.label }}</option>
            </select>
          </div>

          <!-- Date + Time row -->
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('calendar.dueDateField') }}</label>
              <input
                v-model="newTaskDate"
                type="date"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('calendar.timeField') }}</label>
              <input
                v-model="newTaskTime"
                type="time"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
          </div>

          <!-- Description -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('calendar.descriptionField') }}</label>
            <textarea
              v-model="newTaskDescription"
              rows="2"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
            />
          </div>

          <!-- Submit -->
          <div class="flex gap-3 pt-1">
            <button
              type="button"
              class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="showNewTaskModal = false"
            >
              {{ t('calendar.cancel') }}
            </button>
            <button
              type="submit"
              :disabled="taskFormLoading"
              class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60 transition-colors"
            >
              {{ taskFormLoading ? t('calendar.creating') : t('calendar.createTask') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- ── PR4: outcome prompt modal ─────────────────────────────────────────── -->
  <TaskOutcomeModal
    v-if="showOutcomeModal && selectedTask"
    :task="selectedTask"
    @close="showOutcomeModal = false"
    @resolved="onOutcomeResolved"
  />
</template>

<style>
/* Subtle opacity for completed events */
.fc-event-completed {
  opacity: 0.65;
}
/* PR4: expired calendar tasks — gray + line-through to signal "we gave up" */
.fc-event-expired {
  opacity: 0.6;
  text-decoration: line-through;
}
/* PR4: prompted-but-unresolved — amber dashed border to draw the eye */
.fc-event-prompted {
  outline: 2px dashed #d97706;
  outline-offset: -2px;
}
/* Remove default FullCalendar border radius for a cleaner look */
.fc-leadlab .fc-event {
  border-radius: 6px;
  font-size: 0.75rem;
  padding: 1px 4px;
}
.fc-leadlab .fc-daygrid-event {
  border-radius: 6px;
}
/* Dark mode FullCalendar adjustments */
.dark .fc-leadlab {
  color: #e5e7eb;
}
.dark .fc-leadlab .fc-col-header-cell,
.dark .fc-leadlab .fc-timegrid-slot-label,
.dark .fc-leadlab .fc-daygrid-day-number {
  color: #9ca3af;
}
.dark .fc-leadlab .fc-scrollgrid,
.dark .fc-leadlab .fc-scrollgrid-sync-table,
.dark .fc-leadlab td,
.dark .fc-leadlab th {
  border-color: #374151;
}
.dark .fc-leadlab .fc-timegrid-now-indicator-line {
  border-color: #ef4444;
}
.dark .fc-leadlab .fc-button {
  background-color: #374151;
  border-color: #4b5563;
  color: #e5e7eb;
}
.dark .fc-leadlab .fc-button:hover {
  background-color: #4b5563;
}
.dark .fc-leadlab .fc-button-active {
  background-color: #dc2626 !important;
  border-color: #dc2626 !important;
}
.dark .fc-leadlab .fc-today-button {
  background-color: #374151;
  border-color: #4b5563;
}
.dark .fc-leadlab .fc-daygrid-day.fc-day-today,
.dark .fc-leadlab .fc-timegrid-col.fc-day-today {
  background-color: rgba(239, 68, 68, 0.07);
}
</style>

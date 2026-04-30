<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import type { TaskOut } from '@/stores/tasks'
import { useI18n } from '@/composables/useI18n'

const props = defineProps<{
  tasks: TaskOut[]
}>()

const emit = defineEmits<{
  taskDateChange: [id: string, start: string, end: string]
}>()

const { t } = useI18n()
const ganttContainer = ref<HTMLDivElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let ganttInstance: any = null

type GanttViewMode = 'Quarter Day' | 'Day' | 'Week' | 'Month'
const viewMode = ref<GanttViewMode>('Week')

function toGanttTasks(tasks: TaskOut[]) {
  return tasks
    .filter((t) => t.due_date)
    .map((t) => {
      const rawStart = t.due_date_end ? t.due_date! : t.due_date!
      const rawEnd = t.due_date_end ?? t.due_date!
      const startMs = new Date(rawStart).getTime()
      const endMs = new Date(rawEnd).getTime()
      const start = (startMs <= endMs ? rawStart : rawEnd).split('T')[0]
      const end = (startMs <= endMs ? rawEnd : rawStart).split('T')[0]
      return {
        id: t.id,
        name: t.title,
        start,
        end,
        progress: t.is_completed ? 100 : t.status === 'in_progress' ? 40 : 0,
        dependencies: '',
        custom_class: t.is_completed
          ? 'gantt-bar-done'
          : t.status === 'blocked'
            ? 'gantt-bar-blocked'
            : '',
      }
    })
}

async function initGantt() {
  if (!ganttContainer.value) return
  const ganttTasks = toGanttTasks(props.tasks)
  if (ganttTasks.length === 0) return

  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const FrappeGantt = (await import('frappe-gantt')).default as any
    ganttContainer.value.innerHTML = ''
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    ganttContainer.value.appendChild(svg)
    ganttInstance = new FrappeGantt(svg, ganttTasks, {
      view_mode: viewMode.value,
      date_format: 'YYYY-MM-DD',
      language: 'en',
      on_date_change(task: { id: string; _start: Date; _end: Date }) {
        const start = task._start.toISOString().split('T')[0] ?? ''
        const end = task._end.toISOString().split('T')[0] ?? ''
        emit('taskDateChange', task.id, start, end)
      },
      on_progress_change() {},
      on_click() {},
      on_view_change() {},
      popup_trigger: 'click',
      custom_popup_html(task: { id: string; name: string }) {
        const found = props.tasks.find((tsk) => tsk.id === task.id)
        if (!found) return `<div class="details-container"><h5>${task.name}</h5></div>`
        return `
          <div class="details-container" style="padding:8px;min-width:160px;font-family:sans-serif">
            <p style="font-weight:600;margin:0 0 4px">${found.title}</p>
            <p style="font-size:11px;color:#666;margin:0 0 2px">${found.status} · ${found.priority}</p>
            ${found.assigned_to_name ? `<p style="font-size:11px;color:#888;margin:0">👤 ${found.assigned_to_name}</p>` : ''}
          </div>
        `
      },
    })
  } catch (e) {
    console.error('Failed to initialize Gantt chart:', e)
  }
}

function setViewMode(mode: GanttViewMode) {
  viewMode.value = mode
  if (ganttInstance) {
    ganttInstance.change_view_mode(mode)
  }
}

onMounted(async () => {
  await nextTick()
  await initGantt()
})

onUnmounted(() => {
  ganttInstance = null
})

watch(
  () => props.tasks.length,
  async () => {
    await nextTick()
    await initGantt()
  },
)
</script>

<template>
  <div class="gantt-wrapper">
    <!-- View mode controls -->
    <div class="flex items-center gap-2 mb-4 flex-wrap">
      <span class="text-sm font-medium text-gray-600 dark:text-gray-400">{{ t('tasks.ganttViewMode') }}:</span>
      <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1">
        <button
          v-for="mode in (['Quarter Day', 'Day', 'Week', 'Month'] as const)"
          :key="mode"
          class="px-3 py-1 rounded-lg text-xs font-medium transition-colors"
          :class="viewMode === mode
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
          @click="setViewMode(mode)"
        >{{ mode }}</button>
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="tasks.filter(t => t.due_date).length === 0"
      class="text-center py-16 text-gray-400 dark:text-gray-500 text-sm"
    >
      {{ t('tasks.ganttNoTasks') }}
    </div>

    <!-- Gantt chart container -->
    <div
      v-else
      ref="ganttContainer"
      class="gantt-container overflow-x-auto"
    />
  </div>
</template>

<style>
@import 'frappe-gantt/dist/frappe-gantt.css';

.gantt-container svg {
  min-width: 100%;
}

/* Custom bar colours */
.gantt .bar-wrapper.gantt-bar-done .bar {
  fill: #22c55e !important;
}
.gantt .bar-wrapper.gantt-bar-blocked .bar {
  fill: #ef4444 !important;
}

/* Dark mode */
.dark .gantt .grid-background { fill: #1f2937; }
.dark .gantt .grid-header     { fill: #111827; }
.dark .gantt .row-line,
.dark .gantt .tick             { stroke: #374151; }
.dark .gantt .lower-text,
.dark .gantt .upper-text       { fill: #9ca3af; }
</style>

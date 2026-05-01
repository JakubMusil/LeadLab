<script setup lang="ts">
/**
 * TaskCard — inline task card for the unified entity feed.
 *
 * Renders a Task as a rich card inside the ActivityTimeline feed so tasks
 * are visible in context alongside comments, calls, emails, etc.
 *
 * Props:
 *   task — full TaskOut object from the feed endpoint
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import { useTasksStore } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'
import {
  CheckCircleIcon,
  ClockIcon,
  UserIcon,
  Bars3BottomLeftIcon,
} from '@heroicons/vue/24/outline'
import { CheckCircleIcon as CheckCircleSolid } from '@heroicons/vue/24/solid'
import type { TaskOut } from '@/stores/tasks'

const props = defineProps<{
  task: TaskOut
}>()

const emit = defineEmits<{
  refreshed: []
}>()

const router = useRouter()
const { t } = useI18n()
const tasksStore = useTasksStore()
const toast = useToast()

// ---------------------------------------------------------------------------
// Computed helpers
// ---------------------------------------------------------------------------
const isOverdue = computed(() => {
  if (!props.task.due_date || props.task.is_completed) return false
  return new Date(props.task.due_date) < new Date()
})

const dueDateFormatted = computed(() => {
  if (!props.task.due_date) return null
  return new Date(props.task.due_date).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
  })
})

const PRIORITY_DOT: Record<string, string> = {
  none:     'bg-gray-300 dark:bg-gray-500',
  low:      'bg-blue-400',
  medium:   'bg-yellow-400',
  high:     'bg-orange-500',
  critical: 'bg-red-600',
}

const STATUS_LABEL: Record<string, string> = {
  todo:        '',
  in_progress: 'Probíhá',
  blocked:     'Blokováno',
  done:        'Hotovo',
  cancelled:   'Zrušeno',
  expired:     'Vypršelo',
}

const itemsProgress = computed(() => {
  const total = props.task.streamline_count ?? 0
  const done  = props.task.streamline_resolved ?? 0
  if (total === 0) return null
  return { total, done, pct: Math.round((done / total) * 100) }
})

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function toggleComplete() {
  if (props.task.is_completed) return
  const res = await tasksStore.completeTask(props.task.id)
  if (res.ok) emit('refreshed')
  else toast.error(res.error ?? t('tasks.completeFailed'))
}

function openDetail() {
  router.push(`/app/tasks/${props.task.id}`)
}
</script>

<template>
  <div
    class="mt-1.5 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 overflow-hidden"
    data-testid="task-card"
  >
    <!-- Header row -->
    <div class="flex items-start gap-2.5 px-3 pt-3 pb-2">
      <!-- Complete toggle -->
      <button
        class="mt-0.5 flex-shrink-0 transition-colors"
        :class="task.is_completed
          ? 'text-green-500 cursor-default'
          : 'text-gray-300 hover:text-green-500'"
        :disabled="task.is_completed"
        :title="task.is_completed ? t('tasks.completed') : t('tasks.markDone')"
        @click.stop="toggleComplete"
      >
        <CheckCircleSolid v-if="task.is_completed" class="w-5 h-5" />
        <CheckCircleIcon v-else class="w-5 h-5" />
      </button>

      <!-- Title + meta -->
      <div class="flex-1 min-w-0">
        <button
          class="text-sm font-medium text-left w-full truncate hover:text-red-600 dark:hover:text-red-400 transition-colors"
          :class="task.is_completed
            ? 'line-through text-gray-400 dark:text-gray-500'
            : 'text-gray-900 dark:text-gray-100'"
          @click="openDetail"
        >
          {{ task.title }}
        </button>

        <!-- Meta row -->
        <div class="flex items-center flex-wrap gap-x-2 gap-y-0.5 mt-0.5">
          <!-- Priority dot -->
          <span
            v-if="task.priority && task.priority !== 'none'"
            class="w-2 h-2 rounded-full flex-shrink-0"
            :class="PRIORITY_DOT[task.priority] ?? 'bg-gray-300'"
            :title="task.priority"
          />

          <!-- Status badge (only non-todo) -->
          <span
            v-if="task.status !== 'todo' && STATUS_LABEL[task.status]"
            class="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-md"
            :class="task.is_completed
              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
              : task.status === 'blocked'
                ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'"
          >
            {{ STATUS_LABEL[task.status] }}
          </span>

          <!-- Due date -->
          <span
            v-if="dueDateFormatted"
            class="flex items-center gap-0.5 text-xs"
            :class="isOverdue ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'"
          >
            <ClockIcon class="w-3 h-3" />
            {{ dueDateFormatted }}
          </span>

          <!-- Assignee -->
          <span
            v-if="task.assigned_to_name"
            class="flex items-center gap-0.5 text-xs text-gray-400 dark:text-gray-500"
          >
            <UserIcon class="w-3 h-3" />
            {{ task.assigned_to_name }}
          </span>
        </div>
      </div>

      <!-- Open detail link -->
      <button
        class="flex-shrink-0 text-gray-300 hover:text-red-500 dark:hover:text-red-400 transition-colors mt-0.5"
        :title="t('tasks.openDetail')"
        @click="openDetail"
      >
        <Bars3BottomLeftIcon class="w-4 h-4" />
      </button>
    </div>

    <!-- Streamline items progress bar -->
    <div
      v-if="itemsProgress"
      class="px-3 pb-2.5"
    >
      <div class="flex items-center justify-between text-[10px] text-gray-400 dark:text-gray-500 mb-1">
        <span>{{ itemsProgress.done }}/{{ itemsProgress.total }} {{ t('tasks.streamlineProgress').replace('{done}', '').replace('{total}', '') }}</span>
        <span>{{ itemsProgress.pct }}%</span>
      </div>
      <div class="w-full h-1 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all"
          :class="task.is_completed ? 'bg-green-500' : 'bg-blue-500'"
          :style="{ width: `${itemsProgress.pct}%` }"
        />
      </div>
    </div>
  </div>
</template>

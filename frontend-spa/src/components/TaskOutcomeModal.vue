<script setup lang="ts">
/**
 * Outcome prompt for calendar-bound tasks (kind=call/meeting).
 *
 * Triggered when ``Task.outcome_prompted_at`` is set on a still-open task.
 * Asks the user one of three things via ``POST /tasks/{id}/outcome``:
 *
 * - ``held``        — the call/meeting took place; logs CALL/MEETING Activity
 *                     with the optional note.
 * - ``rescheduled`` — moves the task to a new date; clears the prompt mark
 *                     so the next slot will prompt again.
 * - ``no_show``     — terminal EXPIRED with ``outcome=no_show``.
 *
 * Emits ``close`` after a successful submission so the parent can refresh.
 */
import { ref, computed } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import { useTasksStore, type TaskOut, type TaskOutcomeAction } from '@/stores/tasks'

const props = defineProps<{ task: TaskOut }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'resolved', task: TaskOut): void }>()

const { t } = useI18n()
const toast = useToast()
const tasksStore = useTasksStore()

// Tri-state: null = picker; otherwise we're confirming a chosen action.
const action = ref<TaskOutcomeAction | null>(null)
const note = ref('')
const submitting = ref(false)
const formError = ref('')

// Reschedule fields — pre-filled from the task's current slot so the user
// only has to bump the date, not retype everything.
const rescheduleDate = ref('')
const rescheduleTime = ref('')
const rescheduleEndTime = ref('')

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function splitIso(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: '', time: '' }
  const d = new Date(iso)
  return {
    date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
    time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
  }
}

function pick(next: TaskOutcomeAction) {
  action.value = next
  formError.value = ''
  if (next === 'rescheduled') {
    const start = splitIso(props.task.due_date)
    const end = splitIso(props.task.due_date_end)
    rescheduleDate.value = start.date
    rescheduleTime.value = start.time
    rescheduleEndTime.value = end.time
  }
}

function back() {
  action.value = null
  formError.value = ''
}

const headerLabel = computed(() => {
  switch (action.value) {
    case 'held':
      return t('taskOutcome.headerHeld')
    case 'rescheduled':
      return t('taskOutcome.headerRescheduled')
    case 'no_show':
      return t('taskOutcome.headerNoShow')
    default:
      return t('taskOutcome.headerPicker')
  }
})

async function submit() {
  if (!action.value) return
  formError.value = ''

  const payload: { action: TaskOutcomeAction; note?: string; new_due_date?: string; new_due_date_end?: string | null } = {
    action: action.value,
  }
  if (note.value.trim()) payload.note = note.value.trim()

  if (action.value === 'rescheduled') {
    if (!rescheduleDate.value) {
      formError.value = t('taskOutcome.errorDateRequired')
      return
    }
    const startTime = rescheduleTime.value || '00:00'
    const start = new Date(`${rescheduleDate.value}T${startTime}:00`)
    if (Number.isNaN(start.getTime())) {
      formError.value = t('taskOutcome.errorInvalidDate')
      return
    }
    payload.new_due_date = start.toISOString()
    if (rescheduleEndTime.value) {
      const end = new Date(`${rescheduleDate.value}T${rescheduleEndTime.value}:00`)
      if (Number.isNaN(end.getTime())) {
        formError.value = t('taskOutcome.errorInvalidDate')
        return
      }
      if (end < start) {
        formError.value = t('taskOutcome.errorEndBeforeStart')
        return
      }
      payload.new_due_date_end = end.toISOString()
    } else {
      payload.new_due_date_end = null
    }
  }

  submitting.value = true
  const r = await tasksStore.recordTaskOutcome(props.task.id, payload)
  submitting.value = false
  if (r.ok) {
    const updated = tasksStore.tasks.find((tt) => tt.id === props.task.id) ?? props.task
    toast.success(
      action.value === 'held'
        ? t('taskOutcome.toastHeld')
        : action.value === 'rescheduled'
          ? t('taskOutcome.toastRescheduled')
          : t('taskOutcome.toastNoShow'),
    )
    emit('resolved', updated)
    emit('close')
  } else {
    formError.value = r.error ?? t('taskOutcome.toastFailed')
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <div
        class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
        role="dialog"
        aria-modal="true"
        :aria-label="headerLabel"
      >
        <!-- Header -->
        <div class="flex items-start justify-between p-5 pb-3 border-b border-gray-100 dark:border-gray-700">
          <div class="flex-1 min-w-0 pr-3">
            <p class="text-xs uppercase tracking-wide text-amber-600 dark:text-amber-400 font-semibold mb-1">
              {{ t('taskOutcome.eyebrow') }}
            </p>
            <h2 class="text-lg font-bold text-gray-900 dark:text-gray-100 leading-tight">{{ headerLabel }}</h2>
            <p class="text-sm text-gray-500 dark:text-gray-400 mt-1 truncate">{{ task.title }}</p>
          </div>
          <button
            class="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1 rounded-lg"
            :aria-label="t('taskOutcome.close')"
            @click="emit('close')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Picker view -->
        <div v-if="action === null" class="p-5 space-y-2.5">
          <p class="text-sm text-gray-600 dark:text-gray-300 mb-3">{{ t('taskOutcome.prompt') }}</p>
          <button
            class="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 hover:border-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 text-left transition-colors"
            @click="pick('held')"
          >
            <span class="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400 flex items-center justify-center flex-shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('taskOutcome.actionHeld') }}</span>
              <span class="block text-xs text-gray-500 dark:text-gray-400">{{ t('taskOutcome.actionHeldHint') }}</span>
            </span>
          </button>
          <button
            class="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-left transition-colors"
            @click="pick('rescheduled')"
          >
            <span class="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-400 flex items-center justify-center flex-shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('taskOutcome.actionRescheduled') }}</span>
              <span class="block text-xs text-gray-500 dark:text-gray-400">{{ t('taskOutcome.actionRescheduledHint') }}</span>
            </span>
          </button>
          <button
            class="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 hover:border-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 text-left transition-colors"
            @click="pick('no_show')"
          >
            <span class="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-400 flex items-center justify-center flex-shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L5.636 5.636" />
              </svg>
            </span>
            <span class="flex-1 min-w-0">
              <span class="block text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('taskOutcome.actionNoShow') }}</span>
              <span class="block text-xs text-gray-500 dark:text-gray-400">{{ t('taskOutcome.actionNoShowHint') }}</span>
            </span>
          </button>
        </div>

        <!-- Confirm view -->
        <form v-else class="p-5 space-y-3" @submit.prevent="submit">
          <div
            v-if="formError"
            class="rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400"
            role="alert"
          >
            {{ formError }}
          </div>

          <!-- Reschedule date / time -->
          <template v-if="action === 'rescheduled'">
            <div>
              <label for="task-outcome-date" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                {{ t('taskOutcome.fieldDate') }} *
              </label>
              <input
                id="task-outcome-date"
                v-model="rescheduleDate"
                type="date"
                required
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
              />
            </div>
            <div class="grid grid-cols-2 gap-2">
              <div>
                <label for="task-outcome-time" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {{ t('taskOutcome.fieldStart') }}
                </label>
                <input
                  id="task-outcome-time"
                  v-model="rescheduleTime"
                  type="time"
                  class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
                />
              </div>
              <div>
                <label for="task-outcome-time-end" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {{ t('taskOutcome.fieldEnd') }}
                </label>
                <input
                  id="task-outcome-time-end"
                  v-model="rescheduleEndTime"
                  type="time"
                  class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
                />
              </div>
            </div>
          </template>

          <!-- Optional note (all three actions) -->
          <div>
            <label for="task-outcome-note" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              {{ t('taskOutcome.fieldNote') }}
            </label>
            <textarea
              id="task-outcome-note"
              v-model="note"
              rows="3"
              :placeholder="t('taskOutcome.fieldNotePlaceholder')"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400 resize-none"
            />
          </div>

          <!-- Actions -->
          <div class="flex gap-2 pt-1">
            <button
              type="button"
              class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="back"
            >
              {{ t('taskOutcome.back') }}
            </button>
            <button
              type="submit"
              :disabled="submitting"
              class="flex-1 rounded-xl py-2 text-sm font-medium text-white disabled:opacity-60 transition-colors"
              :class="action === 'no_show' ? 'bg-red-600 hover:bg-red-700' : action === 'rescheduled' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-emerald-600 hover:bg-emerald-700'"
            >
              {{ submitting ? t('taskOutcome.submitting') : t('taskOutcome.confirm') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

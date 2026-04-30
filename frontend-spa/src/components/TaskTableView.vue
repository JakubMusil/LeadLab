<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { TaskOut } from '@/stores/tasks'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'

interface Props {
  tasks: TaskOut[]
  onUpdateTask: (id: string, payload: Partial<TaskOut>) => Promise<{ ok: boolean; error?: string }>
}

const props = defineProps<Props>()
const emit = defineEmits<{ refresh: [] }>()

const router = useRouter()
const { t } = useI18n()
const toast = useToast()

type SortField = 'title' | 'status' | 'priority' | 'due_date' | 'assigned_to_name' | 'created_at'
type GroupByField = 'none' | 'status' | 'priority' | 'assigned_to_name'

const sortField = ref<SortField>('created_at')
const sortDir = ref<'asc' | 'desc'>('asc')
const groupBy = ref<GroupByField>('none')

const editingCell = ref<{ id: string; field: string } | null>(null)
const editValue = ref<string>('')

const PRIORITY_ORDER: Record<string, number> = {
  critical: 5, high: 4, medium: 3, low: 2, none: 1,
}
const STATUS_ORDER: Record<string, number> = {
  todo: 1, in_progress: 2, blocked: 3, done: 4, cancelled: 5,
}

function sortedTasks(list: TaskOut[]) {
  return [...list].sort((a, b) => {
    let cmp = 0
    if (sortField.value === 'priority') {
      cmp = (PRIORITY_ORDER[a.priority] ?? 0) - (PRIORITY_ORDER[b.priority] ?? 0)
    } else if (sortField.value === 'status') {
      cmp = (STATUS_ORDER[a.status] ?? 0) - (STATUS_ORDER[b.status] ?? 0)
    } else if (sortField.value === 'due_date') {
      const da = a.due_date ? new Date(a.due_date).getTime() : Infinity
      const db = b.due_date ? new Date(b.due_date).getTime() : Infinity
      cmp = da - db
    } else if (sortField.value === 'created_at') {
      cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    } else {
      const va = (a[sortField.value] ?? '') as string
      const vb = (b[sortField.value] ?? '') as string
      cmp = va.localeCompare(vb)
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
}

function setSort(field: SortField) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'asc'
  }
}

function sortIcon(field: SortField) {
  if (sortField.value !== field) return '⇅'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

interface GroupEntry { key: string; label: string; tasks: TaskOut[] }

const grouped = computed<GroupEntry[]>(() => {
  const sorted = sortedTasks(props.tasks)
  if (groupBy.value === 'none') return [{ key: 'all', label: '', tasks: sorted }]

  const groups = new Map<string, TaskOut[]>()
  for (const task of sorted) {
    const key = (task[groupBy.value as keyof TaskOut] as string) ?? '—'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(task)
  }

  const statusLabels: Record<string, string> = {
    todo: t('tasks.statusTodo'), in_progress: t('tasks.statusInProgress'),
    blocked: t('tasks.statusBlocked'), done: t('tasks.statusDone'), cancelled: t('tasks.statusCancelled'),
  }
  const priorityLabels: Record<string, string> = {
    none: t('tasks.priorityNone'), low: t('tasks.priorityLow'), medium: t('tasks.priorityMedium'),
    high: t('tasks.priorityHigh'), critical: t('tasks.priorityCritical'),
  }

  return Array.from(groups.entries()).map(([key, tasks]) => {
    const label = groupBy.value === 'status' ? (statusLabels[key] ?? key)
      : groupBy.value === 'priority' ? (priorityLabels[key] ?? key)
      : key
    return { key, label, tasks }
  })
})

function startEdit(task: TaskOut, field: string) {
  editingCell.value = { id: task.id, field }
  if (field === 'due_date') {
    editValue.value = task.due_date ? (task.due_date.split('T')[0] ?? '') : ''
  } else if (field === 'tags') {
    editValue.value = (task.tags ?? []).join(', ')
  } else {
    const val = task[field as keyof TaskOut]
    editValue.value = val !== null && val !== undefined ? String(val) : ''
  }
}

async function commitEdit(task: TaskOut) {
  if (!editingCell.value || editingCell.value.id !== task.id) return
  const field = editingCell.value.field
  editingCell.value = null

  const payload: Record<string, unknown> = {}
  if (field === 'title') {
    const trimmed = editValue.value.trim()
    if (!trimmed) return
    payload.title = trimmed
  } else if (field === 'status') {
    payload.status = editValue.value
  } else if (field === 'priority') {
    payload.priority = editValue.value
  } else if (field === 'due_date') {
    payload.due_date = editValue.value ? new Date(editValue.value).toISOString() : null
    if (!editValue.value) payload.clear_due_date = true
  } else if (field === 'tags') {
    payload.tags = editValue.value.split(',').map((s) => s.trim()).filter(Boolean)
  } else {
    return
  }

  const result = await props.onUpdateTask(task.id, payload as Partial<TaskOut>)
  if (!result.ok) {
    toast.error(result.error ?? t('tasks.updateFailed'))
  } else {
    emit('refresh')
  }
}

function cancelEdit() {
  editingCell.value = null
}

function formatDate(ds: string | null) {
  if (!ds) return '—'
  return new Date(ds).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function isOverdue(task: TaskOut) {
  return !task.is_completed && task.due_date && new Date(task.due_date) < new Date()
}

function priorityColor(p: string) {
  const map: Record<string, string> = {
    none: 'text-gray-400', low: 'text-blue-500', medium: 'text-yellow-500',
    high: 'text-orange-500', critical: 'text-red-600',
  }
  return map[p] ?? 'text-gray-400'
}

function statusBg(s: string) {
  const map: Record<string, string> = {
    todo: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
    in_progress: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    blocked: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
    done: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
    cancelled: 'bg-gray-200 text-gray-500 dark:bg-gray-800 dark:text-gray-400',
  }
  return map[s] ?? 'bg-gray-100 text-gray-600'
}

const statusLabels = computed(() => ({
  todo: t('tasks.statusTodo'), in_progress: t('tasks.statusInProgress'),
  blocked: t('tasks.statusBlocked'), done: t('tasks.statusDone'), cancelled: t('tasks.statusCancelled'),
}))

const priorityLabels = computed(() => ({
  none: t('tasks.priorityNone'), low: t('tasks.priorityLow'), medium: t('tasks.priorityMedium'),
  high: t('tasks.priorityHigh'), critical: t('tasks.priorityCritical'),
}))
</script>

<template>
  <div class="task-table-view space-y-4">
    <!-- Toolbar -->
    <div class="flex flex-wrap items-center gap-3">
      <div class="flex items-center gap-2">
        <span class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('tasks.tableGroupBy') }}:</span>
        <select
          v-model="groupBy"
          class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-2 py-1.5 focus:outline-none focus:border-red-400"
        >
          <option value="none">{{ t('tasks.tableGroupNone') }}</option>
          <option value="status">{{ t('tasks.status') }}</option>
          <option value="priority">{{ t('tasks.priority') }}</option>
          <option value="assigned_to_name">{{ t('tasks.assignee') }}</option>
        </select>
      </div>
    </div>

    <!-- Table groups -->
    <div
      v-for="group in grouped"
      :key="group.key"
      class="overflow-x-auto rounded-2xl border border-gray-200 dark:border-gray-700"
    >
      <!-- Group header -->
      <div
        v-if="groupBy !== 'none'"
        class="px-4 py-2 bg-gray-50 dark:bg-gray-800/60 border-b border-gray-200 dark:border-gray-700 text-xs font-semibold text-gray-600 dark:text-gray-300 uppercase tracking-wide"
      >
        {{ group.label || '—' }}
        <span class="ml-2 text-gray-400 font-normal">{{ group.tasks.length }}</span>
      </div>

      <!-- Table -->
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-200 dark:border-gray-700">
            <th
              class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap hover:text-gray-700 dark:hover:text-gray-200 w-full min-w-[200px]"
              @click="setSort('title')"
            >{{ t('tasks.taskTitle') }} <span class="opacity-60">{{ sortIcon('title') }}</span></th>
            <th
              class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap hover:text-gray-700 dark:hover:text-gray-200"
              @click="setSort('status')"
            >{{ t('tasks.status') }} <span class="opacity-60">{{ sortIcon('status') }}</span></th>
            <th
              class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap hover:text-gray-700 dark:hover:text-gray-200"
              @click="setSort('priority')"
            >{{ t('tasks.priority') }} <span class="opacity-60">{{ sortIcon('priority') }}</span></th>
            <th
              class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap hover:text-gray-700 dark:hover:text-gray-200"
              @click="setSort('due_date')"
            >{{ t('tasks.deadline') }} <span class="opacity-60">{{ sortIcon('due_date') }}</span></th>
            <th
              class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap hover:text-gray-700 dark:hover:text-gray-200"
              @click="setSort('assigned_to_name')"
            >{{ t('tasks.assignee') }} <span class="opacity-60">{{ sortIcon('assigned_to_name') }}</span></th>
            <th class="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 whitespace-nowrap">{{ t('tasks.tags') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
          <tr
            v-for="task in group.tasks"
            :key="task.id"
            class="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors"
            :class="task.is_completed ? 'opacity-60' : ''"
          >
            <!-- Title -->
            <td class="px-4 py-2.5 min-w-[200px]">
              <div v-if="editingCell?.id === task.id && editingCell.field === 'title'" class="flex gap-1.5">
                <input
                  v-model="editValue"
                  class="flex-1 border border-blue-400 rounded-lg px-2 py-1 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none"
                  autofocus
                  @blur="commitEdit(task)"
                  @keyup.enter="commitEdit(task)"
                  @keyup.escape="cancelEdit"
                />
              </div>
              <div
                v-else
                class="flex items-center gap-1.5 cursor-pointer group/title"
                @dblclick="startEdit(task, 'title')"
                @click="router.push(`/app/tasks/${task.id}`)"
              >
                <span
                  class="font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 dark:hover:text-red-400 transition-colors truncate max-w-[300px]"
                  :class="task.is_completed ? 'line-through text-gray-400' : ''"
                >{{ task.title }}</span>
                <span class="opacity-0 group-hover/title:opacity-50 text-xs text-gray-400 flex-shrink-0">✏</span>
              </div>
            </td>

            <!-- Status -->
            <td class="px-4 py-2.5 whitespace-nowrap">
              <div v-if="editingCell?.id === task.id && editingCell.field === 'status'">
                <select
                  v-model="editValue"
                  class="rounded-lg border border-blue-400 px-2 py-1 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none"
                  autofocus
                  @blur="commitEdit(task)"
                  @change="commitEdit(task)"
                >
                  <option value="todo">{{ t('tasks.statusTodo') }}</option>
                  <option value="in_progress">{{ t('tasks.statusInProgress') }}</option>
                  <option value="blocked">{{ t('tasks.statusBlocked') }}</option>
                  <option value="done">{{ t('tasks.statusDone') }}</option>
                  <option value="cancelled">{{ t('tasks.statusCancelled') }}</option>
                </select>
              </div>
              <span
                v-else
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium cursor-pointer"
                :class="statusBg(task.status)"
                @dblclick="startEdit(task, 'status')"
              >{{ statusLabels[task.status] ?? task.status }}</span>
            </td>

            <!-- Priority -->
            <td class="px-4 py-2.5 whitespace-nowrap">
              <div v-if="editingCell?.id === task.id && editingCell.field === 'priority'">
                <select
                  v-model="editValue"
                  class="rounded-lg border border-blue-400 px-2 py-1 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none"
                  autofocus
                  @blur="commitEdit(task)"
                  @change="commitEdit(task)"
                >
                  <option value="none">{{ t('tasks.priorityNone') }}</option>
                  <option value="low">{{ t('tasks.priorityLow') }}</option>
                  <option value="medium">{{ t('tasks.priorityMedium') }}</option>
                  <option value="high">{{ t('tasks.priorityHigh') }}</option>
                  <option value="critical">{{ t('tasks.priorityCritical') }}</option>
                </select>
              </div>
              <span
                v-else
                class="text-xs font-medium cursor-pointer"
                :class="priorityColor(task.priority)"
                @dblclick="startEdit(task, 'priority')"
              >{{ priorityLabels[task.priority] ?? task.priority }}</span>
            </td>

            <!-- Due date -->
            <td class="px-4 py-2.5 whitespace-nowrap">
              <div v-if="editingCell?.id === task.id && editingCell.field === 'due_date'">
                <input
                  v-model="editValue"
                  type="date"
                  class="rounded-lg border border-blue-400 px-2 py-1 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none"
                  autofocus
                  @blur="commitEdit(task)"
                  @change="commitEdit(task)"
                />
              </div>
              <span
                v-else
                class="text-xs cursor-pointer"
                :class="isOverdue(task) ? 'text-red-500 font-semibold' : 'text-gray-500 dark:text-gray-400'"
                @dblclick="startEdit(task, 'due_date')"
              >{{ formatDate(task.due_date) }}</span>
            </td>

            <!-- Assignee -->
            <td class="px-4 py-2.5 whitespace-nowrap">
              <span class="text-xs text-gray-600 dark:text-gray-400">{{ task.assigned_to_name || '—' }}</span>
            </td>

            <!-- Tags -->
            <td class="px-4 py-2.5">
              <div v-if="editingCell?.id === task.id && editingCell.field === 'tags'">
                <input
                  v-model="editValue"
                  class="rounded-lg border border-blue-400 px-2 py-1 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none w-32"
                  :placeholder="t('tasks.tagsPlaceholder')"
                  autofocus
                  @blur="commitEdit(task)"
                  @keyup.enter="commitEdit(task)"
                  @keyup.escape="cancelEdit"
                />
              </div>
              <div
                v-else
                class="flex flex-wrap gap-1 cursor-pointer"
                @dblclick="startEdit(task, 'tags')"
              >
                <span
                  v-for="tag in (task.tags ?? []).slice(0, 3)"
                  :key="tag"
                  class="px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-xs"
                >{{ tag }}</span>
                <span v-if="!(task.tags ?? []).length" class="text-xs text-gray-300 dark:text-gray-600">—</span>
              </div>
            </td>
          </tr>

          <!-- Empty -->
          <tr v-if="group.tasks.length === 0">
            <td colspan="6" class="px-4 py-8 text-center text-xs text-gray-400">{{ t('tasks.noTasks') }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

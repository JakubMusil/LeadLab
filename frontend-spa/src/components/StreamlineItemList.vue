<script setup lang="ts">
/**
 * StreamlineItemList — unified TODO / sub-task list attached to a Task.
 *
 * Replaces the old inline Checklist + Subtasks sections in TaskDetailView.
 * Each kind (todo | subtask) is rendered in its own card with a shared component.
 *
 * Multi-line input: the textarea accepts any number of lines; on submit every
 * non-empty line becomes a separate StreamlineItem.
 *
 * Props:
 *   taskId   — the owning Task UUID
 *   kind     — 'todo' | 'subtask'
 *   resolved — count of resolved items (from TaskOut; kept in sync via @refreshed)
 *   total    — total count of items      (from TaskOut; kept in sync via @refreshed)
 *
 * Emits:
 *   refreshed — parent should reload the task to update the counter fields
 */

import { ref, onMounted } from 'vue'
import { useTasksStore, type StreamlineItemOut } from '@/stores/tasks'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import { TrashIcon, CheckIcon, ClipboardDocumentListIcon, ClipboardDocumentCheckIcon } from '@heroicons/vue/24/outline'

const props = defineProps<{
  taskId: string
  kind: 'todo' | 'subtask'
  resolved: number
  total: number
}>()

const emit = defineEmits<{
  refreshed: []
}>()

const store = useTasksStore()
const { t } = useI18n()
const toast = useToast()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const items = ref<StreamlineItemOut[]>([])
const loading = ref(false)
const newText = ref('')
const submitting = ref(false)
const togglingId = ref<string | null>(null)

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------
async function load() {
  if (!props.taskId) return
  loading.value = true
  const res = await store.fetchStreamlineItems(props.taskId, props.kind)
  loading.value = false
  if (res.ok && res.data) items.value = res.data
  else toast.error(res.error ?? t('tasks.streamlineLoadFailed'))
}

onMounted(load)

// ---------------------------------------------------------------------------
// Add items (multi-line)
// ---------------------------------------------------------------------------
async function addItems() {
  const text = newText.value.trim()
  if (!text) return
  submitting.value = true
  const res = await store.createStreamlineItems(props.taskId, { text, kind: props.kind })
  submitting.value = false
  if (res.ok && res.data) {
    items.value.push(...res.data)
    newText.value = ''
    toast.success(
      res.data.length === 1
        ? t('tasks.streamlineItemAdded')
        : t('tasks.streamlineItemsAdded', { count: String(res.data.length) }),
    )
    emit('refreshed')
  } else {
    toast.error(res.error ?? t('tasks.streamlineAddFailed'))
  }
}

// ---------------------------------------------------------------------------
// Toggle resolved (optimistic)
// ---------------------------------------------------------------------------
async function toggleItem(item: StreamlineItemOut) {
  if (togglingId.value) return
  togglingId.value = item.id
  const newVal = !item.is_resolved
  // Optimistic update
  const idx = items.value.findIndex((i) => i.id === item.id)
  if (idx !== -1) {
    const old = items.value[idx]
    if (old) {
      items.value[idx] = {
        ...old,
        is_resolved: newVal,
        resolved_at: newVal ? new Date().toISOString() : null,
      }
    }
  }
  const res = await store.updateStreamlineItem(item.id, { is_resolved: newVal })
  togglingId.value = null
  if (res.ok && res.data) {
    if (idx !== -1) items.value[idx] = res.data
    emit('refreshed')
  } else {
    // Rollback
    if (idx !== -1) items.value[idx] = item
    toast.error(res.error ?? t('tasks.streamlineToggleFailed'))
  }
}

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------
async function deleteItem(id: string) {
  const res = await store.deleteStreamlineItem(id)
  if (res.ok) {
    const idx = items.value.findIndex((i) => i.id === id)
    if (idx !== -1 && res.data) {
      items.value[idx] = res.data
    } else {
      items.value = items.value.filter((i) => i.id !== id)
    }
    emit('refreshed')
  } else {
    toast.error(res.error ?? t('tasks.streamlineDeleteFailed'))
  }
}

// ---------------------------------------------------------------------------
// Computed helpers
// ---------------------------------------------------------------------------
function deletionLabel(item: any): string {
  const base = t('tasks.streamlineDeleted')
  if (!item.deleted_by_name) return base
  return `${base} ${t('tasks.streamlineDeletedBy').replace('{name}', item.deleted_by_name)}`
}

const progressPct = () =>
  props.total > 0 ? Math.round((props.resolved / props.total) * 100) : 0

const accentClass = props.kind === 'todo'
  ? { check: 'bg-blue-500 border-blue-500', hover: 'hover:border-blue-400', bar: 'bg-blue-500' }
  : { check: 'bg-green-500 border-green-500', hover: 'hover:border-green-400', bar: 'bg-green-500' }
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
    <!-- Header -->
    <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
      <component :is="kind === 'todo' ? ClipboardDocumentCheckIcon : ClipboardDocumentListIcon" class="w-5 h-5 text-gray-500 dark:text-gray-400 inline-block mr-1 align-text-bottom" />
      {{ kind === 'todo' ? t('tasks.streamlineTodos') : t('tasks.streamlineSubtasks') }}
      <span v-if="total > 0" class="text-sm font-normal text-gray-400 ml-1">
        ({{ resolved }}/{{ total }})
      </span>
    </h2>

    <!-- Progress bar -->
    <div v-if="total > 0" class="mb-4">
      <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span>
          {{
            t('tasks.streamlineProgress')
              .replace('{done}', String(resolved))
              .replace('{total}', String(total))
          }}
        </span>
        <span>{{ progressPct() }}%</span>
      </div>
      <div class="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all"
          :class="accentClass.bar"
          :style="{ width: `${progressPct()}%` }"
        />
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-2 animate-pulse">
      <div v-for="i in 2" :key="i" class="h-8 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Item list -->
    <div v-else>
      <div v-if="items.length === 0" class="text-sm text-gray-400 dark:text-gray-500 mb-3">
        {{
          kind === 'todo'
            ? t('tasks.streamlineNoTodos')
            : t('tasks.streamlineNoSubtasks')
        }}
      </div>
      <ul v-else class="space-y-1.5 mb-3">
        <li
          v-for="item in items"
          :key="item.id"
          class="flex items-center gap-2.5 group"
        >
          <template v-if="!item.is_deleted">
            <!-- Checkbox toggle -->
            <button
              class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors"
              :class="item.is_resolved
                ? `${accentClass.check} text-white`
                : `border-gray-300 ${accentClass.hover}`"
              :disabled="togglingId === item.id"
              @click="toggleItem(item)"
            >
              <span v-if="item.is_resolved" class="flex items-center justify-center"><CheckIcon class="w-3 h-3" /></span>
              <span v-else-if="togglingId === item.id" class="text-xs text-gray-400">…</span>
            </button>

            <!-- Text -->
            <span
              class="flex-1 text-sm text-gray-700 dark:text-gray-200"
              :class="item.is_resolved ? 'line-through text-gray-400 dark:text-gray-500' : ''"
            >{{ item.text }}</span>

            <!-- Resolved-by hint -->
            <span
              v-if="item.is_resolved && item.resolved_by_id"
              class="text-xs text-gray-400 dark:text-gray-500 hidden group-hover:inline flex-shrink-0"
            >
              {{ item.resolved_at ? new Date(item.resolved_at).toLocaleDateString() : '' }}
            </span>

            <!-- Delete button -->
            <button
              class="text-xs text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0"
              :title="t('tasks.delete')"
              @click="deleteItem(item.id)"
            ><TrashIcon class="w-3.5 h-3.5" /></button>
          </template>
          <template v-else>
            <div class="flex items-center gap-2 py-2 text-gray-400 dark:text-gray-500 text-sm line-through">
              <span>{{ item.text }}</span>
              <span class="text-xs no-underline">
                — {{ deletionLabel(item) }}
              </span>
            </div>
          </template>
        </li>
      </ul>

      <!-- Multi-line add textarea -->
      <div class="mt-2">
        <textarea
          v-model="newText"
          :placeholder="t('tasks.streamlineAddPlaceholder')"
          rows="2"
          class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400 dark:focus:border-blue-500 resize-none"
          @keydown.ctrl.enter.prevent="addItems"
          @keydown.meta.enter.prevent="addItems"
        />
        <div class="flex justify-between items-center mt-1.5">
          <span class="text-xs text-gray-400">{{ t('tasks.streamlineHint') }}</span>
          <button
            :disabled="submitting || !newText.trim()"
            class="px-3 py-1.5 rounded-lg text-white text-xs font-medium disabled:opacity-50 transition-colors"
            :class="kind === 'todo' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-green-600 hover:bg-green-700'"
            @click="addItems"
          >
            {{ submitting ? '…' : t('tasks.streamlineAdd') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useTasksStore, type TaskTemplateOut, type TaskTemplateIn, type TaskTemplateUpdateIn } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'

const { t } = useI18n()
const router = useRouter()
const tasksStore = useTasksStore()
const toast = useToast()

// ---------------------------------------------------------------------------
// Template list
// ---------------------------------------------------------------------------
const templates = ref<TaskTemplateOut[]>([])
const loading = ref(false)
const loadError = ref('')

async function loadTemplates() {
  loading.value = true
  loadError.value = ''
  const result = await tasksStore.fetchTaskTemplates()
  loading.value = false
  if (result.ok && result.data) {
    templates.value = result.data
  } else {
    loadError.value = result.error ?? t('taskTemplates.loadFailed')
  }
}

// ---------------------------------------------------------------------------
// Create template modal
// ---------------------------------------------------------------------------
const showCreateModal = ref(false)
const createName = ref('')
const createDescriptionHtml = ref('')
const createPriority = ref('medium')
const createEstimateHours = ref<number | null>(null)
const createEstimateMinutes = ref<number | null>(null)
const createTags = ref('')
const createChecklistRaw = ref('')
const createSubmitting = ref(false)
const createError = ref('')

function openCreateModal() {
  createName.value = ''
  createDescriptionHtml.value = ''
  createPriority.value = 'medium'
  createEstimateHours.value = null
  createEstimateMinutes.value = null
  createTags.value = ''
  createChecklistRaw.value = ''
  createError.value = ''
  showCreateModal.value = true
}

async function submitCreate() {
  if (!createName.value.trim()) {
    createError.value = t('taskTemplates.nameRequired')
    return
  }
  createSubmitting.value = true
  createError.value = ''

  const estimatedMinutes =
    (Number(createEstimateHours.value || 0) * 60) + Number(createEstimateMinutes.value || 0)

  const checklistItems = createChecklistRaw.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text, idx) => ({ text, position: idx }))

  const payload: TaskTemplateIn = {
    name: createName.value.trim(),
    description_html: createDescriptionHtml.value,
    priority: createPriority.value,
    estimated_minutes: estimatedMinutes > 0 ? estimatedMinutes : undefined,
    checklist_items: checklistItems,
    tags: createTags.value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  }

  const result = await tasksStore.createTaskTemplate(payload)
  createSubmitting.value = false
  if (result.ok && result.data) {
    templates.value.unshift(result.data)
    showCreateModal.value = false
    toast.success(t('taskTemplates.created'))
  } else {
    createError.value = result.error ?? t('taskTemplates.createFailed')
  }
}

// ---------------------------------------------------------------------------
// Edit template modal
// ---------------------------------------------------------------------------
const showEditModal = ref(false)
const editingTemplate = ref<TaskTemplateOut | null>(null)
const editName = ref('')
const editDescriptionHtml = ref('')
const editPriority = ref('medium')
const editEstimateHours = ref<number | null>(null)
const editEstimateMinutes = ref<number | null>(null)
const editTags = ref('')
const editChecklistRaw = ref('')
const editSubmitting = ref(false)
const editError = ref('')

function openEditModal(tmpl: TaskTemplateOut) {
  editingTemplate.value = tmpl
  editName.value = tmpl.name
  editDescriptionHtml.value = tmpl.description_html
  editPriority.value = tmpl.priority
  const totalMin = tmpl.estimated_minutes ?? 0
  editEstimateHours.value = Math.floor(totalMin / 60) || null
  editEstimateMinutes.value = totalMin % 60 || null
  editTags.value = (tmpl.tags ?? []).join(', ')
  editChecklistRaw.value = (tmpl.checklist_items ?? []).map((i) => i.text).join('\n')
  editError.value = ''
  showEditModal.value = true
}

async function submitEdit() {
  if (!editingTemplate.value || !editName.value.trim()) {
    editError.value = t('taskTemplates.nameRequired')
    return
  }
  editSubmitting.value = true
  editError.value = ''

  const estimatedMinutes =
    (Number(editEstimateHours.value || 0) * 60) + Number(editEstimateMinutes.value || 0)

  const checklistItems = editChecklistRaw.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text, idx) => ({ text, position: idx }))

  const payload: TaskTemplateUpdateIn = {
    name: editName.value.trim(),
    description_html: editDescriptionHtml.value,
    priority: editPriority.value,
    ...(estimatedMinutes > 0
      ? { estimated_minutes: estimatedMinutes }
      : { clear_estimated_minutes: true }),
    checklist_items: checklistItems,
    tags: editTags.value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean),
  }

  const result = await tasksStore.updateTaskTemplate(editingTemplate.value.id, payload)
  editSubmitting.value = false
  if (result.ok && result.data) {
    const idx = templates.value.findIndex((t) => t.id === editingTemplate.value!.id)
    if (idx !== -1) templates.value[idx] = result.data
    showEditModal.value = false
    toast.success(t('taskTemplates.updated'))
  } else {
    editError.value = result.error ?? t('taskTemplates.updateFailed')
  }
}

// ---------------------------------------------------------------------------
// Delete template
// ---------------------------------------------------------------------------
const deletingId = ref<string | null>(null)
const showDeleteConfirm = ref(false)
const deleteTargetId = ref<string | null>(null)

function confirmDelete(id: string) {
  deleteTargetId.value = id
  showDeleteConfirm.value = true
}

async function executeDelete() {
  if (!deleteTargetId.value) return
  deletingId.value = deleteTargetId.value
  const result = await tasksStore.deleteTaskTemplate(deleteTargetId.value)
  deletingId.value = null
  if (result.ok) {
    templates.value = templates.value.filter((t) => t.id !== deleteTargetId.value)
    showDeleteConfirm.value = false
    toast.success(t('taskTemplates.deleted'))
  } else {
    toast.error(result.error ?? t('taskTemplates.deleteFailed'))
  }
}

// ---------------------------------------------------------------------------
// Apply template modal
// ---------------------------------------------------------------------------
const showApplyModal = ref(false)
const applyingTemplate = ref<TaskTemplateOut | null>(null)
const applyTitle = ref('')
const applySubmitting = ref(false)
const applyError = ref('')

function openApplyModal(tmpl: TaskTemplateOut) {
  applyingTemplate.value = tmpl
  applyTitle.value = tmpl.name
  applyError.value = ''
  showApplyModal.value = true
}

async function submitApply() {
  if (!applyingTemplate.value || !applyTitle.value.trim()) {
    applyError.value = t('taskTemplates.titleRequired')
    return
  }
  applySubmitting.value = true
  applyError.value = ''
  const result = await tasksStore.applyTaskTemplate(applyingTemplate.value.id, {
    title: applyTitle.value.trim(),
  })
  applySubmitting.value = false
  if (result.ok && result.data) {
    showApplyModal.value = false
    toast.success(t('taskTemplates.applied'))
    router.push(`/app/tasks/${result.data.id}`)
  } else {
    applyError.value = result.error ?? t('taskTemplates.applyFailed')
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatMinutes(mins: number | null): string {
  if (!mins) return '—'
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h === 0) return `${m} min`
  if (m === 0) return `${h} h`
  return `${h} h ${m} min`
}

function formatDate(ds: string): string {
  return new Date(ds).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

const priorityColors: Record<string, string> = {
  none: 'text-gray-400',
  low: 'text-blue-500',
  medium: 'text-yellow-500',
  high: 'text-orange-500',
  critical: 'text-red-600',
}

onMounted(() => { loadTemplates() })
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">
          📋 {{ t('taskTemplates.title') }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ t('taskTemplates.subtitle') }}</p>
      </div>
      <button
        class="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-colors"
        @click="openCreateModal"
      >
        + {{ t('taskTemplates.createTemplate') }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-4 animate-pulse">
      <div v-for="i in 3" :key="i" class="h-20 bg-gray-100 dark:bg-gray-700 rounded-2xl" />
    </div>

    <!-- Error -->
    <div v-else-if="loadError" class="text-red-500 text-sm py-8 text-center">{{ loadError }}</div>

    <!-- Empty -->
    <div
      v-else-if="templates.length === 0"
      class="py-16 text-center text-gray-400 dark:text-gray-500"
    >
      <div class="text-5xl mb-4">📋</div>
      <p class="text-base font-medium mb-2">{{ t('taskTemplates.noTemplates') }}</p>
      <p class="text-sm">{{ t('taskTemplates.noTemplatesHint') }}</p>
    </div>

    <!-- Template list -->
    <div v-else class="space-y-3">
      <div
        v-for="tmpl in templates"
        :key="tmpl.id"
        class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 hover:border-gray-200 dark:hover:border-gray-600 transition-colors group"
      >
        <div class="flex items-start justify-between gap-4">
          <!-- Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <h3 class="font-semibold text-gray-900 dark:text-gray-100 text-base">{{ tmpl.name }}</h3>
              <span :class="['text-xs font-medium', priorityColors[tmpl.priority] ?? 'text-gray-400']">
                {{ t(`tasks.priority_${tmpl.priority}`) }}
              </span>
              <span v-for="tag in tmpl.tags.slice(0, 3)" :key="tag" class="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs">
                {{ tag }}
              </span>
              <span v-if="tmpl.tags.length > 3" class="text-xs text-gray-400">+{{ tmpl.tags.length - 3 }}</span>
            </div>
            <div class="flex items-center gap-3 text-xs text-gray-400 dark:text-gray-500 flex-wrap">
              <span v-if="tmpl.estimated_minutes">⏱ {{ formatMinutes(tmpl.estimated_minutes) }}</span>
              <span v-if="tmpl.checklist_items.length">☑ {{ tmpl.checklist_items.length }} {{ t('taskTemplates.items') }}</span>
              <span>{{ t('taskTemplates.createdBy') }} {{ tmpl.created_by_name || '?' }}</span>
              <span>{{ formatDate(tmpl.created_at) }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-2 flex-shrink-0">
            <button
              class="px-3 py-1.5 rounded-xl bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors"
              :title="t('taskTemplates.useTemplate')"
              @click="openApplyModal(tmpl)"
            >
              ▶ {{ t('taskTemplates.useTemplate') }}
            </button>
            <button
              class="px-2.5 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 text-xs hover:border-blue-400 hover:text-blue-500 transition-colors"
              :title="t('taskTemplates.edit')"
              @click="openEditModal(tmpl)"
            >✏️</button>
            <button
              class="px-2.5 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-gray-400 text-xs hover:border-red-400 hover:text-red-500 transition-colors"
              :title="t('taskTemplates.delete')"
              :disabled="deletingId === tmpl.id"
              @click="confirmDelete(tmpl.id)"
            >🗑</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ===================== CREATE MODAL ===================== -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showCreateModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4 max-h-[90vh] overflow-y-auto">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">📋 {{ t('taskTemplates.createTemplate') }}</h2>

          <div v-if="createError" class="text-red-500 text-sm">{{ createError }}</div>

          <!-- Name -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('taskTemplates.name') }} *</label>
            <input
              v-model="createName"
              type="text"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
              :placeholder="t('taskTemplates.namePlaceholder')"
            />
          </div>

          <!-- Priority -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.priority') }}</label>
            <select
              v-model="createPriority"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
            >
              <option value="none">{{ t('tasks.priorityNone') }}</option>
              <option value="low">{{ t('tasks.priorityLow') }}</option>
              <option value="medium">{{ t('tasks.priorityMedium') }}</option>
              <option value="high">{{ t('tasks.priorityHigh') }}</option>
              <option value="critical">{{ t('tasks.priorityCritical') }}</option>
            </select>
          </div>

          <!-- Estimate -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.hoursShort') }}</label>
              <input v-model.number="createEstimateHours" type="number" min="0" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400" placeholder="0" />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.minutesShort') }}</label>
              <input v-model.number="createEstimateMinutes" type="number" min="0" max="59" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400" placeholder="0" />
            </div>
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.tags') }} <span class="text-gray-400">({{ t('tasks.tagsHint') }})</span></label>
            <input v-model="createTags" type="text" :placeholder="t('tasks.tagsPlaceholder')" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
          </div>

          <!-- Checklist items (one per line) -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('taskTemplates.checklistItems') }} <span class="text-gray-400">({{ t('taskTemplates.checklistHint') }})</span></label>
            <textarea
              v-model="createChecklistRaw"
              rows="4"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400"
              :placeholder="t('taskTemplates.checklistPlaceholder')"
            />
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showCreateModal = false">{{ t('tasks.cancel') }}</button>
            <button :disabled="createSubmitting" class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50" @click="submitCreate">
              {{ createSubmitting ? '…' : t('tasks.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ===================== EDIT MODAL ===================== -->
    <Teleport to="body">
      <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showEditModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4 max-h-[90vh] overflow-y-auto">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">✏️ {{ t('taskTemplates.editTemplate') }}</h2>

          <div v-if="editError" class="text-red-500 text-sm">{{ editError }}</div>

          <!-- Name -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('taskTemplates.name') }} *</label>
            <input v-model="editName" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
          </div>

          <!-- Priority -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.priority') }}</label>
            <select v-model="editPriority" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400">
              <option value="none">{{ t('tasks.priorityNone') }}</option>
              <option value="low">{{ t('tasks.priorityLow') }}</option>
              <option value="medium">{{ t('tasks.priorityMedium') }}</option>
              <option value="high">{{ t('tasks.priorityHigh') }}</option>
              <option value="critical">{{ t('tasks.priorityCritical') }}</option>
            </select>
          </div>

          <!-- Estimate -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.hoursShort') }}</label>
              <input v-model.number="editEstimateHours" type="number" min="0" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400" placeholder="0" />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.minutesShort') }}</label>
              <input v-model.number="editEstimateMinutes" type="number" min="0" max="59" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400" placeholder="0" />
            </div>
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.tags') }}</label>
            <input v-model="editTags" type="text" :placeholder="t('tasks.tagsPlaceholder')" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
          </div>

          <!-- Checklist items -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('taskTemplates.checklistItems') }} <span class="text-gray-400">({{ t('taskTemplates.checklistHint') }})</span></label>
            <textarea v-model="editChecklistRaw" rows="4" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-blue-400" :placeholder="t('taskTemplates.checklistPlaceholder')" />
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showEditModal = false">{{ t('tasks.cancel') }}</button>
            <button :disabled="editSubmitting" class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50" @click="submitEdit">
              {{ editSubmitting ? '…' : t('tasks.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ===================== APPLY MODAL ===================== -->
    <Teleport to="body">
      <div v-if="showApplyModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showApplyModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">▶ {{ t('taskTemplates.useTemplate') }}</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ t('taskTemplates.applyHint') }} <span class="font-medium text-gray-700 dark:text-gray-200">{{ applyingTemplate?.name }}</span>
          </p>

          <div v-if="applyError" class="text-red-500 text-sm">{{ applyError }}</div>

          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.taskTitle') }} *</label>
            <input
              v-model="applyTitle"
              type="text"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
              :placeholder="t('tasks.taskTitle')"
            />
          </div>

          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showApplyModal = false">{{ t('tasks.cancel') }}</button>
            <button
              :disabled="applySubmitting || !applyTitle.trim()"
              class="px-4 py-2 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              @click="submitApply"
            >{{ applySubmitting ? '…' : t('taskTemplates.createTask') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ===================== DELETE CONFIRM ===================== -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showDeleteConfirm = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('taskTemplates.deleteTemplate') }}</h2>
          <p class="text-sm text-gray-600 dark:text-gray-400">{{ t('taskTemplates.deleteConfirm') }}</p>
          <div class="flex gap-3 justify-end pt-2">
            <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showDeleteConfirm = false">{{ t('tasks.cancel') }}</button>
            <button :disabled="!!deletingId" class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50" @click="executeDelete">
              {{ deletingId ? '…' : t('taskTemplates.deleteTemplate') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

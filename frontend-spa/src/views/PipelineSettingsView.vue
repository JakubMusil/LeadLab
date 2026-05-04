<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { usePipelineStore, type CategoryOut, type StageOut, type CategoryFieldOut } from '@/stores/pipeline'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { ConfirmDeleteModal } from '@/components/ui'
import {
  PlusIcon,
  TrashIcon,
  PencilSquareIcon,
  CheckIcon,
  XMarkIcon,
  Bars3Icon,
} from '@heroicons/vue/24/outline'

const pipelineStore = usePipelineStore()
const toast = useToast()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const selectedCategoryId = ref<string | null>(null)
const editingCategoryId = ref<string | null>(null)
const editingCategoryName = ref('')
const editingCategoryIcon = ref('')
const editingCategoryColor = ref('')

const newCategoryName = ref('')
const newCategoryColor = ref('#3B82F6')
const newCategoryIcon = ref('funnel')
const showNewCategoryForm = ref(false)
const savingCategory = ref(false)

// Stages
const editingStageId = ref<string | null>(null)
const editingStage = ref<Partial<StageOut>>({})
const showNewStageForm = ref(false)
const newStageName = ref('')
const newStageColor = ref('#94A3B8')
const newStageIsTerminal = ref(false)
const newStageIsWon = ref(false)
const savingStage = ref(false)

// Fields
const editingFieldKey = ref<string | null>(null)
const editingField = ref<{ is_visible: boolean; is_required: boolean }>({ is_visible: true, is_required: false })
const showNewFieldForm = ref(false)
const newFieldKey = ref('')
const newFieldIsVisible = ref(true)
const newFieldIsRequired = ref(false)
const savingField = ref(false)

// Delete confirmations
const pendingDeleteCategoryId = ref<string | null>(null)
const pendingDeleteStageId = ref<string | null>(null)
const pendingDeleteFieldKey = ref<string | null>(null)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const categories = computed(() => pipelineStore.categories)
const selectedCategory = computed<CategoryOut | undefined>(() =>
  selectedCategoryId.value ? pipelineStore.getCategoryById(selectedCategoryId.value) : undefined,
)
const selectedStages = computed<StageOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : [],
)
const selectedFields = computed<CategoryFieldOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getFieldsForCategory(selectedCategoryId.value) : [],
)

// All valid field keys (must match BE FIELD_KEY_CHOICES)
const ALL_FIELD_KEYS = [
  'value_currency',
  'date_range',
  'expires_at',
  'notes',
  'source',
  'origin_record',
] as const

// Field keys not yet configured for the selected category
const availableFieldKeys = computed(() =>
  ALL_FIELD_KEYS.filter((k) => !selectedFields.value.some((f) => f.field_key === k)),
)

// ---------------------------------------------------------------------------
// Role/permissions
// ---------------------------------------------------------------------------
interface Member {
  id: string
  user_id: string
  user_email: string
  role: string
}

const members = ref<Member[]>([])

async function loadMembers() {
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (!firmId) return
  const res = await api.get<Member[]>(`/api/v1/firms/${firmId}/members`)
  if (res.ok) members.value = res.data
}

const currentMember = computed(() =>
  members.value.find((m) => m.user_email === authStore.user?.email),
)

const isAdminOrOwner = computed(() =>
  currentMember.value?.role === 'admin' || currentMember.value?.role === 'owner',
)

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

onMounted(async () => {
  await loadMembers()
  if (pipelineStore.categories.length === 0) {
    await pipelineStore.fetchCategories()
  }
  if (pipelineStore.categories.length > 0 && !selectedCategoryId.value) {
    selectedCategoryId.value = pipelineStore.categories[0]!.id
  }
})

// ---------------------------------------------------------------------------
// Category actions
// ---------------------------------------------------------------------------

function selectCategory(id: string) {
  selectedCategoryId.value = id
  cancelEditCategory()
  cancelEditStage()
  showNewStageForm.value = false
  cancelEditField()
  showNewFieldForm.value = false
}

function startEditCategory(cat: CategoryOut) {
  editingCategoryId.value = cat.id
  editingCategoryName.value = cat.name
  editingCategoryIcon.value = cat.icon
  editingCategoryColor.value = cat.color || '#3B82F6'
}

function cancelEditCategory() {
  editingCategoryId.value = null
  editingCategoryName.value = ''
}

async function saveEditCategory() {
  if (!editingCategoryId.value || !editingCategoryName.value.trim()) return
  savingCategory.value = true
  const result = await pipelineStore.updateCategory(editingCategoryId.value, {
    name: editingCategoryName.value.trim(),
    icon: editingCategoryIcon.value,
    color: editingCategoryColor.value,
  })
  savingCategory.value = false
  if (result.ok) {
    toast.success(t('pipeline.categoryUpdated'))
    cancelEditCategory()
  } else {
    toast.error(result.error ?? t('pipeline.categoryUpdateFailed'))
  }
}

async function createCategory() {
  if (!newCategoryName.value.trim()) return
  savingCategory.value = true
  const result = await pipelineStore.createCategory({
    name: newCategoryName.value.trim(),
    icon: newCategoryIcon.value,
    color: newCategoryColor.value,
  })
  savingCategory.value = false
  if (result.ok && result.data) {
    toast.success(t('pipeline.categoryCreated'))
    newCategoryName.value = ''
    newCategoryColor.value = '#3B82F6'
    newCategoryIcon.value = 'funnel'
    showNewCategoryForm.value = false
    selectedCategoryId.value = result.data.id
  } else {
    toast.error(result.error ?? t('pipeline.categoryCreateFailed'))
  }
}

async function confirmDeleteCategory() {
  if (!pendingDeleteCategoryId.value) return
  const result = await pipelineStore.deleteCategory(pendingDeleteCategoryId.value)
  if (result.ok) {
    toast.success(t('pipeline.categoryDeleted'))
    if (selectedCategoryId.value === pendingDeleteCategoryId.value) {
      selectedCategoryId.value = pipelineStore.categories[0]?.id ?? null
    }
  } else {
    toast.error(result.error ?? t('pipeline.categoryDeleteFailed'))
  }
  pendingDeleteCategoryId.value = null
}

// ---------------------------------------------------------------------------
// Stage actions
// ---------------------------------------------------------------------------

function startEditStage(stage: StageOut) {
  editingStageId.value = stage.id
  editingStage.value = { ...stage }
}

function cancelEditStage() {
  editingStageId.value = null
  editingStage.value = {}
}

async function saveEditStage() {
  if (!selectedCategoryId.value || !editingStageId.value) return
  savingStage.value = true
  const result = await pipelineStore.updateStage(selectedCategoryId.value, editingStageId.value, {
    name: editingStage.value.name,
    label: editingStage.value.label,
    color: editingStage.value.color,
    is_terminal: editingStage.value.is_terminal,
    is_won: editingStage.value.is_won,
  })
  savingStage.value = false
  if (result.ok) {
    toast.success(t('pipeline.stageUpdatedOk'))
    cancelEditStage()
  } else {
    toast.error(result.error ?? t('pipeline.stageUpdateFailed'))
  }
}

async function createStage() {
  if (!selectedCategoryId.value || !newStageName.value.trim()) return
  savingStage.value = true
  const nextOrder = selectedStages.value.length
    ? Math.max(...selectedStages.value.map((s) => s.order)) + 1
    : 0
  const result = await pipelineStore.createStage(selectedCategoryId.value, {
    name: newStageName.value.trim(),
    label: newStageName.value.trim(),
    color: newStageColor.value,
    order: nextOrder,
    is_terminal: newStageIsTerminal.value,
    is_won: newStageIsWon.value,
  })
  savingStage.value = false
  if (result.ok) {
    toast.success(t('pipeline.stageCreated'))
    newStageName.value = ''
    newStageColor.value = '#94A3B8'
    newStageIsTerminal.value = false
    newStageIsWon.value = false
    showNewStageForm.value = false
  } else {
    toast.error(result.error ?? t('pipeline.stageCreateFailed'))
  }
}

async function confirmDeleteStage() {
  if (!pendingDeleteStageId.value || !selectedCategoryId.value) return
  const result = await pipelineStore.deleteStage(selectedCategoryId.value, pendingDeleteStageId.value)
  if (result.ok) {
    toast.success(t('pipeline.stageDeleted'))
  } else {
    toast.error(result.error ?? t('pipeline.stageDeleteFailed'))
  }
  pendingDeleteStageId.value = null
}

// ---------------------------------------------------------------------------
// Drag-and-drop stage reordering
// ---------------------------------------------------------------------------

const draggableStages = computed({
  get: () => selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : [],
  set: (reordered: StageOut[]) => {
    if (!selectedCategoryId.value) return
    const cat = pipelineStore.getCategoryById(selectedCategoryId.value)
    if (cat) cat.stages = reordered
  },
})

async function onStageDragEnd() {
  if (!selectedCategoryId.value) return
  const stages = pipelineStore.getStagesForCategory(selectedCategoryId.value)
  await Promise.all(
    stages.map((stage, idx) =>
      pipelineStore.updateStage(selectedCategoryId.value!, stage.id, { order: idx }),
    ),
  )
}

// ---------------------------------------------------------------------------
// Field actions
// ---------------------------------------------------------------------------

function startEditField(field: CategoryFieldOut) {
  editingFieldKey.value = field.field_key
  editingField.value = { is_visible: field.is_visible, is_required: field.is_required }
}

function cancelEditField() {
  editingFieldKey.value = null
  editingField.value = { is_visible: true, is_required: false }
}

async function saveEditField() {
  if (!selectedCategoryId.value || !editingFieldKey.value) return
  savingField.value = true
  const result = await pipelineStore.updateField(selectedCategoryId.value, editingFieldKey.value, {
    is_visible: editingField.value.is_visible,
    is_required: editingField.value.is_required,
  })
  savingField.value = false
  if (result.ok) {
    toast.success(t('pipeline.fieldUpdated'))
    cancelEditField()
  } else {
    toast.error(result.error ?? t('pipeline.fieldUpdateFailed'))
  }
}

async function createField() {
  if (!selectedCategoryId.value || !newFieldKey.value) return
  savingField.value = true
  const nextOrder = selectedFields.value.length
    ? Math.max(0, ...selectedFields.value.map((f) => f.order)) + 1
    : 0
  const result = await pipelineStore.createField(selectedCategoryId.value, newFieldKey.value, {
    is_visible: newFieldIsVisible.value,
    is_required: newFieldIsRequired.value,
    order: nextOrder,
  })
  savingField.value = false
  if (result.ok) {
    toast.success(t('pipeline.fieldCreated'))
    newFieldKey.value = ''
    newFieldIsVisible.value = true
    newFieldIsRequired.value = false
    showNewFieldForm.value = false
  } else {
    toast.error(result.error ?? t('pipeline.fieldCreateFailed'))
  }
}

async function confirmDeleteField() {
  if (!pendingDeleteFieldKey.value || !selectedCategoryId.value) return
  const result = await pipelineStore.deleteField(selectedCategoryId.value, pendingDeleteFieldKey.value)
  if (result.ok) {
    toast.success(t('pipeline.fieldDeleted'))
  } else {
    toast.error(result.error ?? t('pipeline.fieldDeleteFailed'))
  }
  pendingDeleteFieldKey.value = null
}

// ---------------------------------------------------------------------------
// Drag-and-drop field reordering
// ---------------------------------------------------------------------------

const draggableFields = computed({
  get: () => selectedCategoryId.value ? pipelineStore.getFieldsForCategory(selectedCategoryId.value) : [],
  set: (reordered: CategoryFieldOut[]) => {
    if (!selectedCategoryId.value) return
    const cat = pipelineStore.getCategoryById(selectedCategoryId.value)
    if (cat) cat.fields = reordered
  },
})

async function onFieldDragEnd() {
  if (!selectedCategoryId.value) return
  const fields = pipelineStore.getFieldsForCategory(selectedCategoryId.value)
  await Promise.all(
    fields.map((field, idx) =>
      pipelineStore.updateField(selectedCategoryId.value!, field.field_key, { order: idx }),
    ),
  )
}
</script>

<template>
  <div class="p-6 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold text-gray-900">{{ t('pipeline.settingsTitle') }}</h1>
    </div>

    <div v-if="pipelineStore.loading" class="text-gray-500 text-sm">{{ t('pipeline.loadingCategories') }}</div>

    <div v-else class="flex gap-6 min-h-[500px]">
      <!-- Left panel: categories -->
      <div class="w-64 flex-shrink-0 space-y-2">
        <div class="text-xs font-semibold uppercase text-gray-400 tracking-wider mb-1">Kategorie</div>

        <div
          v-for="cat in categories"
          :key="cat.id"
          class="group relative flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
          :class="selectedCategoryId === cat.id ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-50 text-gray-700'"
          @click="selectCategory(cat.id)"
        >
          <!-- Color dot -->
          <span
            class="w-3 h-3 rounded-full flex-shrink-0"
            :style="{ backgroundColor: cat.color || '#94A3B8' }"
          ></span>

          <!-- Name or inline edit -->
          <template v-if="editingCategoryId === cat.id">
            <input
              v-model="editingCategoryName"
              class="flex-1 text-sm border border-indigo-300 rounded px-1 py-0.5 outline-none"
              @keyup.enter="saveEditCategory"
              @keyup.escape="cancelEditCategory"
              @click.stop
            />
            <button class="p-0.5 text-green-600 hover:text-green-700" @click.stop="saveEditCategory">
              <CheckIcon class="w-4 h-4" />
            </button>
            <button class="p-0.5 text-gray-400 hover:text-gray-600" @click.stop="cancelEditCategory">
              <XMarkIcon class="w-4 h-4" />
            </button>
          </template>
          <template v-else>
            <span class="flex-1 text-sm font-medium truncate">{{ cat.name }}</span>
            <div class="hidden group-hover:flex items-center gap-1">
              <button class="p-0.5 text-gray-400 hover:text-gray-600" @click.stop="startEditCategory(cat)">
                <PencilSquareIcon class="w-4 h-4" />
              </button>
              <button class="p-0.5 text-gray-400 hover:text-red-500" @click.stop="pendingDeleteCategoryId = cat.id">
                <TrashIcon class="w-4 h-4" />
              </button>
            </div>
          </template>
        </div>

        <!-- Add category -->
        <div v-if="showNewCategoryForm" class="space-y-2 p-2 border border-gray-200 rounded-lg">
          <input
            v-model="newCategoryName"
            placeholder="Název kategorie"
            class="w-full text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
            @keyup.enter="createCategory"
          />
          <div class="flex items-center gap-2">
            <label class="text-xs text-gray-500">Barva</label>
            <input v-model="newCategoryColor" type="color" class="w-8 h-6 rounded cursor-pointer border border-gray-200" />
          </div>
          <div class="flex gap-1">
            <button
              class="flex-1 px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
              :disabled="savingCategory || !newCategoryName.trim()"
              @click="createCategory"
            >Přidat</button>
            <button
              class="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
              @click="showNewCategoryForm = false"
            >Zrušit</button>
          </div>
        </div>
        <button
          v-else
          class="flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 px-3 py-1"
          @click="showNewCategoryForm = true"
        >
          <PlusIcon class="w-4 h-4" />
          Nová kategorie
        </button>
      </div>

      <!-- Right panel: stages & fields -->
      <div class="flex-1 space-y-6">
        <template v-if="selectedCategory">
          <!-- Category header -->
          <div class="flex items-center gap-3">
            <span
              class="w-4 h-4 rounded-full"
              :style="{ backgroundColor: selectedCategory.color || '#94A3B8' }"
            ></span>
            <h2 class="text-lg font-semibold text-gray-900">{{ selectedCategory.name }}</h2>
            <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{{ selectedCategory.slug }}</span>
          </div>

          <!-- Stages -->
          <div>
            <div class="text-sm font-semibold text-gray-700 mb-2">Stavy (stages)</div>

            <VueDraggable
              v-model="draggableStages"
              handle=".stage-drag-handle"
              class="space-y-2"
              @end="onStageDragEnd"
            >
              <div
                v-for="stage in draggableStages"
                :key="stage.id"
                class="flex items-center gap-3 p-3 border border-gray-100 rounded-lg bg-white group"
              >
                <!-- Drag handle -->
                <span class="stage-drag-handle cursor-grab text-gray-300 hover:text-gray-500 flex-shrink-0" :title="t('pipeline.stageDragHandle')">
                  <Bars3Icon class="w-4 h-4" />
                </span>

                <!-- Color -->
                <span class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: stage.color || '#94A3B8' }"></span>

                <template v-if="editingStageId === stage.id">
                  <div class="flex-1 grid grid-cols-2 gap-2">
                    <input
                      v-model="editingStage.name"
                      placeholder="Název"
                      class="text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                    />
                    <input
                      v-model="editingStage.color"
                      type="color"
                      class="w-10 h-8 rounded cursor-pointer border border-gray-200"
                    />
                    <label class="flex items-center gap-1 text-xs text-gray-600 col-span-2">
                      <input v-model="editingStage.is_terminal" type="checkbox" class="rounded" />
                      Terminální stav
                    </label>
                    <label v-if="editingStage.is_terminal" class="flex items-center gap-1 text-xs text-gray-600 col-span-2">
                      <input v-model="editingStage.is_won" type="checkbox" class="rounded" />
                      Je to výhra (won)
                    </label>
                  </div>
                  <div class="flex gap-1">
                    <button class="p-1 text-green-600 hover:text-green-700" :disabled="savingStage" @click="saveEditStage">
                      <CheckIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="cancelEditStage">
                      <XMarkIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
                <template v-else>
                  <span class="flex-1 text-sm font-medium text-gray-800">{{ stage.name }}</span>
                  <div class="flex items-center gap-2">
                    <span v-if="stage.is_terminal && stage.is_won" class="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">Výhra</span>
                    <span v-else-if="stage.is_terminal" class="text-xs text-red-500 bg-red-50 px-1.5 py-0.5 rounded">Konec</span>
                  </div>
                  <div class="hidden group-hover:flex items-center gap-1">
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="startEditStage(stage)">
                      <PencilSquareIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-red-500" @click="pendingDeleteStageId = stage.id">
                      <TrashIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
              </div>
            </VueDraggable>

              <!-- Add stage form -->
              <div v-if="showNewStageForm" class="p-3 border border-indigo-100 rounded-lg bg-indigo-50 space-y-2 mt-2">
                <div class="grid grid-cols-2 gap-2">
                  <input
                    v-model="newStageName"
                    placeholder="Název stavu"
                    class="col-span-2 text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                    @keyup.enter="createStage"
                  />
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-gray-500">Barva</label>
                    <input v-model="newStageColor" type="color" class="w-8 h-6 rounded cursor-pointer border border-gray-200" />
                  </div>
                  <label class="flex items-center gap-1 text-xs text-gray-600">
                    <input v-model="newStageIsTerminal" type="checkbox" class="rounded" />
                    Terminální
                  </label>
                  <label v-if="newStageIsTerminal" class="flex items-center gap-1 text-xs text-gray-600 col-span-2">
                    <input v-model="newStageIsWon" type="checkbox" class="rounded" />
                    Je to výhra (won)
                  </label>
                </div>
                <div class="flex gap-2">
                  <button
                    class="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                    :disabled="savingStage || !newStageName.trim()"
                    @click="createStage"
                  >Přidat stav</button>
                  <button
                    class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700"
                    @click="showNewStageForm = false"
                  >Zrušit</button>
                </div>
              </div>

              <button
                v-if="!showNewStageForm"
                class="flex items-center gap-1 mt-2 text-sm text-indigo-600 hover:text-indigo-700"
                @click="showNewStageForm = true"
              >
                <PlusIcon class="w-4 h-4" />
                Přidat stav
              </button>
          </div>

          <!-- Fields management -->
          <div>
            <div class="text-sm font-semibold text-gray-700 mb-2">{{ t('pipeline.fieldsTitle') }}</div>

            <VueDraggable
              v-model="draggableFields"
              handle=".field-drag-handle"
              class="space-y-2"
              @end="onFieldDragEnd"
            >
              <div
                v-for="field in draggableFields"
                :key="field.field_key"
                class="flex items-center gap-3 p-3 border border-gray-100 rounded-lg bg-white group"
              >
                <!-- Drag handle -->
                <span class="field-drag-handle cursor-grab text-gray-300 hover:text-gray-500 flex-shrink-0" :title="t('pipeline.fieldDragHandle')">
                  <Bars3Icon class="w-4 h-4" />
                </span>

                <template v-if="editingFieldKey === field.field_key">
                  <div class="flex-1 flex flex-col gap-1">
                    <span class="text-sm font-medium text-gray-800">{{ t(`pipeline.fieldKey.${field.field_key}`) }}</span>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-1 text-xs text-gray-600">
                        <input v-model="editingField.is_visible" type="checkbox" class="rounded" />
                        {{ t('pipeline.fieldVisible') }}
                      </label>
                      <label class="flex items-center gap-1 text-xs text-gray-600">
                        <input v-model="editingField.is_required" type="checkbox" class="rounded" />
                        {{ t('pipeline.fieldRequired') }}
                      </label>
                    </div>
                  </div>
                  <div class="flex gap-1">
                    <button class="p-1 text-green-600 hover:text-green-700" :disabled="savingField" @click="saveEditField">
                      <CheckIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="cancelEditField">
                      <XMarkIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
                <template v-else>
                  <span class="flex-1 text-sm font-medium text-gray-800">{{ t(`pipeline.fieldKey.${field.field_key}`) }}</span>
                  <div class="flex items-center gap-2">
                    <span v-if="!field.is_visible" class="text-xs text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">{{ t('pipeline.fieldHidden') }}</span>
                    <span v-if="field.is_required" class="text-xs text-red-500 bg-red-50 px-1.5 py-0.5 rounded">{{ t('pipeline.fieldRequired') }}</span>
                  </div>
                  <div class="hidden group-hover:flex items-center gap-1">
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="startEditField(field)">
                      <PencilSquareIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-red-500" @click="pendingDeleteFieldKey = field.field_key">
                      <TrashIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
              </div>
            </VueDraggable>

            <p v-if="selectedFields.length === 0 && !showNewFieldForm" class="text-xs text-gray-400 py-1">
              {{ t('pipeline.noFields') }}
            </p>

            <!-- Add field form -->
            <div v-if="showNewFieldForm" class="p-3 border border-indigo-100 rounded-lg bg-indigo-50 space-y-2 mt-2">
              <div class="space-y-2">
                <select
                  v-model="newFieldKey"
                  class="w-full text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                >
                  <option value="" disabled>{{ t('pipeline.fieldKeyPlaceholder') }}</option>
                  <option v-for="key in availableFieldKeys" :key="key" :value="key">
                    {{ t(`pipeline.fieldKey.${key}`) }}
                  </option>
                </select>
                <div class="flex gap-4">
                  <label class="flex items-center gap-1 text-xs text-gray-600">
                    <input v-model="newFieldIsVisible" type="checkbox" class="rounded" />
                    {{ t('pipeline.fieldVisible') }}
                  </label>
                  <label class="flex items-center gap-1 text-xs text-gray-600">
                    <input v-model="newFieldIsRequired" type="checkbox" class="rounded" />
                    {{ t('pipeline.fieldRequired') }}
                  </label>
                </div>
              </div>
              <div class="flex gap-2">
                <button
                  class="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                  :disabled="savingField || !newFieldKey"
                  @click="createField"
                >{{ t('pipeline.addField') }}</button>
                <button
                  class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700"
                  @click="showNewFieldForm = false"
                >{{ t('pipeline.cancel') }}</button>
              </div>
            </div>

            <button
              v-if="!showNewFieldForm && availableFieldKeys.length > 0"
              class="flex items-center gap-1 mt-2 text-sm text-indigo-600 hover:text-indigo-700"
              @click="showNewFieldForm = true"
            >
              <PlusIcon class="w-4 h-4" />
              {{ t('pipeline.addField') }}
            </button>
          </div>
        </template>

        <div v-else class="flex items-center justify-center h-48 text-gray-400 text-sm">
          Vyberte kategorii vlevo
        </div>
      </div>
    </div>
  </div>

  <!-- Delete category confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeleteCategoryId"
    :message="t('pipeline.confirmDeleteCategory')"
    @confirm="confirmDeleteCategory"
    @cancel="pendingDeleteCategoryId = null"
  />

  <!-- Delete stage confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeleteStageId"
    :message="t('pipeline.confirmDeleteStage')"
    @confirm="confirmDeleteStage"
    @cancel="pendingDeleteStageId = null"
  />

  <!-- Delete field confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeleteFieldKey"
    :message="t('pipeline.confirmDeleteField')"
    @confirm="confirmDeleteField"
    @cancel="pendingDeleteFieldKey = null"
  />
</template>

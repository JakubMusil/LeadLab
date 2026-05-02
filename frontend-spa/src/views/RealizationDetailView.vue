<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRealizationsStore, REALIZATION_STATUSES, getRealizationStatusMeta, type MilestoneOut } from '@/stores/realizations'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { type DocumentOut, docFileIcon, fmtDocBytes } from '@/types/documents'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import EntitySidebarActionPicker from '@/components/EntitySidebarActionPicker.vue'

import StreamlineFilterDropdown from '@/components/StreamlineFilterDropdown.vue'

const route = useRoute()
const router = useRouter()
const store = useRealizationsStore()
const authStore = useAuthStore()
const toast = useToast()
const { t } = useI18n()

const realizationId = computed(() => route.params.id as string)

const selectedShortcutId = ref('overview')
const customFilters = ref<Set<string>>(new Set())
const newShortcutName = ref('')
const allTools = ref<any[]>([])

interface ShortcutPreset {
  id: string
  name: string
  visible_activity_types: string[]
}
const shortcuts = ref<ShortcutPreset[]>([])

const shortcutsKey = computed(() => {
  const userId = authStore.user?.id || 'guest'
  return `realization_shortcuts_u${userId}`
})

function loadShortcuts() {
  const data = localStorage.getItem(shortcutsKey.value)
  if (data) {
    try {
      shortcuts.value = JSON.parse(data)
    } catch {
      shortcuts.value = []
    }
  } else {
    shortcuts.value = [
      { id: 'sc-tasks', name: 'Úkoly', visible_activity_types: ['task', 'task_assigned', 'task_completed', 'task_created', 'task_reopened'] },
      { id: 'sc-files', name: 'Soubory', visible_activity_types: ['file_upload'] }
    ]
  }
}

function saveShortcutsToLocalStorage() {
  localStorage.setItem(shortcutsKey.value, JSON.stringify(shortcuts.value))
}

function moveShortcut(fromIdx: number, toIdx: number) {
  const arr = [...shortcuts.value]
  const item = arr[fromIdx]
  if (!item) return
  arr.splice(fromIdx, 1)
  arr.splice(toIdx, 0, item)
  shortcuts.value = arr
  saveShortcutsToLocalStorage()
}

function deleteShortcut(id: string) {
  shortcuts.value = shortcuts.value.filter(s => s.id !== id)
  saveShortcutsToLocalStorage()
  if (selectedShortcutId.value === id) {
    selectedShortcutId.value = 'overview'
  }
}

async function loadTools() {
  const res = await api.get<any[]>('/api/v1/streamline/tools')
  if (res.ok) {
    allTools.value = res.data
  }
}

const availableTools = computed(() => {
  const t = [...allTools.value]
  if (!t.some((x) => x.activity_type === 'task')) {
    t.push({
      activity_type: 'task',
      label: 'Úkoly',
      category: 'task',
      default_visibility: 'important',
    })
  }
  return t
})

const importantToolsSet = computed(() => {
  return new Set(availableTools.value.filter((t: any) => t.default_visibility === 'important').map((t: any) => t.activity_type))
})

const currentVisibleTypes = computed(() => {
  if (selectedShortcutId.value === 'overview') {
    return importantToolsSet.value
  }
  if (selectedShortcutId.value === 'custom') {
    return customFilters.value
  }
  const preset = shortcuts.value.find(s => s.id === selectedShortcutId.value)
  if (preset) {
    return new Set(preset.visible_activity_types)
  }
  return importantToolsSet.value
})

function onCustomFilterChange(next: string[] | null) {
  if (next === null) {
    customFilters.value = importantToolsSet.value
  } else {
    customFilters.value = new Set(next)
  }
  selectedShortcutId.value = 'custom'
}

function saveCurrentAsShortcut() {
  const name = newShortcutName.value.trim()
  if (!name) return
  const id = `sc-${Date.now()}`
  shortcuts.value.push({
    id,
    name,
    visible_activity_types: Array.from(customFilters.value),
  })
  saveShortcutsToLocalStorage()
  selectedShortcutId.value = id
  newShortcutName.value = ''
}

const displayedStatuses = computed(() => {
  return REALIZATION_STATUSES.map(s => ({
    value: s.value,
    label: s.label
  }))
})

const currentStatusIndex = computed(() => {
  const current = store.currentRealization?.status || 'planned'
  return displayedStatuses.value.findIndex((s) => s.value === current)
})

function getStatusBg(status: string) {
  switch (status) {
    case 'planned': return 'bg-gray-400'
    case 'in_progress': return 'bg-blue-500'
    case 'on_hold': return 'bg-yellow-500'
    case 'done': return 'bg-green-500'
    case 'cancelled': return 'bg-red-500'
    default: return 'bg-indigo-500'
  }
}

function getStatusHexColor(status: string) {
  switch (status) {
    case 'planned': return '#9ca3af'
    case 'in_progress': return '#3b82f6'
    case 'on_hold': return '#eab308'
    case 'done': return '#22c55e'
    case 'cancelled': return '#ef4444'
    default: return '#6366f1'
  }
}

type Tab = 'overview' | 'tasks' | 'milestones' | 'proposals' | 'documents'
const activeTab = ref<Tab>('overview')


// ActivityTimeline ref — used to reload feed after sidebar quick-action submits.
const activityTimelineRef = ref<InstanceType<typeof ActivityTimeline> | null>(null)

const editingTitle = ref(false)
const titleDraft = ref('')
const savingTitle = ref(false)

// Milestone form
const showMilestoneForm = ref(false)
const milestoneFormName = ref('')
const milestoneFormDate = ref('')
const milestoneFormDesc = ref('')
const milestoneFormLoading = ref(false)

// Linked proposals
interface ProposalOut { id: string; title: string; status: string; total_value: string; currency: string; created_at: string }
const linkedProposals = ref<ProposalOut[]>([])
const proposalsLoading = ref(false)

const realization = computed(() => store.currentRealization)

async function saveTitle() {
  if (!realization.value) return
  if (!titleDraft.value.trim()) { editingTitle.value = false; return }
  savingTitle.value = true
  try {
    await store.updateRealization(realization.value.id, { title: titleDraft.value.trim() })
    toast.success(t('realizations.titleSaved'))
  } finally {
    savingTitle.value = false
    editingTitle.value = false
  }
}

function startEditTitle() {
  titleDraft.value = realization.value?.title ?? ''
  editingTitle.value = true
}

// Inline description editing (plain text — Realization.description is a plain string)
const editingDescription = ref(false)
const descriptionDraft = ref('')
const savingDescription = ref(false)

function startEditDescription() {
  descriptionDraft.value = realization.value?.description ?? ''
  editingDescription.value = true
}

async function saveDescription() {
  if (!realization.value) return
  savingDescription.value = true
  try {
    const result = await store.updateRealization(realization.value.id, { description: descriptionDraft.value })
    if (result) {
      toast.success(t('realizations.updated'))
      editingDescription.value = false
    } else {
      toast.error(t('realizations.failedToUpdate'))
    }
  } finally {
    savingDescription.value = false
  }
}

function cancelEditDescription() {
  editingDescription.value = false
}

async function updateStatus(status: string) {
  if (!realization.value) return
  await store.updateRealization(realization.value.id, { status })
}

// Milestones
async function createMilestone() {
  if (!realization.value || !milestoneFormName.value.trim() || !milestoneFormDate.value) return
  milestoneFormLoading.value = true
  try {
    await api.post(
      `/api/v1/crm/realizations/${realization.value.id}/milestones`,
      {
        name: milestoneFormName.value.trim(),
        date: milestoneFormDate.value,
        description: milestoneFormDesc.value,
      },
    )
    await store.fetchRealization(realization.value.id)
    toast.success(t('realizations.milestoneAdded'))
    milestoneFormName.value = ''
    milestoneFormDate.value = ''
    milestoneFormDesc.value = ''
    showMilestoneForm.value = false
  } catch {
    toast.error(t('realizations.failedToAddMilestone'))
  } finally {
    milestoneFormLoading.value = false
  }
}

async function toggleMilestone(m: MilestoneOut) {
  if (!realization.value) return
  try {
    await api.patch(
      `/api/v1/crm/realizations/${realization.value.id}/milestones/${m.id}`,
      { is_completed: !m.is_completed },
    )
    await store.fetchRealization(realization.value.id)
  } catch {
    toast.error(t('common.error'))
  }
}

async function deleteMilestone(m: MilestoneOut) {
  if (!realization.value) return
  try {
    await api.delete(
      `/api/v1/crm/realizations/${realization.value.id}/milestones/${m.id}`,
    )
    await store.fetchRealization(realization.value.id)
    toast.success(t('realizations.milestoneDeleted'))
  } catch {
    toast.error(t('common.error'))
  }
}

const completedMilestones = computed(() => realization.value?.milestones.filter((m) => m.is_completed).length ?? 0)
const totalMilestones = computed(() => realization.value?.milestones.length ?? 0)

async function loadLinkedProposals() {
  proposalsLoading.value = true
  try {
    const res = await api.get<ProposalOut[]>(`/api/v1/crm/proposals?realization_id=${realizationId.value}`)
    if (res.ok) linkedProposals.value = res.data
  } finally {
    proposalsLoading.value = false
  }
}

function proposalStatusColor(status: string) {
  const map: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700', sent: 'bg-blue-100 text-blue-700',
    viewed: 'bg-yellow-100 text-yellow-700', accepted: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700', expired: 'bg-orange-100 text-orange-700',
  }
  return map[status] ?? 'bg-gray-100 text-gray-700'
}

// ---------------------------------------------------------------------------
// Documents
// ---------------------------------------------------------------------------
const documents = ref<DocumentOut[]>([])
const docsLoading = ref(false)
const docsUploading = ref(false)
const docFileInputRef = ref<HTMLInputElement | null>(null)
const deleteDocId = ref<string | null>(null)

async function loadDocuments() {
  docsLoading.value = true
  try {
    const res = await api.get<DocumentOut[]>(`/api/v1/erp/documents?realization_id=${realizationId.value}`)
    if (res.ok) documents.value = res.data
  } finally {
    docsLoading.value = false
  }
}

async function onDocFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  docsUploading.value = true
  for (const file of Array.from(input.files)) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', file.name)
    fd.append('realization_id', realizationId.value)
    const res = await api.postForm<DocumentOut>('/api/v1/erp/documents', fd)
    if (res.ok) documents.value.unshift(res.data)
  }
  docsUploading.value = false
  input.value = ''
}

async function deleteDocument() {
  const id = deleteDocId.value
  if (!id) return
  deleteDocId.value = null
  const res = await api.delete(`/api/v1/erp/documents/${id}`)
  if (res.ok) documents.value = documents.value.filter(d => d.id !== id)
}

onMounted(async () => {
  loadShortcuts()
  await loadTools()
  await store.fetchRealization(realizationId.value)
  await loadLinkedProposals()
})</script>

<template>
  <div class="p-6">
    <!-- Back -->
    <RouterLink to="/app/realizations" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4">
      ← Realizace
    </RouterLink>

    <!-- Loading skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-64" />
      <div class="h-24 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="realization">
      <!-- Title -->
      <div class="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 whitespace-nowrap overflow-hidden text-ellipsis">
          🛠 Realizace - {{ realization.title }}
        </h1>
        <div class="flex-shrink-0">
          <select
            :value="realization.status"
            @change="updateStatus(($event.target as HTMLSelectElement).value)"
            :class="getRealizationStatusMeta(realization.status).color"
            class="rounded-lg px-3 py-1.5 text-sm font-medium border-0 cursor-pointer focus:ring-2 focus:ring-red-500 outline-none"
          >
            <option v-for="s in REALIZATION_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </div>
      </div>

      <!-- Progress bar exactly like Lead Detail -->
      <div class="mb-6 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl p-4 shadow-sm select-none">
        <div class="flex items-center justify-between gap-1 select-none">
          <div v-for="(s, i) in displayedStatuses" :key="s.value" class="flex-1 flex flex-col gap-1.5 items-center relative">
            <div
              class="w-full h-1.5 rounded-full transition-all duration-300"
              :class="[
                i <= currentStatusIndex ? getStatusBg(s.value) : 'bg-gray-200 dark:bg-gray-700',
                i === currentStatusIndex ? 'scale-y-125' : ''
              ]"
              :style="i === currentStatusIndex ? { boxShadow: '0 0 0 2px ' + getStatusHexColor(s.value) + '80' } : {}"
            />
            <span
              class="text-[10px] sm:text-xs font-semibold select-none text-center transition-colors"
              :class="i <= currentStatusIndex ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 dark:text-gray-600'"
            >
              {{ s.label }}
            </span>
          </div>
        </div>
      </div>

      <!-- Tabs exactly like Lead Detail -->
      <div class="flex border-b border-gray-200 dark:border-gray-700 mb-6">
        <button
          v-for="tab in [
            { id: 'overview', label: t('realizations.tabOverview') },
            { id: 'milestones', label: `${t('realizations.tabMilestones')} (${totalMilestones})` },
            { id: 'tasks', label: t('realizations.tabTasks') },
            { id: 'proposals', label: t('realizations.tabProposals') },
            { id: 'documents', label: `${t('realizations.tabDocuments')} (${documents.length})` },
          ]"
          :key="tab.id"
          @click="activeTab = tab.id as Tab; if (tab.id === 'documents' && documents.length === 0) loadDocuments()"
          :class="activeTab === tab.id
            ? 'border-b-2 border-red-600 text-red-600'
            : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
          class="px-4 py-3 text-sm font-medium"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Overview tab: streamline left + sidebar right -->
      <div v-if="activeTab === 'overview'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Left Column: Activity Feed & Presets Switcher from Lead Detail -->
        <div class="lg:col-span-2">
          <!-- Switchers: Přehled + user presets + Filtry -->
          <div class="flex flex-wrap items-center gap-1.5 bg-gray-100 dark:bg-gray-800 rounded-xl p-1 mb-4">
            <button
              class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
              :class="selectedShortcutId === 'overview' ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
              @click="selectedShortcutId = 'overview'"
            >
              Přehled
            </button>

            <!-- User defined shortcuts -->
            <button
              v-for="shortcut in shortcuts"
              :key="shortcut.id"
              class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
              :class="selectedShortcutId === shortcut.id ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
              @click="selectedShortcutId = shortcut.id"
            >
              {{ shortcut.name }}
            </button>

            <!-- Filtry button -->
            <div class="relative flex items-center h-full">
              <StreamlineFilterDropdown
                :tools="availableTools"
                :model-value="currentVisibleTypes"
                :is-customised="selectedShortcutId === 'custom'"
                :shortcuts="shortcuts"
                @update:visible="onCustomFilterChange"
                @delete-shortcut="deleteShortcut"
                @move-shortcut="(payload) => moveShortcut(payload.fromIdx, payload.toIdx)"
              />
            </div>
          </div>

          <!-- Quick action to save custom filter as shortcut if it's selected -->
          <div v-if="selectedShortcutId === 'custom'" class="flex items-center gap-2 mb-4 bg-gray-50 dark:bg-gray-800/50 p-2 rounded-xl border border-gray-100 dark:border-gray-700 w-fit">
            <span class="text-xs text-gray-500 dark:text-gray-400">Nové zobrazení:</span>
            <input
              v-model="newShortcutName"
              type="text"
              placeholder="Název zkratky..."
              class="text-xs rounded-xl border border-gray-300 dark:border-gray-600 px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
            />
            <button
              class="text-xs px-3 py-1.5 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50"
              :disabled="!newShortcutName.trim()"
              @click="saveCurrentAsShortcut"
            >
              Uložit jako zkratku
            </button>
          </div>

          <!-- Activity feed -->
          <ActivityTimeline
            ref="activityTimelineRef"
            :hide-composer="true"
            entity-type="realization"
            :entity-id="realizationId"
            :hide-filter-dropdown="true"
            :override-visible-types="currentVisibleTypes"
          />
        </div>


      <!-- Right: sidebar (quick actions + description + milestones progress + meta) -->
      <div class="space-y-4">

        <!-- Quick actions (unified Streamline composer) -->
        <EntitySidebarActionPicker
          entity-type="realization"
          :entity-id="realizationId"
          @activity-added="activityTimelineRef?.load()"
        />

        <!-- Description -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">{{ t('realizations.descLabel') }}</h3>
            <button
              v-if="!editingDescription"
              class="text-[10px] text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
              @click="startEditDescription"
            >{{ t('realizations.edit') }}</button>
          </div>
          <template v-if="editingDescription">
            <textarea
              v-model="descriptionDraft"
              rows="4"
              class="w-full text-sm px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400 dark:focus:border-red-500 resize-y"
              :placeholder="t('realizations.descPlaceholder')"
            />
            <div class="flex justify-end gap-2 mt-1.5">
              <button
                class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                @click="cancelEditDescription"
              >{{ t('common.cancel') }}</button>
              <button
                :disabled="savingDescription"
                class="px-3 py-1 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                @click="saveDescription"
              >{{ savingDescription ? t('realizations.saving') : t('common.save') }}</button>
            </div>
          </template>
          <p
            v-else-if="realization.description"
            class="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap cursor-pointer"
            @click="startEditDescription"
          >{{ realization.description }}</p>
          <p
            v-else
            class="text-sm text-gray-400 dark:text-gray-500 italic cursor-pointer hover:text-gray-600 dark:hover:text-gray-300"
            @click="startEditDescription"
          >{{ t('realizations.descPlaceholder') }}</p>
        </div>

        <!-- Milestones progress -->
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{{ t('realizations.milestonesTitle') }}</h3>
          <div v-if="totalMilestones > 0">
            <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>{{ completedMilestones }} / {{ totalMilestones }} {{ t('realizations.completed') }}</span>
              <span>{{ Math.round((completedMilestones / totalMilestones) * 100) }}%</span>
            </div>
            <div class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                class="h-full bg-green-500 rounded-full transition-all"
                :style="{ width: `${Math.round((completedMilestones / totalMilestones) * 100)}%` }"
              />
            </div>
          </div>
          <p v-else class="text-sm text-gray-400">{{ t('realizations.noMilestones') }}</p>
        </div>

        <!-- Customer -->
        <div v-if="realization.customer_name" class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('realizations.colCustomer') }}</div>
          <div class="text-sm text-gray-900 dark:text-white">{{ realization.customer_name }}</div>
        </div>

        <!-- Lead -->
        <div v-if="realization.lead_title" class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('realizations.opportunityLabel') }}</div>
          <div class="text-sm text-gray-900 dark:text-white truncate">{{ realization.lead_title }}</div>
        </div>

        <!-- Assigned to -->
        <div v-if="realization.assigned_to_name" class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('realizations.assignedToLabel') }}</div>
          <div class="text-sm text-gray-900 dark:text-white">{{ realization.assigned_to_name }}</div>
        </div>

        <!-- Dates -->
        <div v-if="realization.start_date || realization.end_date" class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 space-y-2">
          <div v-if="realization.start_date">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">{{ t('realizations.startLabel') }}</div>
            <div class="text-sm text-gray-900 dark:text-white">{{ realization.start_date }}</div>
          </div>
          <div v-if="realization.end_date">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">{{ t('realizations.endLabel') }}</div>
            <div class="text-sm text-gray-900 dark:text-white">{{ realization.end_date }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Milestones tab -->
    <div v-if="activeTab === 'milestones'" class="space-y-4">
      <div class="flex justify-between items-center">
        <h2 class="text-base font-semibold text-gray-900 dark:text-white">{{ t('realizations.milestonesTitle') }}</h2>
        <button
          @click="showMilestoneForm = !showMilestoneForm"
          class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg"
        >
          + {{ t('realizations.addMilestone') }}
        </button>
      </div>

      <!-- Milestone form -->
      <div v-if="showMilestoneForm" class="bg-gray-50 dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 space-y-3">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Název *</label>
            <input
              v-model="milestoneFormName"
              type="text"
              placeholder="Název milníku"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.dateLabel') }}</label>
            <input
              v-model="milestoneFormDate"
              type="date"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>
        </div>
        <input
          v-model="milestoneFormDesc"
          type="text"
:placeholder="t('realizations.optionalDesc')"
          class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
        />
        <div class="flex gap-2">
          <button
            @click="createMilestone"
            :disabled="milestoneFormLoading"
            class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
          >
            {{ milestoneFormLoading ? 'Ukládám…' : 'Přidat' }}
          </button>
          <button @click="showMilestoneForm = false" class="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg">
            Zrušit
          </button>
        </div>
      </div>

      <!-- Milestone list -->
      <div class="space-y-2">
        <div
          v-for="m in realization.milestones"
          :key="m.id"
          class="flex items-center gap-3 bg-white dark:bg-gray-800 rounded-xl p-3 border border-gray-200 dark:border-gray-700"
        >
          <button
            @click="toggleMilestone(m)"
            :class="m.is_completed ? 'bg-green-500 text-white' : 'border-2 border-gray-300 dark:border-gray-600'"
            class="w-5 h-5 rounded-full flex-shrink-0 flex items-center justify-center text-xs"
          >
            <span v-if="m.is_completed">✓</span>
          </button>
          <div class="flex-1 min-w-0">
            <p :class="m.is_completed ? 'line-through text-gray-400' : 'text-gray-900 dark:text-white'" class="text-sm font-medium">
              {{ m.name }}
            </p>
            <p v-if="m.description" class="text-xs text-gray-500 mt-0.5">{{ m.description }}</p>
          </div>
          <span class="text-xs text-gray-400 flex-shrink-0">{{ m.date }}</span>
          <button
            @click="deleteMilestone(m)"
            class="text-gray-400 hover:text-red-600 text-xs flex-shrink-0"
          >✕</button>
        </div>
        <p v-if="realization.milestones.length === 0" class="text-sm text-gray-400 text-center py-4">
          Žádné milníky. Přidejte první.
        </p>
      </div>
    </div>

    <!-- Tasks tab -->
    <div v-if="activeTab === 'tasks'">
      <p class="text-sm text-gray-500">Propojení úkolů s realizací bude dostupné v další verzi.</p>
    </div>

    <!-- Proposals tab -->
    <div v-if="activeTab === 'proposals'" class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-gray-900 dark:text-white">Nabídky</h2>
        <RouterLink to="/app/proposals" class="text-xs text-red-600 hover:text-red-700">Všechny nabídky</RouterLink>
      </div>
      <div v-if="proposalsLoading" class="animate-pulse space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 rounded-xl" />
      </div>
      <div v-else-if="linkedProposals.length === 0" class="text-sm text-gray-400 text-center py-8">{{ t('realizations.noProposals') }}</div>
      <div v-else class="space-y-2">
        <RouterLink
          v-for="p in linkedProposals"
          :key="p.id"
          :to="`/app/proposals/${p.id}`"
          class="flex items-center gap-3 p-3 rounded-xl bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          <span class="flex-1 text-sm font-medium text-gray-900 dark:text-white truncate">{{ p.title }}</span>
          <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="proposalStatusColor(p.status)">{{ p.status }}</span>
          <span class="text-xs text-gray-500 font-mono">{{ Number(p.total_value).toFixed(2) }} {{ p.currency }}</span>
        </RouterLink>
      </div>
    </div>

    <!-- Documents tab -->
    <div v-if="activeTab === 'documents'" class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-gray-900 dark:text-white">Dokumenty</h2>
        <button
          @click="docFileInputRef?.click()"
          :disabled="docsUploading"
          class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
        >
          {{ docsUploading ? t('common.uploading') : t('common.upload') }}
        </button>
        <input ref="docFileInputRef" type="file" multiple class="hidden" @change="onDocFileSelected" />
      </div>

      <div v-if="docsLoading" class="animate-pulse space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>

      <div v-else-if="documents.length === 0" class="text-center py-12">
        <div class="text-4xl mb-3">📁</div>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('realizations.noDocs') }}</p>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('realizations.uploadHint') }}</p>
      </div>

      <div v-else class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
        <div v-for="doc in documents" :key="doc.id" class="flex items-center gap-3 p-3 group">
          <span class="text-xl">{{ docFileIcon(doc.content_type) }}</span>
          <div class="flex-1 min-w-0">
            <a :href="doc.file_url" target="_blank" rel="noopener noreferrer"
               class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 truncate block">
              {{ doc.name }}
            </a>
            <p class="text-xs text-gray-400">{{ fmtDocBytes(doc.size_bytes) }} · {{ doc.uploaded_by_name || '—' }} · {{ new Date(doc.created_at).toLocaleDateString('cs-CZ') }}</p>
          </div>
          <button
            @click="deleteDocId = doc.id"
            class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 text-sm transition-opacity"
          >🗑</button>
        </div>
      </div>

      <!-- Delete confirm -->
      <div v-if="deleteDocId" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="deleteDocId = null">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-xl max-w-sm w-full mx-4">
          <p class="text-gray-800 dark:text-white font-medium mb-4">{{ t('realizations.confirmDeleteDoc') }}</p>
          <div class="flex gap-3 justify-end">
            <button @click="deleteDocId = null" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">{{ t('common.cancel') }}</button>
            <button @click="deleteDocument" class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg">{{ t('common.delete') }}</button>
          </div>
        </div>
      </div>
    </div>
  </template>
  <div v-else class="text-center py-12 text-gray-400 dark:text-gray-500">{{ t('realizations.notFound') }}</div>
</div>
</template>


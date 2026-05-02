<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useManagementStore,
  MANAGEMENT_STATUSES,
  MANAGEMENT_TYPES,
  getManagementStatusMeta,
} from '@/stores/management'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { type DocumentOut, docFileIcon, fmtDocBytes } from '@/types/documents'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import EntitySidebarActionPicker from '@/components/EntitySidebarActionPicker.vue'

import { useAuthStore } from '@/stores/auth'
import StreamlineFilterDropdown from '@/components/StreamlineFilterDropdown.vue'

const route = useRoute()
const router = useRouter()
const store = useManagementStore()
const authStore = useAuthStore()
const toast = useToast()
const { t } = useI18n()

const recordId = computed(() => route.params.id as string)

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
  return `management_shortcuts_u${userId}`
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
  return MANAGEMENT_STATUSES.map(s => ({
    value: s.value,
    label: s.label
  }))
})

const currentStatusIndex = computed(() => {
  const current = store.currentRecord?.status || 'new'
  return displayedStatuses.value.findIndex((s) => s.value === current)
})

function getStatusBg(status: string) {
  switch (status) {
    case 'new': return 'bg-gray-400'
    case 'investigating': return 'bg-blue-500'
    case 'working': return 'bg-yellow-500'
    case 'waiting': return 'bg-orange-500'
    case 'solved': return 'bg-green-500'
    case 'closed': return 'bg-gray-500'
    default: return 'bg-indigo-500'
  }
}

function getStatusHexColor(status: string) {
  switch (status) {
    case 'new': return '#9ca3af'
    case 'investigating': return '#3b82f6'
    case 'working': return '#eab308'
    case 'waiting': return '#f97316'
    case 'solved': return '#22c55e'
    case 'closed': return '#6b7280'
    default: return '#6366f1'
  }
}


// ActivityTimeline ref (used to reload feed after sidebar quick-action submits).
const activityTimelineRef = ref<InstanceType<typeof ActivityTimeline> | null>(null)

type Tab = 'overview' | 'tasks' | 'proposals' | 'documents'
const activeTab = ref<Tab>('overview')

const editingTitle = ref(false)
const titleDraft = ref('')
const savingTitle = ref(false)

// Linked proposals
interface ProposalOut { id: string; title: string; status: string; total_value: string; currency: string; created_at: string }
const linkedProposals = ref<ProposalOut[]>([])
const proposalsLoading = ref(false)

async function loadLinkedProposals() {
  proposalsLoading.value = true
  try {
    const res = await api.get<ProposalOut[]>(`/api/v1/crm/proposals?management_id=${recordId.value}`)
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

onMounted(async () => {
  loadShortcuts()
  await loadTools()
  await store.fetchRecord(recordId.value)
  await loadLinkedProposals()
})


const record = computed(() => store.currentRecord as NonNullable<typeof store.currentRecord>)

async function saveTitle() {
  if (!record.value) return
  if (!titleDraft.value.trim()) { editingTitle.value = false; return }
  savingTitle.value = true
  try {
    await store.updateRecord(record.value.id, { title: titleDraft.value.trim() })
    toast.success(t('management.titleSaved'))
  } finally {
    savingTitle.value = false
    editingTitle.value = false
  }
}

function startEditTitle() {
  titleDraft.value = record.value?.title ?? ''
  editingTitle.value = true
}

async function updateStatus(status: string) {
  if (!record.value) return
  await store.updateRecord(record.value.id, { status })
  toast.success(t('management.statusUpdated'))
}

function slaBadgeClass(color: string | null | undefined) {
  if (color === 'red') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (color === 'yellow') return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
  if (color === 'green') return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
  return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
}

function slaLabel(expiresAt: string | null, slaColor: string | null) {
  if (!expiresAt) return null
  const diff = new Date(expiresAt).getTime() - Date.now()
  const days = Math.ceil(diff / 86400000)
  if (days < 0) return t('management.expiredDaysAgo', { days: Math.abs(days) })
  if (days === 0) return t('management.expiresToday')
  return t('management.expiresInDays', { days })
}

function formatDateTime(dt: string | null) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('cs-CZ', { dateStyle: 'medium', timeStyle: 'short' })
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
    const res = await api.get<DocumentOut[]>(`/api/v1/erp/documents?management_id=${recordId.value}`)
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
    fd.append('management_id', recordId.value)
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
</script>

<template>
  <div class="p-6">
    <!-- Back -->
    <RouterLink to="/app/management" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4">
      ← Správa
    </RouterLink>

    <!-- Loading skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-64" />
      <div class="h-24 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="record">
      <!-- Title -->
      <div class="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div class="flex-1 min-w-0">
          <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 whitespace-nowrap overflow-hidden text-ellipsis">
            📋 Správa - {{ record.title }}
          </h1>

          <!-- Metadata -->
          <div class="flex flex-wrap items-center gap-3 mt-2">
            <span
              :class="getManagementStatusMeta(record.status).color"
              class="px-2 py-0.5 rounded-full text-xs font-medium"
            >
              {{ getManagementStatusMeta(record.status).label }}
            </span>
            <span class="text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
              {{ MANAGEMENT_TYPES.find(t => t.value === record?.type)?.label ?? record.type }}
            </span>
            <span
              v-if="record.expires_at"
              :class="slaBadgeClass(record.sla_color)"
              class="text-xs px-2 py-0.5 rounded font-medium"
            >
              {{ slaLabel(record.expires_at, record.sla_color) }}
            </span>
          </div>
        </div>
        <div class="flex-shrink-0">
          <select
            :value="record.status"
            @change="updateStatus(($event.target as HTMLSelectElement).value)"
            class="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
          >
            <option v-for="s in MANAGEMENT_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
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
          v-for="tab in (['overview', 'tasks', 'proposals', 'documents'] as Tab[])"
          :key="tab"
          @click="activeTab = tab; if (tab === 'documents' && documents.length === 0) loadDocuments()"
          :class="activeTab === tab
            ? 'border-b-2 border-red-600 text-red-600 dark:text-red-400'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
          class="px-4 py-3 text-sm font-medium capitalize transition-colors"
        >
          {{ tab === 'overview' ? t('management.tabOverview') : tab === 'tasks' ? t('management.tabTasks') : tab === 'proposals' ? t('management.tabProposals') : `${t('management.tabDocuments')} (${documents.length})` }}
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
            entity-type="management"
            :entity-id="recordId"
            :hide-filter-dropdown="true"
            :override-visible-types="currentVisibleTypes"
          />
        </div>


        <!-- Right: toolbox -->
        <div class="space-y-4">
          <!-- Quick actions (unified Streamline composer) -->
          <EntitySidebarActionPicker
            entity-type="management"
            :entity-id="recordId"
            @activity-added="activityTimelineRef?.load()"
          />

          <!-- Notes -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">{{ t('management.notes') }}</h3>
            <p v-if="record.notes" class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{{ record.notes }}</p>
            <p v-else class="text-sm text-gray-400 italic">{{ t('management.noNotes') }}</p>
          </div>

          <!-- Created / Updated -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-xs text-gray-500 dark:text-gray-400 space-y-1">
            <div>{{ t('management.created') }}: {{ formatDateTime(record.created_at) }}</div>
            <div>{{ t('management.updated') }}: {{ formatDateTime(record.updated_at) }}</div>
          </div>

          <!-- Customer -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('management.customer') }}</div>
            <div v-if="record.customer_name" class="text-sm text-gray-900 dark:text-white">{{ record.customer_name }}</div>
            <div v-else class="text-sm text-gray-400 italic">{{ t('management.unassigned') }}</div>
          </div>

          <!-- Realization -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('management.realization') }}</div>
            <div v-if="record.realization_title">
              <button
                @click="router.push(`/app/realizations/${record.realization_id}`)"
                class="text-sm text-red-600 dark:text-red-400 hover:underline text-left"
              >
                {{ record.realization_title }}
              </button>
            </div>
            <div v-else class="text-sm text-gray-400 italic">{{ t('management.unassignedF') }}</div>
          </div>

          <!-- Assigned to -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('management.assigned') }}</div>
            <div v-if="record.assigned_to_name" class="text-sm text-gray-900 dark:text-white">{{ record.assigned_to_name }}</div>
            <div v-else class="text-sm text-gray-400 italic">{{ t('management.unassignedN') }}</div>
          </div>

          <!-- SLA / Expiry -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">{{ t('management.slaExpiry') }}</div>
            <div v-if="record.expires_at">
              <div class="text-sm text-gray-900 dark:text-white mb-1">{{ formatDateTime(record.expires_at) }}</div>
              <span :class="slaBadgeClass(record.sla_color)" class="text-xs px-2 py-0.5 rounded font-medium">
                {{ slaLabel(record.expires_at, record.sla_color) }}
              </span>
            </div>
            <div v-else class="text-sm text-gray-400 italic">{{ t('management.notSet') }}</div>
          </div>
        </div>
      </div>

      <!-- Tasks tab placeholder -->
      <div v-else-if="activeTab === 'tasks'" class="text-center py-12 text-gray-400 dark:text-gray-500">
        <p class="text-sm">{{ t('management.tasksPlaceholder') }}</p>
      </div>

      <!-- Proposals tab -->
      <div v-else-if="activeTab === 'proposals'" class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ t('management.proposals') }}</h3>
          <RouterLink to="/app/proposals" class="text-xs text-red-600 hover:text-red-700">{{ t('management.allProposals') }}</RouterLink>
        </div>
        <div v-if="proposalsLoading" class="animate-pulse space-y-2">
          <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 rounded-xl" />
        </div>
        <div v-else-if="linkedProposals.length === 0" class="text-sm text-gray-400 text-center py-8">
          {{ t('management.noProposals') }}
        </div>
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
      <div v-else-if="activeTab === 'documents'" class="space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-white">{{ t('management.documents') }}</h3>
          <button
            @click="docFileInputRef?.click()"
            :disabled="docsUploading"
            class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
          >
            {{ docsUploading ? t('management.uploading') : t('management.uploadBtn') }}
          </button>
          <input ref="docFileInputRef" type="file" multiple class="hidden" @change="onDocFileSelected" />
        </div>

        <div v-if="docsLoading" class="animate-pulse space-y-2">
          <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <div v-else-if="documents.length === 0" class="text-center py-10">
          <div class="text-4xl mb-2">📁</div>
          <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('management.noDocuments') }}</p>
        </div>

        <div v-else class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
          <div v-for="doc in documents" :key="doc.id" class="flex items-center gap-3 p-3 group">
            <span class="text-xl">{{ docFileIcon(doc.content_type) }}</span>
            <div class="flex-1 min-w-0">
              <a :href="doc.file_url" target="_blank" rel="noopener noreferrer"
                 class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 truncate block">
                {{ doc.name }}
              </a>
              <p class="text-xs text-gray-400">{{ fmtDocBytes(doc.size_bytes) }} · {{ new Date(doc.created_at).toLocaleDateString('cs-CZ') }}</p>
            </div>
            <button @click="deleteDocId = doc.id" class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 text-sm transition-opacity">🗑</button>
          </div>
        </div>

        <!-- Delete confirm -->
        <div v-if="deleteDocId" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50" @click.self="deleteDocId = null">
          <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-xl max-w-sm w-full mx-4">
            <p class="text-gray-800 dark:text-white font-medium mb-4">{{ t('management.confirmDocDelete') }}</p>
            <div class="flex gap-3 justify-end">
              <button @click="deleteDocId = null" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">{{ t('management.cancelBtn') }}</button>
              <button @click="deleteDocument" class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg">{{ t('management.deleteBtn') }}</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

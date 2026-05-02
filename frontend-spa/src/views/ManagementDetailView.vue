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
import {
  TrashIcon,
  FolderOpenIcon,
  DocumentTextIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ShieldExclamationIcon,
  LinkIcon,
} from '@heroicons/vue/24/outline'
import { useClipboard } from '@/composables/useClipboard'
import { ConfirmDeleteModal } from '@/components/ui'

const route = useRoute()
const router = useRouter()
const store = useManagementStore()
const authStore = useAuthStore()
const toast = useToast()
const { t } = useI18n()
const { copiedId: permalinkCopiedId, copyToClipboard } = useClipboard()
const currentPageUrl = computed(() => window.location.href)

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

const editingTitle = ref(false)
const titleDraft = ref('')
const savingTitle = ref(false)

// Linked proposals
interface ProposalOut { id: string; title: string; status: string; total_value: string; currency: string; created_at: string }
const linkedProposals = ref<ProposalOut[]>([])
const proposalsLoading = ref(false)
const showProposals = ref(false)
const showDocuments = ref(false)

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
  await loadDocuments()
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
      <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6 flex items-center gap-2 min-w-0">
        <ShieldExclamationIcon class="w-6 h-6 flex-shrink-0 text-gray-500 dark:text-gray-400" />
        <span class="truncate">{{ record.title }}</span>
        <button
          class="ml-1 flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors relative group/permalink"
          :title="permalinkCopiedId === 'page' ? 'Zkopírováno!' : 'Kopírovat odkaz'"
          @click="copyToClipboard(currentPageUrl, 'page')"
        >
          <LinkIcon class="w-4 h-4" />
          <span
            v-if="permalinkCopiedId === 'page'"
            class="absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-gray-900 dark:bg-gray-700 px-2 py-0.5 text-[10px] text-white pointer-events-none"
          >Zkopírováno!</span>
        </button>
      </h1>

      <!-- Progress bar -->
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

      <!-- 2-column layout — identical to Lead detail -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Left Column: Activity Feed & Presets Switcher -->
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

          <!-- Quick action to save custom filter as shortcut -->
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

        <!-- Right Column: Sidebar -->
        <div class="space-y-4">

          <!-- Management details card -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
            <h2 class="text-base font-bold text-gray-900 dark:text-gray-100 mb-3 leading-tight">
              {{ record.title }}
            </h2>
            <dl class="space-y-2">
              <div class="flex justify-between items-center">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.colStatus') }}</dt>
                <dd>
                  <select
                    :value="record.status"
                    @change="updateStatus(($event.target as HTMLSelectElement).value)"
                    class="border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1 text-xs bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
                  >
                    <option v-for="s in MANAGEMENT_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
                  </select>
                </dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.colType') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ MANAGEMENT_TYPES.find(tp => tp.value === record?.type)?.label ?? record.type }}</dd>
              </div>
              <div v-if="record.expires_at" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.slaExpiry') }}</dt>
                <dd>
                  <span :class="slaBadgeClass(record.sla_color)" class="text-xs px-1.5 py-0.5 rounded font-medium">
                    {{ slaLabel(record.expires_at, record.sla_color) }}
                  </span>
                </dd>
              </div>
              <div v-if="record.customer_name" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.customer') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 text-right truncate max-w-[10rem]">{{ record.customer_name }}</dd>
              </div>
              <div v-if="record.realization_title" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.realization') }}</dt>
                <dd>
                  <button
                    @click="router.push(`/app/realizations/${record.realization_id}`)"
                    class="text-xs text-red-600 dark:text-red-400 hover:underline text-right truncate max-w-[10rem] block"
                  >
                    {{ record.realization_title }}
                  </button>
                </dd>
              </div>
              <div v-if="record.assigned_to_name" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.assigned') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ record.assigned_to_name }}</dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.created') }}</dt>
                <dd class="text-xs text-gray-600 dark:text-gray-400">{{ formatDateTime(record.created_at) }}</dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.updated') }}</dt>
                <dd class="text-xs text-gray-600 dark:text-gray-400">{{ formatDateTime(record.updated_at) }}</dd>
              </div>
              <div v-if="record.notes" class="pt-2 border-t border-gray-100 dark:border-gray-700">
                <dt class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('management.notes') }}</dt>
                <dd class="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{{ record.notes }}</dd>
              </div>
            </dl>
          </div>

          <!-- Quick actions card -->
          <EntitySidebarActionPicker
            entity-type="management"
            :entity-id="recordId"
            @activity-added="activityTimelineRef?.load()"
          />

          <!-- Proposals section -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
            <button
              class="w-full flex items-center justify-between p-4 text-sm font-semibold text-gray-700 dark:text-gray-300"
              @click="showProposals = !showProposals"
            >
              <span class="flex items-center gap-2">
                <DocumentTextIcon class="w-4 h-4" />
                {{ t('management.proposals') }} <span v-if="linkedProposals.length" class="text-xs font-normal text-gray-400">({{ linkedProposals.length }})</span>
              </span>
              <ChevronUpIcon v-if="showProposals" class="w-4 h-4 text-gray-400" />
              <ChevronDownIcon v-else class="w-4 h-4 text-gray-400" />
            </button>
            <div v-if="showProposals" class="px-4 pb-4 space-y-2">
              <div v-if="proposalsLoading" class="animate-pulse space-y-2">
                <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-lg" />
              </div>
              <div v-else-if="linkedProposals.length === 0" class="text-xs text-gray-400 py-2">{{ t('management.noProposals') }}</div>
              <RouterLink
                v-for="p in linkedProposals"
                v-else
                :key="p.id"
                :to="`/app/proposals/${p.id}`"
                class="flex items-center gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
              >
                <span class="flex-1 text-xs font-medium text-gray-900 dark:text-white truncate">{{ p.title }}</span>
                <span class="text-[10px] px-1.5 py-0.5 rounded-full font-medium" :class="proposalStatusColor(p.status)">{{ p.status }}</span>
              </RouterLink>
              <RouterLink to="/app/proposals" class="text-xs text-red-600 hover:text-red-700 block pt-1">{{ t('management.allProposals') }} →</RouterLink>
            </div>
          </div>

          <!-- Documents section -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
            <button
              class="w-full flex items-center justify-between p-4 text-sm font-semibold text-gray-700 dark:text-gray-300"
              @click="showDocuments = !showDocuments"
            >
              <span class="flex items-center gap-2">
                <FolderOpenIcon class="w-4 h-4" />
                {{ t('management.tabDocuments') }} <span v-if="documents.length" class="text-xs font-normal text-gray-400">({{ documents.length }})</span>
              </span>
              <ChevronUpIcon v-if="showDocuments" class="w-4 h-4 text-gray-400" />
              <ChevronDownIcon v-else class="w-4 h-4 text-gray-400" />
            </button>
            <div v-if="showDocuments" class="px-4 pb-4 space-y-2">
              <div v-if="docsLoading" class="animate-pulse space-y-2">
                <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-lg" />
              </div>
              <div v-else-if="documents.length === 0" class="flex flex-col items-center py-4 gap-2">
                <FolderOpenIcon class="w-8 h-8 text-gray-300 dark:text-gray-600" />
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('management.noDocuments') }}</p>
              </div>
              <div v-else class="divide-y divide-gray-100 dark:divide-gray-700">
                <div v-for="doc in documents" :key="doc.id" class="flex items-center gap-2 py-2 group">
                  <span class="text-sm flex-shrink-0">{{ docFileIcon(doc.content_type) }}</span>
                  <div class="flex-1 min-w-0">
                    <a :href="doc.file_url" target="_blank" rel="noopener noreferrer"
                       class="text-xs font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 truncate block">
                      {{ doc.name }}
                    </a>
                    <p class="text-[10px] text-gray-400">{{ fmtDocBytes(doc.size_bytes) }}</p>
                  </div>
                  <button
                    @click="deleteDocId = doc.id"
                    class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 transition-opacity flex-shrink-0"
                    :aria-label="t('management.deleteBtn')"
                  >
                    <TrashIcon class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <button
                @click="docFileInputRef?.click()"
                :disabled="docsUploading"
                class="w-full text-xs px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
              >
                {{ docsUploading ? t('management.uploading') : t('management.uploadBtn') }}
              </button>
              <input ref="docFileInputRef" type="file" multiple class="hidden" @change="onDocFileSelected" />
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <ConfirmDeleteModal
    :open="!!deleteDocId"
    :message="t('management.confirmDocDelete')"
    @confirm="deleteDocument"
    @cancel="deleteDocId = null"
  />
</template>

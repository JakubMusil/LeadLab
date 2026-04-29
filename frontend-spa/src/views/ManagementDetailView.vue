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

const route = useRoute()
const router = useRouter()
const store = useManagementStore()
const toast = useToast()
const { t } = useI18n()

const recordId = computed(() => route.params.id as string)

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
  await store.fetchRecord(recordId.value)
  await loadLinkedProposals()
})

const record = computed(() => store.currentRecord)

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
    <button
      @click="router.push('/app/management')"
      class="mb-4 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 flex items-center gap-1"
    >
      ← {{ t('management.backToManagement') }}
    </button>

    <!-- Loading -->
    <div v-if="store.loadingDetail" class="text-center py-16 text-gray-500 dark:text-gray-400">
      {{ t('management.loading') }}
    </div>

    <div v-else-if="!record" class="text-center py-16 text-gray-500 dark:text-gray-400">
      {{ t('management.recordNotFound') }}
    </div>

    <template v-else>
      <!-- Header -->
      <div class="flex items-start justify-between gap-4 mb-6">
        <div class="flex-1 min-w-0">
          <!-- Editable title -->
          <div v-if="editingTitle" class="flex items-center gap-2">
            <input
              v-model="titleDraft"
              @keyup.enter="saveTitle"
              @keyup.escape="editingTitle = false"
              class="text-2xl font-bold bg-transparent border-b-2 border-red-500 outline-none text-gray-900 dark:text-white w-full"
              autofocus
            />
            <button @click="saveTitle" :disabled="savingTitle" class="text-sm text-red-600 hover:text-red-700 font-medium">
              {{ savingTitle ? '…' : t('management.save') }}
            </button>
          </div>
          <h1
            v-else
            @click="startEditTitle"
            class="text-2xl font-bold text-gray-900 dark:text-white cursor-pointer hover:opacity-80 transition-opacity"
            :title="t('management.clickToEdit')"
          >
            {{ record.title }}
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
              {{ MANAGEMENT_TYPES.find(t => t.value === record.type)?.label ?? record.type }}
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

        <!-- Status change dropdown -->
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

      <!-- Tab bar -->
      <div class="flex gap-1 border-b border-gray-200 dark:border-gray-700 mb-4">
        <button
          v-for="tab in (['overview', 'tasks', 'proposals', 'documents'] as Tab[])"
          :key="tab"
          @click="activeTab = tab; if (tab === 'documents' && documents.length === 0) loadDocuments()"
          :class="activeTab === tab
            ? 'border-b-2 border-red-600 text-red-600 dark:text-red-400'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
          class="px-4 py-2 text-sm font-medium capitalize transition-colors"
        >
          {{ tab === 'overview' ? t('management.tabOverview') : tab === 'tasks' ? t('management.tabTasks') : tab === 'proposals' ? t('management.tabProposals') : `${t('management.tabDocuments')} (${documents.length})` }}
        </button>
      </div>

      <!-- Overview tab: streamline left + toolbox right -->
      <div v-if="activeTab === 'overview'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Left: ActivityTimeline (streamline) -->
        <div class="lg:col-span-2">
          <ActivityTimeline ref="activityTimelineRef" entity-type="management" :entity-id="recordId" />
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

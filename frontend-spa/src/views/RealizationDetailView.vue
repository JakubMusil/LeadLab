<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRealizationsStore, REALIZATION_STATUSES, getRealizationStatusMeta, type MilestoneOut } from '@/stores/realizations'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const store = useRealizationsStore()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const toast = useToast()

const realizationId = computed(() => route.params.id as string)

type Tab = 'overview' | 'tasks' | 'milestones' | 'proposals' | 'documents'
const activeTab = ref<Tab>('overview')

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

function firmHeader() {
  return firmStore.activeFirm ? { 'X-Firm-ID': String(firmStore.activeFirm.id) } : {}
}

const realization = computed(() => store.currentRealization)

async function saveTitle() {
  if (!realization.value) return
  if (!titleDraft.value.trim()) { editingTitle.value = false; return }
  savingTitle.value = true
  try {
    await store.updateRealization(realization.value.id, { title: titleDraft.value.trim() })
    toast.success('Název uložen')
  } finally {
    savingTitle.value = false
    editingTitle.value = false
  }
}

function startEditTitle() {
  titleDraft.value = realization.value?.title ?? ''
  editingTitle.value = true
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
      { headers: firmHeader() }
    )
    await store.fetchRealization(realization.value.id)
    toast.success('Milník přidán')
    milestoneFormName.value = ''
    milestoneFormDate.value = ''
    milestoneFormDesc.value = ''
    showMilestoneForm.value = false
  } catch {
    toast.error('Nepodařilo se přidat milník')
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
      { headers: firmHeader() }
    )
    await store.fetchRealization(realization.value.id)
  } catch {
    toast.error('Chyba')
  }
}

async function deleteMilestone(m: MilestoneOut) {
  if (!realization.value) return
  try {
    await api.delete(
      `/api/v1/crm/realizations/${realization.value.id}/milestones/${m.id}`,
      { headers: firmHeader() }
    )
    await store.fetchRealization(realization.value.id)
    toast.success('Milník smazán')
  } catch {
    toast.error('Chyba')
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
interface DocumentOut {
  id: string; name: string; content_type: string; size_bytes: number
  uploaded_by_name: string | null; file_url: string; created_at: string
}
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

function docFileIcon(ct: string): string {
  if (ct.startsWith('image/')) return '🖼️'
  if (ct === 'application/pdf') return '📄'
  if (ct.includes('word') || ct.includes('document')) return '📝'
  if (ct.includes('excel') || ct.includes('spreadsheet')) return '📊'
  return '📎'
}

function fmtDocBytes(b: number): string {
  if (b === 0) return '0 B'
  const k = 1024; const sz = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(b) / Math.log(k))
  return `${parseFloat((b / Math.pow(k, i)).toFixed(1))} ${sz[i]}`
}

onMounted(async () => {
  await store.fetchRealization(realizationId.value)
  await loadLinkedProposals()
})</script>

<template>
  <div v-if="store.loadingDetail" class="p-6 text-center text-gray-500">Načítání…</div>

  <div v-else-if="!realization" class="p-6">
    <p class="text-gray-500">Realizace nenalezena.</p>
    <button @click="router.push('/app/realizations')" class="mt-4 text-sm text-red-600 hover:underline">← Zpět</button>
  </div>

  <div v-else class="p-6 max-w-5xl mx-auto space-y-6">
    <!-- Breadcrumb -->
    <nav class="flex items-center gap-1 text-sm text-gray-500">
      <button @click="router.push('/app/realizations')" class="hover:text-gray-700 dark:hover:text-gray-300">Realizace</button>
      <span class="mx-1">›</span>
      <span class="text-gray-700 dark:text-gray-300 truncate max-w-xs">{{ realization.title }}</span>
    </nav>

    <!-- Title + status header -->
    <div class="flex items-start gap-4">
      <div class="flex-1 min-w-0">
        <div v-if="editingTitle" class="flex items-center gap-2">
          <input
            v-model="titleDraft"
            @keyup.enter="saveTitle"
            @keyup.escape="editingTitle = false"
            class="text-2xl font-bold border-b-2 border-red-500 bg-transparent outline-none text-gray-900 dark:text-white w-full"
            autofocus
          />
          <button @click="saveTitle" :disabled="savingTitle" class="text-sm text-red-600 hover:underline">Uložit</button>
          <button @click="editingTitle = false" class="text-sm text-gray-500 hover:underline">Zrušit</button>
        </div>
        <h1
          v-else
          class="text-2xl font-bold text-gray-900 dark:text-white cursor-pointer hover:underline decoration-dotted"
          @click="startEditTitle"
        >
          {{ realization.title }}
        </h1>

        <!-- Meta line -->
        <div class="flex flex-wrap items-center gap-4 mt-2 text-sm text-gray-500">
          <span v-if="realization.customer_name">
            <span class="text-gray-400">Zákazník:</span> {{ realization.customer_name }}
          </span>
          <span v-if="realization.lead_title">
            <span class="text-gray-400">Příležitost:</span> {{ realization.lead_title }}
          </span>
          <span v-if="realization.assigned_to_name">
            <span class="text-gray-400">Odpovědná osoba:</span> {{ realization.assigned_to_name }}
          </span>
          <span v-if="realization.start_date">
            <span class="text-gray-400">Zahájení:</span> {{ realization.start_date }}
          </span>
          <span v-if="realization.end_date">
            <span class="text-gray-400">Termín:</span> {{ realization.end_date }}
          </span>
        </div>
      </div>

      <!-- Status selector -->
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

    <!-- Tabs -->
    <div class="flex border-b border-gray-200 dark:border-gray-700">
      <button
        v-for="tab in [
          { id: 'overview', label: 'Přehled' },
          { id: 'milestones', label: `Milníky (${totalMilestones})` },
          { id: 'tasks', label: 'Úkoly' },
          { id: 'proposals', label: 'Nabídky' },
          { id: 'documents', label: `Dokumenty (${documents.length})` },
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

    <!-- Overview tab -->
    <div v-if="activeTab === 'overview'" class="space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Popis</h3>
          <p class="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap">{{ realization.description || '—' }}</p>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Milníky</h3>
          <div v-if="totalMilestones > 0">
            <div class="flex items-center justify-between text-xs text-gray-500 mb-1">
              <span>{{ completedMilestones }} / {{ totalMilestones }} splněno</span>
              <span>{{ Math.round((completedMilestones / totalMilestones) * 100) }}%</span>
            </div>
            <div class="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                class="h-full bg-green-500 rounded-full transition-all"
                :style="{ width: `${Math.round((completedMilestones / totalMilestones) * 100)}%` }"
              />
            </div>
          </div>
          <p v-else class="text-sm text-gray-400">Žádné milníky</p>
        </div>
      </div>
    </div>

    <!-- Milestones tab -->
    <div v-if="activeTab === 'milestones'" class="space-y-4">
      <div class="flex justify-between items-center">
        <h2 class="text-base font-semibold text-gray-900 dark:text-white">Milníky</h2>
        <button
          @click="showMilestoneForm = !showMilestoneForm"
          class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg"
        >
          + Přidat milník
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
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Datum *</label>
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
          placeholder="Popis (volitelné)"
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
      <div v-else-if="linkedProposals.length === 0" class="text-sm text-gray-400 text-center py-8">
        Žádné nabídky pro tuto realizaci.
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
    <div v-if="activeTab === 'documents'" class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-base font-semibold text-gray-900 dark:text-white">Dokumenty</h2>
        <button
          @click="docFileInputRef?.click()"
          :disabled="docsUploading"
          class="px-3 py-1.5 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg disabled:opacity-50"
        >
          {{ docsUploading ? 'Nahrávám…' : '⬆ Nahrát' }}
        </button>
        <input ref="docFileInputRef" type="file" multiple class="hidden" @change="onDocFileSelected" />
      </div>

      <div v-if="docsLoading" class="animate-pulse space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>

      <div v-else-if="documents.length === 0" class="text-center py-12">
        <div class="text-4xl mb-3">📁</div>
        <p class="text-sm text-gray-500 dark:text-gray-400">Žádné dokumenty</p>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Nahrajte soubory kliknutím na Nahrát výše.</p>
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
          <p class="text-gray-800 dark:text-white font-medium mb-4">Opravdu chcete smazat tento dokument?</p>
          <div class="flex gap-3 justify-end">
            <button @click="deleteDocId = null" class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">Zrušit</button>
            <button @click="deleteDocument" class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg">Smazat</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

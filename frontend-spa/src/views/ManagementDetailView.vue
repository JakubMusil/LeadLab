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

const route = useRoute()
const router = useRouter()
const store = useManagementStore()
const toast = useToast()

const recordId = computed(() => route.params.id as string)

type Tab = 'overview' | 'tasks' | 'activities'
const activeTab = ref<Tab>('overview')

const editingTitle = ref(false)
const titleDraft = ref('')
const savingTitle = ref(false)

onMounted(async () => {
  await store.fetchRecord(recordId.value)
})

const record = computed(() => store.currentRecord)

async function saveTitle() {
  if (!record.value) return
  if (!titleDraft.value.trim()) { editingTitle.value = false; return }
  savingTitle.value = true
  try {
    await store.updateRecord(record.value.id, { title: titleDraft.value.trim() })
    toast.success('Název uložen')
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
  toast.success('Stav aktualizován')
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
  if (days < 0) return `Expirováno před ${Math.abs(days)} dny`
  if (days === 0) return 'Expiruje dnes'
  return `Vyprší za ${days} dní`
}

function formatDateTime(dt: string | null) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('cs-CZ', { dateStyle: 'medium', timeStyle: 'short' })
}
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Back -->
    <button
      @click="router.push('/app/management')"
      class="mb-4 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 flex items-center gap-1"
    >
      ← Zpět na Správu
    </button>

    <!-- Loading -->
    <div v-if="store.loadingDetail" class="text-center py-16 text-gray-500 dark:text-gray-400">
      Načítání…
    </div>

    <div v-else-if="!record" class="text-center py-16 text-gray-500 dark:text-gray-400">
      Záznam nenalezen.
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
              {{ savingTitle ? '…' : 'Uložit' }}
            </button>
          </div>
          <h1
            v-else
            @click="startEditTitle"
            class="text-2xl font-bold text-gray-900 dark:text-white cursor-pointer hover:opacity-80 transition-opacity"
            title="Klikněte pro editaci"
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

      <!-- Sidebar + main content layout -->
      <div class="flex gap-6">
        <!-- Main tabs -->
        <div class="flex-1 min-w-0">
          <!-- Tab bar -->
          <div class="flex gap-1 border-b border-gray-200 dark:border-gray-700 mb-4">
            <button
              v-for="tab in (['overview', 'tasks', 'activities'] as Tab[])"
              :key="tab"
              @click="activeTab = tab"
              :class="activeTab === tab
                ? 'border-b-2 border-red-600 text-red-600 dark:text-red-400'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
              class="px-4 py-2 text-sm font-medium capitalize transition-colors"
            >
              {{ tab === 'overview' ? 'Přehled' : tab === 'tasks' ? 'Úkoly' : 'Aktivity' }}
            </button>
          </div>

          <!-- Overview tab -->
          <div v-if="activeTab === 'overview'" class="space-y-4">
            <!-- Notes -->
            <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
              <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Poznámky</h3>
              <p v-if="record.notes" class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{{ record.notes }}</p>
              <p v-else class="text-sm text-gray-400 italic">Žádné poznámky</p>
            </div>

            <!-- Created / Updated -->
            <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 text-xs text-gray-500 dark:text-gray-400 space-y-1">
              <div>Vytvořeno: {{ formatDateTime(record.created_at) }}</div>
              <div>Aktualizováno: {{ formatDateTime(record.updated_at) }}</div>
            </div>
          </div>

          <!-- Tasks tab placeholder -->
          <div v-else-if="activeTab === 'tasks'" class="text-center py-12 text-gray-400 dark:text-gray-500">
            <p class="text-sm">Úkoly propojené s tímto záznamem budou zobrazeny zde.</p>
          </div>

          <!-- Activities tab placeholder -->
          <div v-else-if="activeTab === 'activities'" class="text-center py-12 text-gray-400 dark:text-gray-500">
            <p class="text-sm">Aktivity propojené s tímto záznamem budou zobrazeny zde.</p>
          </div>
        </div>

        <!-- Sidebar -->
        <div class="w-64 flex-shrink-0 space-y-4">
          <!-- Customer -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Zákazník</div>
            <div v-if="record.customer_name" class="text-sm text-gray-900 dark:text-white">{{ record.customer_name }}</div>
            <div v-else class="text-sm text-gray-400 italic">Nepřiřazen</div>
          </div>

          <!-- Realization -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Realizace</div>
            <div v-if="record.realization_title">
              <button
                @click="router.push(`/app/realizations/${record.realization_id}`)"
                class="text-sm text-red-600 dark:text-red-400 hover:underline text-left"
              >
                {{ record.realization_title }}
              </button>
            </div>
            <div v-else class="text-sm text-gray-400 italic">Nepřiřazena</div>
          </div>

          <!-- Assigned to -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Přiřazeno</div>
            <div v-if="record.assigned_to_name" class="text-sm text-gray-900 dark:text-white">{{ record.assigned_to_name }}</div>
            <div v-else class="text-sm text-gray-400 italic">Nepřiřazeno</div>
          </div>

          <!-- SLA / Expiry -->
          <div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">SLA / Expiry</div>
            <div v-if="record.expires_at">
              <div class="text-sm text-gray-900 dark:text-white mb-1">{{ formatDateTime(record.expires_at) }}</div>
              <span :class="slaBadgeClass(record.sla_color)" class="text-xs px-2 py-0.5 rounded font-medium">
                {{ slaLabel(record.expires_at, record.sla_color) }}
              </span>
            </div>
            <div v-else class="text-sm text-gray-400 italic">Nenastaveno</div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

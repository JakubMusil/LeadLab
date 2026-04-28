<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  useManagementStore,
  MANAGEMENT_STATUSES,
  MANAGEMENT_TYPES,
  getManagementStatusMeta,
  type ManagementOut,
  type ManagementIn,
} from '@/stores/management'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const store = useManagementStore()
const customersStore = useCustomersStore()
const toast = useToast()

type ViewMode = 'kanban' | 'table'
const viewMode = ref<ViewMode>('kanban')

const showModal = ref(false)
const editingRecord = ref<ManagementOut | null>(null)
const confirmDeleteId = ref<string | null>(null)

// Form fields
const formTitle = ref('')
const formNotes = ref('')
const formStatus = ref('open')
const formType = ref('care')
const formCustomerId = ref<string | null>(null)
const formCustomerQuery = ref('')
const formExpiresAt = ref('')
const customerSuggestions = ref<CustomerOut[]>([])
const showCustomerDropdown = ref(false)
const formLoading = ref(false)
const formError = ref('')

onMounted(async () => {
  await store.fetchRecords()
  await customersStore.fetchCustomers()
})

const byStatus = computed(() => {
  const map: Record<string, ManagementOut[]> = {}
  for (const s of MANAGEMENT_STATUSES) map[s.value] = []
  for (const r of store.records) {
    if (map[r.status]) map[r.status].push(r)
    else map['open'].push(r)
  }
  return map
})

function slaIndicatorClass(record: ManagementOut) {
  if (!record.sla_color) return ''
  if (record.sla_color === 'red') return 'border-l-4 border-red-500'
  if (record.sla_color === 'yellow') return 'border-l-4 border-yellow-400'
  return 'border-l-4 border-green-500'
}

function slaBadgeClass(color: string | null) {
  if (color === 'red') return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
  if (color === 'yellow') return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
  if (color === 'green') return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
  return ''
}

function slaLabel(record: ManagementOut) {
  if (!record.expires_at) return null
  const diff = new Date(record.expires_at).getTime() - Date.now()
  const days = Math.ceil(diff / 86400000)
  if (days < 0) return `Expirováno před ${Math.abs(days)} d`
  if (days === 0) return 'Expiruje dnes'
  return `Vyprší za ${days} d`
}

function openCreate() {
  editingRecord.value = null
  formTitle.value = ''
  formNotes.value = ''
  formStatus.value = 'open'
  formType.value = 'care'
  formCustomerId.value = null
  formCustomerQuery.value = ''
  formExpiresAt.value = ''
  formError.value = ''
  showModal.value = true
}

function openEdit(r: ManagementOut) {
  editingRecord.value = r
  formTitle.value = r.title
  formNotes.value = r.notes
  formStatus.value = r.status
  formType.value = r.type
  formCustomerId.value = r.customer_id
  formCustomerQuery.value = r.customer_name ?? ''
  formExpiresAt.value = r.expires_at ? r.expires_at.slice(0, 16) : ''
  formError.value = ''
  showModal.value = true
}

async function submitForm() {
  if (!formTitle.value.trim()) {
    formError.value = 'Název je povinný'
    return
  }
  formLoading.value = true
  formError.value = ''
  try {
    const payload: ManagementIn = {
      title: formTitle.value.trim(),
      notes: formNotes.value,
      status: formStatus.value,
      type: formType.value,
      customer_id: formCustomerId.value || null,
      expires_at: formExpiresAt.value ? new Date(formExpiresAt.value).toISOString() : null,
    }
    if (editingRecord.value) {
      const updated = await store.updateRecord(editingRecord.value.id, payload)
      if (updated) {
        toast.success('Záznam aktualizován')
        showModal.value = false
      }
    } else {
      const created = await store.createRecord(payload)
      if (created) {
        toast.success('Záznam vytvořen')
        showModal.value = false
      }
    }
  } finally {
    formLoading.value = false
  }
}

async function handleDelete(id: string) {
  const ok = await store.deleteRecord(id)
  if (ok) {
    toast.success('Záznam smazán')
    confirmDeleteId.value = null
  }
}

async function updateStatus(r: ManagementOut, status: string) {
  await store.updateRecord(r.id, { status })
}

// Customer typeahead
function onCustomerInput() {
  const q = formCustomerQuery.value.trim().toLowerCase()
  if (!q) {
    customerSuggestions.value = []
    showCustomerDropdown.value = false
    return
  }
  customerSuggestions.value = customersStore.customers.filter((c) => {
    const name = `${c.first_name} ${c.last_name} ${c.company_name}`.toLowerCase()
    return name.includes(q)
  }).slice(0, 8)
  showCustomerDropdown.value = customerSuggestions.value.length > 0
}

function selectCustomer(c: CustomerOut) {
  formCustomerId.value = c.id
  formCustomerQuery.value = `${c.first_name} ${c.last_name}`.trim() || c.company_name
  showCustomerDropdown.value = false
}
</script>

<template>
  <div class="p-6 space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Správa</h1>
      <div class="flex items-center gap-2">
        <!-- View toggle -->
        <div class="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
          <button
            @click="viewMode = 'kanban'"
            :class="viewMode === 'kanban' ? 'bg-red-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300'"
            class="px-3 py-1.5 text-sm font-medium"
          >
            Kanban
          </button>
          <button
            @click="viewMode = 'table'"
            :class="viewMode === 'table' ? 'bg-red-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300'"
            class="px-3 py-1.5 text-sm font-medium"
          >
            Tabulka
          </button>
        </div>
        <button
          @click="openCreate"
          class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium"
        >
          + Nový záznam
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="text-center py-12 text-gray-500 dark:text-gray-400">
      Načítání…
    </div>

    <!-- Kanban board -->
    <div v-else-if="viewMode === 'kanban'" class="flex gap-4 overflow-x-auto pb-4">
      <div
        v-for="col in MANAGEMENT_STATUSES"
        :key="col.value"
        class="flex-shrink-0 w-72 bg-gray-50 dark:bg-gray-800 rounded-xl p-3"
      >
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-300">{{ col.label }}</span>
          <span class="text-xs text-gray-500 bg-gray-200 dark:bg-gray-700 rounded-full px-2 py-0.5">
            {{ byStatus[col.value]?.length ?? 0 }}
          </span>
        </div>

        <div class="space-y-2 min-h-[4rem]">
          <div
            v-for="r in byStatus[col.value]"
            :key="r.id"
            :class="slaIndicatorClass(r)"
            class="bg-white dark:bg-gray-700 rounded-lg p-3 shadow-sm border border-gray-100 dark:border-gray-600 cursor-pointer hover:shadow-md transition-shadow"
            @click="router.push(`/app/management/${r.id}`)"
          >
            <p class="text-sm font-medium text-gray-900 dark:text-white leading-snug mb-1">{{ r.title }}</p>
            <div class="flex items-center gap-1 mb-2">
              <span class="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-300">
                {{ MANAGEMENT_TYPES.find(t => t.value === r.type)?.label ?? r.type }}
              </span>
            </div>
            <div v-if="r.customer_name" class="text-xs text-gray-500 dark:text-gray-400">{{ r.customer_name }}</div>
            <div v-if="r.expires_at" class="mt-1.5">
              <span :class="slaBadgeClass(r.sla_color)" class="text-xs px-1.5 py-0.5 rounded font-medium">
                {{ slaLabel(r) }}
              </span>
            </div>
            <div class="flex justify-end gap-1 mt-2">
              <button
                @click.stop="openEdit(r)"
                class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xs"
              >✎</button>
              <button
                @click.stop="confirmDeleteId = r.id"
                class="text-gray-400 hover:text-red-600 text-xs"
              >✕</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Table view -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table class="min-w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200 dark:border-gray-700">
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Název</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Typ</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Stav</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Zákazník</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">Expiry / SLA</th>
            <th class="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in store.records"
            :key="r.id"
            class="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
            @click="router.push(`/app/management/${r.id}`)"
          >
            <td class="px-4 py-3 text-gray-900 dark:text-white font-medium">{{ r.title }}</td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-300 capitalize">
              {{ MANAGEMENT_TYPES.find(t => t.value === r.type)?.label ?? r.type }}
            </td>
            <td class="px-4 py-3">
              <span :class="getManagementStatusMeta(r.status).color" class="px-2 py-0.5 rounded-full text-xs font-medium">
                {{ getManagementStatusMeta(r.status).label }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-300">{{ r.customer_name ?? '—' }}</td>
            <td class="px-4 py-3">
              <span v-if="r.expires_at" :class="slaBadgeClass(r.sla_color)" class="text-xs px-1.5 py-0.5 rounded font-medium">
                {{ slaLabel(r) }}
              </span>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="px-4 py-3 text-right">
              <button @click.stop="openEdit(r)" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 mr-2">✎</button>
              <button @click.stop="confirmDeleteId = r.id" class="text-gray-400 hover:text-red-600">✕</button>
            </td>
          </tr>
          <tr v-if="store.records.length === 0">
            <td colspan="6" class="px-4 py-12 text-center text-gray-400">Žádné záznamy správy</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {{ editingRecord ? 'Upravit záznam' : 'Nový záznam správy' }}
        </h2>

        <div v-if="formError" class="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-sm">{{ formError }}</div>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Název *</label>
            <input
              v-model="formTitle"
              type="text"
              placeholder="Název záznamu"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Typ</label>
              <select
                v-model="formType"
                class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
              >
                <option v-for="t in MANAGEMENT_TYPES" :key="t.value" :value="t.value">{{ t.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Stav</label>
              <select
                v-model="formStatus"
                class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
              >
                <option v-for="s in MANAGEMENT_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Expiry / SLA termín</label>
            <input
              v-model="formExpiresAt"
              type="datetime-local"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>

          <!-- Customer typeahead -->
          <div class="relative">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Zákazník</label>
            <input
              v-model="formCustomerQuery"
              @input="onCustomerInput"
              type="text"
              placeholder="Hledat zákazníka…"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            />
            <div v-if="showCustomerDropdown" class="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-700 rounded-lg border border-gray-200 dark:border-gray-600 shadow-lg z-10 max-h-48 overflow-y-auto">
              <button
                v-for="c in customerSuggestions"
                :key="c.id"
                @mousedown.prevent="selectCustomer(c)"
                class="w-full text-left px-3 py-2 text-sm text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                {{ c.first_name }} {{ c.last_name }} {{ c.company_name ? `(${c.company_name})` : '' }}
              </button>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Poznámky</label>
            <textarea
              v-model="formNotes"
              rows="3"
              placeholder="Poznámky…"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none resize-none"
            />
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button
            @click="showModal = false"
            class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
          >
            Zrušit
          </button>
          <button
            @click="submitForm"
            :disabled="formLoading"
            class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {{ formLoading ? 'Ukládám…' : (editingRecord ? 'Uložit' : 'Vytvořit') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="confirmDeleteId" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm mx-4 p-6">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">Smazat záznam?</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6">Tato akce je nevratná.</p>
        <div class="flex justify-end gap-2">
          <button
            @click="confirmDeleteId = null"
            class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
          >
            Zrušit
          </button>
          <button
            @click="handleDelete(confirmDeleteId!)"
            class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium"
          >
            Smazat
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  useRealizationsStore,
  REALIZATION_STATUSES,
  getRealizationStatusMeta,
  type RealizationOut,
  type RealizationIn,
} from '@/stores/realizations'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { PencilSquareIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

const router = useRouter()
const store = useRealizationsStore()
const customersStore = useCustomersStore()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const toast = useToast()
const { t } = useI18n()

type ViewMode = 'kanban' | 'table'
const viewMode = ref<ViewMode>('kanban')

const showModal = ref(false)
const editingRealization = ref<RealizationOut | null>(null)
const confirmDeleteId = ref<string | null>(null)

// Form fields
const formTitle = ref('')
const formStatus = ref('planned')
const formCustomerId = ref<string | null>(null)
const formCustomerQuery = ref('')
const customerSuggestions = ref<CustomerOut[]>([])
const showCustomerDropdown = ref(false)
const formLoading = ref(false)
const formError = ref('')

onMounted(async () => {
  await store.fetchRealizations()
  await customersStore.fetchCustomers()
})

const reByStatus = computed(() => {
  const map: Record<string, RealizationOut[]> = {}
  for (const s of REALIZATION_STATUSES) map[s.value] = []
  for (const r of store.realizations) {
    const bucket = map[r.status] ?? map['planned']
    bucket?.push(r)
  }
  return map
})

function openCreate() {
  editingRealization.value = null
  formTitle.value = ''
  formStatus.value = 'planned'
  formCustomerId.value = null
  formCustomerQuery.value = ''
  formError.value = ''
  showModal.value = true
}

function openEdit(r: RealizationOut) {
  editingRealization.value = r
  formTitle.value = r.title
  formStatus.value = r.status
  formCustomerId.value = r.customer_id
  formCustomerQuery.value = r.customer_name ?? ''
  formError.value = ''
  showModal.value = true
}

async function submitForm() {
  if (!formTitle.value.trim()) {
    formError.value = t('realizations.titleRequired')
    return
  }
  formLoading.value = true
  formError.value = ''
  try {
    const payload: RealizationIn = {
      title: formTitle.value.trim(),
      status: formStatus.value,
      customer_id: formCustomerId.value || null,
    }
    if (editingRealization.value) {
      const updated = await store.updateRealization(editingRealization.value.id, payload)
      if (updated) {
        toast.success(t('realizations.updated'))
        showModal.value = false
      }
    } else {
      const created = await store.createRealization(payload)
      if (created) {
        toast.success(t('realizations.created'))
        showModal.value = false
      }
    }
  } finally {
    formLoading.value = false
  }
}

async function handleDelete(id: string) {
  const ok = await store.deleteRealization(id)
  if (ok) {
    toast.success(t('realizations.deleted'))
    confirmDeleteId.value = null
  }
}

async function updateStatus(r: RealizationOut, status: string) {
  await store.updateRealization(r.id, { status })
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
      <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ t('realizations.title') }}</h1>
      <div class="flex items-center gap-2">
        <!-- View toggle -->
        <div class="flex rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
          <button
            @click="viewMode = 'kanban'"
            :class="viewMode === 'kanban' ? 'bg-red-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300'"
            class="px-3 py-1.5 text-sm font-medium"
          >
            {{ t('realizations.kanban') }}
          </button>
          <button
            @click="viewMode = 'table'"
            :class="viewMode === 'table' ? 'bg-red-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300'"
            class="px-3 py-1.5 text-sm font-medium"
          >
            {{ t('realizations.tableView') }}
          </button>
        </div>
        <button
          @click="openCreate"
          class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium"
        >
          + {{ t('realizations.new') }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading" class="text-center py-12 text-gray-500">
      {{ t('common.loading') }}
    </div>

    <!-- Kanban board -->
    <div v-else-if="viewMode === 'kanban'" class="flex gap-4 overflow-x-auto pb-4">
      <div
        v-for="col in REALIZATION_STATUSES"
        :key="col.value"
        class="flex-shrink-0 w-72 bg-gray-50 dark:bg-gray-800 rounded-xl p-3"
      >
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-300">{{ col.label }}</span>
          <span class="text-xs text-gray-500 bg-gray-200 dark:bg-gray-700 rounded-full px-2 py-0.5">
            {{ reByStatus[col.value]?.length ?? 0 }}
          </span>
        </div>

        <div class="space-y-2 min-h-[4rem]">
          <div
            v-for="r in reByStatus[col.value]"
            :key="r.id"
            class="bg-white dark:bg-gray-700 rounded-lg p-3 shadow-sm border border-gray-100 dark:border-gray-600 cursor-pointer hover:shadow-md transition-shadow"
            @click="router.push(`/app/realizations/${r.id}`)"
          >
            <p class="text-sm font-medium text-gray-900 dark:text-white leading-snug mb-2">{{ r.title }}</p>
            <div v-if="r.customer_name" class="text-xs text-gray-500 dark:text-gray-400">{{ r.customer_name }}</div>
            <div class="flex items-center justify-between mt-2">
              <span v-if="r.end_date" class="text-xs text-gray-400">{{ r.end_date }}</span>
              <div class="flex gap-1 ml-auto">
                <button
                  @click.stop="openEdit(r)"
                  class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xs"><PencilSquareIcon class="w-4 h-4" /></button>
                <button
                  @click.stop="confirmDeleteId = r.id"
                  class="text-gray-400 hover:text-red-600 text-xs"><XMarkIcon class="w-4 h-4" /></button>
              </div>
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
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">{{ t('realizations.colName') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">{{ t('realizations.colStatus') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">{{ t('realizations.colCustomer') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-700 dark:text-gray-300">{{ t('realizations.colDeadline') }}</th>
            <th class="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in store.realizations"
            :key="r.id"
            class="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
            @click="router.push(`/app/realizations/${r.id}`)"
          >
            <td class="px-4 py-3 text-gray-900 dark:text-white font-medium">{{ r.title }}</td>
            <td class="px-4 py-3">
              <span :class="getRealizationStatusMeta(r.status).color" class="px-2 py-0.5 rounded-full text-xs font-medium">
                {{ getRealizationStatusMeta(r.status).label }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-300">{{ r.customer_name ?? '—' }}</td>
            <td class="px-4 py-3 text-gray-500">{{ r.end_date ?? '—' }}</td>
            <td class="px-4 py-3 text-right">
              <button @click.stop="openEdit(r)" class="text-gray-400 hover:text-gray-600 mr-2"><PencilSquareIcon class="w-4 h-4" /></button>
              <button @click.stop="confirmDeleteId = r.id" class="text-gray-400 hover:text-red-600"><XMarkIcon class="w-4 h-4" /></button>
            </td>
          </tr>
          <tr v-if="store.realizations.length === 0">
            <td colspan="5" class="px-4 py-12 text-center text-gray-400">{{ t('realizations.none') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md mx-4 p-6">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {{ editingRealization ? t('realizations.editTitle') : t('realizations.newTitle') }}
        </h2>

        <div v-if="formError" class="mb-4 p-3 rounded-lg bg-red-50 text-red-700 text-sm">{{ formError }}</div>

        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.nameLabel') }}</label>
            <input
              v-model="formTitle"
              type="text"
              :placeholder="t('realizations.namePlaceholder')"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.statusLabel') }}</label>
            <select
              v-model="formStatus"
              class="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-red-500 outline-none"
            >
              <option v-for="s in REALIZATION_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>

          <!-- Customer typeahead -->
          <div class="relative">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.customerLabel') }}</label>
            <input
              v-model="formCustomerQuery"
              @input="onCustomerInput"
              type="text"
              :placeholder="t('realizations.customerSearch')"
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
        </div>

        <div class="flex justify-end gap-2 mt-6">
          <button
            @click="showModal = false"
            class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="submitForm"
            :disabled="formLoading"
            class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {{ formLoading ? t('common.saving') : (editingRealization ? t('common.save') : t('common.create')) }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <ConfirmDeleteModal
      :open="!!confirmDeleteId"
      :title="t('realizations.confirmDeleteTitle')"
      :message="t('common.irreversible')"
      @confirm="handleDelete(confirmDeleteId!)"
      @cancel="confirmDeleteId = null"
    />
  </div>
</template>

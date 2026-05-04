<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import { useMoney } from '@/composables/useMoney'
import CurrencySelect from '@/components/CurrencySelect.vue'

const router = useRouter()
const { t } = useI18n()
const toast = useToast()
const { firmCurrency, formatAmount } = useMoney()

interface Proposal {
  id: string
  record_id: string | null
  customer_id: string | null
  realization_id: string | null
  management_id: string | null
  firm_id: string
  title: string
  status: string
  currency: string
  total_value: string
  expiry_date: string | null
  created_at: string
}

const proposals = ref<Proposal[]>([])
const loading = ref(false)

// Filters
const filterStatus = ref('')
const filterContext = ref('')

// Create modal
const showCreateModal = ref(false)
const createTitle = ref('')
const createCurrency = ref(firmCurrency.value)
const createContext = ref<'record' | 'customer' | 'realization' | 'management' | 'none'>('none')
const createRecordId = ref('')
const createCustomerId = ref('')
const createRealizationId = ref('')
const createManagementId = ref('')
const creating = ref(false)

const STATUSES = computed(() => [
  { value: '', label: t('proposals.statusAll') },
  { value: 'draft', label: t('proposals.statusDraft'), color: 'bg-gray-100 text-gray-700' },
  { value: 'sent', label: t('proposals.statusSent'), color: 'bg-blue-100 text-blue-700' },
  { value: 'viewed', label: t('proposals.statusViewed'), color: 'bg-yellow-100 text-yellow-700' },
  { value: 'accepted', label: t('proposals.statusAccepted'), color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: t('proposals.statusRejected'), color: 'bg-red-100 text-red-700' },
  { value: 'expired', label: t('proposals.statusExpired'), color: 'bg-orange-100 text-orange-700' },
])

function statusMeta(status: string) {
  return STATUSES.value.find(s => s.value === status) ?? { value: status, label: status, color: 'bg-gray-100 text-gray-700' }
}

function contextLabel(p: Proposal): string {
  if (p.record_id) return t('proposals.contextLead')
  if (p.customer_id) return t('proposals.contextCustomer')
  if (p.realization_id) return t('proposals.contextRealization')
  if (p.management_id) return t('proposals.contextManagement')
  return '—'
}

const filteredProposals = computed(() => {
  let result = proposals.value
  if (filterStatus.value) result = result.filter(p => p.status === filterStatus.value)
  if (filterContext.value === 'record') result = result.filter(p => p.record_id)
  if (filterContext.value === 'customer') result = result.filter(p => p.customer_id)
  if (filterContext.value === 'realization') result = result.filter(p => p.realization_id)
  if (filterContext.value === 'management') result = result.filter(p => p.management_id)
  if (filterContext.value === 'none') result = result.filter(p => !p.record_id && !p.customer_id && !p.realization_id && !p.management_id)
  return result
})

async function loadProposals() {
  loading.value = true
  try {
    const res = await api.get<Proposal[]>('/api/v1/crm/proposals')
    if (res.ok) proposals.value = res.data
  } finally {
    loading.value = false
  }
}

function openProposal(p: Proposal) {
  router.push(`/app/proposals/${p.id}`)
}

function openCreateModal() {
  createTitle.value = ''
  createCurrency.value = firmCurrency.value
  createContext.value = 'none'
  createRecordId.value = ''
  createCustomerId.value = ''
  createRealizationId.value = ''
  createManagementId.value = ''
  showCreateModal.value = true
}

async function createProposal() {
  if (!createTitle.value.trim()) return
  creating.value = true
  const payload: Record<string, unknown> = {
    title: createTitle.value.trim(),
    currency: createCurrency.value,
  }
  if (createContext.value === 'record' && createRecordId.value.trim()) {
    payload.record_id = createRecordId.value.trim()
  } else if (createContext.value === 'customer' && createCustomerId.value.trim()) {
    payload.customer_id = createCustomerId.value.trim()
  } else if (createContext.value === 'realization' && createRealizationId.value.trim()) {
    payload.realization_id = createRealizationId.value.trim()
  } else if (createContext.value === 'management' && createManagementId.value.trim()) {
    payload.management_id = createManagementId.value.trim()
  }

  const res = await api.post<Proposal>('/api/v1/crm/proposals', payload)
  creating.value = false
  if (res.ok) {
    showCreateModal.value = false
    router.push(`/app/proposals/${res.data.id}`)
  } else {
    toast.error(t('proposals.errorCreate'))
  }
}

function fmt(n: number | string) {
  return formatAmount(Number(n))
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString()
}

onMounted(loadProposals)
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ t('proposals.title') }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{{ t('proposals.allProposals') }}</p>
      </div>
      <button
        class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreateModal"
      >
        {{ t('proposals.newProposal') }}
      </button>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-5">
      <select
        v-model="filterStatus"
        class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm px-3 py-2 text-gray-700 dark:text-gray-300"
      >
        <option v-for="s in STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
      <select
        v-model="filterContext"
        class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm px-3 py-2 text-gray-700 dark:text-gray-300"
      >
        <option value="">{{ t('proposals.filterAll') }}</option>
        <option value="record">{{ t('proposals.filterLeads') }}</option>
        <option value="customer">{{ t('proposals.filterCustomers') }}</option>
        <option value="realization">{{ t('proposals.filterRealizations') }}</option>
        <option value="management">{{ t('proposals.filterManagement') }}</option>
        <option value="none">{{ t('proposals.filterNone') }}</option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="filteredProposals.length === 0" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-16 text-center">
      <p class="text-gray-400 dark:text-gray-500 text-sm mb-4">{{ t('proposals.noProposals') }}</p>
      <p class="text-gray-400 dark:text-gray-500 text-xs">{{ t('proposals.noProposalsHint') }}</p>
    </div>

    <!-- Table -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            <th class="text-left px-4 py-3">{{ t('proposals.colTitle') }}</th>
            <th class="text-left px-4 py-3">{{ t('proposals.status') }}</th>
            <th class="text-left px-4 py-3">{{ t('proposals.linkedTo') }}</th>
            <th class="text-right px-4 py-3">{{ t('proposals.total') }}</th>
            <th class="text-left px-4 py-3">{{ t('proposals.colCreated') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in filteredProposals"
            :key="p.id"
            class="border-b border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
            @click="openProposal(p)"
          >
            <td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{{ p.title }}</td>
            <td class="px-4 py-3">
              <span class="px-2 py-0.5 rounded text-xs font-medium" :class="statusMeta(p.status).color">
                {{ statusMeta(p.status).label }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs">{{ contextLabel(p) }}</td>
            <td class="px-4 py-3 text-right font-mono text-gray-900 dark:text-gray-100">
              {{ fmt(p.total_value) }} {{ p.currency }}
            </td>
            <td class="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs">{{ formatDate(p.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create modal -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showCreateModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('proposals.createProposal') }}</h2>

          <div class="space-y-4">
            <!-- Title -->
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.nameLabel') }}</label>
              <input
                v-model="createTitle"
                type="text"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100"
                :placeholder="t('proposals.namePlaceholder')"
              />
            </div>

            <!-- Currency -->
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.currency') }}</label>
              <CurrencySelect v-model="createCurrency" />
            </div>

            <!-- Context -->
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.selectContext') }}</label>
              <select
                v-model="createContext"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100"
              >
                <option value="none">{{ t('proposals.contextNone') }}</option>
                <option value="record">{{ t('proposals.contextLead') }}</option>
                <option value="customer">{{ t('proposals.contextCustomer') }}</option>
                <option value="realization">{{ t('proposals.contextRealization') }}</option>
                <option value="management">{{ t('proposals.contextManagement') }}</option>
              </select>
            </div>

            <div v-if="createContext === 'record'">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.contextLead') }} ID</label>
              <input v-model="createRecordId" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100" :placeholder="t('proposals.contextLead') + ' UUID'" />
            </div>
            <div v-else-if="createContext === 'customer'">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.contextCustomer') }} ID</label>
              <input v-model="createCustomerId" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100" :placeholder="t('proposals.contextCustomer') + ' UUID'" />
            </div>
            <div v-else-if="createContext === 'realization'">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.contextRealization') }} ID</label>
              <input v-model="createRealizationId" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100" :placeholder="t('proposals.contextRealization') + ' UUID'" />
            </div>
            <div v-else-if="createContext === 'management'">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('proposals.contextManagement') }} ID</label>
              <input v-model="createManagementId" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100" :placeholder="t('proposals.contextManagement') + ' UUID'" />
            </div>
          </div>

          <div class="flex items-center justify-end gap-3 mt-6">
            <button
              class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="showCreateModal = false"
            >
              {{ t('proposals.cancel') }}
            </button>
            <button
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              :disabled="creating || !createTitle.trim()"
              @click="createProposal"
            >
              {{ creating ? t('proposals.creating') : t('proposals.create') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

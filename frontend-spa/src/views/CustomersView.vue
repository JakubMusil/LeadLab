<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useSavedViewsStore } from '@/stores/savedViews'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import ContextMenu, { type ContextMenuItem } from '@/components/ContextMenu.vue'

const router = useRouter()
const store = useCustomersStore()
const savedViewsStore = useSavedViewsStore()
const toast = useToast()
const { t } = useI18n()

const showModal = ref(false)
const editingCustomer = ref<CustomerOut | null>(null)
const confirmDeleteId = ref<string | null>(null)
const searchInput = ref('')
const activeTab = ref<'all' | 'company' | 'person'>('all')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Form fields
const formType = ref<'person' | 'company'>('person')
const formFirstName = ref('')
const formLastName = ref('')
const formEmail = ref('')
const formPhone = ref('')
const formCompany = ref('')
const formCompanyId = ref<string>('')
const formIco = ref('')
const formDic = ref('')
const formWebsite = ref('')
const formAddressStreet = ref('')
const formAddressCity = ref('')
const formAddressZip = ref('')
const formAddressCountry = ref('')
const formTagsInput = ref('')
const formError = ref('')
const formLoading = ref(false)

// Available companies for person→company link
const availableCompanies = computed(() => store.customers.filter((c) => c.type === 'company'))

onMounted(() => {
  store.fetchCustomers()
  savedViewsStore.fetchViews()
})

watch(searchInput, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    store.search = val
    store.fetchCustomers({ search: val, page: 1, type: activeTab.value === 'all' ? '' : activeTab.value })
  }, 300)
})

watch(activeTab, (val) => {
  store.fetchCustomers({ search: searchInput.value, page: 1, type: val === 'all' ? '' : val })
})

function openCreate() {
  editingCustomer.value = null
  formType.value = 'person'
  formFirstName.value = ''
  formLastName.value = ''
  formEmail.value = ''
  formPhone.value = ''
  formCompany.value = ''
  formCompanyId.value = ''
  formIco.value = ''
  formDic.value = ''
  formWebsite.value = ''
  formAddressStreet.value = ''
  formAddressCity.value = ''
  formAddressZip.value = ''
  formAddressCountry.value = ''
  formTagsInput.value = ''
  formError.value = ''
  showModal.value = true
}

function openEdit(c: CustomerOut) {
  editingCustomer.value = c
  formType.value = c.type
  formFirstName.value = c.first_name
  formLastName.value = c.last_name
  formEmail.value = c.email
  formPhone.value = c.phone
  formCompany.value = c.company_name
  formCompanyId.value = c.company_id ?? ''
  formIco.value = c.ico
  formDic.value = c.dic
  formWebsite.value = c.website
  formAddressStreet.value = c.address_street
  formAddressCity.value = c.address_city
  formAddressZip.value = c.address_zip
  formAddressCountry.value = c.address_country
  formTagsInput.value = c.tags.join(', ')
  formError.value = ''
  showModal.value = true
}

async function submitForm() {
  if (formType.value === 'person' && !formFirstName.value.trim()) {
    formError.value = t('customers.firstNameRequired'); return
  }
  if (formType.value === 'company' && !formFirstName.value.trim()) {
    formError.value = t('customers.companyNameRequired'); return
  }
  formLoading.value = true
  formError.value = ''
  const tags = formTagsInput.value.split(',').map((tag) => tag.trim()).filter(Boolean)
  const payload = {
    type: formType.value,
    first_name: formFirstName.value.trim(),
    last_name: formLastName.value.trim(),
    email: formEmail.value.trim(),
    phone: formPhone.value.trim(),
    company_name: formCompany.value.trim(),
    company_id: formType.value === 'person' && formCompanyId.value ? formCompanyId.value : null,
    ico: formIco.value.trim(),
    dic: formDic.value.trim(),
    website: formWebsite.value.trim(),
    address_street: formAddressStreet.value.trim(),
    address_city: formAddressCity.value.trim(),
    address_zip: formAddressZip.value.trim(),
    address_country: formAddressCountry.value.trim(),
    tags,
    metadata: editingCustomer.value?.metadata ?? {},
  }
  let result
  if (editingCustomer.value) {
    result = await store.updateCustomer(editingCustomer.value.id, payload)
  } else {
    result = await store.createCustomer(payload)
  }
  formLoading.value = false
  if (result.ok) {
    showModal.value = false
    toast.success(editingCustomer.value ? t('customers.updated') : t('customers.created'))
  } else {
    formError.value = result.error ?? t('customers.errorOccurred')
  }
}

async function confirmDelete(id: string) {
  const result = await store.deleteCustomer(id)
  confirmDeleteId.value = null
  if (result.ok) toast.success(t('customers.deleted'))
  else toast.error(result.error ?? t('customers.failedToDelete'))
}

function goToDetail(id: string) {
  router.push(`/app/directory/${id}`)
}

function fullName(c: CustomerOut) {
  return [c.first_name, c.last_name].filter(Boolean).join(' ')
}

function contactTypeClass(type: string) {
  return type === 'company'
    ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
    : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
}

function contactTypeLabel(type: string) {
  return type === 'company' ? t('customers.typeCompany') : t('customers.typePerson')
}

// Context menu
const contextMenuRef = ref<InstanceType<typeof ContextMenu> | null>(null)
const contextCustomer = ref<CustomerOut | null>(null)

const CUSTOMER_CONTEXT_ITEMS = computed<ContextMenuItem[]>(() => [
  { id: 'view', label: t('customers.contextView'), icon: '↗' },
  { id: 'edit', label: t('customers.contextEdit'), icon: '✎' },
  { id: 'divider1', label: '', divider: true },
  { id: 'delete', label: t('customers.contextDelete'), icon: '🗑', danger: true },
])

function onRowContextMenu(e: MouseEvent, customer: CustomerOut) {
  e.preventDefault()
  contextCustomer.value = customer
  contextMenuRef.value?.open(e.clientX, e.clientY)
}

function onContextAction(id: string) {
  const customer = contextCustomer.value
  if (!customer) return
  if (id === 'view') goToDetail(customer.id)
  else if (id === 'edit') openEdit(customer)
  else if (id === 'delete') confirmDeleteId.value = customer.id
}

// CSV Import
const importInput = ref<HTMLInputElement | null>(null)
const importLoading = ref(false)

async function onImportFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  importLoading.value = true
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await api.postForm<{ id: string; status: string }>(
      '/api/v1/integrations/import/customers',
      fd,
    )
    if (res.ok) {
      toast.success(t('customers.importStarted'))
      setTimeout(() => store.fetchCustomers(), 2000)
    } else {
      const msg = ((res.data as unknown) as Record<string, string> | null)?.detail ?? t('customers.importFailed')
      toast.error(msg)
    }
  } finally {
    importLoading.value = false
    if (importInput.value) importInput.value.value = ''
  }
}

function exportCsv() {
  const params = new URLSearchParams()
  if (searchInput.value) params.set('search', searchInput.value)
  window.location.href = `/api/v1/integrations/export/customers.csv?${params.toString()}`
}
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('customers.title') }}</h2>

      <!-- Saved views -->
      <div v-if="savedViewsStore.viewsForEntity('directory').length > 0" class="flex items-center gap-1 flex-wrap">
        <button
          v-for="view in savedViewsStore.viewsForEntity('directory')"
          :key="view.id"
          class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          :title="view.name"
          @click="router.push(`/app/customers?view=${view.id}`)"
        >
          🔖 {{ view.name }}
        </button>
      </div>

      <!-- Search -->
      <div class="flex items-center flex-1 min-w-48 max-w-sm bg-gray-100 dark:bg-gray-700 rounded-xl px-3 py-2 gap-2" role="search">
        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <label for="customer-search" class="sr-only">{{ t('customers.searchPlaceholder') }}</label>
        <input id="customer-search" v-model="searchInput" type="search" :placeholder="t('customers.searchPlaceholder')" class="bg-transparent text-sm text-gray-700 dark:text-gray-300 placeholder-gray-400 dark:placeholder-gray-500 outline-none flex-1" />
      </div>
      <button
        class="bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreate"
      >{{ t('customers.newCustomer') }}</button>

      <!-- Import / Export -->
      <label
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors cursor-pointer"
        :class="importLoading ? 'opacity-60 pointer-events-none' : ''"
        :title="t('customers.importTitle')"
      >
        ⬆ {{ t('customers.importCsv') }}
        <input ref="importInput" type="file" accept=".csv" class="hidden" @change="onImportFile" />
      </label>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        :title="t('customers.exportTitle')"
        @click="exportCsv"
      >⬇ {{ t('customers.exportCsv') }}</button>
    </div>

    <!-- Type tabs -->
    <div class="flex gap-1 mb-4">
      <button
        v-for="tab in [{ key: 'all', label: t('customers.tabAll') }, { key: 'company', label: t('customers.tabCompanies') }, { key: 'person', label: t('customers.tabPeople') }]"
        :key="tab.key"
        class="px-4 py-1.5 rounded-xl text-sm font-medium transition-colors"
        :class="activeTab === tab.key
          ? 'bg-red-600 text-white'
          : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'"
        @click="activeTab = tab.key as 'all' | 'company' | 'person'"
      >{{ tab.label }}</button>
    </div>

    <!-- Skeleton -->
    <div v-if="store.loading && store.customers.length === 0" class="animate-pulse space-y-2">
      <div v-for="i in 6" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="store.customers.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
      <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
        <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </div>
      <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">
        <template v-if="searchInput">{{ t('customers.noSearchResults') }}</template>
        <template v-else>{{ t('customers.noCustomers') }}</template>
      </h3>
      <p class="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-xs">
        <template v-if="searchInput">{{ t('customers.tryDifferentSearch') }}</template>
        <template v-else>{{ t('customers.addFirstHint') }}</template>
      </p>
      <button
        v-if="!searchInput"
        class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreate"
      >{{ t('customers.addFirst') }}</button>
    </div>

    <!-- Table -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100 dark:border-gray-700 text-left">
            <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('customers.colName') }}</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden sm:table-cell">{{ t('customers.colType') }}</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden sm:table-cell">{{ t('customers.colCompany') }}</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden md:table-cell">{{ t('customers.colEmail') }}</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden lg:table-cell">{{ t('customers.colTags') }}</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in store.customers"
            :key="c.id"
            class="border-b border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
            @click.self="goToDetail(c.id)"
            @contextmenu="onRowContextMenu($event, c)"
          >
            <td class="px-4 py-3" @click="goToDetail(c.id)">
              <div class="font-medium text-gray-900 dark:text-gray-100">{{ fullName(c) }}</div>
              <div v-if="c.phone" class="text-xs text-gray-400 dark:text-gray-500">{{ c.phone }}</div>
            </td>
            <td class="px-4 py-3 hidden sm:table-cell" @click="goToDetail(c.id)">
              <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium" :class="contactTypeClass(c.type)">
                {{ contactTypeLabel(c.type) }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-500 dark:text-gray-400 hidden sm:table-cell" @click="goToDetail(c.id)">{{ c.company_name || '—' }}</td>
            <td class="px-4 py-3 hidden md:table-cell" @click="goToDetail(c.id)">
              <a v-if="c.email" :href="`mailto:${c.email}`" class="text-blue-600 hover:underline text-xs" @click.stop>{{ c.email }}</a>
              <span v-else class="text-gray-400 dark:text-gray-500">—</span>
            </td>
            <td class="px-4 py-3 hidden lg:table-cell" @click="goToDetail(c.id)">
              <span v-for="tag in c.tags.slice(0, 3)" :key="tag" class="inline-block px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs mr-1">{{ tag }}</span>
              <span v-if="c.tags.length > 3" class="text-xs text-gray-400 dark:text-gray-500">+{{ c.tags.length - 3 }}</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('customers.editAria')" @click.stop="openEdit(c)">✎</button>
                <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('customers.deleteAria')" @click.stop="confirmDeleteId = c.id">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="flex justify-between items-center px-4 py-3 border-t border-gray-100 dark:border-gray-700">
        <span class="text-xs text-gray-400 dark:text-gray-500">{{ t('customers.page', { n: store.page }) }}</span>
        <div class="flex gap-2">
          <button
            v-if="store.page > 1"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            @click="store.fetchCustomers({ page: store.page - 1, type: activeTab === 'all' ? '' : activeTab })"
          >{{ t('customers.prev') }}</button>
          <button
            v-if="store.hasMore"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            @click="store.fetchCustomers({ page: store.page + 1, type: activeTab === 'all' ? '' : activeTab })"
          >{{ t('customers.next') }}</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto" role="dialog" aria-modal="true" :aria-label="editingCustomer ? t('customers.editTitle') : t('customers.newTitle')">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ editingCustomer ? t('customers.editTitle') : t('customers.newTitle') }}</h3>
        <div v-if="formError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ formError }}</div>
        <form class="space-y-3" @submit.prevent="submitForm">
          <!-- Type selector -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.typeLabel') }}</label>
            <div class="flex gap-2">
              <button
                type="button"
                class="flex-1 py-2 rounded-xl text-sm font-medium border transition-colors"
                :class="formType === 'person' ? 'bg-red-600 text-white border-red-600' : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
                @click="formType = 'person'"
              >👤 {{ t('customers.typePerson') }}</button>
              <button
                type="button"
                class="flex-1 py-2 rounded-xl text-sm font-medium border transition-colors"
                :class="formType === 'company' ? 'bg-blue-600 text-white border-blue-600' : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
                @click="formType = 'company'"
              >🏢 {{ t('customers.typeCompany') }}</button>
            </div>
          </div>

          <!-- Name -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                {{ formType === 'company' ? t('customers.companyNameLabel') : t('customers.firstName') }}
              </label>
              <input v-model="formFirstName" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div v-if="formType === 'person'">
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.lastName') }}</label>
              <input v-model="formLastName" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>

          <!-- Contact info -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.email') }}</label>
              <input v-model="formEmail" type="email" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.phone') }}</label>
              <input v-model="formPhone" type="tel" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>

          <!-- Person: link to company -->
          <div v-if="formType === 'person'">
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.employerCompany') }}</label>
            <select v-model="formCompanyId" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
              <option value="">— {{ t('customers.noCompany') }} —</option>
              <option v-for="comp in availableCompanies" :key="comp.id" :value="comp.id">{{ comp.first_name }}</option>
            </select>
          </div>

          <!-- Company name (display field for persons) -->
          <div v-if="formType === 'person'">
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.company') }}</label>
            <input v-model="formCompany" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" :placeholder="t('customers.companyPlaceholder')" />
          </div>

          <!-- Business identifiers (for companies) -->
          <div v-if="formType === 'company'" class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.ico') }}</label>
              <input v-model="formIco" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.dic') }}</label>
              <input v-model="formDic" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>

          <!-- Website -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.website') }}</label>
            <input v-model="formWebsite" type="url" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="https://" />
          </div>

          <!-- Address -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressStreet') }}</label>
            <input v-model="formAddressStreet" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div class="grid grid-cols-3 gap-3">
            <div class="col-span-2">
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressCity') }}</label>
              <input v-model="formAddressCity" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressZip') }}</label>
              <input v-model="formAddressZip" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressCountry') }}</label>
            <input v-model="formAddressCountry" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>

          <!-- Tags -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.tags') }}</label>
            <input v-model="formTagsInput" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" :placeholder="t('customers.tagsPlaceholder')" />
          </div>

          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showModal = false">{{ t('customers.cancel') }}</button>
            <button type="submit" :disabled="formLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ formLoading ? t('customers.saving') : (editingCustomer ? t('customers.save') : t('customers.create')) }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Delete confirm -->
  <Teleport to="body">
    <div v-if="confirmDeleteId" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="confirmDeleteId = null">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center" role="dialog" aria-modal="true" aria-label="Delete customer confirmation">
        <div class="text-3xl mb-3" aria-hidden="true">🗑</div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">{{ t('customers.deleteTitle') }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{{ t('customers.deleteDesc') }}</p>
        <div class="flex gap-3">
          <button class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-700 dark:text-gray-300" @click="confirmDeleteId = null">{{ t('customers.cancel') }}</button>
          <button class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700" @click="confirmDelete(confirmDeleteId!)">{{ t('customers.delete') }}</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Context menu -->
  <ContextMenu ref="contextMenuRef" :items="CUSTOMER_CONTEXT_ITEMS" @action="onContextAction" />
</template>

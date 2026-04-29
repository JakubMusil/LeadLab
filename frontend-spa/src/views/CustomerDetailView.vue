<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

const route = useRoute()
const store = useCustomersStore()
const toast = useToast()
const { t } = useI18n()

const customerId = computed(() => route.params.id as string)

// Edit mode
const editing = ref(false)
const editFirstName = ref('')
const editLastName = ref('')
const editEmail = ref('')
const editPhone = ref('')
const editCompany = ref('')
const editCompanyId = ref<string>('')
const editIco = ref('')
const editDic = ref('')
const editWebsite = ref('')
const editAddressStreet = ref('')
const editAddressCity = ref('')
const editAddressZip = ref('')
const editAddressCountry = ref('')
const editLoading = ref(false)
const editError = ref('')

// Tags
const newTag = ref('')
const tagsLoading = ref(false)

// Metadata
const newMetaKey = ref('')
const newMetaValue = ref('')
const metaLoading = ref(false)

// Employees (for company contacts)
const employees = ref<CustomerOut[]>([])
const employeesLoading = ref(false)

// Available companies for person→company link
const availableCompanies = computed(() => store.customers.filter((c) => c.type === 'company' && c.id !== customerId.value))

// Linked leads
interface LeadOut { id: string; title: string; status: string; value: number | null; currency: string; created_at: string }
const linkedLeads = ref<LeadOut[]>([])
const leadsLoading = ref(false)

// Linked proposals
interface ProposalOut { id: string; title: string; status: string; total_value: string; currency: string; created_at: string }
const linkedProposals = ref<ProposalOut[]>([])
const proposalsLoading = ref(false)

function startEdit() {
  const c = store.currentCustomer
  if (!c) return
  editFirstName.value = c.first_name
  editLastName.value = c.last_name
  editEmail.value = c.email
  editPhone.value = c.phone
  editCompany.value = c.company_name
  editCompanyId.value = c.company_id ?? ''
  editIco.value = c.ico
  editDic.value = c.dic
  editWebsite.value = c.website
  editAddressStreet.value = c.address_street
  editAddressCity.value = c.address_city
  editAddressZip.value = c.address_zip
  editAddressCountry.value = c.address_country
  editError.value = ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function saveEdit() {
  if (!editFirstName.value.trim()) { editError.value = t('customers.firstNameRequired'); return }
  editLoading.value = true
  const c = store.currentCustomer!
  const result = await store.updateCustomer(customerId.value, {
    type: c.type,
    first_name: editFirstName.value.trim(),
    last_name: editLastName.value.trim(),
    email: editEmail.value.trim(),
    phone: editPhone.value.trim(),
    company_name: editCompany.value.trim(),
    company_id: c.type === 'person' && editCompanyId.value ? editCompanyId.value : null,
    ico: editIco.value.trim(),
    dic: editDic.value.trim(),
    website: editWebsite.value.trim(),
    address_street: editAddressStreet.value.trim(),
    address_city: editAddressCity.value.trim(),
    address_zip: editAddressZip.value.trim(),
    address_country: editAddressCountry.value.trim(),
    tags: c.tags,
    metadata: c.metadata,
  })
  editLoading.value = false
  if (result.ok) {
    editing.value = false
    toast.success(t('customers.updated'))
  } else {
    editError.value = result.error ?? t('customers.failedToUpdate')
  }
}

async function addTag() {
  const tag = newTag.value.trim()
  if (!tag) return
  const c = store.currentCustomer!
  if (c.tags.includes(tag)) { newTag.value = ''; return }
  tagsLoading.value = true
  const result = await store.updateCustomer(customerId.value, {
    type: c.type, first_name: c.first_name, last_name: c.last_name,
    email: c.email, phone: c.phone, company_name: c.company_name,
    tags: [...c.tags, tag],
    metadata: c.metadata,
  })
  tagsLoading.value = false
  if (result.ok) newTag.value = ''
  else toast.error(t('customers.failedToAddTag'))
}

async function removeTag(tag: string) {
  const c = store.currentCustomer!
  tagsLoading.value = true
  await store.updateCustomer(customerId.value, {
    type: c.type, first_name: c.first_name, last_name: c.last_name,
    email: c.email, phone: c.phone, company_name: c.company_name,
    tags: c.tags.filter((tg) => tg !== tag),
    metadata: c.metadata,
  })
  tagsLoading.value = false
}

async function addMetadata() {
  const key = newMetaKey.value.trim()
  const value = newMetaValue.value.trim()
  if (!key) return
  const c = store.currentCustomer!
  metaLoading.value = true
  const result = await store.updateCustomer(customerId.value, {
    type: c.type, first_name: c.first_name, last_name: c.last_name,
    email: c.email, phone: c.phone, company_name: c.company_name,
    tags: c.tags,
    metadata: { ...c.metadata, [key]: value },
  })
  metaLoading.value = false
  if (result.ok) { newMetaKey.value = ''; newMetaValue.value = '' }
  else toast.error(t('customers.failedToSaveMeta'))
}

async function removeMetadata(key: string) {
  const c = store.currentCustomer!
  const meta = { ...c.metadata }
  delete meta[key]
  metaLoading.value = true
  await store.updateCustomer(customerId.value, {
    type: c.type, first_name: c.first_name, last_name: c.last_name,
    email: c.email, phone: c.phone, company_name: c.company_name,
    tags: c.tags,
    metadata: meta,
  })
  metaLoading.value = false
}

async function loadLinkedLeads() {
  leadsLoading.value = true
  try {
    const allLeads = await api.get<Array<LeadOut & { customer_id: string | null }>>('/api/v1/crm/opportunities?page_size=100')
    if (allLeads.ok) {
      linkedLeads.value = allLeads.data.filter((l) => l.customer_id === customerId.value)
    }
  } finally {
    leadsLoading.value = false
  }
}

function statusColor(status: string) {
  const map: Record<string, string> = {
    new: 'bg-gray-100 text-gray-700', contacted: 'bg-blue-100 text-blue-700',
    proposal: 'bg-yellow-100 text-yellow-700', negotiation: 'bg-orange-100 text-orange-700',
    won: 'bg-green-100 text-green-700', lost: 'bg-red-100 text-red-700', canceled: 'bg-gray-100 text-gray-500',
  }
  return map[status] ?? 'bg-gray-100 text-gray-700'
}

function proposalStatusColor(status: string) {
  const map: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700', sent: 'bg-blue-100 text-blue-700',
    viewed: 'bg-yellow-100 text-yellow-700', accepted: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700', expired: 'bg-orange-100 text-orange-700',
  }
  return map[status] ?? 'bg-gray-100 text-gray-700'
}

async function loadLinkedProposals() {
  proposalsLoading.value = true
  try {
    const res = await api.get<ProposalOut[]>(`/api/v1/crm/proposals?customer_id=${customerId.value}`)
    if (res.ok) linkedProposals.value = res.data
  } finally {
    proposalsLoading.value = false
  }
}

async function loadEmployees() {
  if (store.currentCustomer?.type !== 'company') return
  employeesLoading.value = true
  const result = await store.fetchCompanyEmployees(customerId.value)
  if (result.ok) employees.value = result.data ?? []
  employeesLoading.value = false
}

onMounted(async () => {
  await store.fetchCustomers({ page: 1 })
  await store.fetchCustomer(customerId.value)
  await loadLinkedLeads()
  await loadLinkedProposals()
  await loadEmployees()
})
</script>

<template>
  <div class="p-6 space-y-5">
    <RouterLink to="/app/directory" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600">
      ← {{ t('customers.title') }}
    </RouterLink>

    <!-- Skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-32 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="store.currentCustomer">
      <!-- Contact card -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div class="flex items-center gap-4">
            <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-xl font-semibold flex-shrink-0"
              :class="store.currentCustomer.type === 'company' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600' : 'bg-red-100 dark:bg-red-900/30 text-red-600'">
              {{ store.currentCustomer.type === 'company' ? '🏢' : store.currentCustomer.first_name[0]?.toUpperCase() ?? '?' }}
            </div>
            <div>
              <template v-if="!editing">
                <div class="flex items-center gap-2 mb-0.5">
                  <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
                    {{ [store.currentCustomer.first_name, store.currentCustomer.last_name].filter(Boolean).join(' ') }}
                  </h2>
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                    :class="store.currentCustomer.type === 'company' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'">
                    {{ store.currentCustomer.type === 'company' ? t('customers.typeCompany') : t('customers.typePerson') }}
                  </span>
                </div>
                <p v-if="store.currentCustomer.company_name" class="text-sm text-gray-500 dark:text-gray-400">{{ store.currentCustomer.company_name }}</p>
                <!-- Company link for persons -->
                <RouterLink
                  v-if="store.currentCustomer.company_id"
                  :to="`/app/directory/${store.currentCustomer.company_id}`"
                  class="text-xs text-blue-600 hover:underline dark:text-blue-400"
                >🏢 {{ availableCompanies.find(c => c.id === store.currentCustomer!.company_id)?.first_name ?? t('customers.viewCompany') }}</RouterLink>
                <div class="flex items-center gap-3 mt-2 flex-wrap">
                  <a v-if="store.currentCustomer.email" :href="`mailto:${store.currentCustomer.email}`" class="text-sm text-blue-600 hover:underline flex items-center gap-1 dark:text-blue-400">
                    📧 {{ store.currentCustomer.email }}
                  </a>
                  <a v-if="store.currentCustomer.phone" :href="`tel:${store.currentCustomer.phone}`" class="text-sm text-green-600 hover:underline flex items-center gap-1">
                    📞 {{ store.currentCustomer.phone }}
                  </a>
                  <a v-if="store.currentCustomer.website" :href="store.currentCustomer.website" target="_blank" rel="noopener" class="text-sm text-purple-600 hover:underline flex items-center gap-1">
                    🌐 {{ store.currentCustomer.website }}
                  </a>
                </div>
                <!-- IČO / DIČ -->
                <div v-if="store.currentCustomer.ico || store.currentCustomer.dic" class="flex items-center gap-4 mt-2 text-xs text-gray-500 dark:text-gray-400">
                  <span v-if="store.currentCustomer.ico">IČO: <strong>{{ store.currentCustomer.ico }}</strong></span>
                  <span v-if="store.currentCustomer.dic">DIČ: <strong>{{ store.currentCustomer.dic }}</strong></span>
                </div>
                <!-- Address -->
                <div v-if="store.currentCustomer.address_street || store.currentCustomer.address_city" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
                  📍 {{ [store.currentCustomer.address_street, store.currentCustomer.address_zip, store.currentCustomer.address_city, store.currentCustomer.address_country].filter(Boolean).join(', ') }}
                </div>
              </template>
              <template v-else>
                <div v-if="editError" class="mb-2 text-sm text-red-600 dark:text-red-400">{{ editError }}</div>
                <div class="grid grid-cols-2 gap-2">
                  <input v-model="editFirstName" :placeholder="store.currentCustomer.type === 'company' ? t('customers.companyNameLabel') : t('customers.firstName')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-if="store.currentCustomer.type === 'person'" v-model="editLastName" :placeholder="t('customers.lastName')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editEmail" type="email" :placeholder="t('customers.email')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editPhone" type="tel" :placeholder="t('customers.phone')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editCompany" :placeholder="t('customers.company')" class="col-span-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editWebsite" type="url" placeholder="https://" class="col-span-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-if="store.currentCustomer.type === 'company'" v-model="editIco" :placeholder="t('customers.ico')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-if="store.currentCustomer.type === 'company'" v-model="editDic" :placeholder="t('customers.dic')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <!-- Employer company for persons -->
                  <div v-if="store.currentCustomer.type === 'person'" class="col-span-2">
                    <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('customers.employerCompany') }}</label>
                    <select v-model="editCompanyId" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400">
                      <option value="">— {{ t('customers.noCompany') }} —</option>
                      <option v-for="comp in availableCompanies" :key="comp.id" :value="comp.id">{{ comp.first_name }}</option>
                    </select>
                  </div>
                  <input v-model="editAddressStreet" :placeholder="t('customers.addressStreet')" class="col-span-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editAddressCity" :placeholder="t('customers.addressCity')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editAddressZip" :placeholder="t('customers.addressZip')" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editAddressCountry" :placeholder="t('customers.addressCountry')" class="col-span-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                </div>
                <div class="flex gap-2 mt-2">
                  <button :disabled="editLoading" class="px-3 py-1.5 bg-red-600 text-white rounded-xl text-sm hover:bg-red-700 disabled:opacity-50" @click="saveEdit">{{ editLoading ? t('customers.saving') : t('customers.save') }}</button>
                  <button class="px-3 py-1.5 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-700 dark:text-gray-300" @click="cancelEdit">{{ t('customers.cancel') }}</button>
                </div>
              </template>
            </div>
          </div>
          <button v-if="!editing" class="px-3 py-1.5 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="startEdit">{{ t('customers.edit') }}</button>
        </div>
      </div>

      <!-- Employees (for companies) -->
      <div v-if="store.currentCustomer.type === 'company'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.employees') }}</h3>
        <div v-if="employeesLoading" class="animate-pulse space-y-2">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>
        <div v-else-if="employees.length === 0" class="text-sm text-gray-400 dark:text-gray-500">{{ t('customers.noEmployees') }}</div>
        <div v-else class="space-y-1">
          <RouterLink
            v-for="emp in employees"
            :key="emp.id"
            :to="`/app/directory/${emp.id}`"
            class="flex items-center gap-3 p-2.5 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <div class="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center text-red-600 text-sm font-medium flex-shrink-0">
              {{ emp.first_name[0]?.toUpperCase() ?? '?' }}
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ [emp.first_name, emp.last_name].filter(Boolean).join(' ') }}</div>
              <div v-if="emp.email" class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ emp.email }}</div>
            </div>
          </RouterLink>
        </div>
      </div>

      <!-- Tags -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.tagsSection') }}</h3>
        <div class="flex flex-wrap gap-2 mb-3">
          <span
            v-for="tag in store.currentCustomer.tags"
            :key="tag"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-sm text-gray-700 dark:text-gray-300"
          >
            {{ tag }}
            <button class="text-gray-400 hover:text-red-500 ml-1 text-xs" :disabled="tagsLoading" @click="removeTag(tag)">×</button>
          </span>
          <span v-if="store.currentCustomer.tags.length === 0" class="text-sm text-gray-400 dark:text-gray-500">{{ t('customers.noTags') }}</span>
        </div>
        <div class="flex gap-2">
          <input
            v-model="newTag"
            type="text"
            :placeholder="t('customers.addTag')"
            class="flex-1 max-w-48 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
            @keydown.enter.prevent="addTag"
          />
          <button :disabled="tagsLoading || !newTag.trim()" class="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50" @click="addTag">{{ t('customers.add') }}</button>
        </div>
      </div>

      <!-- Metadata -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.customFields') }}</h3>
        <div v-if="Object.keys(store.currentCustomer.metadata).length > 0" class="divide-y divide-gray-50 dark:divide-gray-700 mb-3">
          <div v-for="(val, key) in store.currentCustomer.metadata" :key="key" class="flex items-center gap-3 py-2 group">
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300 w-32 flex-shrink-0 truncate">{{ key }}</span>
            <span class="text-sm text-gray-500 dark:text-gray-400 flex-1 truncate">{{ val }}</span>
            <button class="opacity-0 group-hover:opacity-100 text-xs text-red-500 hover:text-red-700" :disabled="metaLoading" @click="removeMetadata(key)">✕</button>
          </div>
        </div>
        <div v-else class="text-sm text-gray-400 dark:text-gray-500 mb-3">{{ t('customers.noCustomFields') }}</div>
        <div class="flex gap-2 flex-wrap">
          <input v-model="newMetaKey" type="text" :placeholder="t('customers.metaKeyPlaceholder')" class="w-36 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
          <input v-model="newMetaValue" type="text" :placeholder="t('customers.metaValuePlaceholder')" class="flex-1 min-w-36 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
          <button :disabled="metaLoading || !newMetaKey.trim()" class="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50" @click="addMetadata">{{ t('customers.add') }}</button>
        </div>
      </div>

      <!-- Linked Leads -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.linkedLeads') }}</h3>
        <div v-if="leadsLoading" class="animate-pulse space-y-2">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>
        <div v-else-if="linkedLeads.length === 0" class="text-sm text-gray-400 dark:text-gray-500">{{ t('customers.noLinkedLeads') }}</div>
        <div v-else class="space-y-2">
          <RouterLink
            v-for="lead in linkedLeads"
            :key="lead.id"
            :to="`/app/opportunities/${lead.id}`"
            class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ lead.title }}</span>
            <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="statusColor(lead.status)">{{ lead.status }}</span>
            <span v-if="lead.value != null" class="text-xs text-gray-500 dark:text-gray-400">{{ lead.value }} {{ lead.currency }}</span>
          </RouterLink>
        </div>
      </div>

      <!-- Linked Proposals -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('proposals.title') }}</h3>
          <RouterLink
            :to="`/app/proposals`"
            class="text-xs text-red-600 hover:text-red-700"
          >{{ t('proposals.allProposals') }}</RouterLink>
        </div>
        <div v-if="proposalsLoading" class="animate-pulse space-y-2">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>
        <div v-else-if="linkedProposals.length === 0" class="text-sm text-gray-400 dark:text-gray-500">{{ t('proposals.noProposals') }}</div>
        <div v-else class="space-y-2">
          <RouterLink
            v-for="p in linkedProposals"
            :key="p.id"
            :to="`/app/proposals/${p.id}`"
            class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ p.title }}</span>
            <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="proposalStatusColor(p.status)">{{ p.status }}</span>
            <span class="text-xs text-gray-500 dark:text-gray-400 font-mono">{{ Number(p.total_value).toFixed(2) }} {{ p.currency }}</span>
          </RouterLink>
        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400 dark:text-gray-500">{{ t('customers.notFound') }}</div>
  </div>
</template>

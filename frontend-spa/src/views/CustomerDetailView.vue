<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
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
const editLoading = ref(false)
const editError = ref('')

// Tags
const newTag = ref('')
const tagsLoading = ref(false)

// Metadata
const newMetaKey = ref('')
const newMetaValue = ref('')
const metaLoading = ref(false)

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
    first_name: editFirstName.value.trim(),
    last_name: editLastName.value.trim(),
    email: editEmail.value.trim(),
    phone: editPhone.value.trim(),
    company_name: editCompany.value.trim(),
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
    first_name: c.first_name, last_name: c.last_name,
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
    first_name: c.first_name, last_name: c.last_name,
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
    first_name: c.first_name, last_name: c.last_name,
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
    first_name: c.first_name, last_name: c.last_name,
    email: c.email, phone: c.phone, company_name: c.company_name,
    tags: c.tags,
    metadata: meta,
  })
  metaLoading.value = false
}

async function loadLinkedLeads() {
  leadsLoading.value = true
  try {
    const res = await api.get<LeadOut[]>(`/api/v1/crm/opportunities?page_size=50`)
    if (res.ok) {
      linkedLeads.value = res.data.filter((l) => {
        // Filter by customer_id if available from leads endpoint
        return true
      })
      // For simplicity fetch all and filter client-side (leads don't include customer_id check here)
      // Actually leads have customer_id field, let's re-fetch properly
      const allLeads = await api.get<Array<LeadOut & { customer_id: string | null }>>('/api/v1/crm/opportunities?page_size=100')
      if (allLeads.ok) {
        linkedLeads.value = allLeads.data.filter((l) => l.customer_id === customerId.value)
      }
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

onMounted(async () => {
  await store.fetchCustomer(customerId.value)
  await loadLinkedLeads()
  await loadLinkedProposals()
})
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto space-y-5">
    <RouterLink to="/app/directory" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600">
      ← {{ t('customers.title') }}
    </RouterLink>

    <!-- Skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-32 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="store.currentCustomer">
      <!-- Contact card -->
      <div class="bg-white rounded-2xl border border-gray-100 p-5">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div class="flex items-center gap-4">
            <div class="w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center text-red-600 text-xl font-semibold flex-shrink-0">
              {{ store.currentCustomer.first_name[0]?.toUpperCase() ?? '?' }}
            </div>
            <div>
              <template v-if="!editing">
                <h2 class="text-xl font-semibold text-gray-900">
                  {{ [store.currentCustomer.first_name, store.currentCustomer.last_name].filter(Boolean).join(' ') }}
                </h2>
                <p v-if="store.currentCustomer.company_name" class="text-sm text-gray-500">{{ store.currentCustomer.company_name }}</p>
                <div class="flex items-center gap-3 mt-2 flex-wrap">
                  <a v-if="store.currentCustomer.email" :href="`mailto:${store.currentCustomer.email}`" class="text-sm text-blue-600 hover:underline flex items-center gap-1">
                    📧 {{ store.currentCustomer.email }}
                  </a>
                  <a v-if="store.currentCustomer.phone" :href="`tel:${store.currentCustomer.phone}`" class="text-sm text-green-600 hover:underline flex items-center gap-1">
                    📞 {{ store.currentCustomer.phone }}
                  </a>
                </div>
              </template>
              <template v-else>
                <div v-if="editError" class="mb-2 text-sm text-red-600">{{ editError }}</div>
                <div class="grid grid-cols-2 gap-2">
                  <input v-model="editFirstName" :placeholder="t('customers.firstName')" class="rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editLastName" :placeholder="t('customers.lastName')" class="rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editEmail" type="email" :placeholder="t('customers.email')" class="rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editPhone" type="tel" :placeholder="t('customers.phone')" class="rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                  <input v-model="editCompany" :placeholder="t('customers.company')" class="col-span-2 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
                </div>
                <div class="flex gap-2 mt-2">
                  <button :disabled="editLoading" class="px-3 py-1.5 bg-red-600 text-white rounded-xl text-sm hover:bg-red-700 disabled:opacity-50" @click="saveEdit">{{ editLoading ? t('customers.saving') : t('customers.save') }}</button>
                  <button class="px-3 py-1.5 border border-gray-200 rounded-xl text-sm" @click="cancelEdit">{{ t('customers.cancel') }}</button>
                </div>
              </template>
            </div>
          </div>
          <button v-if="!editing" class="px-3 py-1.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50" @click="startEdit">{{ t('customers.edit') }}</button>
        </div>
      </div>

      <!-- Tags -->
      <div class="bg-white rounded-2xl border border-gray-100 p-5">
        <h3 class="text-sm font-semibold text-gray-900 mb-3">{{ t('customers.tagsSection') }}</h3>
        <div class="flex flex-wrap gap-2 mb-3">
          <span
            v-for="tag in store.currentCustomer.tags"
            :key="tag"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 text-sm text-gray-700"
          >
            {{ tag }}
            <button class="text-gray-400 hover:text-red-500 ml-1 text-xs" :disabled="tagsLoading" @click="removeTag(tag)">×</button>
          </span>
          <span v-if="store.currentCustomer.tags.length === 0" class="text-sm text-gray-400">{{ t('customers.noTags') }}</span>
        </div>
        <div class="flex gap-2">
          <input
            v-model="newTag"
            type="text"
            :placeholder="t('customers.addTag')"
            class="flex-1 max-w-48 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
            @keydown.enter.prevent="addTag"
          />
          <button :disabled="tagsLoading || !newTag.trim()" class="px-3 py-1.5 bg-gray-100 rounded-xl text-sm text-gray-700 hover:bg-gray-200 disabled:opacity-50" @click="addTag">{{ t('customers.add') }}</button>
        </div>
      </div>

      <!-- Metadata -->
      <div class="bg-white rounded-2xl border border-gray-100 p-5">
        <h3 class="text-sm font-semibold text-gray-900 mb-3">{{ t('customers.customFields') }}</h3>
        <div v-if="Object.keys(store.currentCustomer.metadata).length > 0" class="divide-y divide-gray-50 mb-3">
          <div v-for="(val, key) in store.currentCustomer.metadata" :key="key" class="flex items-center gap-3 py-2 group">
            <span class="text-sm font-medium text-gray-700 w-32 flex-shrink-0 truncate">{{ key }}</span>
            <span class="text-sm text-gray-500 flex-1 truncate">{{ val }}</span>
            <button class="opacity-0 group-hover:opacity-100 text-xs text-red-500 hover:text-red-700" :disabled="metaLoading" @click="removeMetadata(key)">✕</button>
          </div>
        </div>
        <div v-else class="text-sm text-gray-400 mb-3">{{ t('customers.noCustomFields') }}</div>
        <div class="flex gap-2 flex-wrap">
          <input v-model="newMetaKey" type="text" :placeholder="t('customers.metaKeyPlaceholder')" class="w-36 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
          <input v-model="newMetaValue" type="text" :placeholder="t('customers.metaValuePlaceholder')" class="flex-1 min-w-36 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
          <button :disabled="metaLoading || !newMetaKey.trim()" class="px-3 py-1.5 bg-gray-100 rounded-xl text-sm text-gray-700 hover:bg-gray-200 disabled:opacity-50" @click="addMetadata">{{ t('customers.add') }}</button>
        </div>
      </div>

      <!-- Linked Leads -->
      <div class="bg-white rounded-2xl border border-gray-100 p-5">
        <h3 class="text-sm font-semibold text-gray-900 mb-3">{{ t('customers.linkedLeads') }}</h3>
        <div v-if="leadsLoading" class="animate-pulse space-y-2">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 rounded-xl" />
        </div>
        <div v-else-if="linkedLeads.length === 0" class="text-sm text-gray-400">{{ t('customers.noLinkedLeads') }}</div>
        <div v-else class="space-y-2">
          <RouterLink
            v-for="lead in linkedLeads"
            :key="lead.id"
            :to="`/app/opportunities/${lead.id}`"
            class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors"
          >
            <span class="flex-1 text-sm font-medium text-gray-900 truncate">{{ lead.title }}</span>
            <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="statusColor(lead.status)">{{ lead.status }}</span>
            <span v-if="lead.value != null" class="text-xs text-gray-500">{{ lead.value }} {{ lead.currency }}</span>
          </RouterLink>
        </div>
      </div>
      <!-- Linked Proposals -->
      <div class="bg-white rounded-2xl border border-gray-100 p-5">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-900">{{ t('proposals.title') }}</h3>
          <RouterLink
            :to="`/app/proposals`"
            class="text-xs text-red-600 hover:text-red-700"
          >{{ t('proposals.allProposals') }}</RouterLink>
        </div>
        <div v-if="proposalsLoading" class="animate-pulse space-y-2">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 rounded-xl" />
        </div>
        <div v-else-if="linkedProposals.length === 0" class="text-sm text-gray-400">{{ t('proposals.noProposals') }}</div>
        <div v-else class="space-y-2">
          <RouterLink
            v-for="p in linkedProposals"
            :key="p.id"
            :to="`/app/proposals/${p.id}`"
            class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors"
          >
            <span class="flex-1 text-sm font-medium text-gray-900 truncate">{{ p.title }}</span>
            <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="proposalStatusColor(p.status)">{{ p.status }}</span>
            <span class="text-xs text-gray-500 font-mono">{{ Number(p.total_value).toFixed(2) }} {{ p.currency }}</span>
          </RouterLink>
        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400">{{ t('customers.notFound') }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useToast } from '@/composables/useToast'

const router = useRouter()
const store = useCustomersStore()
const toast = useToast()

const showModal = ref(false)
const editingCustomer = ref<CustomerOut | null>(null)
const confirmDeleteId = ref<string | null>(null)
const searchInput = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Form
const formFirstName = ref('')
const formLastName = ref('')
const formEmail = ref('')
const formPhone = ref('')
const formCompany = ref('')
const formTagsInput = ref('')
const formError = ref('')
const formLoading = ref(false)

onMounted(() => store.fetchCustomers())

watch(searchInput, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    store.search = val
    store.fetchCustomers({ search: val, page: 1 })
  }, 300)
})

function openCreate() {
  editingCustomer.value = null
  formFirstName.value = ''
  formLastName.value = ''
  formEmail.value = ''
  formPhone.value = ''
  formCompany.value = ''
  formTagsInput.value = ''
  formError.value = ''
  showModal.value = true
}

function openEdit(c: CustomerOut) {
  editingCustomer.value = c
  formFirstName.value = c.first_name
  formLastName.value = c.last_name
  formEmail.value = c.email
  formPhone.value = c.phone
  formCompany.value = c.company_name
  formTagsInput.value = c.tags.join(', ')
  formError.value = ''
  showModal.value = true
}

async function submitForm() {
  if (!formFirstName.value.trim()) { formError.value = 'First name is required.'; return }
  formLoading.value = true
  formError.value = ''
  const tags = formTagsInput.value.split(',').map((t) => t.trim()).filter(Boolean)
  const payload = {
    first_name: formFirstName.value.trim(),
    last_name: formLastName.value.trim(),
    email: formEmail.value.trim(),
    phone: formPhone.value.trim(),
    company_name: formCompany.value.trim(),
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
    toast.success(editingCustomer.value ? 'Customer updated.' : 'Customer created.')
  } else {
    formError.value = result.error ?? 'An error occurred.'
  }
}

async function confirmDelete(id: string) {
  const result = await store.deleteCustomer(id)
  confirmDeleteId.value = null
  if (result.ok) toast.success('Customer deleted.')
  else toast.error(result.error ?? 'Failed to delete.')
}

function goToDetail(id: string) {
  router.push(`/app/customers/${id}`)
}

function fullName(c: CustomerOut) {
  return [c.first_name, c.last_name].filter(Boolean).join(' ')
}
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <h2 class="text-lg font-semibold text-gray-900">Customers</h2>
      <!-- Search -->
      <div class="flex items-center flex-1 min-w-48 max-w-sm bg-gray-100 rounded-xl px-3 py-2 gap-2">
        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input v-model="searchInput" type="text" placeholder="Search customers…" class="bg-transparent text-sm text-gray-700 placeholder-gray-400 outline-none flex-1" />
      </div>
      <button
        class="bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreate"
      >+ New Customer</button>
    </div>

    <!-- Skeleton -->
    <div v-if="store.loading && store.customers.length === 0" class="animate-pulse space-y-2">
      <div v-for="i in 6" :key="i" class="h-14 bg-gray-100 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="store.customers.length === 0" class="text-center py-16 text-gray-400">
      <div class="text-4xl mb-3">👥</div>
      <p v-if="searchInput">No customers match your search.</p>
      <p v-else>No customers yet. <button class="text-red-600 font-medium hover:underline" @click="openCreate">Add your first customer.</button></p>
    </div>

    <!-- Table -->
    <div v-else class="bg-white rounded-2xl border border-gray-100 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100 text-left">
            <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Name</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide hidden sm:table-cell">Company</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide hidden md:table-cell">Email</th>
            <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide hidden lg:table-cell">Tags</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in store.customers"
            :key="c.id"
            class="border-b border-gray-50 hover:bg-gray-50 transition-colors cursor-pointer group"
            @click.self="goToDetail(c.id)"
          >
            <td class="px-4 py-3" @click="goToDetail(c.id)">
              <div class="font-medium text-gray-900">{{ fullName(c) }}</div>
              <div v-if="c.phone" class="text-xs text-gray-400">{{ c.phone }}</div>
            </td>
            <td class="px-4 py-3 text-gray-500 hidden sm:table-cell" @click="goToDetail(c.id)">{{ c.company_name || '—' }}</td>
            <td class="px-4 py-3 hidden md:table-cell" @click="goToDetail(c.id)">
              <a v-if="c.email" :href="`mailto:${c.email}`" class="text-blue-600 hover:underline text-xs" @click.stop>{{ c.email }}</a>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="px-4 py-3 hidden lg:table-cell" @click="goToDetail(c.id)">
              <span v-for="tag in c.tags.slice(0, 3)" :key="tag" class="inline-block px-2 py-0.5 rounded bg-gray-100 text-gray-600 text-xs mr-1">{{ tag }}</span>
              <span v-if="c.tags.length > 3" class="text-xs text-gray-400">+{{ c.tags.length - 3 }}</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500" @click.stop="openEdit(c)">✎</button>
                <button class="p-1.5 rounded-lg hover:bg-red-50 text-red-500" @click.stop="confirmDeleteId = c.id">🗑</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="flex justify-between items-center px-4 py-3 border-t border-gray-100">
        <span class="text-xs text-gray-400">Page {{ store.page }}</span>
        <div class="flex gap-2">
          <button
            v-if="store.page > 1"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 hover:bg-gray-50"
            @click="store.fetchCustomers({ page: store.page - 1 })"
          >← Prev</button>
          <button
            v-if="store.hasMore"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 hover:bg-gray-50"
            @click="store.fetchCustomers({ page: store.page + 1 })"
          >Next →</button>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showModal = false">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">{{ editingCustomer ? 'Edit Customer' : 'New Customer' }}</h3>
        <div v-if="formError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ formError }}</div>
        <form class="space-y-3" @submit.prevent="submitForm">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">First Name *</label>
              <input v-model="formFirstName" type="text" required class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Last Name</label>
              <input v-model="formLastName" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Email</label>
            <input v-model="formEmail" type="email" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Phone</label>
            <input v-model="formPhone" type="tel" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Company</label>
            <input v-model="formCompany" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Tags (comma-separated)</label>
            <input v-model="formTagsInput" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="vip, enterprise, priority" />
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 py-2 text-sm text-gray-600 hover:bg-gray-50" @click="showModal = false">Cancel</button>
            <button type="submit" :disabled="formLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ formLoading ? 'Saving…' : (editingCustomer ? 'Save' : 'Create') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Delete confirm -->
  <Teleport to="body">
    <div v-if="confirmDeleteId" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="confirmDeleteId = null">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 text-center">
        <div class="text-3xl mb-3">🗑</div>
        <h3 class="text-base font-semibold text-gray-900 mb-2">Delete this customer?</h3>
        <p class="text-sm text-gray-500 mb-4">This action cannot be undone.</p>
        <div class="flex gap-3">
          <button class="flex-1 rounded-xl border border-gray-200 py-2 text-sm" @click="confirmDeleteId = null">Cancel</button>
          <button class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700" @click="confirmDelete(confirmDeleteId!)">Delete</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

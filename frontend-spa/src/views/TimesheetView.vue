<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import type { TimeEntryOut, TimeEntryIn } from '@/stores/timer'
import { XMarkIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

// ─── State ─────────────────────────────────────────────────────────────────

const entries = ref<TimeEntryOut[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const toast = ref<string | null>(null)

// Filters
const filterUser = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

// Manual entry form
const showManualForm = ref(false)
const formLoading = ref(false)
const form = ref<{
  duration_minutes: number
  description: string
  is_billable: boolean
  hourly_rate: string
  started_at: string
  lead_id: string
  lead_label: string
  customer_id: string
  customer_label: string
  task_id: string
  task_label: string
}>({
  duration_minutes: 60,
  description: '',
  is_billable: true,
  hourly_rate: '',
  started_at: new Date().toISOString().substring(0, 16),
  lead_id: '',
  lead_label: '',
  customer_id: '',
  customer_label: '',
  task_id: '',
  task_label: '',
})

// Entity search helpers
const leadSearch = ref('')
const leadResults = ref<{ id: string; label: string }[]>([])
const customerSearch = ref('')
const customerResults = ref<{ id: string; label: string }[]>([])

async function searchLeads(q: string) {
  if (!q) { leadResults.value = []; return }
  const res = await api.get<Record<string, string>[]>(`/api/v1/crm/leads?search=${encodeURIComponent(q)}&page_size=10`)
  if (res.ok) {
    leadResults.value = (Array.isArray(res.data) ? res.data : (res.data as { results?: Record<string, string>[] }).results ?? [])
      .map((l) => ({ id: l.id as string, label: l.title as string }))
  }
}

async function searchCustomers(q: string) {
  if (!q) { customerResults.value = []; return }
  const res = await api.get<Record<string, string>[]>(`/api/v1/crm/customers?search=${encodeURIComponent(q)}&page_size=10`)
  if (res.ok) {
    customerResults.value = (Array.isArray(res.data) ? res.data : (res.data as { results?: Record<string, string>[] }).results ?? [])
      .map((c) => ({ id: c.id as string, label: `${c.first_name ?? ''} ${c.last_name ?? ''}`.trim() || c.email as string }))
  }
}

function pickLead(item: { id: string; label: string }) {
  form.value.lead_id = item.id
  form.value.lead_label = item.label
  leadSearch.value = item.label
  leadResults.value = []
}

function pickCustomer(item: { id: string; label: string }) {
  form.value.customer_id = item.id
  form.value.customer_label = item.label
  customerSearch.value = item.label
  customerResults.value = []
}

function clearLead() {
  form.value.lead_id = ''
  form.value.lead_label = ''
  leadSearch.value = ''
  leadResults.value = []
}

function clearCustomer() {
  form.value.customer_id = ''
  form.value.customer_label = ''
  customerSearch.value = ''
  customerResults.value = []
}

// Editing
const editingId = ref<string | null>(null)
const editDuration = ref<number>(0)
const editDescription = ref<string>('')
const editHourlyRate = ref<string>('')
const confirmDeleteEntryId = ref<string | null>(null)

// ─── Helpers ────────────────────────────────────────────────────────────────

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = null }, 3000)
}

function formatDate(isoStr: string | null): string {
  if (!isoStr) return '—'
  return new Date(isoStr).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

const totalMinutes = computed(() => entries.value.reduce((s, e) => s + e.duration_minutes, 0))
const billableMinutes = computed(() => entries.value.filter(e => e.is_billable).reduce((s, e) => s + e.duration_minutes, 0))

// ─── Data fetching ───────────────────────────────────────────────────────────

async function fetchEntries() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams()
    if (filterUser.value) params.set('user_id', filterUser.value)
    if (filterDateFrom.value) params.set('date_from', filterDateFrom.value)
    if (filterDateTo.value) params.set('date_to', filterDateTo.value)
    const url = `/api/v1/erp/time-entries${params.size ? '?' + params.toString() : ''}`
    const res = await api.get<TimeEntryOut[]>(url)
    if (res.ok) {
      entries.value = res.data
    } else {
      error.value = extractErrorMessage(res.data, 'Failed to load time entries')
    }
  } finally {
    loading.value = false
  }
}

onMounted(fetchEntries)

// ─── Manual entry ────────────────────────────────────────────────────────────

async function submitManualEntry() {
  formLoading.value = true
  try {
    const payload: TimeEntryIn = {
      duration_minutes: form.value.duration_minutes,
      description: form.value.description,
      is_billable: form.value.is_billable,
      hourly_rate: form.value.hourly_rate ? parseFloat(form.value.hourly_rate) : null,
      started_at: form.value.started_at ? new Date(form.value.started_at).toISOString() : null,
      lead_id: form.value.lead_id || null,
      customer_id: form.value.customer_id || null,
      task_id: form.value.task_id || null,
    }
    const res = await api.post<TimeEntryOut>('/api/v1/erp/time-entries', payload)
    if (res.ok) {
      entries.value.unshift(res.data)
      showManualForm.value = false
      showToast('Time entry added')
      form.value = {
        duration_minutes: 60,
        description: '',
        is_billable: true,
        hourly_rate: '',
        started_at: new Date().toISOString().substring(0, 16),
        lead_id: '',
        lead_label: '',
        customer_id: '',
        customer_label: '',
        task_id: '',
        task_label: '',
      }
      leadSearch.value = ''
      customerSearch.value = ''
    } else {
      showToast(extractErrorMessage(res.data, 'Failed to add entry'))
    }
  } finally {
    formLoading.value = false
  }
}

// ─── Inline editing ──────────────────────────────────────────────────────────

function startEdit(entry: TimeEntryOut) {
  editingId.value = entry.id
  editDuration.value = entry.duration_minutes
  editDescription.value = entry.description
  editHourlyRate.value = entry.hourly_rate != null ? String(entry.hourly_rate) : ''
}

function cancelEdit() {
  editingId.value = null
}

async function saveEdit(entry: TimeEntryOut) {
  const res = await api.patch<TimeEntryOut>(`/api/v1/erp/time-entries/${entry.id}`, {
    duration_minutes: editDuration.value,
    description: editDescription.value,
    hourly_rate: editHourlyRate.value ? parseFloat(editHourlyRate.value) : null,
  })
  if (res.ok) {
    const idx = entries.value.findIndex(e => e.id === entry.id)
    if (idx !== -1) entries.value[idx] = res.data
    editingId.value = null
    showToast('Entry updated')
  } else {
    showToast(extractErrorMessage(res.data, 'Failed to update entry'))
  }
}

async function doDeleteEntry(id: string) {
  const res = await api.delete(`/api/v1/erp/time-entries/${id}`)
  if (res.ok || res.status === 204) {
    entries.value = entries.value.filter(e => e.id !== id)
    showToast('Entry deleted')
  } else {
    showToast('Failed to delete entry')
  }
}

function deleteEntry(id: string) {
  confirmDeleteEntryId.value = id
}
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Timesheet</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">Track and review worked time</p>
      </div>
      <button
        class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
        @click="showManualForm = !showManualForm"
      >
        + Manual entry
      </button>
    </div>

    <!-- Toast -->
    <Transition name="fade">
      <div v-if="toast" class="mb-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-xl w-fit">
        {{ toast }}
      </div>
    </Transition>

    <!-- Summary cards -->
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Total time</div>
        <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ formatDuration(totalMinutes) }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Billable time</div>
        <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ formatDuration(billableMinutes) }}</div>
      </div>
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
        <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Entries</div>
        <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ entries.length }}</div>
      </div>
    </div>

    <!-- Manual entry form -->
    <div v-if="showManualForm" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 mb-6">
      <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Add manual time entry</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Duration (minutes)</label>
          <input v-model.number="form.duration_minutes" type="number" min="1"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Date &amp; time</label>
          <input v-model="form.started_at" type="datetime-local"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
        </div>
        <div class="sm:col-span-2">
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Description</label>
          <input v-model="form.description" type="text" placeholder="What did you work on?"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
        </div>
        <div class="relative">
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Opportunity (optional)</label>
          <input v-model="leadSearch" type="text" placeholder="Search opportunities…"
            @input="searchLeads(leadSearch)"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
          <button v-if="form.lead_id" class="absolute right-2 top-7 text-gray-400 hover:text-gray-600 text-xs" @click="clearLead"><XMarkIcon class="w-4 h-4" /></button>
          <div v-if="leadResults.length" class="absolute z-10 w-full mt-0.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-40 overflow-y-auto">
            <button v-for="r in leadResults" :key="r.id"
              class="w-full text-left px-3 py-2 text-sm text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-600"
              @click="pickLead(r)">{{ r.label }}</button>
          </div>
        </div>
        <div class="relative">
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Contact (optional)</label>
          <input v-model="customerSearch" type="text" placeholder="Search contacts…"
            @input="searchCustomers(customerSearch)"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
          <button v-if="form.customer_id" class="absolute right-2 top-7 text-gray-400 hover:text-gray-600 text-xs" @click="clearCustomer"><XMarkIcon class="w-4 h-4" /></button>
          <div v-if="customerResults.length" class="absolute z-10 w-full mt-0.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-40 overflow-y-auto">
            <button v-for="r in customerResults" :key="r.id"
              class="w-full text-left px-3 py-2 text-sm text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-600"
              @click="pickCustomer(r)">{{ r.label }}</button>
          </div>
        </div>
        <div class="flex items-center gap-2 sm:col-span-2">
          <button
            type="button"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
            :class="form.is_billable ? 'bg-red-600' : 'bg-gray-300 dark:bg-gray-600'"
            @click="form.is_billable = !form.is_billable"
            role="switch"
            :aria-checked="form.is_billable"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
              :class="form.is_billable ? 'translate-x-4' : 'translate-x-0.5'"
            />
          </button>
          <span class="text-sm text-gray-700 dark:text-gray-300">Billable</span>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Hodinová sazba (optional)</label>
          <input v-model="form.hourly_rate" type="number" min="0" step="0.01" placeholder="0.00"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
        </div>
      </div>
      <div class="flex gap-3 mt-4 justify-end">
        <button class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl"
          @click="showManualForm = false">Cancel</button>
        <button class="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-60 transition-colors"
          :disabled="formLoading" @click="submitManualEntry">
          {{ formLoading ? 'Saving…' : 'Save entry' }}
        </button>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-4">
      <input v-model="filterDateFrom" type="date"
        class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
        placeholder="From" />
      <input v-model="filterDateTo" type="date"
        class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
        placeholder="To" />
      <button
        class="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        @click="fetchEntries"
      >Filter</button>
      <button
        class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
        @click="filterDateFrom = ''; filterDateTo = ''; fetchEntries()"
      >Clear</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16 text-gray-400">Loading…</div>
    <div v-else-if="error" class="text-center py-16 text-red-500">{{ error }}</div>

    <!-- Table -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div v-if="entries.length === 0" class="py-16 text-center text-gray-400 dark:text-gray-500 text-sm">
        No time entries yet. Start the timer or add a manual entry.
      </div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100 dark:border-gray-700 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            <th class="px-4 py-3 text-left">Date</th>
            <th class="px-4 py-3 text-left">Duration</th>
            <th class="px-4 py-3 text-left">Description</th>
            <th class="px-4 py-3 text-left">Linked to</th>
            <th class="px-4 py-3 text-left">User</th>
            <th class="px-4 py-3 text-left">Billable</th>
            <th class="px-4 py-3 text-left">Hodinová sazba</th>
            <th class="px-4 py-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.id"
            class="border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30"
          >
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400 whitespace-nowrap">
              {{ formatDate(entry.started_at ?? entry.created_at) }}
            </td>
            <td class="px-4 py-3">
              <template v-if="editingId === entry.id">
                <input v-model.number="editDuration" type="number" min="1"
                  class="w-20 rounded border border-gray-300 dark:border-gray-600 px-2 py-0.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </template>
              <span v-else class="font-medium text-gray-900 dark:text-gray-100">{{ formatDuration(entry.duration_minutes) }}</span>
            </td>
            <td class="px-4 py-3 text-gray-700 dark:text-gray-300 max-w-xs">
              <template v-if="editingId === entry.id">
                <input v-model="editDescription" type="text"
                  class="w-full rounded border border-gray-300 dark:border-gray-600 px-2 py-0.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </template>
              <span v-else class="truncate block">{{ entry.description || '—' }}</span>
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">
              <span v-if="entry.lead_title" class="text-blue-600 dark:text-blue-400">{{ entry.lead_title }}</span>
              <span v-else-if="entry.customer_name" class="text-purple-600 dark:text-purple-400">{{ entry.customer_name }}</span>
              <span v-else-if="entry.task_title" class="text-green-600 dark:text-green-400">{{ entry.task_title }}</span>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ entry.user_name ?? '—' }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="entry.is_billable ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'"
              >
                {{ entry.is_billable ? 'Billable' : 'Non-billable' }}
              </span>
            </td>
            <td class="px-4 py-3 text-gray-700 dark:text-gray-300">
              <template v-if="editingId === entry.id">
                <input v-model="editHourlyRate" type="number" min="0" step="0.01" placeholder="0.00"
                  class="w-24 rounded border border-gray-300 dark:border-gray-600 px-2 py-0.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </template>
              <span v-else>{{ entry.hourly_rate != null ? entry.hourly_rate : '—' }}</span>
            </td>
            <td class="px-4 py-3 text-right">
              <template v-if="editingId === entry.id">
                <button class="text-sm text-green-600 hover:text-green-700 mr-2" @click="saveEdit(entry)">Save</button>
                <button class="text-sm text-gray-500 hover:text-gray-700" @click="cancelEdit">Cancel</button>
              </template>
              <template v-else>
                <button class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mr-3" @click="startEdit(entry)">Edit</button>
                <button class="text-sm text-red-500 hover:text-red-700" @click="deleteEntry(entry.id)">Delete</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <ConfirmDeleteModal
    :open="!!confirmDeleteEntryId"
    @confirm="doDeleteEntry(confirmDeleteEntryId!); confirmDeleteEntryId = null"
    @cancel="confirmDeleteEntryId = null"
  />
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLeadsStore, LEAD_STATUSES, getStatusMeta, type LeadOut } from '@/stores/leads'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const store = useLeadsStore()
const toast = useToast()

type ViewMode = 'table' | 'kanban'
const viewMode = ref<ViewMode>('table')
const filterStatus = ref((route.query.status as string) ?? '')
const filterSource = ref('')
const showModal = ref(false)
const editingLead = ref<LeadOut | null>(null)
const confirmDeleteId = ref<string | null>(null)
const statusPopupId = ref<string | null>(null)

// Form
const formTitle = ref('')
const formDescription = ref('')
const formStatus = ref('new')
const formSource = ref('web')
const formValue = ref<string>('')
const formCurrency = ref('CZK')
const formError = ref('')
const formLoading = ref(false)

watch(filterStatus, () => { store.fetchLeads({ status: filterStatus.value, source: filterSource.value }) })
watch(filterSource, () => { store.fetchLeads({ status: filterStatus.value, source: filterSource.value }) })

onMounted(() => {
  store.fetchLeads({ status: filterStatus.value })
})

const leadsByStatus = computed(() => {
  const map: Record<string, LeadOut[]> = {}
  for (const s of LEAD_STATUSES) map[s.value] = []
  for (const l of store.leads) {
    if (map[l.status]) map[l.status]!.push(l)
    else map[l.status] = [l]
  }
  return map
})

function openCreate() {
  editingLead.value = null
  formTitle.value = ''
  formDescription.value = ''
  formStatus.value = 'new'
  formSource.value = 'web'
  formValue.value = ''
  formCurrency.value = 'CZK'
  formError.value = ''
  showModal.value = true
}

function openEdit(lead: LeadOut) {
  editingLead.value = lead
  formTitle.value = lead.title
  formDescription.value = lead.description
  formStatus.value = lead.status
  formSource.value = lead.source
  formValue.value = lead.value != null ? String(lead.value) : ''
  formCurrency.value = lead.currency
  formError.value = ''
  showModal.value = true
}

async function submitForm() {
  if (!formTitle.value.trim()) { formError.value = 'Title is required.'; return }
  formLoading.value = true
  formError.value = ''
  const payload = {
    title: formTitle.value.trim(),
    description: formDescription.value,
    status: formStatus.value,
    source: formSource.value,
    value: formValue.value ? parseFloat(formValue.value) : null,
    currency: formCurrency.value,
  }
  let result
  if (editingLead.value) {
    result = await store.updateLead(editingLead.value.id, payload)
  } else {
    result = await store.createLead(payload)
  }
  formLoading.value = false
  if (result.ok) {
    showModal.value = false
    toast.success(editingLead.value ? 'Lead updated.' : 'Lead created.')
  } else {
    formError.value = result.error ?? 'An error occurred.'
  }
}

async function confirmDelete(id: string) {
  const result = await store.deleteLead(id)
  confirmDeleteId.value = null
  if (result.ok) toast.success('Lead deleted.')
  else toast.error(result.error ?? 'Failed to delete lead.')
}

async function changeStatus(leadId: string, newStatus: string) {
  statusPopupId.value = null
  const result = await store.patchStatus(leadId, newStatus)
  if (!result.ok) toast.error(result.error ?? 'Failed to update status.')
}

function goToDetail(id: string) {
  router.push(`/app/leads/${id}`)
}

// Kanban drag state
const draggingLead = ref<LeadOut | null>(null)
const dragOverStatus = ref<string | null>(null)

function onDragStart(lead: LeadOut) {
  draggingLead.value = lead
}
function onDragOver(e: DragEvent, status: string) {
  e.preventDefault()
  dragOverStatus.value = status
}
function onDragLeave() {
  dragOverStatus.value = null
}
async function onDrop(status: string) {
  dragOverStatus.value = null
  if (!draggingLead.value || draggingLead.value.status === status) {
    draggingLead.value = null
    return
  }
  const lead = draggingLead.value
  draggingLead.value = null
  await changeStatus(lead.id, status)
}

function fmtValue(lead: LeadOut) {
  if (lead.value == null) return ''
  return new Intl.NumberFormat(undefined, { style: 'decimal', maximumFractionDigits: 0 }).format(lead.value) + ' ' + lead.currency
}

// Fetch lead tasks to check overdue
const overdueTasks = ref<Set<string>>(new Set())
async function checkOverdueTasks() {
  const res = await api.get<{ id: string; lead_id: string; due_date: string | null; is_completed: boolean }[]>(
    '/api/v1/crm/tasks?completed=false&page_size=100'
  )
  if (res.ok) {
    const now = Date.now()
    const set = new Set<string>()
    for (const t of res.data) {
      if (t.due_date && new Date(t.due_date).getTime() < now) {
        set.add(t.lead_id)
      }
    }
    overdueTasks.value = set
  }
}
onMounted(checkOverdueTasks)
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <h2 class="text-lg font-semibold text-gray-900 flex-1">Leads</h2>

      <!-- View toggle -->
      <div class="flex rounded-xl border border-gray-200 overflow-hidden text-sm">
        <button
          class="px-3 py-1.5 transition-colors"
          :class="viewMode === 'table' ? 'bg-red-600 text-white' : 'text-gray-600 hover:bg-gray-50'"
          @click="viewMode = 'table'"
        >☰ Table</button>
        <button
          class="px-3 py-1.5 transition-colors"
          :class="viewMode === 'kanban' ? 'bg-red-600 text-white' : 'text-gray-600 hover:bg-gray-50'"
          @click="viewMode = 'kanban'"
        >⊞ Kanban</button>
      </div>

      <!-- Filters (table only) -->
      <template v-if="viewMode === 'table'">
        <select v-model="filterStatus" class="rounded-xl border border-gray-200 text-sm px-3 py-1.5 text-gray-700 focus:outline-none focus:border-red-400">
          <option value="">All Statuses</option>
          <option v-for="s in LEAD_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
        <select v-model="filterSource" class="rounded-xl border border-gray-200 text-sm px-3 py-1.5 text-gray-700 focus:outline-none focus:border-red-400">
          <option value="">All Sources</option>
          <option value="web">Web</option>
          <option value="email">Email</option>
          <option value="referral">Referral</option>
          <option value="cold_call">Cold Call</option>
          <option value="social">Social</option>
          <option value="other">Other</option>
        </select>
      </template>

      <button
        class="bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreate"
      >+ New Lead</button>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && store.leads.length === 0" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-14 bg-gray-100 rounded-xl" />
    </div>

    <!-- TABLE VIEW -->
    <template v-else-if="viewMode === 'table'">
      <div v-if="store.leads.length === 0" class="text-center py-16 text-gray-400">
        <div class="text-4xl mb-3">◎</div>
        <p>No leads yet. <button class="text-red-600 font-medium hover:underline" @click="openCreate">Create your first lead.</button></p>
      </div>
      <div v-else class="bg-white rounded-2xl border border-gray-100 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-100 text-left">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Title</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide hidden md:table-cell">Source</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide hidden lg:table-cell">Value</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide hidden lg:table-cell">Created</th>
              <th class="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="lead in store.leads"
              :key="lead.id"
              class="border-b border-gray-50 hover:bg-gray-50 transition-colors cursor-pointer group"
              @click.self="goToDetail(lead.id)"
            >
              <td class="px-4 py-3 font-medium text-gray-900 max-w-xs" @click="goToDetail(lead.id)">
                <div class="flex items-center gap-1.5">
                  <span class="truncate">{{ lead.title }}</span>
                  <span v-if="overdueTasks.has(lead.id)" title="Overdue task" class="text-red-500 text-xs flex-shrink-0">⚠</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="relative">
                  <button
                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-80"
                    :class="getStatusMeta(lead.status).color"
                    @click.stop="statusPopupId = statusPopupId === lead.id ? null : lead.id"
                  >
                    {{ getStatusMeta(lead.status).label }}
                    <span class="text-xs opacity-60">▾</span>
                  </button>
                  <!-- Status popup -->
                  <div
                    v-if="statusPopupId === lead.id"
                    class="absolute z-10 top-8 left-0 bg-white rounded-xl border border-gray-200 shadow-lg py-1 min-w-36"
                    @click.stop
                  >
                    <button
                      v-for="s in LEAD_STATUSES"
                      :key="s.value"
                      class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 flex items-center gap-2"
                      :class="s.value === lead.status ? 'font-semibold' : ''"
                      @click="changeStatus(lead.id, s.value)"
                    >
                      <span class="w-2 h-2 rounded-full flex-shrink-0" :class="s.color.split(' ')[0]" />
                      {{ s.label }}
                    </button>
                  </div>
                </div>
              </td>
              <td class="px-4 py-3 text-gray-500 hidden md:table-cell capitalize" @click="goToDetail(lead.id)">{{ lead.source.replace('_', ' ') }}</td>
              <td class="px-4 py-3 text-gray-700 hidden lg:table-cell" @click="goToDetail(lead.id)">{{ fmtValue(lead) }}</td>
              <td class="px-4 py-3 text-gray-400 text-xs hidden lg:table-cell" @click="goToDetail(lead.id)">{{ new Date(lead.created_at).toLocaleDateString() }}</td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500" title="Edit" @click.stop="openEdit(lead)">✎</button>
                  <button class="p-1.5 rounded-lg hover:bg-red-50 text-red-500" title="Delete" @click.stop="confirmDeleteId = lead.id">🗑</button>
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
              @click="store.fetchLeads({ status: filterStatus, source: filterSource, page: store.page - 1 })"
            >← Prev</button>
            <button
              v-if="store.hasMore"
              class="px-3 py-1 text-xs rounded-lg border border-gray-200 hover:bg-gray-50"
              @click="store.fetchLeads({ status: filterStatus, source: filterSource, page: store.page + 1 })"
            >Next →</button>
          </div>
        </div>
      </div>
    </template>

    <!-- KANBAN VIEW -->
    <template v-else>
      <div class="flex gap-4 overflow-x-auto pb-4 min-h-96">
        <div
          v-for="s in LEAD_STATUSES"
          :key="s.value"
          class="flex-shrink-0 w-64 flex flex-col"
          @dragover="onDragOver($event, s.value)"
          @dragleave="onDragLeave"
          @drop="onDrop(s.value)"
        >
          <!-- Column header -->
          <div
            class="flex items-center gap-2 px-3 py-2 rounded-xl mb-2 text-xs font-semibold transition-colors"
            :class="[s.color, dragOverStatus === s.value ? 'ring-2 ring-offset-1 ring-red-400' : '']"
          >
            {{ s.label }}
            <span class="ml-auto bg-white/60 rounded px-1.5 py-0.5">{{ leadsByStatus[s.value]?.length ?? 0 }}</span>
          </div>
          <!-- Cards -->
          <div
            class="flex-1 space-y-2 min-h-16 rounded-xl transition-colors p-1"
            :class="dragOverStatus === s.value ? 'bg-red-50' : 'bg-gray-50'"
          >
            <div
              v-for="lead in leadsByStatus[s.value]"
              :key="lead.id"
              class="bg-white rounded-xl border border-gray-100 p-3 cursor-grab shadow-sm hover:shadow transition-shadow group"
              draggable="true"
              @dragstart="onDragStart(lead)"
            >
              <div class="flex items-start justify-between gap-2">
                <button
                  class="text-xs font-medium text-gray-900 text-left hover:text-red-600 transition-colors leading-snug"
                  @click="goToDetail(lead.id)"
                >{{ lead.title }}</button>
                <div class="flex gap-0.5 opacity-0 group-hover:opacity-100">
                  <button class="p-1 rounded hover:bg-gray-100 text-gray-400 text-xs" @click.stop="openEdit(lead)">✎</button>
                </div>
              </div>
              <div class="flex items-center gap-2 mt-2 flex-wrap">
                <span v-if="fmtValue(lead)" class="text-xs text-gray-500">{{ fmtValue(lead) }}</span>
                <span v-if="overdueTasks.has(lead.id)" class="text-xs text-red-500" title="Overdue task">⚠ overdue</span>
              </div>
            </div>
            <div v-if="(leadsByStatus[s.value]?.length ?? 0) === 0" class="text-center text-xs text-gray-300 py-4">Drop here</div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- Create/Edit Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showModal = false">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-semibold text-gray-900 mb-4">{{ editingLead ? 'Edit Lead' : 'New Lead' }}</h3>
        <div v-if="formError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ formError }}</div>
        <form class="space-y-3" @submit.prevent="submitForm">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Title *</label>
            <input v-model="formTitle" type="text" required class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Description</label>
            <textarea v-model="formDescription" rows="2" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Status</label>
              <select v-model="formStatus" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option v-for="s in LEAD_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Source</label>
              <select v-model="formSource" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option value="web">Web</option>
                <option value="email">Email</option>
                <option value="referral">Referral</option>
                <option value="cold_call">Cold Call</option>
                <option value="social">Social</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Value</label>
              <input v-model="formValue" type="number" min="0" step="0.01" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="0" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 mb-1">Currency</label>
              <input v-model="formCurrency" type="text" maxlength="3" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="CZK" />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 py-2 text-sm text-gray-600 hover:bg-gray-50" @click="showModal = false">Cancel</button>
            <button type="submit" :disabled="formLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ formLoading ? 'Saving…' : (editingLead ? 'Save' : 'Create') }}
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
        <h3 class="text-base font-semibold text-gray-900 mb-2">Delete this lead?</h3>
        <p class="text-sm text-gray-500 mb-4">This action cannot be undone.</p>
        <div class="flex gap-3">
          <button class="flex-1 rounded-xl border border-gray-200 py-2 text-sm" @click="confirmDeleteId = null">Cancel</button>
          <button class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700" @click="confirmDelete(confirmDeleteId!)">Delete</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Global status popup backdrop -->
  <div v-if="statusPopupId" class="fixed inset-0 z-5" @click="statusPopupId = null" />
</template>

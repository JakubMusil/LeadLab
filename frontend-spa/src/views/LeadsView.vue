<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLeadsStore, LEAD_STATUSES, getStatusMeta, type LeadOut } from '@/stores/leads'
import { useSavedViewsStore } from '@/stores/savedViews'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'
import ContextMenu, { type ContextMenuItem } from '@/components/ContextMenu.vue'
import Dropdown from '@/components/ui/Dropdown.vue'
import LeadScoreBadge from '@/components/LeadScoreBadge.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { useI18n } from '@/composables/useI18n'
import { TrashIcon, PencilSquareIcon, XMarkIcon, ArrowTopRightOnSquareIcon, ArrowsRightLeftIcon, Bars3Icon, Squares2X2Icon, ListBulletIcon, BookmarkIcon, ChevronDownIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const router = useRouter()
const store = useLeadsStore()
const savedViewsStore = useSavedViewsStore()
const customersStore = useCustomersStore()
const authStore = useAuthStore()
const toast = useToast()
const { t } = useI18n()

type ViewMode = 'table' | 'kanban' | 'list'

const VIEW_MODES = ['table', 'kanban', 'list'] as const

const viewModeIcons: Record<ViewMode, object> = {
  table: Bars3Icon,
  kanban: Squares2X2Icon,
  list: ListBulletIcon,
}

const viewMode = ref<ViewMode>('table')

watch(() => authStore.user?.id, (userId) => {
  if (!userId) return
  try {
    const stored = localStorage.getItem(`leadlab_leads_displaymode_u${userId}`)
    if (stored === 'table' || stored === 'kanban' || stored === 'list') {
      viewMode.value = stored
    }
  } catch {
    // ignore
  }
}, { immediate: true })

watch(viewMode, (mode) => {
  const userId = authStore.user?.id
  if (!userId) return
  try {
    localStorage.setItem(`leadlab_leads_displaymode_u${userId}`, mode)
  } catch {
    // ignore
  }
})
const filterStatus = ref((route.query.status as string) ?? '')
const filterSource = ref('')
const showModal = ref(false)
const editingLead = ref<LeadOut | null>(null)
const confirmDeleteId = ref<string | null>(null)
const statusPopupId = ref<string | null>(null)

// Saved view UI
const showSaveViewDialog = ref(false)
const saveViewName = ref('')
const savingView = ref(false)

// Form
const formTitle = ref('')
const formStatus = ref('new')
const formSource = ref('web')
const formValue = ref<string>('')
const formCurrency = ref('CZK')
const formError = ref('')
const formLoading = ref(false)

// Customer typeahead inside lead form
const formCustomerId = ref<string | null>(null)
const formCustomerQuery = ref('')
const customerSuggestions = ref<CustomerOut[]>([])
const customerSearchLoading = ref(false)
const showCustomerDropdown = ref(false)
const showNewCustomerForm = ref(false)
const newCustomerFirstName = ref('')
const newCustomerLastName = ref('')
const newCustomerEmail = ref('')
const newCustomerPhone = ref('')
const selectedCustomerLabel = ref('')

// Company & Contact Person inside lead form
const formCompanyId = ref<string | null>(null)
const formContactPersonId = ref<string | null>(null)
const companies = ref<CustomerOut[]>([])
const contactPersons = ref<CustomerOut[]>([])
const loadingCompanies = ref(false)
const loadingContactPersons = ref(false)

async function loadCompanies() {
  loadingCompanies.value = true
  const res = await api.get<CustomerOut[]>('/api/v1/crm/directory?type=company&page_size=200')
  loadingCompanies.value = false
  if (res.ok) companies.value = res.data
}

async function loadEmployeesForCompany(companyId: string) {
  loadingContactPersons.value = true
  const res = await api.get<CustomerOut[]>(`/api/v1/crm/directory/${companyId}/employees`)
  loadingContactPersons.value = false
  if (res.ok) contactPersons.value = res.data
}

let customerSearchTimer: ReturnType<typeof setTimeout> | null = null

async function searchCustomers(query: string) {
  if (!query.trim()) { customerSuggestions.value = []; return }
  customerSearchLoading.value = true
  const res = await api.get<CustomerOut[]>(`/api/v1/crm/directory?search=${encodeURIComponent(query)}&page_size=10`)
  customerSearchLoading.value = false
  if (res.ok) customerSuggestions.value = res.data
}

function onCustomerQueryInput() {
  showCustomerDropdown.value = true
  showNewCustomerForm.value = false
  if (customerSearchTimer) clearTimeout(customerSearchTimer)
  customerSearchTimer = setTimeout(() => searchCustomers(formCustomerQuery.value), 280)
}

function selectCustomer(c: CustomerOut) {
  formCustomerId.value = c.id
  selectedCustomerLabel.value = [c.first_name, c.last_name].filter(Boolean).join(' ') + (c.email ? ` (${c.email})` : '')
  formCustomerQuery.value = selectedCustomerLabel.value
  showCustomerDropdown.value = false
  customerSuggestions.value = []
}

function clearCustomer() {
  formCustomerId.value = null
  formCustomerQuery.value = ''
  selectedCustomerLabel.value = ''
  customerSuggestions.value = []
  showCustomerDropdown.value = false
}

function openNewCustomerInline() {
  showCustomerDropdown.value = false
  showNewCustomerForm.value = true
  newCustomerFirstName.value = formCustomerQuery.value.split(' ')[0] ?? ''
  newCustomerLastName.value = formCustomerQuery.value.split(' ').slice(1).join(' ')
  newCustomerEmail.value = ''
  newCustomerPhone.value = ''
}

async function createAndSelectCustomer() {
  if (!newCustomerFirstName.value.trim()) return
  const result = await customersStore.createCustomer({
    first_name: newCustomerFirstName.value.trim(),
    last_name: newCustomerLastName.value.trim(),
    email: newCustomerEmail.value.trim(),
    phone: newCustomerPhone.value.trim(),
  })
  if (result.ok && result.data) {
    selectCustomer(result.data)
    showNewCustomerForm.value = false
    toast.success(t('leads.customerCreated'))
  } else {
    toast.error(result.error ?? t('leads.failedToCreateCustomer'))
  }
}

// Context menu
const contextMenuRef = ref<InstanceType<typeof ContextMenu> | null>(null)
const contextLead = ref<LeadOut | null>(null)

const LEAD_CONTEXT_ITEMS = computed<ContextMenuItem[]>(() => [
  { id: 'view', label: t('leads.viewDetail'), icon: ArrowTopRightOnSquareIcon },
  { id: 'edit', label: t('leads.edit'), icon: PencilSquareIcon },
  { id: 'change_status', label: t('leads.changeStatus'), icon: ArrowsRightLeftIcon },
  { id: 'divider1', label: '', divider: true },
  { id: 'delete', label: t('leads.delete'), icon: TrashIcon, danger: true },
])

function onRowContextMenu(e: MouseEvent, lead: LeadOut) {
  e.preventDefault()
  contextLead.value = lead
  contextMenuRef.value?.open(e.clientX, e.clientY)
}

function onRowLongPress(lead: LeadOut, e: TouchEvent) {
  e.preventDefault()
  const touch = e.touches[0]
  if (!touch) return
  contextLead.value = lead
  contextMenuRef.value?.open(touch.clientX, touch.clientY)
}

function onContextAction(id: string) {
  const lead = contextLead.value
  if (!lead) return
  if (id === 'view') goToDetail(lead.id)
  else if (id === 'edit') openEdit(lead)
  else if (id === 'change_status') statusPopupId.value = lead.id
  else if (id === 'delete') confirmDeleteId.value = lead.id
}

watch(filterStatus, () => { store.fetchLeads({ status: filterStatus.value, source: filterSource.value }) })
watch(filterSource, () => { store.fetchLeads({ status: filterStatus.value, source: filterSource.value }) })

// Apply saved view from ?view= query param
watch(() => route.query.view, async (viewId) => {
  if (!viewId) return
  await savedViewsStore.fetchViews()
  const v = savedViewsStore.views.find((sv) => sv.id === viewId)
  if (v) {
    filterStatus.value = (v.filters.status as string) ?? ''
    filterSource.value = (v.filters.source as string) ?? ''
  }
}, { immediate: true })

onMounted(async () => {
  store.fetchLeads({ status: filterStatus.value })
  savedViewsStore.fetchViews()
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
  formStatus.value = 'new'
  formSource.value = 'web'
  formValue.value = ''
  formCurrency.value = 'CZK'
  formError.value = ''
  formCompanyId.value = null
  formContactPersonId.value = null
  contactPersons.value = []
  clearCustomer()
  showNewCustomerForm.value = false
  loadCompanies()
  showModal.value = true
}

function openEdit(lead: LeadOut) {
  editingLead.value = lead
  formTitle.value = lead.title
  formStatus.value = lead.status
  formSource.value = lead.source
  formValue.value = lead.value != null ? String(lead.value) : ''
  formCurrency.value = lead.currency
  formError.value = ''
  // Restore customer if already linked
  formCustomerId.value = lead.customer_id ?? null
  const extLead = lead as LeadOut & { customer_name?: string; customer_email?: string }
  if (lead.customer_id && extLead.customer_name) {
    selectedCustomerLabel.value = extLead.customer_name + (extLead.customer_email ? ` (${extLead.customer_email})` : '')
    formCustomerQuery.value = selectedCustomerLabel.value
  } else {
    clearCustomer()
  }
  formCompanyId.value = lead.company_id ?? null
  formContactPersonId.value = lead.contact_person_id ?? null
  if (lead.company_id) {
    loadEmployeesForCompany(lead.company_id)
  } else {
    contactPersons.value = []
  }
  showNewCustomerForm.value = false
  loadCompanies()
  showModal.value = true
}

function onCompanyChange() {
  if (formCompanyId.value) {
    loadEmployeesForCompany(formCompanyId.value)
  } else {
    contactPersons.value = []
    formContactPersonId.value = null
  }
}

async function submitForm() {
  if (!formTitle.value.trim()) { formError.value = t('leads.titleRequired'); return }
  formLoading.value = true
  formError.value = ''
  const payload = {
    title: formTitle.value.trim(),
    status: formStatus.value,
    source: formSource.value,
    value: formValue.value ? parseFloat(formValue.value) : null,
    currency: formCurrency.value,
    customer_id: formCustomerId.value ?? null,
    company_id: formCompanyId.value ?? null,
    contact_person_id: formContactPersonId.value ?? null,
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
    toast.success(editingLead.value ? t('leads.leadUpdated') : t('leads.leadCreated'))
  } else {
    formError.value = result.error ?? t('leads.errorOccurred')
  }
}

async function confirmDelete(id: string) {
  const result = await store.deleteLead(id)
  confirmDeleteId.value = null
  if (result.ok) toast.success(t('leads.leadDeleted'))
  else toast.error(result.error ?? t('leads.failedToDelete'))
}

async function changeStatus(leadId: string, newStatus: string) {
  statusPopupId.value = null
  const result = await store.patchStatus(leadId, newStatus)
  if (!result.ok) toast.error(result.error ?? t('leads.failedToUpdateStatus'))
}

function goToDetail(id: string) {
  router.push(`/app/opportunities/${id}`)
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

function statusLabel(value: string): string {
  const map: Record<string, string> = {
    new: t('leads.statusNew'),
    contacted: t('leads.statusContacted'),
    proposal: t('leads.statusProposal'),
    negotiation: t('leads.statusNegotiation'),
    won: t('leads.statusWon'),
    lost: t('leads.statusLost'),
    canceled: t('leads.statusCanceled'),
  }
  return map[value] ?? value
}

function sourceLabel(value: string): string {
  const map: Record<string, string> = {
    web: t('leads.sourceWeb'),
    email: t('leads.sourceEmail'),
    referral: t('leads.sourceReferral'),
    cold_call: t('leads.sourceColdCall'),
    social: t('leads.sourceSocial'),
    other: t('leads.sourceOther'),
  }
  return map[value] ?? value
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
    for (const task of res.data) {
      if (task.due_date && new Date(task.due_date).getTime() < now) {
        set.add(task.lead_id)
      }
    }
    overdueTasks.value = set
  }
}
onMounted(checkOverdueTasks)

// Saved views
async function saveCurrentView() {
  if (!saveViewName.value.trim()) return
  savingView.value = true
  const result = await savedViewsStore.createView({
    name: saveViewName.value.trim(),
    entity: 'opportunities',
    filters: {
      ...(filterStatus.value ? { status: filterStatus.value } : {}),
      ...(filterSource.value ? { source: filterSource.value } : {}),
    },
  })
  savingView.value = false
  if (result) {
    toast.success(t('leads.viewSaved'))
    showSaveViewDialog.value = false
    saveViewName.value = ''
  } else {
    toast.error(t('leads.failedToSaveView'))
  }
}

async function deleteSavedView(id: string) {
  await savedViewsStore.deleteView(id)
  toast.success(t('leads.viewDeleted'))
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
      '/api/v1/integrations/import/leads',
      fd,
    )
    if (res.ok) {
      toast.success(t('leads.importStarted'))
      setTimeout(() => store.fetchLeads({ status: filterStatus.value, source: filterSource.value }), 2000)
    } else {
      const msg = ((res.data as unknown) as Record<string, string> | null)?.detail ?? t('leads.importFailed')
      toast.error(msg)
    }
  } finally {
    importLoading.value = false
    if (importInput.value) importInput.value.value = ''
  }
}

function exportCsv() {
  const params = new URLSearchParams()
  if (filterStatus.value) params.set('status', filterStatus.value)
  if (filterSource.value) params.set('source', filterSource.value)
  window.location.href = `/api/v1/integrations/export/leads.csv?${params.toString()}`
}

function exportPdf() {
  window.location.href = '/api/v1/integrations/export/pipeline.pdf'
}

const actionsDropdownItems = computed(() => [
  { label: t('leads.saveView'), onClick: () => { showSaveViewDialog.value = true } },
  { label: t('leads.importCsv'), onClick: () => { importInput.value?.click() } },
  { label: t('leads.exportCsv'), onClick: exportCsv },
  { label: t('leads.exportPdf'), onClick: exportPdf },
])
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 flex-1">{{ t('leads.title') }}</h2>

      <!-- Saved views -->
      <div v-if="savedViewsStore.viewsForEntity('opportunities').length > 0" class="flex items-center gap-1 flex-wrap">
        <div
          v-for="view in savedViewsStore.viewsForEntity('opportunities')"
          :key="view.id"
          class="flex items-center gap-0.5"
        >
          <button
            class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-l-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            :title="view.name"
            @click="router.push(`/app/leads?view=${view.id}`)"
          >
            <BookmarkIcon class="w-3.5 h-3.5" /> {{ view.name }}
          </button>
          <button
            class="px-1.5 py-1 text-xs font-medium rounded-r-xl border border-l-0 border-gray-200 dark:border-gray-600 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
            :title="`Delete view: ${view.name}`"
            :aria-label="`Delete saved view ${view.name}`"
            @click="deleteSavedView(view.id)"
          ><XMarkIcon class="w-3.5 h-3.5" /></button>
        </div>
      </div>

      <!-- View toggle (Task-list style) -->
      <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1">
        <button
          v-for="mode in VIEW_MODES"
          :key="mode"
          class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          :class="viewMode === mode
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
          @click="viewMode = mode"
        >
          <component :is="viewModeIcons[mode]" class="w-4 h-4 inline-block mr-1 align-text-bottom" />{{ t(`leads.${mode}`) }}
        </button>
      </div>

      <!-- Filters (table & list views) -->
      <template v-if="viewMode !== 'kanban'">
        <select v-model="filterStatus" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400">
          <option value="">{{ t('leads.allStatuses') }}</option>
          <option v-for="s in LEAD_STATUSES" :key="s.value" :value="s.value">{{ statusLabel(s.value) }}</option>
        </select>
        <select v-model="filterSource" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400">
          <option value="">{{ t('leads.allSources') }}</option>
          <option value="web">{{ t('leads.sourceWeb') }}</option>
          <option value="email">{{ t('leads.sourceEmail') }}</option>
          <option value="referral">{{ t('leads.sourceReferral') }}</option>
          <option value="cold_call">{{ t('leads.sourceColdCall') }}</option>
          <option value="social">{{ t('leads.sourceSocial') }}</option>
          <option value="other">{{ t('leads.sourceOther') }}</option>
        </select>
      </template>

      <button
        class="bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreate"
      >{{ t('leads.newLead') }}</button>

      <!-- Actions dropdown (import / export / save view) -->
      <Dropdown :items="actionsDropdownItems" placement="right">
        <button
          type="button"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          <span>{{ t('leads.actions') }}</span>
          <ChevronDownIcon class="w-3.5 h-3.5" aria-hidden="true" />
        </button>
      </Dropdown>

      <!-- Hidden file input for CSV import -->
      <input ref="importInput" type="file" accept=".csv" class="hidden" @change="onImportFile" />
    </div>

    <!-- Loading -->
    <div v-if="store.loading && store.leads.length === 0" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- TABLE VIEW -->
    <template v-else-if="viewMode === 'table'">
      <div v-if="store.leads.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
        <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('leads.noLeadsFound') }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-xs">
          <template v-if="filterStatus || filterSource">{{ t('leads.filterSubtitle') }}</template>
          <template v-else>{{ t('leads.pipelineSubtitle') }}</template>
        </p>
        <button
          v-if="!filterStatus && !filterSource"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
          @click="openCreate"
        >{{ t('leads.createFirst') }}</button>
      </div>
      <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-100 dark:border-gray-700 text-left">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colTitle') }}</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colStatus') }}</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden md:table-cell">{{ t('leads.colSource') }}</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden lg:table-cell">{{ t('leads.colValue') }}</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden xl:table-cell">{{ t('leads.colScore') }}</th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden lg:table-cell">{{ t('leads.colCreated') }}</th>
              <th class="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="lead in store.leads"
              :key="lead.id"
              class="border-b border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
              @click.self="goToDetail(lead.id)"
              @contextmenu="onRowContextMenu($event, lead)"
            >
              <td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100 max-w-xs" @click="goToDetail(lead.id)">
                <div class="flex items-center gap-1.5">
                  <span class="truncate">{{ lead.title }}</span>
                  <span v-if="overdueTasks.has(lead.id)" title="Overdue task" class="text-red-500 text-xs flex-shrink-0" aria-label="Overdue task">⚠</span>
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="relative">
                  <button
                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-80"
                    :class="getStatusMeta(lead.status).color"
                    :aria-label="`Status: ${statusLabel(lead.status)}. Click to change.`"
                    @click.stop="statusPopupId = statusPopupId === lead.id ? null : lead.id"
                  >
                    {{ statusLabel(lead.status) }}
                    <span class="text-xs opacity-60" aria-hidden="true">▾</span>
                  </button>
                  <!-- Status popup -->
                  <div
                    v-if="statusPopupId === lead.id"
                    class="absolute z-10 top-8 left-0 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1 min-w-36"
                    role="listbox"
                    :aria-label="`Change status for ${lead.title}`"
                    @click.stop
                  >
                    <button
                      v-for="s in LEAD_STATUSES"
                      :key="s.value"
                      class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2 text-gray-700 dark:text-gray-300"
                      :class="s.value === lead.status ? 'font-semibold' : ''"
                      role="option"
                      :aria-selected="s.value === lead.status"
                      @click="changeStatus(lead.id, s.value)"
                    >
                      <span class="w-2 h-2 rounded-full flex-shrink-0" :class="s.color.split(' ')[0]" aria-hidden="true" />
                      {{ statusLabel(s.value) }}
                    </button>
                  </div>
                </div>
              </td>
              <td class="px-4 py-3 text-gray-500 dark:text-gray-400 hidden md:table-cell" @click="goToDetail(lead.id)">{{ sourceLabel(lead.source) }}</td>
              <td class="px-4 py-3 text-gray-700 dark:text-gray-300 hidden lg:table-cell" @click="goToDetail(lead.id)">{{ fmtValue(lead) }}</td>
              <td class="px-4 py-3 hidden xl:table-cell" @click="goToDetail(lead.id)">
                <LeadScoreBadge :score="(lead as LeadOut & { score?: number }).score" />
              </td>
              <td class="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs hidden lg:table-cell" @click="goToDetail(lead.id)">{{ new Date(lead.created_at).toLocaleDateString() }}</td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('leads.edit')" @click.stop="openEdit(lead)"><PencilSquareIcon class="w-4 h-4" /></button>
                  <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('leads.delete')" @click.stop="confirmDeleteId = lead.id"><TrashIcon class="w-4 h-4" /></button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Pagination -->
        <div class="flex justify-between items-center px-4 py-3 border-t border-gray-100 dark:border-gray-700">
          <span class="text-xs text-gray-400 dark:text-gray-500">{{ t('leads.page', { n: store.page }) }}</span>
          <div class="flex gap-2">
            <button
              v-if="store.page > 1"
              class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
              @click="store.fetchLeads({ status: filterStatus, source: filterSource, page: store.page - 1 })"
            >{{ t('leads.prev') }}</button>
            <button
              v-if="store.hasMore"
              class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
              @click="store.fetchLeads({ status: filterStatus, source: filterSource, page: store.page + 1 })"
            >{{ t('leads.next') }}</button>
          </div>
        </div>
      </div>
    </template>

    <!-- LIST VIEW -->
    <template v-else-if="viewMode === 'list'">
      <div v-if="store.leads.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('leads.noLeadsFound') }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-xs">
          <template v-if="filterStatus || filterSource">{{ t('leads.filterSubtitle') }}</template>
          <template v-else>{{ t('leads.pipelineSubtitle') }}</template>
        </p>
        <button
          v-if="!filterStatus && !filterSource"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
          @click="openCreate"
        >{{ t('leads.createFirst') }}</button>
      </div>
      <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
        <div
          v-for="lead in store.leads"
          :key="lead.id"
          class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
          @click="goToDetail(lead.id)"
          @contextmenu="onRowContextMenu($event, lead)"
        >
          <!-- Status indicator dot -->
          <span class="w-2.5 h-2.5 rounded-full flex-shrink-0" :class="getStatusMeta(lead.status).color.split(' ')[0]" :aria-label="statusLabel(lead.status)" />

          <!-- Title -->
          <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {{ lead.title }}
            <span v-if="overdueTasks.has(lead.id)" class="text-red-500 text-xs ml-1" title="Overdue task" aria-label="Overdue task">⚠</span>
          </span>

          <!-- Status badge -->
          <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium flex-shrink-0" :class="getStatusMeta(lead.status).color">
            {{ statusLabel(lead.status) }}
          </span>

          <!-- Source -->
          <span class="hidden md:block text-xs text-gray-400 dark:text-gray-500 flex-shrink-0 w-20 truncate">{{ sourceLabel(lead.source) }}</span>

          <!-- Value -->
          <span class="hidden lg:block text-xs text-gray-600 dark:text-gray-300 flex-shrink-0 w-24 text-right">{{ fmtValue(lead) }}</span>

          <!-- Score -->
          <span class="hidden xl:block flex-shrink-0"><LeadScoreBadge :score="(lead as LeadOut & { score?: number }).score" /></span>

          <!-- Date -->
          <span class="hidden lg:block text-xs text-gray-400 dark:text-gray-500 flex-shrink-0 w-24 text-right">{{ new Date(lead.created_at).toLocaleDateString() }}</span>

          <!-- Actions -->
          <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" @click.stop>
            <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('leads.edit')" @click="openEdit(lead)"><PencilSquareIcon class="w-4 h-4" /></button>
            <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('leads.delete')" @click="confirmDeleteId = lead.id"><TrashIcon class="w-4 h-4" /></button>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div class="flex justify-between items-center px-4 py-3">
        <span class="text-xs text-gray-400 dark:text-gray-500">{{ t('leads.page', { n: store.page }) }}</span>
        <div class="flex gap-2">
          <button
            v-if="store.page > 1"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            @click="store.fetchLeads({ status: filterStatus, source: filterSource, page: store.page - 1 })"
          >{{ t('leads.prev') }}</button>
          <button
            v-if="store.hasMore"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            @click="store.fetchLeads({ status: filterStatus, source: filterSource, page: store.page + 1 })"
          >{{ t('leads.next') }}</button>
        </div>
      </div>
    </template>

    <!-- KANBAN VIEW -->
    <template v-else-if="viewMode === 'kanban'">
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
            {{ statusLabel(s.value) }}
            <span class="ml-auto bg-white/60 dark:bg-black/30 rounded px-1.5 py-0.5">{{ leadsByStatus[s.value]?.length ?? 0 }}</span>
          </div>
          <!-- Cards -->
          <div
            class="flex-1 space-y-2 min-h-16 rounded-xl transition-colors p-1"
            :class="dragOverStatus === s.value ? 'bg-red-50 dark:bg-red-900/20' : 'bg-gray-50 dark:bg-gray-700/30'"
          >
            <div
              v-for="lead in leadsByStatus[s.value]"
              :key="lead.id"
              class="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 cursor-grab shadow-sm hover:shadow transition-shadow group"
              draggable="true"
              @dragstart="onDragStart(lead)"
              @contextmenu="onRowContextMenu($event, lead)"
            >
              <div class="flex items-start justify-between gap-2">
                <button
                  class="text-xs font-medium text-gray-900 dark:text-gray-100 text-left hover:text-red-600 transition-colors leading-snug"
                  @click="goToDetail(lead.id)"
                >{{ lead.title }}</button>
                <div class="flex gap-0.5 opacity-0 group-hover:opacity-100">
                  <button class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400" :aria-label="t('leads.edit')" @click.stop="openEdit(lead)"><PencilSquareIcon class="w-3.5 h-3.5" /></button>
                </div>
              </div>
              <div class="flex items-center gap-2 mt-2 flex-wrap">
                <span v-if="fmtValue(lead)" class="text-xs text-gray-500 dark:text-gray-400">{{ fmtValue(lead) }}</span>
                <LeadScoreBadge :score="(lead as LeadOut & { score?: number }).score" />
                <span v-if="overdueTasks.has(lead.id)" class="text-xs text-red-500" :title="t('leads.overdueLabel')">{{ t('leads.overdueLabel') }}</span>
              </div>
            </div>
            <div v-if="(leadsByStatus[s.value]?.length ?? 0) === 0" class="text-center text-xs text-gray-300 dark:text-gray-600 py-4">{{ t('leads.dropHere') }}</div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- Context menu -->
  <ContextMenu ref="contextMenuRef" :items="LEAD_CONTEXT_ITEMS" @action="onContextAction" />

  <!-- Save view dialog -->
  <Teleport to="body">
    <div v-if="showSaveViewDialog" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showSaveViewDialog = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6" role="dialog" aria-modal="true" aria-label="Save view">
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('leads.saveCurrentView') }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.viewName') }}</label>
            <input
              v-model="saveViewName"
              type="text"
              :placeholder="t('leads.viewNamePlaceholder')"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>
          <p class="text-xs text-gray-500 dark:text-gray-400">
            Saves: status={{ filterStatus || 'any' }}, source={{ filterSource || 'any' }}
          </p>
        </div>
        <div class="flex gap-3 pt-4">
          <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showSaveViewDialog = false">{{ t('leads.cancel') }}</button>
          <button type="button" :disabled="savingView || !saveViewName.trim()" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60" @click="saveCurrentView">
            {{ savingView ? t('leads.saving') : t('leads.saveViewBtn') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Create/Edit Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" :aria-label="editingLead ? t('leads.editTitle') : t('leads.newTitle')">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ editingLead ? t('leads.editTitle') : t('leads.newTitle') }}</h3>
        <div v-if="formError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ formError }}</div>
        <form class="space-y-3" @submit.prevent="submitForm">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.titleField') }}</label>
            <input v-model="formTitle" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <!-- Customer search/create -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.customerField') }}</label>
            <div class="relative">
              <div class="flex gap-1">
                <input
                  v-model="formCustomerQuery"
                  type="text"
                  :placeholder="t('leads.customerSearchPlaceholder')"
                  autocomplete="off"
                  class="flex-1 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  @input="onCustomerQueryInput"
                  @focus="if (formCustomerQuery && !formCustomerId) { showCustomerDropdown = true; searchCustomers(formCustomerQuery) }"
                />
                <button
                  v-if="formCustomerId"
                  type="button"
                  class="px-2 text-gray-400 hover:text-red-500"
                  title="Clear customer"
                  @click="clearCustomer"
                ><XMarkIcon class="w-4 h-4" /></button>
              </div>
              <!-- Suggestions dropdown -->
              <div
                v-if="showCustomerDropdown && (customerSuggestions.length > 0 || customerSearchLoading)"
                class="absolute z-20 top-full mt-1 w-full bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1 max-h-48 overflow-y-auto"
              >
                <div v-if="customerSearchLoading" class="px-3 py-2 text-xs text-gray-400">{{ t('leads.searching') }}</div>
                <button
                  v-for="c in customerSuggestions"
                  :key="c.id"
                  type="button"
                  class="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                  @click="selectCustomer(c)"
                >
                  <span class="font-medium">{{ [c.first_name, c.last_name].filter(Boolean).join(' ') }}</span>
                  <span v-if="c.email" class="text-xs text-gray-400 ml-2">{{ c.email }}</span>
                  <span v-if="c.phone" class="text-xs text-gray-400 ml-2">{{ c.phone }}</span>
                </button>
              </div>
              <!-- Create new customer link -->
              <div v-if="showCustomerDropdown && !customerSearchLoading && customerSuggestions.length === 0 && formCustomerQuery.trim()" class="absolute z-20 top-full mt-1 w-full bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1">
                <button type="button" class="w-full text-left px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30" @click="openNewCustomerInline">
                  + Create new customer "{{ formCustomerQuery }}"
                </button>
              </div>
            </div>
            <!-- Inline new customer form -->
            <div v-if="showNewCustomerForm" class="mt-2 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-600 space-y-2">
              <p class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('leads.newCustomerLabel') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="newCustomerFirstName" type="text" placeholder="First name *" class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
                <input v-model="newCustomerLastName" type="text" placeholder="Last name" class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              </div>
              <input v-model="newCustomerEmail" type="email" placeholder="Email" class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              <input v-model="newCustomerPhone" type="tel" placeholder="Phone" class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              <div class="flex gap-2">
                <button type="button" class="text-xs text-gray-500 hover:text-gray-700" @click="showNewCustomerForm = false">{{ t('leads.cancel') }}</button>
                <button type="button" class="text-xs text-white bg-red-600 px-3 py-1 rounded-lg hover:bg-red-700" @click="createAndSelectCustomer">{{ t('leads.createAndSelect') }}</button>
              </div>
            </div>
          </div>

          <!-- Company & Contact Person Selection -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Společnost</label>
              <select
                v-model="formCompanyId"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                @change="onCompanyChange"
              >
                <option :value="null">-- Žádná společnost --</option>
                <option v-for="c in companies" :key="c.id" :value="c.id">
                  {{ c.company_name || [c.first_name, c.last_name].filter(Boolean).join(' ') }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Kontaktní osoba</label>
              <select
                v-model="formContactPersonId"
                :disabled="!formCompanyId"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 disabled:opacity-50"
              >
                <option :value="null">-- Žádná kontaktní osoba --</option>
                <option v-for="cp in contactPersons" :key="cp.id" :value="cp.id">
                  {{ [cp.first_name, cp.last_name].filter(Boolean).join(' ') }}
                </option>
              </select>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.statusField') }}</label>
              <select v-model="formStatus" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option v-for="s in LEAD_STATUSES" :key="s.value" :value="s.value">{{ statusLabel(s.value) }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.sourceField') }}</label>
              <select v-model="formSource" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option value="web">{{ t('leads.sourceWeb') }}</option>
                <option value="email">{{ t('leads.sourceEmail') }}</option>
                <option value="referral">{{ t('leads.sourceReferral') }}</option>
                <option value="cold_call">{{ t('leads.sourceColdCall') }}</option>
                <option value="social">{{ t('leads.sourceSocial') }}</option>
                <option value="other">{{ t('leads.sourceOther') }}</option>
              </select>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.valueField') }}</label>
              <input v-model="formValue" type="number" min="0" step="0.01" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="0" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.currencyField') }}</label>
              <input v-model="formCurrency" type="text" maxlength="3" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="CZK" />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showModal = false">{{ t('leads.cancel') }}</button>
            <button type="submit" :disabled="formLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ formLoading ? t('leads.saving') : (editingLead ? t('leads.save') : t('leads.create')) }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Delete confirm -->
  <Teleport to="body">
    <div v-if="confirmDeleteId" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="confirmDeleteId = null">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center" role="dialog" aria-modal="true" aria-label="Delete lead confirmation">
        <div class="flex justify-center mb-3" aria-hidden="true"><TrashIcon class="w-10 h-10 text-red-400" /></div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">{{ t('leads.deleteTitle') }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">{{ t('leads.deleteText') }}</p>
        <div class="flex gap-3">
          <button class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-700 dark:text-gray-300" @click="confirmDeleteId = null">{{ t('leads.cancel') }}</button>
          <button class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700" @click="confirmDelete(confirmDeleteId!)">{{ t('leads.delete') }}</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Global status popup backdrop -->
  <div v-if="statusPopupId" class="fixed inset-0 z-5" @click="statusPopupId = null" />
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import EntitySidebarActionPicker from '@/components/EntitySidebarActionPicker.vue'
import StreamlineCreateModal from '@/components/StreamlineCreateModal.vue'
import { type DocumentOut, docFileIcon, fmtDocBytes } from '@/types/documents'
import { useAuthStore } from '@/stores/auth'
import StreamlineFilterDropdown from '@/components/StreamlineFilterDropdown.vue'
import { XMarkIcon, BuildingOfficeIcon, UserIcon, LinkIcon } from '@heroicons/vue/24/outline'
import { useClipboard } from '@/composables/useClipboard'
import { ConfirmDeleteModal } from '@/components/ui'
import { useMoney } from '@/composables/useMoney'

const route = useRoute()
const router = useRouter()
const store = useCustomersStore()
const toast = useToast()
const authStore = useAuthStore()
const { t } = useI18n()
const { copiedId: permalinkCopiedId, copyToClipboard } = useClipboard()
const { formatAmount, formatAmountPlain } = useMoney()
const currentPageUrl = computed(() => window.location.href)

const customerId = computed(() => route.params.id as string)

const selectedShortcutId = ref('overview')
const customFilters = ref<Set<string>>(new Set())
const newShortcutName = ref('')
const allTools = ref<any[]>([])

interface ShortcutPreset {
  id: string
  name: string
  visible_activity_types: string[]
}
const shortcuts = ref<ShortcutPreset[]>([])

const shortcutsKey = computed(() => {
  const userId = authStore.user?.id || 'guest'
  return `customer_shortcuts_u${userId}`
})

function loadShortcuts() {
  const data = localStorage.getItem(shortcutsKey.value)
  if (data) {
    try {
      shortcuts.value = JSON.parse(data)
    } catch {
      shortcuts.value = []
    }
  } else {
    // default shortcuts
    shortcuts.value = [
      { id: 'sc-tasks', name: 'Úkoly', visible_activity_types: ['task', 'task_assigned', 'task_completed', 'task_created', 'task_reopened'] },
      { id: 'sc-files', name: 'Soubory', visible_activity_types: ['file_upload'] },
      { id: 'sc-proposals', name: 'Proposals', visible_activity_types: ['proposal_created', 'proposal_accepted', 'proposal_rejected'] }
    ]
  }
}

function saveShortcutsToLocalStorage() {
  localStorage.setItem(shortcutsKey.value, JSON.stringify(shortcuts.value))
}

function moveShortcut(fromIdx: number, toIdx: number) {
  const arr = [...shortcuts.value]
  const item = arr[fromIdx]
  if (!item) return
  arr.splice(fromIdx, 1)
  arr.splice(toIdx, 0, item)
  shortcuts.value = arr
  saveShortcutsToLocalStorage()
}


function deleteShortcut(id: string) {
  shortcuts.value = shortcuts.value.filter(s => s.id !== id)
  saveShortcutsToLocalStorage()
  if (selectedShortcutId.value === id) {
    selectedShortcutId.value = 'overview'
  }
}

async function loadTools() {
  const res = await api.get<any[]>('/api/v1/streamline/tools')
  if (res.ok) {
    allTools.value = res.data
  }
}

const availableTools = computed(() => {
  const t = [...allTools.value]
  if (!t.some((x) => x.activity_type === 'task')) {
    t.push({
      activity_type: 'task',
      label: 'Úkoly',
      category: 'task',
      default_visibility: 'important',
    })
  }
  return t
})

const importantToolsSet = computed(() => {
  return new Set(availableTools.value.filter((t: any) => t.default_visibility === 'important').map((t: any) => t.activity_type))
})

const currentVisibleTypes = computed(() => {
  if (selectedShortcutId.value === 'overview') {
    return importantToolsSet.value
  }
  if (selectedShortcutId.value === 'custom') {
    return customFilters.value
  }
  const preset = shortcuts.value.find(s => s.id === selectedShortcutId.value)
  if (preset) {
    return new Set(preset.visible_activity_types)
  }
  return importantToolsSet.value
})

function onCustomFilterChange(next: string[] | null) {
  if (next === null) {
    customFilters.value = importantToolsSet.value
  } else {
    customFilters.value = new Set(next)
  }
  selectedShortcutId.value = 'custom'
}

function saveCurrentAsShortcut() {
  const name = newShortcutName.value.trim()
  if (!name) return
  const id = `sc-${Date.now()}`
  shortcuts.value.push({
    id,
    name,
    visible_activity_types: Array.from(customFilters.value),
  })
  saveShortcutsToLocalStorage()
  selectedShortcutId.value = id
  newShortcutName.value = ''
}


// ActivityTimeline ref (used to reload feed after sidebar quick-action submits).
const activityTimelineRef = ref<InstanceType<typeof ActivityTimeline> | null>(null)

// Streamline Create Modal state (opened from sidebar picker tool-selected event).
const activeModalTool = ref('')

function openModalTool(type: string) {
  activeModalTool.value = type
}

function closeModalTool() {
  activeModalTool.value = ''
}
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

// Linked records
interface RecordOut { id: string; title: string; status: string; value: number | null; currency: string; created_at: string }
const linkedRecords = ref<RecordOut[]>([])
const leadsLoading = ref(false)

// Linked proposals
interface ProposalOut { id: string; title: string; status: string; total_value: string; currency: string; created_at: string }
const linkedProposals = ref<ProposalOut[]>([])
const proposalsLoading = ref(false)

const showEditModal = ref(false)

function openEdit() {
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
  showEditModal.value = true
}

function cancelEdit() {
  showEditModal.value = false
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
    showEditModal.value = false
    toast.success(t('customers.updated'))
  } else {
    editError.value = result.error ?? t('customers.failedToUpdate')
  }
}

async function deleteCustomer() {
  deleteCustomerLoading.value = true
  try {
    const result = await store.deleteCustomer(customerId.value)
    if (result.ok) {
      toast.success(t('customers.deleted'))
      router.push('/app/directory')
    } else {
      toast.error(t('customers.failedToDelete'))
    }
  } finally {
    deleteCustomerLoading.value = false
    showDeleteCustomerModal.value = false
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
    const allRecords = await api.get<Array<RecordOut & { customer_id: string | null }>>('/api/v1/crm/opportunities?page_size=100')
    if (allRecords.ok) {
      linkedRecords.value = allRecords.data.filter((l) => l.customer_id === customerId.value)
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

// ---------------------------------------------------------------------------
// Linked tasks (tasks tab)
// ---------------------------------------------------------------------------
interface TaskOut {
  id: string
  title: string
  is_completed: boolean
  status: string
  priority: string
  due_date: string | null
  assigned_to_id: string | null
  assigned_to_name?: string | null
}
const linkedTasks = ref<TaskOut[]>([])
const tasksLoading = ref(false)

async function loadLinkedTasks() {
  tasksLoading.value = true
  try {
    const res = await api.get<TaskOut[]>(`/api/v1/crm/tasks?customer_id=${customerId.value}&page_size=100`)
    if (res.ok) linkedTasks.value = res.data
  } finally {
    tasksLoading.value = false
  }
}

function taskStatusColor(status: string) {
  const map: Record<string, string> = {
    todo: 'bg-gray-100 text-gray-700', in_progress: 'bg-blue-100 text-blue-700',
    blocked: 'bg-red-100 text-red-700', done: 'bg-green-100 text-green-700',
  }
  return map[status] ?? 'bg-gray-100 text-gray-700'
}

// ---------------------------------------------------------------------------
// Documents (files tab)
// ---------------------------------------------------------------------------
const documents = ref<DocumentOut[]>([])
const docsLoading = ref(false)
const docsUploading = ref(false)
const docFileInputRef = ref<HTMLInputElement | null>(null)
const deleteDocId = ref<string | null>(null)
const showDeleteCustomerModal = ref(false)
const deleteCustomerLoading = ref(false)

async function loadDocuments() {
  docsLoading.value = true
  try {
    const res = await api.get<DocumentOut[]>(`/api/v1/erp/documents?customer_id=${customerId.value}`)
    if (res.ok) documents.value = res.data
  } finally {
    docsLoading.value = false
  }
}

async function onDocFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  docsUploading.value = true
  for (const file of Array.from(input.files)) {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', file.name)
    fd.append('customer_id', customerId.value)
    const res = await api.postForm<DocumentOut>('/api/v1/erp/documents', fd)
    if (res.ok) documents.value.unshift(res.data)
    else toast.error(t('customers.failedToUpload'))
  }
  docsUploading.value = false
  input.value = ''
}

async function deleteDocument() {
  const id = deleteDocId.value
  if (!id) return
  deleteDocId.value = null
  const res = await api.delete(`/api/v1/erp/documents/${id}`)
  if (res.ok) documents.value = documents.value.filter(d => d.id !== id)
}



onMounted(async () => {
  loadShortcuts()
  await loadTools()
  await store.fetchCustomers({ page: 1 })
  await store.fetchCustomer(customerId.value)
  await loadLinkedLeads()
  await loadLinkedProposals()
  await loadEmployees()
})
</script>
<template>
  <div class="p-6">
    <!-- Back -->
    <RouterLink to="/app/directory" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4">
      ← {{ t('customers.title') }}
    </RouterLink>

    <!-- Loading skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-64" />
      <div class="h-24 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="store.currentCustomer">
      <!-- Title -->
      <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-6 flex items-center gap-2 min-w-0">
        <component :is="store.currentCustomer.type === 'company' ? BuildingOfficeIcon : UserIcon" class="w-6 h-6 text-gray-500 flex-shrink-0" />
        <span class="truncate">{{ [store.currentCustomer.first_name, store.currentCustomer.last_name].filter(Boolean).join(' ') }}</span>
        <button
          class="ml-1 flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors relative group/permalink"
          :title="permalinkCopiedId === 'page' ? 'Zkopírováno!' : 'Kopírovat odkaz'"
          @click="copyToClipboard(currentPageUrl, 'page')"
        >
          <LinkIcon class="w-4 h-4" />
          <span
            v-if="permalinkCopiedId === 'page'"
            class="absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-gray-900 dark:bg-gray-700 px-2 py-0.5 text-[10px] text-white pointer-events-none"
          >Zkopírováno!</span>
        </button>
      </h1>

      <!-- 2-column layout from the start -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Left Column: Activity Feed & Presets Switcher -->
        <div class="lg:col-span-2">
          <!-- Switchers: Přehled + user presets + Filtry -->
          <div class="flex flex-wrap items-center gap-1.5 bg-gray-100 dark:bg-gray-800 rounded-xl p-1 mb-4">
            <button
              class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
              :class="selectedShortcutId === 'overview' ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
              @click="selectedShortcutId = 'overview'"
            >
              Přehled
            </button>

            <!-- User defined shortcuts -->
            <button
              v-for="shortcut in shortcuts"
              :key="shortcut.id"
              class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
              :class="selectedShortcutId === shortcut.id ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
              @click="selectedShortcutId = shortcut.id"
            >
              {{ shortcut.name }}
            </button>

            <!-- Filtry button -->
            <div class="relative flex items-center h-full">
              <StreamlineFilterDropdown
                :tools="availableTools"
                :model-value="currentVisibleTypes"
                :is-customised="selectedShortcutId === 'custom'"
                :shortcuts="shortcuts"
                @update:visible="onCustomFilterChange"
                @delete-shortcut="deleteShortcut"
                @move-shortcut="(payload) => moveShortcut(payload.fromIdx, payload.toIdx)"
              />
            </div>
          </div>

          <!-- Quick action to save custom filter as shortcut if it's selected -->
          <div v-if="selectedShortcutId === 'custom'" class="flex items-center gap-2 mb-4 bg-gray-50 dark:bg-gray-800/50 p-2 rounded-xl border border-gray-100 dark:border-gray-700 w-fit">
            <span class="text-xs text-gray-500 dark:text-gray-400">Nové zobrazení:</span>
            <input
              v-model="newShortcutName"
              type="text"
              placeholder="Název zkratky..."
              class="text-xs rounded-xl border border-gray-300 dark:border-gray-600 px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
            />
            <button
              class="text-xs px-3 py-1.5 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50"
              :disabled="!newShortcutName.trim()"
              @click="saveCurrentAsShortcut"
            >
              Uložit jako zkratku
            </button>
          </div>

          <!-- Activity feed -->
          <ActivityTimeline
            ref="activityTimelineRef"
            :hide-composer="true"
            entity-type="customer"
            :entity-id="customerId"
            :hide-filter-dropdown="true"
            :override-visible-types="currentVisibleTypes"
          />
        </div>


        <!-- Right Column: Sidebar -->
        <div class="space-y-4">
          <!-- Contact Details Card -->
          <div class="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl p-4 shadow-sm">
            <h2 class="text-base font-bold text-gray-900 dark:text-gray-100 mb-3 leading-tight">
              {{ [store.currentCustomer.first_name, store.currentCustomer.last_name].filter(Boolean).join(' ') }}
            </h2>
            <dl class="space-y-2">
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('customers.email') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[12rem] text-right">
                  <a v-if="store.currentCustomer.email" :href="`mailto:${store.currentCustomer.email}`" class="text-red-600 hover:underline dark:text-red-400">
                    {{ store.currentCustomer.email }}
                  </a>
                  <span v-else class="text-gray-400 dark:text-gray-600 italic">—</span>
                </dd>
              </div>

              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('customers.phone') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[12rem] text-right">
                  <a v-if="store.currentCustomer.phone" :href="`tel:${store.currentCustomer.phone}`" class="text-red-600 hover:underline dark:text-red-400">
                    {{ store.currentCustomer.phone }}
                  </a>
                  <span v-else class="text-gray-400 dark:text-gray-600 italic">—</span>
                </dd>
              </div>

              <div v-if="store.currentCustomer.company_name || store.currentCustomer.company_id" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('customers.company') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[12rem] text-right">
                  <span v-if="store.currentCustomer.company_name">{{ store.currentCustomer.company_name }}</span>
                  <RouterLink
                    v-if="store.currentCustomer.company_id"
                    :to="`/app/directory/${store.currentCustomer.company_id}`"
                    class="text-red-600 hover:underline dark:text-red-400 block"
                  >
                    <BuildingOfficeIcon class="w-4 h-4 inline-block mr-1 align-text-bottom" />{{ availableCompanies.find(c => c.id === store.currentCustomer!.company_id)?.first_name ?? t('customers.viewCompany') }}
                  </RouterLink>
                </dd>
              </div>

              <div v-if="store.currentCustomer.website" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('customers.website') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[12rem] text-right">
                  <a :href="store.currentCustomer.website" target="_blank" rel="noopener" class="text-red-600 hover:underline dark:text-red-400">
                    {{ store.currentCustomer.website }}
                  </a>
                </dd>
              </div>

              <div v-if="store.currentCustomer.ico" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">IČO</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[12rem] text-right">{{ store.currentCustomer.ico }}</dd>
              </div>

              <div v-if="store.currentCustomer.dic" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">DIČ</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate max-w-[12rem] text-right">{{ store.currentCustomer.dic }}</dd>
              </div>

              <div v-if="store.currentCustomer.address_street || store.currentCustomer.address_city" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">Adresa</dt>
                <dd class="text-xs text-gray-700 dark:text-gray-300 text-right max-w-[12rem] truncate">
                  {{ [store.currentCustomer.address_street, store.currentCustomer.address_zip, store.currentCustomer.address_city, store.currentCustomer.address_country].filter(Boolean).join(', ') }}
                </dd>
              </div>
            </dl>
            <div class="flex gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
              <button class="flex-1 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="openEdit">{{ t('customers.edit') }}</button>
              <button class="px-3 py-1.5 rounded-xl border border-red-200 dark:border-red-800 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30" @click="showDeleteCustomerModal = true">{{ t('customers.delete') }}</button>
            </div>
          </div>

          <!-- Quick actions card -->
          <EntitySidebarActionPicker
            entity-type="customer"
            :entity-id="customerId"
            @tool-selected="openModalTool"
          />

          <!-- Employees card (for companies) -->
          <div v-if="store.currentCustomer.type === 'company'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 shadow-sm">
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
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 shadow-sm">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.tagsSection') }}</h3>
            <div class="flex flex-wrap gap-2 mb-3">
              <span
                v-for="tag in store.currentCustomer.tags"
                :key="tag"
                class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-sm text-gray-700 dark:text-gray-300"
              >
                {{ tag }}
                <button class="text-gray-400 hover:text-red-500 ml-1" :disabled="tagsLoading" @click="removeTag(tag)"><XMarkIcon class="w-3.5 h-3.5" /></button>
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

          <!-- Metadata / Custom Fields -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 shadow-sm">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.customFields') }}</h3>
            <div v-if="Object.keys(store.currentCustomer.metadata).length > 0" class="divide-y divide-gray-50 dark:divide-gray-700 mb-3">
              <div v-for="(val, key) in store.currentCustomer.metadata" :key="key" class="flex items-center gap-3 py-2 group">
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300 w-32 flex-shrink-0 truncate">{{ key }}</span>
                <span class="text-sm text-gray-500 dark:text-gray-400 flex-1 truncate">{{ val }}</span>
                <button class="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700" :disabled="metaLoading" @click="removeMetadata(key)"><XMarkIcon class="w-3.5 h-3.5" /></button>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400 dark:text-gray-500 mb-3">{{ t('customers.noCustomFields') }}</div>
            <div class="flex gap-2 flex-wrap">
              <input v-model="newMetaKey" type="text" :placeholder="t('customers.metaKeyPlaceholder')" class="w-36 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              <input v-model="newMetaValue" type="text" :placeholder="t('customers.metaValuePlaceholder')" class="flex-1 min-w-36 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              <button :disabled="metaLoading || !newMetaKey.trim()" class="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50" @click="addMetadata">{{ t('customers.add') }}</button>
            </div>
          </div>

          <!-- Linked Records -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 shadow-sm">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('customers.linkedLeads') }}</h3>
            <div v-if="leadsLoading" class="animate-pulse space-y-2">
              <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
            </div>
            <div v-else-if="linkedRecords.length === 0" class="text-sm text-gray-400 dark:text-gray-500">{{ t('customers.noLinkedLeads') }}</div>
            <div v-else class="space-y-2">
              <RouterLink
                v-for="record in linkedRecords"
                :key="record.id"
                :to="`/app/opportunities/${record.id}`"
                class="flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
              >
                <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ record.title }}</span>
                <span class="text-xs px-2 py-0.5 rounded-full font-medium" :class="statusColor(record.status)">{{ record.status }}</span>
                <span v-if="record.value != null" class="text-xs text-gray-500 dark:text-gray-400">{{ formatAmount(record.value, record.currency) }}</span>
              </RouterLink>
            </div>
          </div>

          <!-- Linked Proposals -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 shadow-sm">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('proposals.title') }}</h3>
              <RouterLink
                :to="`/app/proposals`"
                class="text-xs text-red-600 hover:text-red-700 font-medium"
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
                <span class="text-xs text-gray-500 dark:text-gray-400 font-mono">{{ formatAmountPlain(Number(p.total_value)) }}</span>
              </RouterLink>
            </div>
          </div>

        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400 dark:text-gray-500">{{ t('customers.notFound') }}</div>


    <!-- Edit Modal Teleport exactly like Lead Detail -->
    <Teleport to="body">
      <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showEditModal = false">
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" aria-labelledby="edit-customer-title">
          <h3 id="edit-customer-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('customers.editTitle') }}</h3>
          <div v-if="editError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ editError }}</div>
          <form class="space-y-3" @submit.prevent="saveEdit">
            <div class="grid grid-cols-2 gap-2">
              <div :class="store.currentCustomer!.type === 'company' ? 'col-span-2' : ''">
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {{ store.currentCustomer!.type === 'company' ? t('customers.companyNameLabel') : t('customers.firstName') }}
                </label>
                <input v-model="editFirstName" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
              <div v-if="store.currentCustomer!.type === 'person'">
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.lastName') }}</label>
                <input v-model="editLastName" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.email') }}</label>
                <input v-model="editEmail" type="email" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.phone') }}</label>
                <input v-model="editPhone" type="tel" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
            </div>

            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.company') }}</label>
              <input v-model="editCompany" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
            </div>

            <div v-if="store.currentCustomer!.type === 'person'">
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.employerCompany') }}</label>
              <select v-model="editCompanyId" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400">
                <option value="">— {{ t('customers.noCompany') }} —</option>
                <option v-for="comp in availableCompanies" :key="comp.id" :value="comp.id">{{ comp.first_name }}</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.website') }}</label>
              <input v-model="editWebsite" type="url" placeholder="https://" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
            </div>

            <div v-if="store.currentCustomer!.type === 'company'" class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.ico') }}</label>
                <input v-model="editIco" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.dic') }}</label>
                <input v-model="editDic" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
            </div>

            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressStreet') }}</label>
              <input v-model="editAddressStreet" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressCity') }}</label>
                <input v-model="editAddressCity" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressZip') }}</label>
                <input v-model="editAddressZip" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
              </div>
            </div>

            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('customers.addressCountry') }}</label>
              <input v-model="editAddressCountry" type="text" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" />
            </div>

            <div class="flex justify-end gap-2 pt-4 border-t border-gray-100 dark:border-gray-700 mt-4">
              <button type="button" class="px-4 py-2 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-700 dark:text-gray-300" @click="cancelEdit">{{ t('customers.cancel') }}</button>
              <button type="submit" :disabled="editLoading" class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-sm font-medium disabled:opacity-50">
                {{ editLoading ? t('customers.saving') : t('customers.save') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>

  <ConfirmDeleteModal
    :open="showDeleteCustomerModal"
    :title="t('customers.deleteTitle')"
    :message="t('customers.deleteText')"
    :loading="deleteCustomerLoading"
    @confirm="deleteCustomer"
    @cancel="showDeleteCustomerModal = false"
  />

  <!-- Streamline Create Modal — opened from sidebar picker -->
  <StreamlineCreateModal
    :model-value="!!activeModalTool"
    :action-type="activeModalTool"
    entity-type="customer"
    :entity-id="customerId"
    @update:model-value="(v) => { if (!v) closeModalTool() }"
    @activity-added="activityTimelineRef?.load()"
  />
</template>

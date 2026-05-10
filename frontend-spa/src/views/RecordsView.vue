<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useRecordsStore,
  RECORD_STATUSES,
  getStatusMeta,
  normalizeStageChangeIssues,
  type RecordOut,
  type StageChangeEvaluationOut,
  type StageChangeIssueWithSource,
} from '@/stores/records'
import { usePipelineStore, type StageOut } from '@/stores/pipeline'
import { useSavedViewsStore } from '@/stores/savedViews'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useToast } from '@/composables/useToast'
import { useMoney } from '@/composables/useMoney'
import { api } from '@/api'
import ContextMenu, { type ContextMenuItem } from '@/components/ContextMenu.vue'
import Dropdown from '@/components/ui/Dropdown.vue'
import { ConfirmDeleteModal } from '@/components/ui'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import RecordScoreBadge from '@/components/RecordScoreBadge.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { useI18n } from '@/composables/useI18n'
import { useListView, type ColumnDef } from '@/composables/useListView'
import CurrencySelect from '@/components/CurrencySelect.vue'
import { TrashIcon, PencilSquareIcon, XMarkIcon, ArrowTopRightOnSquareIcon, ArrowsRightLeftIcon, Bars3Icon, Squares2X2Icon, ListBulletIcon, BookmarkIcon, ChevronDownIcon, FunnelIcon, AdjustmentsHorizontalIcon, BuildingOfficeIcon, UserIcon, MagnifyingGlassIcon, ShareIcon } from '@heroicons/vue/24/outline'
import Avatar from '@/components/ui/Avatar.vue'
import RecordShareModal from '@/components/RecordShareModal.vue'
import PeoplePicker from '@/components/PeoplePicker.vue'
import { usePermissionsStore } from '@/stores/permissions'

const route = useRoute()
const router = useRouter()
const store = useRecordsStore()
const pipelineStore = usePipelineStore()
const savedViewsStore = useSavedViewsStore()
const customersStore = useCustomersStore()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const toast = useToast()
const { t } = useI18n()
const { firmCurrency, formatAmount } = useMoney()

type ViewMode = 'table' | 'kanban' | 'list'

const VIEW_MODES = ['table', 'kanban', 'list'] as const

const viewModeIcons: Record<ViewMode, object> = {
  table: Bars3Icon,
  kanban: Squares2X2Icon,
  list: ListBulletIcon,
}

const viewMode = ref<ViewMode>('list')

watch(() => authStore.user?.id, (userId) => {
  if (!userId) return
  try {
    const stored = localStorage.getItem(`leadlab_records_displaymode_u${userId}`)
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
    localStorage.setItem(`leadlab_records_displaymode_u${userId}`, mode)
  } catch {
    // ignore
  }
})

// ---------------------------------------------------------------------------
// Team members (for filter dropdowns)
// ---------------------------------------------------------------------------
interface Member {
  id: string
  user_id: string
  user_email: string
  user_full_name: string
  role: string
}
const members = ref<Member[]>([])
async function loadMembers() {
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (!firmId) return
  const res = await api.get<Member[]>(`/api/v1/firms/${firmId}/members`)
  if (res.ok) members.value = res.data
}
function memberLabel(m: Member) {
  return m.user_full_name?.trim() || m.user_email
}

// ---------------------------------------------------------------------------
// Sort + Column visibility (via useListView composable)
// ---------------------------------------------------------------------------
type SortField = 'title' | 'status' | 'source' | 'value' | 'created_at' | 'updated_at'
type ColumnId = 'status' | 'source' | 'value' | 'score' | 'created_at' | 'updated_at' | 'users' | 'company' | 'contact_person'

const TABLE_COLUMNS: ColumnDef<ColumnId>[] = [
  { id: 'status', labelKey: 'colStatus', defaultVisible: true },
  { id: 'source', labelKey: 'colSource', defaultVisible: true },
  { id: 'value', labelKey: 'colValue', defaultVisible: true },
  { id: 'score', labelKey: 'colScore', defaultVisible: false },
  { id: 'created_at', labelKey: 'colCreated', defaultVisible: true },
  { id: 'updated_at', labelKey: 'colUpdated', defaultVisible: true },
  { id: 'company', labelKey: 'colCompany', defaultVisible: true },
  { id: 'contact_person', labelKey: 'colContactPerson', defaultVisible: true },
  { id: 'users', labelKey: 'colUsers', defaultVisible: true },
]

const {
  sortField, sortDir, setSort, sortIcon,
  DEFAULT_SORT_FIELD, DEFAULT_SORT_DIR,
  visibleColumns, columnPickerOpen, isColVisible, toggleColumn, resetColumns,
} = useListView<SortField, ColumnId>(
  { storageKeyPrefix: 'leadlab_records', columns: TABLE_COLUMNS, defaultSortField: 'created_at', defaultSortDir: 'desc' },
  computed(() => authStore.user?.id?.toString()),
)

const STATUS_ORDER: Record<string, number> = {
  new: 1, contacted: 2, proposal: 3, negotiation: 4, won: 5, lost: 6, canceled: 7,
}

const sortedRecords = computed(() => {
  return [...store.records].sort((a, b) => {
    let cmp = 0
    if (sortField.value === 'value') {
      // Null values sort to the end regardless of direction
      const av = a.value ?? null
      const bv = b.value ?? null
      if (av === null && bv === null) cmp = 0
      else if (av === null) cmp = 1
      else if (bv === null) cmp = -1
      else cmp = av - bv
    } else if (sortField.value === 'status') {
      cmp = (STATUS_ORDER[a.status] ?? 0) - (STATUS_ORDER[b.status] ?? 0)
    } else if (sortField.value === 'created_at') {
      cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    } else if (sortField.value === 'updated_at') {
      cmp = new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime()
    } else {
      const va = (a[sortField.value] ?? '') as string
      const vb = (b[sortField.value] ?? '') as string
      cmp = va.localeCompare(vb)
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

// ---------------------------------------------------------------------------
// Advanced filters
// ---------------------------------------------------------------------------
const filterStatus = ref((route.query.status as string) ?? '')
const filterSource = ref('')
const filterAssignedTo = ref('')
const filterCreatedBy = ref('')
const filterValueMin = ref('')
const filterValueMax = ref('')
const filterCreatedAfter = ref('')
const filterCreatedBefore = ref('')
const filterUpdatedAfter = ref('')
const filterUpdatedBefore = ref('')
const filterCategoryId = ref((route.query.category_id as string) ?? '')
const filterStageId = ref((route.query.stage_id as string) ?? '')
const filterCompanyId = ref('')
const filterCompanyName = ref('')
const filterContactPersonId = ref('')
const showAdvancedFilters = ref(false)

function hasActiveAdvancedFilters() {
  return !!(filterStatus.value || filterSource.value ||
            filterAssignedTo.value || filterCreatedBy.value || filterValueMin.value ||
            filterValueMax.value || filterCreatedAfter.value || filterCreatedBefore.value ||
            filterUpdatedAfter.value || filterUpdatedBefore.value ||
            filterStageId.value || filterCompanyId.value || filterCompanyName.value || filterContactPersonId.value)
}

function buildFilters(page = 1) {
  const valueMin = filterValueMin.value ? parseFloat(filterValueMin.value) : undefined
  const valueMax = filterValueMax.value ? parseFloat(filterValueMax.value) : undefined
  return {
    status: filterStatus.value,
    source: filterSource.value,
    assigned_to: filterAssignedTo.value || undefined,
    created_by: filterCreatedBy.value || undefined,
    value_min: valueMin != null && !isNaN(valueMin) ? valueMin : undefined,
    value_max: valueMax != null && !isNaN(valueMax) ? valueMax : undefined,
    created_after: filterCreatedAfter.value || undefined,
    created_before: filterCreatedBefore.value || undefined,
    updated_after: filterUpdatedAfter.value || undefined,
    updated_before: filterUpdatedBefore.value || undefined,
    category_id: filterCategoryId.value || undefined,
    stage_id: filterStageId.value || undefined,
    company_id: filterCompanyId.value || undefined,
    company_name: filterCompanyName.value || undefined,
    contact_person_id: filterContactPersonId.value || undefined,
    page,
  }
}

function loadRecords(page = 1) {
  return store.fetchRecords(buildFilters(page))
}

function clearAdvancedFilters() {
  filterStatus.value = ''
  filterSource.value = ''
  filterAssignedTo.value = ''
  filterCreatedBy.value = ''
  filterValueMin.value = ''
  filterValueMax.value = ''
  filterCreatedAfter.value = ''
  filterCreatedBefore.value = ''
  filterUpdatedAfter.value = ''
  filterUpdatedBefore.value = ''
  filterCategoryId.value = ''
  filterStageId.value = ''
  filterCompanyId.value = ''
  filterCompanyName.value = ''
  filterContactPersonId.value = ''
  router.replace({ query: { ...route.query, category_id: undefined, stage_id: undefined } })
  loadRecords()
}
const showModal = ref(false)
const editingRecord = ref<RecordOut | null>(null)
const confirmDeleteId = ref<string | null>(null)
const statusPopupId = ref<string | null>(null)

// Bulk record selection & share
const selectedRecordIds = ref<Set<string>>(new Set())
const showBulkShareModal = ref(false)
const bulkSharePrincipalId = ref<string>('')
const bulkShareLevel = ref<string>('view')
const bulkShareExpiresAt = ref<string>('')
const bulkShareLoading = ref(false)

const firmIdStr = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')
const selectedRecordCount = computed(() => selectedRecordIds.value.size)
const hasBulkSelection = computed(() => selectedRecordIds.value.size > 0)

function toggleRecordSelect(recordId: string) {
  if (selectedRecordIds.value.has(recordId)) {
    selectedRecordIds.value.delete(recordId)
  } else {
    selectedRecordIds.value.add(recordId)
  }
  selectedRecordIds.value = new Set(selectedRecordIds.value) // trigger reactivity
}

function selectAllRecords() {
  if (selectedRecordIds.value.size === sortedRecords.value.length) {
    clearRecordSelection()
  } else {
    selectedRecordIds.value = new Set(sortedRecords.value.map((r) => r.id))
  }
}

async function applyBulkShare() {
  if (!bulkSharePrincipalId.value || selectedRecordIds.value.size === 0) return
  bulkShareLoading.value = true
  const ids = Array.from(selectedRecordIds.value)
  let successCount = 0
  const payload: Record<string, unknown> = {
    principal_type: 'user',
    principal_id: bulkSharePrincipalId.value,
    level: bulkShareLevel.value,
  }
  if (bulkShareExpiresAt.value) {
    payload.expires_at = new Date(bulkShareExpiresAt.value).toISOString()
  }
  for (const recordId of ids) {
    const res = await api.post(`/api/v1/crm/records/${recordId}/grants`, payload)
    if (res.ok) successCount++
  }
  bulkShareLoading.value = false
  if (successCount > 0) {
    toast.success(t('leads.bulkShareSuccess', { count: successCount }))
    showBulkShareModal.value = false
    bulkSharePrincipalId.value = ''
    bulkShareLevel.value = 'view'
    bulkShareExpiresAt.value = ''
    clearRecordSelection()
  } else {
    toast.error(t('leads.bulkShareFailed'))
  }
}

// Quick-create (inline header form)
const qcTitle = ref('')
const qcSubmitting = ref(false)

async function quickCreateRecord() {
  if (!qcTitle.value.trim() || qcSubmitting.value) return
  qcSubmitting.value = true
  const payload: Record<string, unknown> = {
    title: qcTitle.value.trim(),
    status: 'new',
    source: 'web',
  }
  if (filterCategoryId.value) payload.category_id = filterCategoryId.value
  const result = await store.createRecord(payload)
  qcSubmitting.value = false
  if (result.ok) {
    qcTitle.value = ''
    toast.success(t('leads.recordCreated'))
    loadRecords()
  } else {
    toast.error(result.error ?? t('leads.createFailed'))
  }
}

// Saved view UI
const showSaveViewDialog = ref(false)
const saveViewName = ref('')
const savingView = ref(false)

// Form
const formTitle = ref('')
const formStatus = ref('new')
const formSource = ref('web')
const formValue = ref<string>('')
const formCurrency = ref(firmCurrency.value)
const formError = ref('')
const formLoading = ref(false)

// Smart unified contact picker
const selectedPrimaryContact = ref<CustomerOut | null>(null)
const formCustomerQuery = ref('')
const customerSuggestions = ref<CustomerOut[]>([])
const customerSearchLoading = ref(false)
const showCustomerDropdown = ref(false)

// Secondary: contact person (used when primary is a company)
const selectedContactPerson = ref<CustomerOut | null>(null)
const allEmployees = ref<CustomerOut[]>([])
const loadingEmployees = ref(false)
const contactPersonQuery = ref('')
const showContactPersonDropdown = ref(false)

// Inline create person form
const showNewCustomerForm = ref(false)
const newCustomerFirstName = ref('')
const newCustomerLastName = ref('')
const newCustomerEmail = ref('')
const newCustomerPhone = ref('')

// Inline create company form
const showNewCompanyForm = ref(false)
const newCompanyName = ref('')
const newCompanyIco = ref('')
const newCompanyEmail = ref('')
const newCompanyPhone = ref('')

// Final payload values, derived from selections
const formCustomerId = ref<string | null>(null)
const formCompanyId = ref<string | null>(null)
const formContactPersonId = ref<string | null>(null)

// Grouped dropdown results
const companySuggestions = computed(() => customerSuggestions.value.filter((c) => c.type === 'company'))
const personSuggestions = computed(() => customerSuggestions.value.filter((c) => c.type === 'person'))

// Client-side filter for loaded employees
const filteredEmployees = computed(() => {
  const q = contactPersonQuery.value.trim().toLowerCase()
  if (!q) return allEmployees.value
  return allEmployees.value.filter((p) => {
    const name = [p.first_name, p.last_name].filter(Boolean).join(' ').toLowerCase()
    return name.includes(q) || (p.email?.toLowerCase() ?? '').includes(q) || (p.phone ?? '').includes(q)
  })
})

function makeContactStub(
  id: string,
  type: 'person' | 'company',
  firstName: string,
  lastName = '',
  email = '',
  phone = '',
  companyId: string | null = null,
  companyName = '',
): CustomerOut {
  return {
    id, type, first_name: firstName, last_name: lastName, email, phone,
    company_id: companyId, company_name: companyName,
    firm_id: '', ico: '', dic: '', address_street: '', address_city: '',
    address_zip: '', address_country: '', website: '', tags: [], metadata: {},
    created_at: '', updated_at: '',
  }
}

async function loadEmployees(companyId: string) {
  loadingEmployees.value = true
  const res = await api.get<CustomerOut[]>(`/api/v1/crm/directory/${companyId}/employees`)
  loadingEmployees.value = false
  if (res.ok) allEmployees.value = res.data
}

let customerSearchTimer: ReturnType<typeof setTimeout> | null = null

async function searchContacts(query: string) {
  if (!query.trim()) { customerSuggestions.value = []; return }
  customerSearchLoading.value = true
  const res = await api.get<CustomerOut[]>(`/api/v1/crm/directory?search=${encodeURIComponent(query)}&page_size=12`)
  customerSearchLoading.value = false
  if (res.ok) customerSuggestions.value = res.data
}

function onCustomerQueryInput() {
  showCustomerDropdown.value = true
  showNewCustomerForm.value = false
  showNewCompanyForm.value = false
  if (customerSearchTimer) clearTimeout(customerSearchTimer)
  customerSearchTimer = setTimeout(() => searchContacts(formCustomerQuery.value), 250)
}

function closeCustomerDropdownDelayed() {
  setTimeout(() => { showCustomerDropdown.value = false }, 200)
}

function closeContactPersonDropdownDelayed() {
  setTimeout(() => { showContactPersonDropdown.value = false }, 200)
}

function selectPrimaryContact(c: CustomerOut) {
  selectedPrimaryContact.value = c
  showCustomerDropdown.value = false
  customerSuggestions.value = []
  formCustomerQuery.value = ''
  // Reset secondary contact
  selectedContactPerson.value = null
  formContactPersonId.value = null
  contactPersonQuery.value = ''
  allEmployees.value = []
  if (c.type === 'company') {
    formCompanyId.value = c.id
    formCustomerId.value = null
    loadEmployees(c.id)
  } else if (c.company_id) {
    // Person that belongs to a company → store as contact_person so they are visible in the record detail
    formContactPersonId.value = c.id
    formCompanyId.value = c.company_id
    formCustomerId.value = null
  } else {
    // Standalone person (no company)
    formCustomerId.value = c.id
    formCompanyId.value = null
  }
}

function clearPrimaryContact() {
  selectedPrimaryContact.value = null
  formCustomerQuery.value = ''
  customerSuggestions.value = []
  showCustomerDropdown.value = false
  formCustomerId.value = null
  formCompanyId.value = null
  formContactPersonId.value = null
  selectedContactPerson.value = null
  allEmployees.value = []
  contactPersonQuery.value = ''
  showNewCustomerForm.value = false
  showNewCompanyForm.value = false
}

function selectContactPerson(cp: CustomerOut) {
  selectedContactPerson.value = cp
  formContactPersonId.value = cp.id
  contactPersonQuery.value = ''
  showContactPersonDropdown.value = false
}

function clearContactPerson() {
  selectedContactPerson.value = null
  formContactPersonId.value = null
  contactPersonQuery.value = ''
}

function onContactPersonQueryInput() {
  showContactPersonDropdown.value = true
}

function openCreatePerson() {
  showCustomerDropdown.value = false
  showNewCustomerForm.value = true
  showNewCompanyForm.value = false
  newCustomerFirstName.value = formCustomerQuery.value.split(' ')[0] ?? ''
  newCustomerLastName.value = formCustomerQuery.value.split(' ').slice(1).join(' ')
  newCustomerEmail.value = ''
  newCustomerPhone.value = ''
}

function openCreateCompany() {
  showCustomerDropdown.value = false
  showNewCompanyForm.value = true
  showNewCustomerForm.value = false
  newCompanyName.value = formCustomerQuery.value
  newCompanyIco.value = ''
  newCompanyEmail.value = ''
  newCompanyPhone.value = ''
}

async function createAndSelectCustomer() {
  if (!newCustomerFirstName.value.trim()) return
  const result = await customersStore.createCustomer({
    type: 'person',
    first_name: newCustomerFirstName.value.trim(),
    last_name: newCustomerLastName.value.trim(),
    email: newCustomerEmail.value.trim(),
    phone: newCustomerPhone.value.trim(),
  })
  if (result.ok && result.data) {
    selectPrimaryContact(result.data)
    showNewCustomerForm.value = false
    toast.success(t('leads.customerCreated'))
  } else {
    toast.error(result.error ?? t('leads.failedToCreateCustomer'))
  }
}

async function createAndSelectCompany() {
  if (!newCompanyName.value.trim()) return
  const result = await customersStore.createCustomer({
    type: 'company',
    first_name: newCompanyName.value.trim(),
    company_name: newCompanyName.value.trim(),
    ico: newCompanyIco.value.trim(),
    email: newCompanyEmail.value.trim(),
    phone: newCompanyPhone.value.trim(),
  })
  if (result.ok && result.data) {
    selectPrimaryContact(result.data)
    showNewCompanyForm.value = false
    toast.success(t('leads.companyCreated'))
  } else {
    toast.error(result.error ?? t('leads.failedToCreateCompany'))
  }
}

// Context menu
const contextMenuRef = ref<InstanceType<typeof ContextMenu> | null>(null)
const contextRecord = ref<RecordOut | null>(null)

const RECORD_CONTEXT_ITEMS = computed<ContextMenuItem[]>(() => [
  { id: 'view', label: t('leads.viewDetail'), icon: ArrowTopRightOnSquareIcon },
  { id: 'edit', label: t('leads.edit'), icon: PencilSquareIcon },
  { id: 'change_status', label: t('leads.changeStatus'), icon: ArrowsRightLeftIcon },
  { id: 'divider1', label: '', divider: true },
  { id: 'delete', label: t('leads.delete'), icon: TrashIcon, danger: true },
])

function onRowContextMenu(e: MouseEvent, record: RecordOut) {
  e.preventDefault()
  contextRecord.value = record
  contextMenuRef.value?.open(e.clientX, e.clientY)
}

function onRowLongPress(record: RecordOut, e: TouchEvent) {
  e.preventDefault()
  const touch = e.touches[0]
  if (!touch) return
  contextRecord.value = record
  contextMenuRef.value?.open(touch.clientX, touch.clientY)
}

function onContextAction(id: string) {
  const record = contextRecord.value
  if (!record) return
  if (id === 'view') goToDetail(record.id)
  else if (id === 'edit') openEdit(record)
  else if (id === 'change_status') statusPopupId.value = record.id
  else if (id === 'delete') confirmDeleteId.value = record.id
}

watch(filterStatus, () => { loadRecords() })
watch(filterSource, () => { loadRecords() })
watch(filterAssignedTo, () => { loadRecords() })
watch(filterCreatedBy, () => { loadRecords() })
watch(filterValueMin, () => { loadRecords() })
watch(filterValueMax, () => { loadRecords() })
watch(filterCreatedAfter, () => { loadRecords() })
watch(filterCreatedBefore, () => { loadRecords() })
watch(filterUpdatedAfter, () => { loadRecords() })
watch(filterUpdatedBefore, () => { loadRecords() })
watch(filterStageId, () => { loadRecords() })
watch(filterCompanyId, () => { loadRecords() })
watch(filterCompanyName, () => { loadRecords() })
watch(filterContactPersonId, () => { loadRecords() })

// Apply saved view from ?view= query param
watch(() => route.query.view, async (viewId) => {
  if (!viewId) return
  await savedViewsStore.fetchViews()
  const v = savedViewsStore.views.find((sv) => sv.id === viewId)
  if (v) {
    filterStatus.value = (v.filters.status as string) ?? ''
    filterSource.value = (v.filters.source as string) ?? ''
    filterAssignedTo.value = (v.filters.assigned_to as string) ?? ''
    filterCreatedBy.value = (v.filters.created_by as string) ?? ''
    filterValueMin.value = (v.filters.value_min as string) ?? ''
    filterValueMax.value = (v.filters.value_max as string) ?? ''
    filterCreatedAfter.value = (v.filters.created_after as string) ?? ''
    filterCreatedBefore.value = (v.filters.created_before as string) ?? ''
    if (hasActiveAdvancedFilters()) showAdvancedFilters.value = true
    // Restore sort
    const validSortFields: SortField[] = ['title', 'status', 'source', 'value', 'created_at', 'updated_at']
    if (v.sort_by && validSortFields.includes(v.sort_by as SortField)) {
      sortField.value = v.sort_by as SortField
    }
    if (v.sort_dir === 'asc' || v.sort_dir === 'desc') {
      sortDir.value = v.sort_dir
    }
    // Restore columns
    if (Array.isArray(v.columns) && v.columns.length > 0) {
      const validCols = TABLE_COLUMNS.map((c) => c.id)
      const restored = v.columns.filter((c) => validCols.includes(c as ColumnId)) as ColumnId[]
      if (restored.length > 0) visibleColumns.value = restored
    }
  }
}, { immediate: true })

onMounted(async () => {
  loadMembers()
  loadRecords()
  savedViewsStore.fetchViews()
  if (pipelineStore.categories.length === 0) {
    pipelineStore.fetchCategories()
  }
})

// React to category_id and stage_id query param changes (combined to avoid double loadRecords)
watch(
  [() => route.query.category_id, () => route.query.stage_id],
  ([catId, stageId]) => {
    filterCategoryId.value = (catId as string) ?? ''
    filterStageId.value = (stageId as string) ?? ''
    loadRecords()
  },
)

const recordsByStatus = computed(() => {
  const map: Record<string, RecordOut[]> = {}
  for (const s of RECORD_STATUSES) map[s.value] = []
  for (const l of store.records) {
    if (map[l.status]) map[l.status]!.push(l)
    else map[l.status] = [l]
  }
  return map
})

// When a category is selected, group by stage for kanban
const currentCategory = computed(() =>
  filterCategoryId.value ? pipelineStore.getCategoryById(filterCategoryId.value) : undefined,
)
const currentCategoryStages = computed(() =>
  filterCategoryId.value ? pipelineStore.getStagesForCategory(filterCategoryId.value) : [],
)
// All stages across all categories (for stage filter when no category selected)
const availableStagesForFilter = computed(() =>
  filterCategoryId.value ? currentCategoryStages.value : pipelineStore.allStages,
)
// Label for the "new record" button
const newRecordButtonLabel = computed(() => {
  if (!currentCategory.value) return ''
  return `+ ${t('leads.newInCategory', { category: currentCategory.value.name })}`
})
const recordsByStage = computed(() => {
  const map: Record<string, RecordOut[]> = {}
  for (const s of currentCategoryStages.value) map[s.id] = []
  map['__none__'] = []
  for (const l of store.records) {
    const stageId = l.current_stage_id ?? '__none__'
    if (map[stageId]) map[stageId]!.push(l)
    else map[stageId] = [l]
  }
  return map
})

/** Field keys that are shown elsewhere in the card (value, expires_at) or are not meaningful to show inline */
const KANBAN_SKIP_FIELD_KEYS = new Set(['value_currency', 'source', 'expires_at'])
const KANBAN_NOTES_MAX_LENGTH = 40

function getKanbanCardFields(record: RecordOut): { label: string; value: string }[] {
  const category = currentCategory.value
  if (!category) return []

  const visibleFields = category.fields
    .filter(f => f.is_visible && !KANBAN_SKIP_FIELD_KEYS.has(f.field_key))
    .slice(0, 2)

  return visibleFields
    .map(f => {
      const label = f.label_override || (t(`pipeline.fieldKey.${f.field_key}` as any) || f.field_key)
      let value = '—'
      switch (f.field_key) {
        case 'date_range': {
          const start = record.start_date ? new Date(record.start_date).toLocaleDateString() : null
          const end = record.end_date ? new Date(record.end_date).toLocaleDateString() : null
          if (start || end) value = `${start ?? '…'} – ${end ?? '…'}`
          break
        }
        case 'notes':
          if (record.notes) {
            value = record.notes.length > KANBAN_NOTES_MAX_LENGTH
              ? record.notes.substring(0, KANBAN_NOTES_MAX_LENGTH) + '…'
              : record.notes
          }
          break
        case 'origin_record': {
          const pid = record.parent_id ? String(record.parent_id) : null
          value = pid ? `#${pid.substring(0, Math.min(8, pid.length))}${pid.length > 8 ? '…' : ''}` : '—'
          break
        }
        default:
          value = '—'
      }
      return { label, value }
    })
    .filter(f => f.value !== '—')
}

function openCreate() {
  editingRecord.value = null
  formTitle.value = ''
  formStatus.value = 'new'
  formSource.value = 'web'
  formValue.value = ''
  formCurrency.value = 'CZK'
  formError.value = ''
  clearPrimaryContact()
  showModal.value = true
}

function openEdit(record: RecordOut) {
  editingRecord.value = record
  formTitle.value = record.title
  formStatus.value = record.status
  formSource.value = record.source
  formValue.value = record.value != null ? String(record.value) : ''
  formCurrency.value = record.currency
  formError.value = ''
  clearPrimaryContact()
  // Reconstruct primary contact from record data
  const extRecord = record as RecordOut & { customer_name?: string; customer_email?: string; customer_phone?: string }
  if (record.contact_person_id && record.company_id) {
    // Person-with-company stored as contact_person + company (new format)
    const [cpFirst = '', ...cpRest] = (record.contact_person_name ?? '').split(' ')
    selectedPrimaryContact.value = makeContactStub(
      record.contact_person_id, 'person', cpFirst, cpRest.join(' '),
      '', '', record.company_id, record.company_name ?? '',
    )
    formContactPersonId.value = record.contact_person_id
    formCompanyId.value = record.company_id
    formCustomerId.value = null
  } else if (record.customer_id) {
    // Standalone person (no company)
    const [firstName = '', ...rest] = (extRecord.customer_name ?? '').split(' ')
    selectedPrimaryContact.value = makeContactStub(
      record.customer_id, 'person', firstName, rest.join(' '),
      extRecord.customer_email ?? '', extRecord.customer_phone ?? '',
    )
    formCustomerId.value = record.customer_id
    formCompanyId.value = null
  } else if (record.company_id) {
    // Company as primary (with optional secondary contact person)
    selectedPrimaryContact.value = makeContactStub(
      record.company_id, 'company', '', '', '', '', null, record.company_name ?? '',
    )
    formCompanyId.value = record.company_id
    loadEmployees(record.company_id)
    if (record.contact_person_id) {
      const [cpFirst = '', ...cpRest] = (record.contact_person_name ?? '').split(' ')
      selectedContactPerson.value = makeContactStub(
        record.contact_person_id, 'person', cpFirst, cpRest.join(' '),
      )
      formContactPersonId.value = record.contact_person_id
    }
  }
  showModal.value = true
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
  if (editingRecord.value) {
    result = await store.updateRecord(editingRecord.value.id, payload)
  } else {
    result = await store.createRecord(payload)
  }
  formLoading.value = false
  if (result.ok) {
    showModal.value = false
    toast.success(editingRecord.value ? t('leads.leadUpdated') : t('leads.leadCreated'))
  } else {
    formError.value = result.error ?? t('leads.errorOccurred')
  }
}

async function confirmDelete(id: string) {
  const result = await store.deleteRecord(id)
  confirmDeleteId.value = null
  if (result.ok) toast.success(t('leads.leadDeleted'))
  else toast.error(result.error ?? t('leads.failedToDelete'))
}

async function changeStatus(recordId: string, newStatus: string) {
  statusPopupId.value = null
  const result = await store.patchStatus(recordId, newStatus)
  if (!result.ok) toast.error(result.error ?? t('leads.failedToUpdateStatus'))
}

function goToDetail(id: string) {
  router.push(`/app/records/${id}`)
}

// Kanban drag state (status-based)
const draggingRecord = ref<RecordOut | null>(null)
const dragOverStatus = ref<string | null>(null)

function onDragStart(record: RecordOut) {
  draggingRecord.value = record
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
  if (!draggingRecord.value || draggingRecord.value.status === status) {
    draggingRecord.value = null
    return
  }
  const record = draggingRecord.value
  draggingRecord.value = null
  await changeStatus(record.id, status)
}

// Kanban drag state (stage-based)
const draggingStageRecord = ref<RecordOut | null>(null)
const dragOverStageId = ref<string | null>(null)

// Terminal stage confirmation modal state
interface TerminalMovePayload {
  record: RecordOut
  stage: StageOut
}
const terminalMovePayload = ref<TerminalMovePayload | null>(null)
const terminalMoveNote = ref('')
const terminalAddCheckpoint = ref(false)
const terminalCheckpointName = ref('')
const terminalCheckpointDate = ref('')
const terminalMoving = ref(false)

const stageValidationModalOpen = ref(false)
const stageValidationRecord = ref<RecordOut | null>(null)
const stageValidationTargetStageName = ref<string | null>(null)
const stageValidationBlocking = ref<StageChangeIssueWithSource[]>([])
const stageValidationWarnings = ref<StageChangeIssueWithSource[]>([])

const stageValidationHasBlocking = computed(() => stageValidationBlocking.value.length > 0)

function showStageValidationModalIfNeeded(record: RecordOut, stageName: string | null, evaluation?: StageChangeEvaluationOut) {
  const normalized = normalizeStageChangeIssues(evaluation)
  stageValidationRecord.value = record
  stageValidationTargetStageName.value = stageName
  stageValidationBlocking.value = normalized.blocking
  stageValidationWarnings.value = normalized.warnings
  stageValidationModalOpen.value = normalized.blocking.length > 0 || normalized.warnings.length > 0
}

function closeStageValidationModal() {
  stageValidationModalOpen.value = false
}

function onStageDragStart(e: DragEvent, record: RecordOut) {
  draggingStageRecord.value = record
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}
function onStageDragOver(e: DragEvent, stageId: string) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  dragOverStageId.value = stageId
}
function onStageDragLeave(e: DragEvent) {
  // Only clear if leaving the column entirely (not entering a child element)
  const rel = e.relatedTarget as Node | null
  if (rel && (e.currentTarget as HTMLElement).contains(rel)) return
  dragOverStageId.value = null
}
async function onStageDrop(stageId: string) {
  dragOverStageId.value = null
  if (!draggingStageRecord.value || draggingStageRecord.value.current_stage_id === stageId) {
    draggingStageRecord.value = null
    return
  }
  const record = draggingStageRecord.value
  draggingStageRecord.value = null
  const stage = currentCategoryStages.value.find(s => s.id === stageId)

  // Show confirmation modal for terminal stages
  if (stage?.is_terminal) {
    terminalMovePayload.value = { record, stage }
    terminalMoveNote.value = ''
    terminalAddCheckpoint.value = false
    terminalCheckpointName.value = ''
    terminalCheckpointDate.value = ''
    return
  }

  const result = await store.patchStage(record.id, stageId, stage?.name ?? null)
  if (result.ok) {
    showStageValidationModalIfNeeded(record, stage?.name ?? null, result.stageChangeEvaluation)
    return
  }
  if (result.code === 'stage_change_blocked') {
    showStageValidationModalIfNeeded(record, stage?.name ?? null, result.stageChangeEvaluation)
    return
  }
  toast.error(result.error ?? t('leads.failedToUpdateStatus'))
}

async function confirmTerminalMove() {
  if (!terminalMovePayload.value) return
  terminalMoving.value = true
  const { record, stage } = terminalMovePayload.value
  const result = await store.patchStage(record.id, stage.id, stage.name)
  if (!result.ok) {
    if (result.code === 'stage_change_blocked') {
      showStageValidationModalIfNeeded(record, stage.name, result.stageChangeEvaluation)
    } else {
      toast.error(result.error ?? t('pipeline.terminalMoveFailed'))
    }
    terminalMoving.value = false
    return
  }
  // Optionally create a checkpoint
  if (terminalAddCheckpoint.value && terminalCheckpointName.value.trim()) {
    const cpRes = await api.post(`/api/v1/crm/records/${record.id}/checkpoints`, {
      name: terminalCheckpointName.value.trim(),
      date: terminalCheckpointDate.value || null,
      description: terminalMoveNote.value.trim(),
    })
    if (!cpRes.ok) toast.error(t('pipeline.terminalCheckpointFailed'))
  }
  terminalMoving.value = false
  terminalMovePayload.value = null
  showStageValidationModalIfNeeded(record, stage.name, result.stageChangeEvaluation)
}

function cancelTerminalMove() {
  terminalMovePayload.value = null
}

function fmtValue(record: RecordOut) {
  if (record.value == null) return ''
  return formatAmount(record.value, record.currency)
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

// Fetch record tasks to check overdue
const overdueTasks = ref<Set<string>>(new Set())
async function checkOverdueTasks() {
  const res = await api.get<{ id: string; record_id: string; due_date: string | null; is_completed: boolean }[]>(
    '/api/v1/crm/tasks?completed=false&page_size=100'
  )
  if (res.ok) {
    const now = Date.now()
    const set = new Set<string>()
    for (const task of res.data) {
      if (task.due_date && new Date(task.due_date).getTime() < now) {
        set.add(task.record_id)
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
    entity: 'records',
    filters: {
      ...(filterStatus.value ? { status: filterStatus.value } : {}),
      ...(filterSource.value ? { source: filterSource.value } : {}),
      ...(filterAssignedTo.value ? { assigned_to: filterAssignedTo.value } : {}),
      ...(filterCreatedBy.value ? { created_by: filterCreatedBy.value } : {}),
      ...(filterValueMin.value ? { value_min: filterValueMin.value } : {}),
      ...(filterValueMax.value ? { value_max: filterValueMax.value } : {}),
      ...(filterCreatedAfter.value ? { created_after: filterCreatedAfter.value } : {}),
      ...(filterCreatedBefore.value ? { created_before: filterCreatedBefore.value } : {}),
    },
    sort_by: sortField.value,
    sort_dir: sortDir.value,
    columns: visibleColumns.value,
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
      '/api/v1/integrations/import/records',
      fd,
    )
    if (res.ok) {
      toast.success(t('leads.importStarted'))
      setTimeout(() => loadRecords(), 2000)
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
  window.location.href = `/api/v1/integrations/export/records.csv?${params.toString()}`
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

// Returns whether assignee should be shown separately from creator
function showAssigneeAvatar(record: RecordOut): boolean {
  if (!record.assigned_to_id) return false
  return record.assigned_to_id !== record.created_by_id
}

// Contact detail modal (for company / contact person click in list/table)
const contactDetailRecord = ref<RecordOut | null>(null)
const contactDetailType = ref<'company' | 'contact_person' | null>(null)
const contactDetailData = ref<Record<string, unknown> | null>(null)
const contactDetailLoading = ref(false)

async function openContactDetail(record: RecordOut, type: 'company' | 'contact_person') {
  const id = type === 'company' ? record.company_id : record.contact_person_id
  if (!id) return
  contactDetailRecord.value = record
  contactDetailType.value = type
  contactDetailData.value = null
  contactDetailLoading.value = true
  const res = await api.get<Record<string, unknown>>(`/api/v1/crm/directory/${id}`)
  contactDetailLoading.value = false
  if (res.ok) contactDetailData.value = res.data
}

function closeContactDetail() {
  contactDetailRecord.value = null
  contactDetailType.value = null
  contactDetailData.value = null
}
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <!-- Category selector -->
      <div v-if="pipelineStore.categories.length > 0" class="flex items-center gap-1">
        <button
          class="px-3 py-1.5 rounded-xl text-sm font-medium transition-colors"
          :class="!filterCategoryId ? 'bg-white shadow text-gray-900 border border-gray-200' : 'text-gray-500 hover:text-gray-700'"
          @click="router.replace({ query: { ...route.query, category_id: undefined, stage_id: undefined } })"
        >{{ t('pipeline.allCategories') }}</button>
        <button
          v-for="cat in pipelineStore.categories.filter((c) => c.is_active)"
          :key="cat.id"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium transition-colors"
          :class="filterCategoryId === cat.id ? 'bg-white shadow text-gray-900 border border-gray-200' : 'text-gray-500 hover:text-gray-700'"
          @click="router.replace({ query: { ...route.query, category_id: cat.id, stage_id: undefined } })"
        >
          <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: cat.color || '#94A3B8' }"></span>
          {{ cat.name }}
        </button>
      </div>

      <!-- Right-side tools: pushed to the far right -->
      <div class="ml-auto flex items-center gap-3 flex-wrap">
        <!-- Saved views -->
        <div v-if="savedViewsStore.viewsForEntity('records').length > 0" class="flex items-center gap-1 flex-wrap">
          <div
            v-for="view in savedViewsStore.viewsForEntity('records')"
            :key="view.id"
            class="flex items-center gap-0.5"
          >
            <button
              class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-l-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              :title="view.name"
              @click="router.push(`/app/records?view=${view.id}`)"
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
          <!-- Advanced filters toggle -->
          <button
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors"
            :class="hasActiveAdvancedFilters()
              ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'
              : 'border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'"
            @click="showAdvancedFilters = !showAdvancedFilters"
          >
            <FunnelIcon class="w-3.5 h-3.5" />
            {{ t('leads.advancedFilters') }}
            <span v-if="hasActiveAdvancedFilters()" class="ml-0.5 w-4 h-4 bg-red-600 text-white rounded-full text-[10px] flex items-center justify-center">!</span>
          </button>
        </template>

        <!-- Actions dropdown (import / export / save view) -->
        <Dropdown :items="actionsDropdownItems" placement="left" :open-on-hover="true">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
          >
            <span>{{ t('leads.actions') }}</span>
            <ChevronDownIcon class="w-3.5 h-3.5" aria-hidden="true" />
          </button>
        </Dropdown>

        <!-- New record button: only shown when a category is selected -->
        <button
          v-if="currentCategory"
          class="bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors"
          @click="openCreate"
        >{{ newRecordButtonLabel }}</button>

        <!-- Hidden file input for CSV import -->
        <input ref="importInput" type="file" accept=".csv" class="hidden" @change="onImportFile" />
      </div>
    </div>

    <!-- Quick-create inline form (only when a category is selected) -->
    <div v-if="currentCategory" class="flex items-center gap-2 mb-4">
      <input
        v-model="qcTitle"
        type="text"
        :placeholder="currentCategory ? t('pipeline.quickCreatePlaceholderInCategory', { category: currentCategory.name }) : t('leads.quickCreatePlaceholder')"
        class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:border-red-400 dark:focus:border-red-500"
        @keyup.enter="quickCreateRecord"
      />
      <button
        class="flex-shrink-0 px-3 py-1.5 text-sm font-medium bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50 transition-colors"
        :disabled="!qcTitle.trim() || qcSubmitting"
        @click="quickCreateRecord"
      >{{ qcSubmitting ? '…' : t('leads.quickCreate') }}</button>
    </div>

    <!-- Advanced filters panel -->
    <div
      v-if="showAdvancedFilters && viewMode !== 'kanban'"
      class="mb-4 p-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700"
    >
      <div class="flex flex-wrap gap-3 items-end">
        <!-- Stav (status) -->
        <div class="flex flex-col gap-1 min-w-36">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.colStatus') }}</label>
          <select v-model="filterStatus" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400">
            <option value="">{{ t('leads.filterAll') }}</option>
            <option v-for="s in RECORD_STATUSES" :key="s.value" :value="s.value">{{ statusLabel(s.value) }}</option>
          </select>
        </div>
        <!-- Zdroj (source) -->
        <div class="flex flex-col gap-1 min-w-36">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.colSource') }}</label>
          <select v-model="filterSource" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400">
            <option value="">{{ t('leads.filterAll') }}</option>
            <option value="web">{{ t('leads.sourceWeb') }}</option>
            <option value="email">{{ t('leads.sourceEmail') }}</option>
            <option value="referral">{{ t('leads.sourceReferral') }}</option>
            <option value="cold_call">{{ t('leads.sourceColdCall') }}</option>
            <option value="social">{{ t('leads.sourceSocial') }}</option>
            <option value="other">{{ t('leads.sourceOther') }}</option>
          </select>
        </div>
        <!-- Řešitel (assigned_to) -->
        <div class="flex flex-col gap-1 min-w-36">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterAssignedTo') }}</label>
          <select v-model="filterAssignedTo" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400">
            <option value="">{{ t('leads.filterAll') }}</option>
            <option v-for="m in members" :key="m.user_id" :value="m.user_id">{{ memberLabel(m) }}</option>
          </select>
        </div>
        <!-- Tvůrce (created_by) -->
        <div class="flex flex-col gap-1 min-w-36">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterCreatedBy') }}</label>
          <select v-model="filterCreatedBy" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400">
            <option value="">{{ t('leads.filterAll') }}</option>
            <option v-for="m in members" :key="m.user_id" :value="m.user_id">{{ memberLabel(m) }}</option>
          </select>
        </div>
        <!-- Hodnota min/max -->
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterValueMin') }}</label>
          <input
            v-model="filterValueMin"
            type="number"
            min="0"
            step="1"
            :placeholder="t('leads.filterValueMinPlaceholder')"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400 w-28"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterValueMax') }}</label>
          <input
            v-model="filterValueMax"
            type="number"
            min="0"
            step="1"
            :placeholder="t('leads.filterValueMaxPlaceholder')"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400 w-28"
          />
        </div>
        <!-- Datum od/do -->
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterCreatedAfter') }}</label>
          <input
            v-model="filterCreatedAfter"
            type="date"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterCreatedBefore') }}</label>
          <input
            v-model="filterCreatedBefore"
            type="date"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400"
          />
        </div>
        <!-- Upraveno od/do -->
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterUpdatedAfter') }}</label>
          <input
            v-model="filterUpdatedAfter"
            type="date"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterUpdatedBefore') }}</label>
          <input
            v-model="filterUpdatedBefore"
            type="date"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400"
          />
        </div>
        <!-- Fáze (stage) - shows all stages when no category, or category stages when selected -->
        <div v-if="availableStagesForFilter.length > 0" class="flex flex-col gap-1 min-w-36">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterStage') }}</label>
          <select v-model="filterStageId" class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400">
            <option value="">{{ t('leads.filterAll') }}</option>
            <option v-for="stage in availableStagesForFilter" :key="stage.id" :value="stage.id">{{ stage.name }}</option>
          </select>
        </div>
        <!-- Společnost (company) -->
        <div class="flex flex-col gap-1 min-w-36">
          <label class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('leads.filterCompany') }}</label>
          <input
            v-model="filterCompanyName"
            type="text"
            :placeholder="t('leads.filterCompanyPlaceholder')"
            class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 focus:outline-none focus:border-red-400 w-36"
          />
        </div>
        <!-- Clear button -->
        <button
          v-if="hasActiveAdvancedFilters()"
          type="button"
          class="mt-auto px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-red-600 border border-gray-200 dark:border-gray-600 rounded-xl"
          @click="clearAdvancedFilters"
        >
          <XMarkIcon class="w-3.5 h-3.5 inline-block mr-0.5 align-text-bottom" />{{ t('leads.clearFilters') }}
        </button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && store.records.length === 0" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- TABLE VIEW -->
    <template v-else-if="viewMode === 'table'">
      <div v-if="store.records.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
        <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('leads.noLeadsFound') }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-xs">
          <template v-if="hasActiveAdvancedFilters()">{{ t('leads.filterSubtitle') }}</template>
          <template v-else>{{ t('leads.pipelineSubtitle') }}</template>
        </p>
        <button
          v-if="!hasActiveAdvancedFilters()"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
          @click="openCreate"
        >{{ t('leads.createFirst') }}</button>
      </div>
      <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
        <!-- Bulk action toolbar -->
        <div v-if="hasBulkSelection" class="flex items-center gap-3 px-4 py-2 bg-indigo-50 dark:bg-indigo-900/20 border-b border-indigo-100 dark:border-indigo-800">
          <span class="text-xs font-medium text-indigo-700 dark:text-indigo-300">
            {{ t('leads.bulkSelected', { count: selectedRecordCount }) }}
          </span>
          <button
            @click="showBulkShareModal = true; permissionsStore.fetchTeams(firmIdStr)"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-indigo-300 dark:border-indigo-600 text-xs text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-800"
          >
            <ShareIcon class="h-3.5 w-3.5" />
            {{ t('leads.shareSelected') }}
          </button>
          <button
            @click="clearRecordSelection"
            class="ml-auto text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >{{ t('leads.clearSelection') }}</button>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-100 dark:border-gray-700 text-left">
              <!-- Bulk select header checkbox -->
              <th class="px-4 py-3 w-8">
                <input
                  type="checkbox"
                  class="rounded border-gray-300 text-indigo-600"
                  :checked="selectedRecordIds.size > 0 && selectedRecordIds.size === sortedRecords.length"
                  :indeterminate="selectedRecordIds.size > 0 && selectedRecordIds.size < sortedRecords.length"
                  @change="selectAllRecords"
                  :aria-label="t('leads.bulkSelected', { count: sortedRecords.length })"
                />
              </th>
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('title')">{{ t('leads.colTitle') }} <span class="opacity-60">{{ sortIcon('title') }}</span></th>
              <th v-if="isColVisible('status')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('status')">{{ t('leads.colStatus') }} <span class="opacity-60">{{ sortIcon('status') }}</span></th>
              <th v-if="isColVisible('source')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('source')">{{ t('leads.colSource') }} <span class="opacity-60">{{ sortIcon('source') }}</span></th>
              <th v-if="isColVisible('value')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('value')">{{ t('leads.colValue') }} <span class="opacity-60">{{ sortIcon('value') }}</span></th>
              <th v-if="isColVisible('score')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colScore') }}</th>
              <th v-if="isColVisible('created_at')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('created_at')">{{ t('leads.colCreated') }} <span class="opacity-60">{{ sortIcon('created_at') }}</span></th>
              <th v-if="isColVisible('updated_at')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('updated_at')">{{ t('leads.colUpdated') }} <span class="opacity-60">{{ sortIcon('updated_at') }}</span></th>
              <th v-if="isColVisible('company')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colCompany') }}</th>
              <th v-if="isColVisible('contact_person')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colContactPerson') }}</th>
              <th v-if="isColVisible('users')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colUsers') }}</th>
              <!-- Column picker -->
              <th class="px-4 py-3 text-right">
                <div class="relative inline-block">
                  <button
                    type="button"
                    class="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    :title="t('leads.colPicker')"
                    :aria-label="t('leads.colPicker')"
                    @click.stop="columnPickerOpen = !columnPickerOpen"
                  >
                    <AdjustmentsHorizontalIcon class="w-4 h-4" />
                  </button>
                  <!-- Column picker dropdown -->
                  <div
                    v-if="columnPickerOpen"
                    class="absolute right-0 top-8 z-20 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-2 min-w-44"
                    @click.stop
                  >
                    <div class="px-3 pb-1.5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
                      <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('leads.colPicker') }}</span>
                      <button type="button" class="text-xs text-red-500 hover:text-red-700" @click="resetColumns">{{ t('leads.resetColumns') }}</button>
                    </div>
                    <label
                      v-for="col in TABLE_COLUMNS"
                      :key="col.id"
                      class="flex items-center gap-2.5 px-3 py-1.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <input
                        type="checkbox"
                        class="rounded border-gray-300 text-red-600 focus:ring-red-500"
                        :checked="isColVisible(col.id)"
                        @change="toggleColumn(col.id)"
                      />
                      {{ t(`leads.${col.labelKey}`) }}
                    </label>
                  </div>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in sortedRecords"
              :key="record.id"
              class="border-b border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
              :class="selectedRecordIds.has(record.id) ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : ''"
              @click.self="goToDetail(record.id)"
              @contextmenu="onRowContextMenu($event, record)"
            >
              <!-- Bulk select checkbox -->
              <td class="px-4 py-3 w-8" @click.stop>
                <input
                  type="checkbox"
                  class="rounded border-gray-300 text-indigo-600"
                  :checked="selectedRecordIds.has(record.id)"
                  @change="toggleRecordSelect(record.id)"
                  :aria-label="`Select ${record.title}`"
                />
              </td>
              <td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100 max-w-xs" @click="goToDetail(record.id)">
                <div class="flex items-center gap-1.5">
                  <span class="truncate">{{ record.title }}</span>
                  <span v-if="overdueTasks.has(record.id)" title="Overdue task" class="text-red-500 text-xs flex-shrink-0" aria-label="Overdue task">⚠</span>
                </div>
              </td>
              <td v-if="isColVisible('status')" class="px-4 py-3">
                <div class="relative">
                  <button
                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-80"
                    :class="getStatusMeta(record.status).color"
                    :aria-label="`Status: ${statusLabel(record.status)}. Click to change.`"
                    @click.stop="statusPopupId = statusPopupId === record.id ? null : record.id"
                  >
                    {{ statusLabel(record.status) }}
                    <span class="text-xs opacity-60" aria-hidden="true">▾</span>
                  </button>
                  <!-- Status popup -->
                  <div
                    v-if="statusPopupId === record.id"
                    class="absolute z-10 top-8 left-0 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1 min-w-36"
                    role="listbox"
                    :aria-label="`Change status for ${record.title}`"
                    @click.stop
                  >
                    <button
                      v-for="s in RECORD_STATUSES"
                      :key="s.value"
                      class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2 text-gray-700 dark:text-gray-300"
                      :class="s.value === record.status ? 'font-semibold' : ''"
                      role="option"
                      :aria-selected="s.value === record.status"
                      @click="changeStatus(record.id, s.value)"
                    >
                      <span class="w-2 h-2 rounded-full flex-shrink-0" :class="s.color.split(' ')[0]" aria-hidden="true" />
                      {{ statusLabel(s.value) }}
                    </button>
                  </div>
                </div>
              </td>
              <td v-if="isColVisible('source')" class="px-4 py-3 text-gray-500 dark:text-gray-400" @click="goToDetail(record.id)">{{ sourceLabel(record.source) }}</td>
              <td v-if="isColVisible('value')" class="px-4 py-3 text-gray-700 dark:text-gray-300" @click="goToDetail(record.id)">{{ fmtValue(record) }}</td>
              <td v-if="isColVisible('score')" class="px-4 py-3" @click="goToDetail(record.id)">
                <RecordScoreBadge :score="(record as RecordOut & { score?: number }).score" />
              </td>
              <td v-if="isColVisible('created_at')" class="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs" @click="goToDetail(record.id)">{{ new Date(record.created_at).toLocaleDateString() }}</td>
              <td v-if="isColVisible('updated_at')" class="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs" @click="goToDetail(record.id)">{{ new Date(record.updated_at).toLocaleDateString() }}</td>
              <td v-if="isColVisible('company')" class="px-4 py-3 text-xs" @click.stop>
                <button
                  v-if="record.company_name"
                  class="flex items-center gap-1 text-gray-600 dark:text-gray-300 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  :title="record.company_name"
                  @click="openContactDetail(record, 'company')"
                >
                  <BuildingOfficeIcon class="w-3.5 h-3.5 flex-shrink-0" />
                  <span class="truncate max-w-28">{{ record.company_name }}</span>
                </button>
                <span v-else class="text-gray-300 dark:text-gray-600">—</span>
              </td>
              <td v-if="isColVisible('contact_person')" class="px-4 py-3 text-xs" @click.stop>
                <button
                  v-if="record.contact_person_name"
                  class="flex items-center gap-1 text-gray-600 dark:text-gray-300 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  :title="record.contact_person_name"
                  @click="openContactDetail(record, 'contact_person')"
                >
                  <UserIcon class="w-3.5 h-3.5 flex-shrink-0" />
                  <span class="truncate max-w-28">{{ record.contact_person_name }}</span>
                </button>
                <span v-else class="text-gray-300 dark:text-gray-600">—</span>
              </td>
              <td v-if="isColVisible('users')" class="px-4 py-3" @click="goToDetail(record.id)">
                <div class="flex items-center gap-1">
                  <Avatar v-if="record.created_by_name" size="xs" :name="record.created_by_name" :title="t('leads.createdBy') + ': ' + record.created_by_name" />
                  <Avatar v-if="showAssigneeAvatar(record)" size="xs" :name="record.assigned_to_name ?? ''" :title="t('leads.assignedTo') + ': ' + record.assigned_to_name" />
                </div>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('leads.edit')" @click.stop="openEdit(record)"><PencilSquareIcon class="w-4 h-4" /></button>
                  <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('leads.delete')" @click.stop="confirmDeleteId = record.id"><TrashIcon class="w-4 h-4" /></button>
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
              @click="loadRecords(store.page - 1)"
            >{{ t('leads.prev') }}</button>
            <button
              v-if="store.hasMore"
              class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
              @click="loadRecords(store.page + 1)"
            >{{ t('leads.next') }}</button>
          </div>
        </div>
      </div>
    </template>

    <!-- LIST VIEW -->
    <template v-else-if="viewMode === 'list'">
      <div v-if="store.records.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('leads.noLeadsFound') }}</h3>
        <p class="text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-xs">
          <template v-if="hasActiveAdvancedFilters()">{{ t('leads.filterSubtitle') }}</template>
          <template v-else>{{ t('leads.pipelineSubtitle') }}</template>
        </p>
        <button
          v-if="!hasActiveAdvancedFilters()"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
          @click="openCreate"
        >{{ t('leads.createFirst') }}</button>
      </div>
      <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
        <div
          v-for="record in sortedRecords"
          :key="record.id"
          class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
          @click="goToDetail(record.id)"
          @contextmenu="onRowContextMenu($event, record)"
        >
          <!-- Status indicator dot -->
          <span class="w-2.5 h-2.5 rounded-full flex-shrink-0" :class="getStatusMeta(record.status).color.split(' ')[0]" :aria-label="statusLabel(record.status)" />

          <!-- Title -->
          <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
            {{ record.title }}
            <span v-if="overdueTasks.has(record.id)" class="text-red-500 text-xs ml-1" title="Overdue task" aria-label="Overdue task">⚠</span>
          </span>

          <!-- Status badge -->
          <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium flex-shrink-0" :class="getStatusMeta(record.status).color">
            {{ statusLabel(record.status) }}
          </span>

          <!-- Source -->
          <span class="hidden md:block text-xs text-gray-400 dark:text-gray-500 flex-shrink-0 w-20 truncate">{{ sourceLabel(record.source) }}</span>

          <!-- Value -->
          <span class="hidden lg:block text-xs text-gray-600 dark:text-gray-300 flex-shrink-0 w-24 text-right">{{ fmtValue(record) }}</span>

          <!-- Score -->
          <span class="hidden xl:block flex-shrink-0"><RecordScoreBadge :score="(record as RecordOut & { score?: number }).score" /></span>

          <!-- Dates: Created + Updated -->
          <div class="hidden lg:flex flex-col items-end flex-shrink-0 w-24" @click.stop="goToDetail(record.id)">
            <span class="text-xs text-gray-400 dark:text-gray-500">{{ new Date(record.created_at).toLocaleDateString() }}</span>
            <span v-if="new Date(record.updated_at).getTime() !== new Date(record.created_at).getTime()" class="text-xs text-gray-300 dark:text-gray-600">{{ new Date(record.updated_at).toLocaleDateString() }}</span>
          </div>

          <!-- Company -->
          <div class="hidden md:block flex-shrink-0 w-28" @click.stop>
            <button
              v-if="record.company_name"
              class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors truncate max-w-full"
              :title="record.company_name"
              @click="openContactDetail(record, 'company')"
            >
              <BuildingOfficeIcon class="w-3 h-3 flex-shrink-0" />
              <span class="truncate">{{ record.company_name }}</span>
            </button>
            <button
              v-if="record.contact_person_name"
              class="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors truncate max-w-full"
              :title="record.contact_person_name"
              @click="openContactDetail(record, 'contact_person')"
            >
              <UserIcon class="w-3 h-3 flex-shrink-0" />
              <span class="truncate">{{ record.contact_person_name }}</span>
            </button>
          </div>

          <!-- User avatars (creator + assignee if different) -->
          <div class="hidden sm:flex items-center gap-1 flex-shrink-0" @click.stop>
            <Avatar v-if="record.created_by_name" size="xs" :name="record.created_by_name" :title="t('leads.createdBy') + ': ' + record.created_by_name" />
            <Avatar v-if="showAssigneeAvatar(record)" size="xs" :name="record.assigned_to_name ?? ''" :title="t('leads.assignedTo') + ': ' + record.assigned_to_name" />
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" @click.stop>
            <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('leads.edit')" @click="openEdit(record)"><PencilSquareIcon class="w-4 h-4" /></button>
            <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('leads.delete')" @click="confirmDeleteId = record.id"><TrashIcon class="w-4 h-4" /></button>
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
            @click="loadRecords(store.page - 1)"
          >{{ t('leads.prev') }}</button>
          <button
            v-if="store.hasMore"
            class="px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
            @click="loadRecords(store.page + 1)"
          >{{ t('leads.next') }}</button>
        </div>
      </div>
    </template>

    <!-- KANBAN VIEW -->
    <template v-else-if="viewMode === 'kanban'">
      <!-- Stage-based kanban (when category is selected) -->
      <template v-if="currentCategory && currentCategoryStages.length > 0">
        <div class="flex gap-4 overflow-x-auto pb-4 min-h-96">
          <div
            v-for="stage in currentCategoryStages"
            :key="stage.id"
            class="flex-shrink-0 w-64 flex flex-col"
            @dragover="onStageDragOver($event, stage.id)"
            @dragleave="onStageDragLeave($event)"
            @drop="onStageDrop(stage.id)"
          >
            <!-- Column header -->
            <div
              class="flex items-center gap-2 px-3 py-2 rounded-xl mb-2 text-xs font-semibold transition-colors"
              :style="{ backgroundColor: dragOverStageId === stage.id ? stage.color + '44' : stage.color + '22', color: stage.color }"
            >
              {{ stage.name }}
              <span v-if="stage.is_terminal && stage.is_won" class="text-green-600">✓</span>
              <span class="ml-auto bg-white/60 rounded px-1.5 py-0.5">{{ recordsByStage[stage.id]?.length ?? 0 }}</span>
            </div>
            <!-- Cards -->
            <div
              class="flex-1 space-y-2 min-h-16 rounded-xl transition-colors p-1"
              :class="dragOverStageId === stage.id ? 'bg-blue-50 dark:bg-blue-900/20 ring-2 ring-blue-300 dark:ring-blue-600' : 'bg-gray-50 dark:bg-gray-700/30'"
            >
              <div
                v-for="record in recordsByStage[stage.id]"
                :key="record.id"
                class="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 cursor-grab shadow-sm hover:shadow transition-shadow group"
                draggable="true"
                @dragstart="onStageDragStart($event, record)"
                @click="goToDetail(record.id)"
                @contextmenu="onRowContextMenu($event, record)"
              >
                <div class="text-xs font-medium text-gray-900 dark:text-gray-100 leading-snug">{{ record.title }}</div>
                <div class="flex items-center gap-2 mt-2 flex-wrap">
                  <span v-if="fmtValue(record)" class="text-xs text-gray-500">{{ fmtValue(record) }}</span>
                  <span v-if="record.expires_at" class="text-xs" :class="pipelineStore.getSlaColor(record.expires_at)">{{ record.expires_at }}</span>
                </div>
                <!-- Category field values -->
                <div v-if="getKanbanCardFields(record).length > 0" class="mt-2 space-y-0.5">
                  <div
                    v-for="kf in getKanbanCardFields(record)"
                    :key="kf.label"
                    class="flex items-baseline gap-1.5 text-[11px]"
                  >
                    <span class="text-gray-400 dark:text-gray-500 shrink-0">{{ kf.label }}:</span>
                    <span class="text-gray-600 dark:text-gray-300 truncate">{{ kf.value }}</span>
                  </div>
                </div>
              </div>
              <div v-if="(recordsByStage[stage.id]?.length ?? 0) === 0" class="text-center text-xs py-6" :class="draggingStageRecord ? 'text-blue-400 dark:text-blue-500' : 'text-gray-400 dark:text-gray-500'">{{ draggingStageRecord ? t('leads.dropHere') : t('leads.noRecordsInStage') }}</div>
            </div>
          </div>
        </div>
      </template>

      <!-- Status-based kanban (no category selected) -->
      <template v-else>
        <div class="flex gap-4 overflow-x-auto pb-4 min-h-96">
          <div
            v-for="s in RECORD_STATUSES"
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
              <span class="ml-auto bg-white/60 dark:bg-black/30 rounded px-1.5 py-0.5">{{ recordsByStatus[s.value]?.length ?? 0 }}</span>
            </div>
            <!-- Cards -->
            <div
              class="flex-1 space-y-2 min-h-16 rounded-xl transition-colors p-1"
              :class="dragOverStatus === s.value ? 'bg-red-50 dark:bg-red-900/20' : 'bg-gray-50 dark:bg-gray-700/30'"
            >
              <div
                v-for="record in recordsByStatus[s.value]"
                :key="record.id"
                class="bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 cursor-grab shadow-sm hover:shadow transition-shadow group"
                draggable="true"
                @dragstart="onDragStart(record)"
                @contextmenu="onRowContextMenu($event, record)"
              >
                <div class="flex items-start justify-between gap-2">
                  <button
                    class="text-xs font-medium text-gray-900 dark:text-gray-100 text-left hover:text-red-600 transition-colors leading-snug"
                    @click="goToDetail(record.id)"
                  >{{ record.title }}</button>
                  <div class="flex gap-0.5 opacity-0 group-hover:opacity-100">
                    <button class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400" :aria-label="t('leads.edit')" @click.stop="openEdit(record)"><PencilSquareIcon class="w-3.5 h-3.5" /></button>
                  </div>
                </div>
                <div class="flex items-center gap-2 mt-2 flex-wrap">
                  <span v-if="fmtValue(record)" class="text-xs text-gray-500 dark:text-gray-400">{{ fmtValue(record) }}</span>
                  <RecordScoreBadge :score="(record as RecordOut & { score?: number }).score" />
                  <span v-if="overdueTasks.has(record.id)" class="text-xs text-red-500" :title="t('leads.overdueLabel')">{{ t('leads.overdueLabel') }}</span>
                </div>
              </div>
              <div v-if="(recordsByStatus[s.value]?.length ?? 0) === 0" class="text-center text-xs text-gray-300 dark:text-gray-600 py-4">{{ t('leads.dropHere') }}</div>
            </div>
          </div>
        </div>
      </template>
    </template>
  </div>

  <!-- Context menu -->
  <ContextMenu ref="contextMenuRef" :items="RECORD_CONTEXT_ITEMS" @action="onContextAction" />

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
            {{ t('leads.saveViewDescription') }}
            <template v-if="hasActiveAdvancedFilters()"> + {{ t('leads.saveViewAdvanced') }}</template>
            <template v-if="sortField !== DEFAULT_SORT_FIELD || sortDir !== DEFAULT_SORT_DIR"> · {{ t('leads.saveViewSort', { field: t(`leads.col_${sortField}`), dir: t(`leads.sort_${sortDir}`) }) }}</template>
          </p>
          <p class="text-xs text-gray-400 dark:text-gray-500">
            {{ t('leads.saveViewColumns', { n: visibleColumns.length }) }}
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
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" :aria-label="editingRecord ? t('leads.editTitle') : t('leads.newTitle')">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ editingRecord ? t('leads.editTitle') : t('leads.newTitle') }}</h3>
        <div v-if="formError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ formError }}</div>
        <form class="space-y-3" @submit.prevent="submitForm">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.titleField') }}</label>
            <input v-model="formTitle" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <!-- Unified Contact Picker -->
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.customerField') }}</label>

            <!-- Selected primary contact chip -->
            <div v-if="selectedPrimaryContact" class="flex flex-col gap-1">
              <!-- Company chip -->
              <div v-if="selectedPrimaryContact.type === 'company'" class="flex items-center gap-2 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-xl px-3 py-2">
                <BuildingOfficeIcon class="w-4 h-4 text-blue-500 flex-shrink-0" />
                <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {{ selectedPrimaryContact.company_name || [selectedPrimaryContact.first_name, selectedPrimaryContact.last_name].filter(Boolean).join(' ') }}
                </span>
                <button type="button" class="text-gray-400 hover:text-red-500" @click="clearPrimaryContact"><XMarkIcon class="w-4 h-4" /></button>
              </div>
              <!-- Person chip -->
              <div v-else class="flex items-center gap-2 bg-gray-50 dark:bg-gray-700/60 border border-gray-200 dark:border-gray-600 rounded-xl px-3 py-2">
                <UserIcon class="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div class="flex-1 min-w-0">
                  <span class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ [selectedPrimaryContact.first_name, selectedPrimaryContact.last_name].filter(Boolean).join(' ') }}</span>
                  <span v-if="selectedPrimaryContact.email" class="text-xs text-gray-400 ml-2">{{ selectedPrimaryContact.email }}</span>
                </div>
                <button type="button" class="text-gray-400 hover:text-red-500" @click="clearPrimaryContact"><XMarkIcon class="w-4 h-4" /></button>
              </div>
              <!-- Read-only company badge for person with a company -->
              <div v-if="selectedPrimaryContact.type === 'person' && selectedPrimaryContact.company_name" class="flex items-center gap-1.5 px-1 py-0.5">
                <BuildingOfficeIcon class="w-3.5 h-3.5 text-gray-400" />
                <span class="text-xs text-gray-400">{{ selectedPrimaryContact.company_name }}</span>
              </div>
            </div>

            <!-- Search input (no contact selected yet) -->
            <div v-else class="relative">
              <div class="relative">
                <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                <input
                  v-model="formCustomerQuery"
                  type="text"
                  :placeholder="t('leads.customerSearchPlaceholder')"
                  autocomplete="off"
                  class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  @input="onCustomerQueryInput"
                  @focus="if (formCustomerQuery) { showCustomerDropdown = true; searchContacts(formCustomerQuery) }"
                  @blur="closeCustomerDropdownDelayed"
                />
              </div>
              <!-- Suggestions dropdown -->
              <div
                v-if="showCustomerDropdown && (customerSearchLoading || customerSuggestions.length > 0 || formCustomerQuery.trim())"
                class="absolute z-20 top-full mt-1 w-full bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1 max-h-60 overflow-y-auto"
              >
                <div v-if="customerSearchLoading" class="px-3 py-2 text-xs text-gray-400">{{ t('leads.searching') }}</div>
                <template v-else-if="customerSuggestions.length > 0">
                  <!-- Companies section -->
                  <template v-if="companySuggestions.length > 0">
                    <div class="px-3 pt-2 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">{{ t('leads.sectionCompanies') }}</div>
                    <button
                      v-for="c in companySuggestions"
                      :key="c.id"
                      type="button"
                      class="w-full flex items-center gap-2 text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                      @mousedown.prevent
                      @click="selectPrimaryContact(c)"
                    >
                      <BuildingOfficeIcon class="w-4 h-4 text-blue-400 flex-shrink-0" />
                      <div class="flex-1 min-w-0">
                        <span class="font-medium text-gray-900 dark:text-gray-100">{{ c.company_name || [c.first_name, c.last_name].filter(Boolean).join(' ') }}</span>
                        <span v-if="c.ico" class="text-xs text-gray-400 ml-2">IČO: {{ c.ico }}</span>
                      </div>
                    </button>
                  </template>
                  <!-- Persons section -->
                  <template v-if="personSuggestions.length > 0">
                    <div class="px-3 pt-2 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide">{{ t('leads.sectionPersons') }}</div>
                    <button
                      v-for="p in personSuggestions"
                      :key="p.id"
                      type="button"
                      class="w-full flex items-center gap-2 text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                      @mousedown.prevent
                      @click="selectPrimaryContact(p)"
                    >
                      <UserIcon class="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <div class="flex-1 min-w-0">
                        <span class="font-medium text-gray-900 dark:text-gray-100">{{ [p.first_name, p.last_name].filter(Boolean).join(' ') }}</span>
                        <span v-if="p.email" class="text-xs text-gray-400 ml-2">{{ p.email }}</span>
                        <span v-if="p.phone" class="text-xs text-gray-400 ml-1">{{ p.email ? '·' : '' }} {{ p.phone }}</span>
                        <span v-if="p.company_name" class="text-xs text-gray-400 ml-1">· {{ p.company_name }}</span>
                      </div>
                    </button>
                  </template>
                </template>
                <!-- No results: offer to create -->
                <template v-else-if="formCustomerQuery.trim()">
                  <button
                    type="button"
                    class="w-full flex items-center gap-2 text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                    @mousedown.prevent
                    @click="openCreatePerson"
                  >
                    <UserIcon class="w-4 h-4 text-gray-400" />
                    <span>{{ t('leads.createNewPerson') }} <span class="font-medium">"{{ formCustomerQuery }}"</span></span>
                  </button>
                  <button
                    type="button"
                    class="w-full flex items-center gap-2 text-left px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                    @mousedown.prevent
                    @click="openCreateCompany"
                  >
                    <BuildingOfficeIcon class="w-4 h-4 text-blue-400" />
                    <span>{{ t('leads.createNewCompany') }} <span class="font-medium">"{{ formCustomerQuery }}"</span></span>
                  </button>
                </template>
              </div>
            </div>

            <!-- Inline: create new person -->
            <div v-if="showNewCustomerForm" class="mt-2 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-600 space-y-2">
              <p class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('leads.newCustomerLabel') }}</p>
              <div class="grid grid-cols-2 gap-2">
                <input v-model="newCustomerFirstName" type="text" :placeholder="t('leads.firstNamePlaceholder')" class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
                <input v-model="newCustomerLastName" type="text" :placeholder="t('leads.lastNamePlaceholder')" class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              </div>
              <input v-model="newCustomerEmail" type="email" placeholder="Email" class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              <input v-model="newCustomerPhone" type="tel" placeholder="Telefon" class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              <div class="flex gap-2">
                <button type="button" class="text-xs text-gray-500 hover:text-gray-700" @click="showNewCustomerForm = false">{{ t('leads.cancel') }}</button>
                <button type="button" class="text-xs text-white bg-red-600 px-3 py-1 rounded-lg hover:bg-red-700" @click="createAndSelectCustomer">{{ t('leads.createAndSelect') }}</button>
              </div>
            </div>

            <!-- Inline: create new company -->
            <div v-if="showNewCompanyForm" class="mt-2 p-3 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 space-y-2">
              <p class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('leads.newCompanyLabel') }}</p>
              <input v-model="newCompanyName" type="text" :placeholder="t('leads.companyNameField')" class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              <div class="grid grid-cols-2 gap-2">
                <input v-model="newCompanyIco" type="text" :placeholder="t('leads.icoField')" class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
                <input v-model="newCompanyPhone" type="tel" placeholder="Telefon" class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              </div>
              <input v-model="newCompanyEmail" type="email" placeholder="Email" class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" />
              <div class="flex gap-2">
                <button type="button" class="text-xs text-gray-500 hover:text-gray-700" @click="showNewCompanyForm = false">{{ t('leads.cancel') }}</button>
                <button type="button" class="text-xs text-white bg-red-600 px-3 py-1 rounded-lg hover:bg-red-700" @click="createAndSelectCompany">{{ t('leads.createAndSelect') }}</button>
              </div>
            </div>
          </div>

          <!-- Secondary: Contact Person (shown only when a company is the primary contact) -->
          <div v-if="selectedPrimaryContact?.type === 'company'">
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.contactPersonField') }}</label>
            <!-- Selected contact person chip -->
            <div v-if="selectedContactPerson" class="flex items-center gap-2 bg-gray-50 dark:bg-gray-700/60 border border-gray-200 dark:border-gray-600 rounded-xl px-3 py-2">
              <UserIcon class="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span class="flex-1 text-sm text-gray-900 dark:text-gray-100 truncate">{{ [selectedContactPerson.first_name, selectedContactPerson.last_name].filter(Boolean).join(' ') }}</span>
              <button type="button" class="text-gray-400 hover:text-red-500" @click="clearContactPerson"><XMarkIcon class="w-4 h-4" /></button>
            </div>
            <!-- Search / filter employees -->
            <div v-else class="relative">
              <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              <input
                v-model="contactPersonQuery"
                type="text"
                :placeholder="t('leads.contactPersonSearchPlaceholder')"
                autocomplete="off"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-red-400"
                @input="onContactPersonQueryInput"
                @focus="showContactPersonDropdown = true"
                @blur="closeContactPersonDropdownDelayed"
              />
              <div
                v-if="showContactPersonDropdown"
                class="absolute z-20 top-full mt-1 w-full bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1 max-h-48 overflow-y-auto"
              >
                <div v-if="loadingEmployees" class="px-3 py-2 text-xs text-gray-400">{{ t('leads.searching') }}</div>
                <template v-else-if="filteredEmployees.length > 0">
                  <button
                    v-for="p in filteredEmployees"
                    :key="p.id"
                    type="button"
                    class="w-full flex items-center gap-2 text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700"
                    @mousedown.prevent
                    @click="selectContactPerson(p)"
                  >
                    <UserIcon class="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <div class="flex-1 min-w-0">
                      <span class="text-gray-900 dark:text-gray-100">{{ [p.first_name, p.last_name].filter(Boolean).join(' ') }}</span>
                      <span v-if="p.email" class="text-xs text-gray-400 ml-2">{{ p.email }}</span>
                    </div>
                  </button>
                </template>
                <div v-else class="px-3 py-2 text-xs text-gray-400">{{ t('leads.noEmployeesFound') }}</div>
              </div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leads.statusField') }}</label>
              <select v-model="formStatus" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option v-for="s in RECORD_STATUSES" :key="s.value" :value="s.value">{{ statusLabel(s.value) }}</option>
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
              <CurrencySelect v-model="formCurrency" />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showModal = false">{{ t('leads.cancel') }}</button>
            <button type="submit" :disabled="formLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ formLoading ? t('leads.saving') : (editingRecord ? t('leads.save') : t('leads.create')) }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Delete confirm -->
  <ConfirmDeleteModal
    :open="!!confirmDeleteId"
    :title="t('leads.deleteTitle')"
    :message="t('leads.deleteText')"
    @confirm="confirmDelete(confirmDeleteId!)"
    @cancel="confirmDeleteId = null"
  />

  <!-- Terminal stage confirmation modal -->
  <Modal
    :open="!!terminalMovePayload"
    :title="terminalMovePayload ? t('pipeline.terminalMoveTitle').replace('{stage}', terminalMovePayload.stage.name) : ''"
    size="sm"
    @close="cancelTerminalMove"
  >
    <div class="space-y-4">
      <!-- Subtitle -->
      <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('pipeline.terminalMoveSubtitle') }}</p>

      <!-- Record name badge -->
      <div
        v-if="terminalMovePayload"
        class="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium"
        :class="terminalMovePayload.stage.is_won
          ? 'bg-green-50 text-green-800 dark:bg-green-900/20 dark:text-green-300'
          : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-200'"
      >
        <span
          class="inline-block w-2 h-2 rounded-full flex-shrink-0"
          :style="{ backgroundColor: terminalMovePayload?.stage.color || '#6b7280' }"
        />
        {{ terminalMovePayload?.record.title }}
        <span class="ml-auto text-xs opacity-70">→ {{ terminalMovePayload?.stage.name }}</span>
      </div>

      <!-- Outcome note -->
      <div>
        <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
          {{ t('pipeline.terminalMoveNote') }}
        </label>
        <textarea
          v-model="terminalMoveNote"
          rows="2"
          :placeholder="t('pipeline.terminalMoveNotePlaceholder')"
          class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
        />
      </div>

      <!-- Checkpoint option -->
      <div class="space-y-2">
        <label class="flex items-center gap-2 cursor-pointer select-none">
          <input
            v-model="terminalAddCheckpoint"
            type="checkbox"
            class="rounded border-gray-300 text-red-600 focus:ring-red-400"
          />
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('pipeline.terminalAddCheckpoint') }}</span>
        </label>
        <template v-if="terminalAddCheckpoint">
          <input
            v-model="terminalCheckpointName"
            type="text"
            :placeholder="t('pipeline.terminalCheckpointNamePlaceholder')"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('pipeline.terminalCheckpointDate') }}</label>
            <input
              v-model="terminalCheckpointDate"
              type="date"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-red-400"
            />
          </div>
        </template>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" :disabled="terminalMoving" @click="cancelTerminalMove">
        {{ t('pipeline.cancel') }}
      </Button>
      <Button
        :variant="terminalMovePayload?.stage.is_won ? 'primary' : 'secondary'"
        :loading="terminalMoving"
        :class="terminalMovePayload?.stage.is_won
          ? '!bg-green-600 hover:!bg-green-700 focus:!ring-green-500'
          : ''"
        @click="confirmTerminalMove"
      >
        {{ terminalMovePayload?.stage.is_won ? t('pipeline.terminalConfirmWon') : t('pipeline.terminalConfirmLost') }}
      </Button>
    </template>
  </Modal>

  <Modal
    :open="stageValidationModalOpen"
    :title="stageValidationHasBlocking ? t('pipeline.stageValidationBlockedTitle') : t('pipeline.stageValidationWarningTitle')"
    size="sm"
    @close="closeStageValidationModal"
  >
    <div class="space-y-4">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        {{
          stageValidationHasBlocking
            ? t('pipeline.stageValidationBlockedSubtitle', { stage: stageValidationTargetStageName || t('pipeline.stageLabel') })
            : t('pipeline.stageValidationWarningSubtitle', { stage: stageValidationTargetStageName || t('pipeline.stageLabel') })
        }}
      </p>

      <div v-if="stageValidationBlocking.length > 0">
        <div class="text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-400 mb-2">
          {{ t('pipeline.stageValidationBlockingListTitle') }}
        </div>
        <ul class="space-y-2">
          <li
            v-for="issue in stageValidationBlocking"
            :key="`board-block-${issue.rule_id}`"
            class="rounded-xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-800 dark:text-red-300"
          >
            {{ issue.message || issue.name }}
          </li>
        </ul>
      </div>

      <div v-if="stageValidationWarnings.length > 0">
        <div class="text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400 mb-2">
          {{ t('pipeline.stageValidationWarningsListTitle') }}
        </div>
        <ul class="space-y-2">
          <li
            v-for="issue in stageValidationWarnings"
            :key="`board-warn-${issue.rule_id}-${issue.source}`"
            class="rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-300"
          >
            {{ issue.message || issue.name }}
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <Button
        v-if="stageValidationRecord"
        variant="secondary"
        @click="goToDetail(stageValidationRecord.id)"
      >
        {{ t('pipeline.stageValidationOpenRecord') }}
      </Button>
      <Button variant="secondary" @click="closeStageValidationModal">
        {{ stageValidationHasBlocking ? t('pipeline.stageValidationClose') : t('pipeline.stageValidationContinue') }}
      </Button>
    </template>
  </Modal>

  <!-- Global status popup backdrop -->
  <div v-if="statusPopupId" class="fixed inset-0 z-5" @click="statusPopupId = null" />

  <!-- Contact detail modal -->
  <Teleport to="body">
    <div
      v-if="contactDetailRecord"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @click.self="closeContactDetail"
    >
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6" role="dialog" aria-modal="true">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('leads.contactDetailTitle') }}</h3>
          <button type="button" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="closeContactDetail">
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>
        <div v-if="contactDetailLoading" class="py-8 text-center text-sm text-gray-400">{{ t('common.loading') }}</div>
        <div v-else-if="contactDetailData" class="space-y-2 text-sm text-gray-700 dark:text-gray-300">
          <div v-if="contactDetailData.company_name" class="flex justify-between border-b border-gray-100 dark:border-gray-700 pb-2">
            <span class="text-gray-500 dark:text-gray-400">{{ t('leads.colCompany') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">{{ contactDetailData.company_name }}</span>
          </div>
          <div v-if="contactDetailData.first_name || contactDetailData.last_name" class="flex justify-between border-b border-gray-100 dark:border-gray-700 pb-2">
            <span class="text-gray-500 dark:text-gray-400">{{ t('leads.colContactPerson') }}</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">{{ [contactDetailData.first_name, contactDetailData.last_name].filter(Boolean).join(' ') }}</span>
          </div>
          <div v-if="contactDetailData.email" class="flex justify-between border-b border-gray-100 dark:border-gray-700 pb-2">
            <span class="text-gray-500 dark:text-gray-400">{{ t('common.email') }}</span>
            <a :href="`mailto:${contactDetailData.email}`" class="text-red-600 dark:text-red-400 hover:underline text-right">{{ contactDetailData.email }}</a>
          </div>
          <div v-if="contactDetailData.phone" class="flex justify-between border-b border-gray-100 dark:border-gray-700 pb-2">
            <span class="text-gray-500 dark:text-gray-400">{{ t('common.phone') }}</span>
            <a :href="`tel:${contactDetailData.phone}`" class="text-red-600 dark:text-red-400 hover:underline text-right">{{ contactDetailData.phone }}</a>
          </div>
          <div v-if="contactDetailData.website" class="flex justify-between border-b border-gray-100 dark:border-gray-700 pb-2">
            <span class="text-gray-500 dark:text-gray-400">{{ t('common.website') }}</span>
            <a :href="String(contactDetailData.website)" target="_blank" class="text-red-600 dark:text-red-400 hover:underline text-right">{{ contactDetailData.website }}</a>
          </div>
          <div v-if="contactDetailData.ico" class="flex justify-between border-b border-gray-100 dark:border-gray-700 pb-2">
            <span class="text-gray-500 dark:text-gray-400">IČO</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">{{ contactDetailData.ico }}</span>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Bulk share modal -->
  <Teleport to="body">
    <div
      v-if="showBulkShareModal"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @click.self="showBulkShareModal = false"
    >
      <div
        class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6"
        role="dialog"
        aria-modal="true"
        :aria-label="t('leads.bulkShareTitle', { count: selectedRecordCount })"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
            {{ t('leads.bulkShareTitle', { count: selectedRecordCount }) }}
          </h3>
          <button type="button" class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" @click="showBulkShareModal = false">
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">{{ t('leads.bulkShareHint') }}</p>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.shareWith') }}</label>
            <PeoplePicker
              v-model="bulkSharePrincipalId"
              :firm-id="firmIdStr"
              :placeholder="t('peoplePicker.placeholder')"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.accessLevel') }}</label>
            <select
              v-model="bulkShareLevel"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-indigo-400"
            >
              <option value="view">{{ t('permissions.accessView') }}</option>
              <option value="edit">{{ t('permissions.accessEdit') }}</option>
              <option value="manage">{{ t('permissions.accessManage') }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.expiresAt') }}</label>
            <input
              v-model="bulkShareExpiresAt"
              type="date"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-indigo-400"
            />
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-5">
          <button
            type="button"
            class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            @click="showBulkShareModal = false"
          >{{ t('leads.cancel') }}</button>
          <button
            type="button"
            class="px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
            :disabled="!bulkSharePrincipalId || bulkShareLoading"
            @click="applyBulkShare"
          >{{ bulkShareLoading ? '…' : t('leads.shareSelected') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

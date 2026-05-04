<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRecordsStore, RECORD_STATUSES, getStatusMeta, type RecordIn } from '@/stores/records'
import { usePipelineStore } from '@/stores/pipeline'
import { useToast } from '@/composables/useToast'
import { useWebSocket } from '@/composables/useWebSocket'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import StreamlineFilterDropdown from '@/components/StreamlineFilterDropdown.vue'
import EntitySidebarActionPicker from '@/components/EntitySidebarActionPicker.vue'
import StreamlineCreateModal from '@/components/StreamlineCreateModal.vue'
import { sanitizeHtml } from '@/utils/sanitizeHtml'
import {
  CheckIcon,
  CalendarDaysIcon,
  UserIcon,
  BellIcon,
  TrashIcon,
  DocumentIcon,
  CloudArrowUpIcon,
  PaperClipIcon,
  ChevronDownIcon,
  XMarkIcon,
  FlagIcon,
  PlusIcon,
} from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

const route = useRoute()
const router = useRouter()
const store = useRecordsStore()
const pipelineStore = usePipelineStore()
const toast = useToast()
const firmStore = useFirmStore()
const authStore = useAuthStore()
const { on, off } = useWebSocket()
const { t } = useI18n()

const leadId = computed(() => route.params.id as string)

const currentCategory = computed(() =>
  store.currentRecord?.category_id
    ? pipelineStore.getCategoryById(store.currentRecord.category_id)
    : undefined,
)

const selectedShortcutId = ref('overview')
const customFilters = ref<Set<string>>(new Set())
const newShortcutName = ref('')
const allTools = ref<any[]>([])

// ─── Streamline Create Modal state ────────────────────────────────────────
const activeModalTool = ref('')

// ─── Akce dropdown state ──────────────────────────────────────────────────
const akceDropdownOpen = ref(false)
const sidebarPickerRef = ref<InstanceType<typeof EntitySidebarActionPicker> | null>(null)

function openModalTool(type: string) {
  activeModalTool.value = type
  akceDropdownOpen.value = false
}

function closeAkceDropdown() {
  akceDropdownOpen.value = false
}

function closeModalTool() {
  activeModalTool.value = ''
}

interface ShortcutPreset {
  id: string
  name: string
  visible_activity_types: string[]
}
const shortcuts = ref<ShortcutPreset[]>([])

const shortcutsKey = computed(() => {
  const userId = authStore.user?.id || 'guest'
  return `leadlab_shortcuts_u${userId}`
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


// Team members (for @mention in task composer on the Tasks tab)
const teamMembers = ref<MentionUser[]>([])

// ActivityTimeline ref (used to reload feed after sidebar actions)
const activityTimelineRef = ref<InstanceType<typeof ActivityTimeline> | null>(null)

async function loadTeamMembers() {
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (!firmId) return
  const res = await api.get<{ id: string; user_id: string; user_full_name: string }[]>(
    `/api/v1/firms/${firmId}/members`,
  )
  if (res.ok) {
    teamMembers.value = res.data.map((m) => ({ id: m.user_id, label: m.user_full_name || m.user_id }))
  }
}

// Tasks
interface Task {
  id: string
  lead_id: string
  title: string
  description?: string
  due_date: string | null
  is_completed: boolean
  created_at: string
  assigned_to_id?: string | null
  watcher_ids?: string[]
  streamline_count?: number
  streamline_resolved?: number
}
interface ChecklistItem { id: string; text: string; is_checked: boolean; position: number }
interface TaskDependency { id: string; from_task_id: string; from_task_title: string; to_task_id: string; to_task_title: string; type: 'blocks' | 'related_to' }
interface TaskDetails { subtasks: Task[]; checklist: ChecklistItem[]; dependencies: TaskDependency[] }

const tasks = ref<Task[]>([])
const tasksLoading = ref(false)
const expandedTasks = ref<Set<string>>(new Set())
const taskDetailsMap = ref<Map<string, TaskDetails>>(new Map())
const taskDetailsLoadingSet = ref<Set<string>>(new Set())
const newTaskTitle = ref('')
const newTaskDueDate = ref('')
const newTaskDescription = ref('')
const newTaskAssigneeId = ref('')
const newTaskWatcherIds = ref<string[]>([])
const taskEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const taskSubmitting = ref(false)

// Files
interface FileItem { id: string; original_filename: string; content_type: string; size_bytes: number; url: string; created_at: string }
const files = ref<FileItem[]>([])
const filesLoading = ref(false)
const confirmDeleteAttachmentId = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadingFile = ref(false)
const uploadProgress = ref(0)
const isDraggingOver = ref(false)

// Edit form
const showEditModal = ref(false)
const editTitle = ref('')
const editStatus = ref('')
const editSource = ref('')
const editValue = ref('')
const editCurrency = ref('')
const editError = ref('')
const editLoading = ref(false)
const statusPopupOpen = ref(false)

const editCompanyId = ref<string | null>(null)
const editContactPersonId = ref<string | null>(null)
const companies = ref<any[]>([])
const contactPersons = ref<any[]>([])
const loadingCompanies = ref(false)
const loadingContactPersons = ref(false)

async function loadCompanies() {
  loadingCompanies.value = true
  const res = await api.get<any[]>('/api/v1/crm/directory?type=company&page_size=200')
  loadingCompanies.value = false
  if (res.ok) companies.value = res.data
}

async function loadEmployeesForCompany(companyId: string) {
  loadingContactPersons.value = true
  const res = await api.get<any[]>(`/api/v1/crm/directory/${companyId}/employees`)
  loadingContactPersons.value = false
  if (res.ok) contactPersons.value = res.data
}

function onCompanyChange() {
  if (editCompanyId.value) {
    loadEmployeesForCompany(editCompanyId.value)
  } else {
    contactPersons.value = []
    editContactPersonId.value = null
  }
}

const displayedStatuses = computed(() => {
  const current = store.currentRecord?.status || 'new'
  const base = [
    { value: 'new', label: t('leads.statusNew') },
    { value: 'contacted', label: t('leads.statusContacted') },
    { value: 'proposal', label: t('leads.statusProposal') },
    { value: 'negotiation', label: t('leads.statusNegotiation') },
    { value: 'won', label: t('leads.statusWon') },
  ]
  if (current === 'lost') {
    base.push({ value: 'lost', label: t('leads.statusLost') })
  } else if (current === 'canceled') {
    base.push({ value: 'canceled', label: t('leads.statusCanceled') })
  }
  return base
})

const currentStatusIndex = computed(() => {
  const current = store.currentRecord?.status || 'new'
  return displayedStatuses.value.findIndex((s) => s.value === current)
})

function getStatusBg(status: string) {
  switch (status) {
    case 'new': return 'bg-gray-400'
    case 'contacted': return 'bg-blue-500'
    case 'proposal': return 'bg-yellow-500'
    case 'negotiation': return 'bg-orange-500'
    case 'won': return 'bg-green-500'
    case 'lost': return 'bg-red-500'
    case 'canceled': return 'bg-gray-500'
    default: return 'bg-indigo-500'
  }
}

function getStatusHexColor(status: string) {
  switch (status) {
    case 'new': return '#9ca3af'
    case 'contacted': return '#3b82f6'
    case 'proposal': return '#eab308'
    case 'negotiation': return '#f97316'
    case 'won': return '#22c55e'
    case 'lost': return '#ef4444'
    case 'canceled': return '#6b7280'
    default: return '#6366f1'
  }
}

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const res = await api.get<Task[]>(`/api/v1/crm/tasks?page_size=100&lead_id=${encodeURIComponent(leadId.value)}`)
    if (res.ok) {
      tasks.value = res.data
    }
  } finally {
    tasksLoading.value = false
  }
}

async function toggleExpand(taskId: string) {
  if (expandedTasks.value.has(taskId)) {
    expandedTasks.value.delete(taskId)
    return
  }
  expandedTasks.value.add(taskId)
  if (taskDetailsMap.value.has(taskId)) return
  taskDetailsLoadingSet.value.add(taskId)
  try {
    const [subtasksRes, checklistRes, depsRes] = await Promise.all([
      api.get<Task[]>(`/api/v1/crm/tasks/${taskId}/subtasks`),
      api.get<ChecklistItem[]>(`/api/v1/crm/tasks/${taskId}/checklist`),
      api.get<TaskDependency[]>(`/api/v1/crm/tasks/${taskId}/dependencies`),
    ])
    taskDetailsMap.value.set(taskId, {
      subtasks: subtasksRes.ok ? subtasksRes.data : [],
      checklist: checklistRes.ok ? checklistRes.data : [],
      dependencies: depsRes.ok ? depsRes.data : [],
    })
  } finally {
    taskDetailsLoadingSet.value.delete(taskId)
  }
}

async function loadFiles() {
  filesLoading.value = true
  try {
    const res = await api.get<FileItem[]>(`/api/v1/crm/records/${leadId.value}/attachments?page_size=50`)
    if (res.ok) files.value = res.data
  } finally {
    filesLoading.value = false
  }
}

async function addTask() {
  if (!newTaskTitle.value.trim()) return
  taskSubmitting.value = true
  // Collect @mentioned user IDs from the description editor
  const mentionedIds = taskEditorRef.value?.getMentionedIds() ?? []
  const payload: Record<string, unknown> = {
    lead_id: leadId.value,
    title: newTaskTitle.value.trim(),
    description: newTaskDescription.value,
    assigned_to_id: newTaskAssigneeId.value || null,
    watcher_ids: newTaskWatcherIds.value,
  }
  if (newTaskDueDate.value) payload.due_date = new Date(newTaskDueDate.value).toISOString()
  if (mentionedIds.length > 0) payload.metadata = { mentions: mentionedIds }
  const res = await api.post<Task>('/api/v1/crm/tasks', payload)
  taskSubmitting.value = false
  if (res.ok) {
    tasks.value.push(res.data)
    newTaskTitle.value = ''
    newTaskDueDate.value = ''
    newTaskDescription.value = ''
    newTaskAssigneeId.value = ''
    newTaskWatcherIds.value = []
    toast.success(t('recordDetail.taskCreated'))
  } else {
    toast.error(t('recordDetail.taskFailed'))
  }
}

function toggleTaskWatcher(userId: string) {
  const idx = newTaskWatcherIds.value.indexOf(userId)
  if (idx !== -1) newTaskWatcherIds.value.splice(idx, 1)
  else newTaskWatcherIds.value.push(userId)
}

async function completeTask(id: string, isCompleted: boolean) {
  const url = isCompleted
    ? `/api/v1/crm/tasks/${id}/reopen`
    : `/api/v1/crm/tasks/${id}/complete`
  const res = await api.post<Task>(url)
  if (res.ok) {
    const idx = tasks.value.findIndex((task) => task.id === id)
    if (idx !== -1) tasks.value[idx] = res.data
    toast.success(isCompleted ? t('tasks.taskReopened') : t('recordDetail.taskCompleted'))
  } else {
    toast.error(t('recordDetail.taskCompleteFailed'))
  }
}

async function uploadFile(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  await doUpload(input.files[0]!)
  if (fileInput.value) fileInput.value.value = ''
}

async function onFileDrop(e: DragEvent) {
  isDraggingOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  await doUpload(file)
}

async function doUpload(file: File) {
  uploadingFile.value = true
  uploadProgress.value = 0
  const fd = new FormData()
  fd.append('file', file)

  await new Promise<void>((resolve) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/v1/crm/records/${leadId.value}/attachments`)
    // Forward cookies / CSRF via credentials
    xhr.withCredentials = true
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) uploadProgress.value = Math.round((ev.loaded / ev.total) * 100)
    }
    xhr.onload = () => {
      uploadingFile.value = false
      uploadProgress.value = 0
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const item = JSON.parse(xhr.responseText) as FileItem
          files.value.unshift(item)
          toast.success(t('recordDetail.fileUploaded'))
        } catch {
          toast.error('Upload response parse error.')
        }
      } else {
        toast.error(t('recordDetail.fileUploadFailed'))
      }
      resolve()
    }
    xhr.onerror = () => {
      uploadingFile.value = false
      uploadProgress.value = 0
      toast.error(t('recordDetail.fileUploadFailed'))
      resolve()
    }
    xhr.send(fd)
  })
}

async function doDeleteFile(id: string) {
  const res = await api.delete(`/api/v1/crm/records/${leadId.value}/attachments/${id}`)
  if (res.ok || res.status === 204) {
    files.value = files.value.filter((f) => f.id !== id)
    toast.success('File deleted.')
  } else {
    toast.error('Failed to delete file.')
  }
}

function deleteFile(id: string) {
  confirmDeleteAttachmentId.value = id
}

async function changeStatus(newStatus: string) {
  statusPopupOpen.value = false
  const result = await store.patchStatus(leadId.value, newStatus)
  if (!result.ok) toast.error(result.error ?? 'Failed to update status.')
  else activityTimelineRef.value?.load()
}

function openEdit() {
  const record = store.currentRecord
  if (!record) return
  editTitle.value = record.title
  editStatus.value = record.status
  editSource.value = record.source
  editValue.value = record.value != null ? String(record.value) : ''
  editCurrency.value = record.currency
  editError.value = ''
  editCompanyId.value = (record as any).company_id ?? null
  editContactPersonId.value = (record as any).contact_person_id ?? null

  if ((record as any).company_id) {
    loadEmployeesForCompany((record as any).company_id)
  } else {
    contactPersons.value = []
  }
  loadCompanies()
  showEditModal.value = true
}

async function submitEdit() {
  if (!editTitle.value.trim()) { editError.value = t('recordDetail.editTitleRequired'); return }
  editLoading.value = true
  const result = await store.updateRecord(leadId.value, {
    title: editTitle.value.trim(),
    status: editStatus.value,
    source: editSource.value,
    value: editValue.value ? parseFloat(editValue.value) : null,
    currency: editCurrency.value,
    company_id: editCompanyId.value ?? null,
    contact_person_id: editContactPersonId.value ?? null,
  })
  editLoading.value = false
  if (result.ok) {
    showEditModal.value = false
    toast.success(t('recordDetail.updated'))
  } else {
    editError.value = result.error ?? 'Failed to update.'
  }
}

async function deleteRecord() {
  const result = await store.deleteRecord(leadId.value)
  if (result.ok) {
    toast.success(t('recordDetail.deleted'))
    router.push('/app/records')
  } else {
    toast.error(result.error ?? 'Failed to delete.')
  }
}

// ---------------------------------------------------------------------------
// Pipeline: Stage changer
// ---------------------------------------------------------------------------

const currentStages = computed(() => {
  const record = store.currentRecord
  if (!record?.category_id) return []
  return pipelineStore.getStagesForCategory(record.category_id)
})

const stageProgress = computed(() => {
  const record = store.currentRecord
  if (!record?.category_id || !record.current_stage_id) return 0
  return pipelineStore.getStageProgress(currentStages.value, record.current_stage_id)
})

async function changeStage(stageId: string) {
  const result = await store.updateRecord(leadId.value, { current_stage_id: stageId })
  if (result.ok) {
    toast.success(t('pipeline.stageUpdated'))
  } else {
    toast.error(result.error ?? t('pipeline.stageUpdateFailed'))
  }
}

// ---------------------------------------------------------------------------
// Pipeline: Checkpoints
// ---------------------------------------------------------------------------

interface CheckpointItem {
  id: string
  name: string
  date: string | null
  is_completed: boolean
  description: string
}

const checkpoints = ref<CheckpointItem[]>([])
const checkpointsLoading = ref(false)
const newCheckpointName = ref('')
const newCheckpointDate = ref('')
const addingCheckpoint = ref(false)

async function loadCheckpoints() {
  const record = store.currentRecord
  if (!record) return
  checkpointsLoading.value = true
  try {
    const res = await api.get<CheckpointItem[]>(`/api/v1/crm/records/${record.id}/checkpoints`)
    if (res.ok) checkpoints.value = res.data
  } finally {
    checkpointsLoading.value = false
  }
}

async function addCheckpoint() {
  if (!newCheckpointName.value.trim()) return
  addingCheckpoint.value = true
  try {
    const res = await api.post<CheckpointItem>(`/api/v1/crm/records/${leadId.value}/checkpoints`, {
      name: newCheckpointName.value.trim(),
      date: newCheckpointDate.value || null,
    })
    if (res.ok) {
      checkpoints.value.push(res.data)
      newCheckpointName.value = ''
      newCheckpointDate.value = ''
    } else {
      toast.error(t('pipeline.checkpointAddFailed'))
    }
  } finally {
    addingCheckpoint.value = false
  }
}

async function toggleCheckpoint(cp: CheckpointItem) {
  const res = await api.patch<CheckpointItem>(`/api/v1/crm/records/${leadId.value}/checkpoints/${cp.id}`, {
    is_completed: !cp.is_completed,
  })
  if (res.ok) {
    const idx = checkpoints.value.findIndex((c) => c.id === cp.id)
    if (idx !== -1) checkpoints.value[idx] = res.data
  }
}

async function deleteCheckpoint(cpId: string) {
  const res = await api.delete(`/api/v1/crm/records/${leadId.value}/checkpoints/${cpId}`)
  if (res.ok || res.status === 204) {
    checkpoints.value = checkpoints.value.filter((c) => c.id !== cpId)
  }
}

onMounted(async () => {
  await store.fetchRecord(leadId.value)
  loadTeamMembers()
  loadShortcuts()
  loadTools()
  // Load pipeline categories if not yet loaded
  if (pipelineStore.categories.length === 0) {
    pipelineStore.fetchCategories()
  }
  // Load checkpoints
  loadCheckpoints()

  on('record.updated', onWsLeadUpdated)
})

onUnmounted(() => {
  off('record.updated', onWsLeadUpdated)
})

function onWsLeadUpdated(_payload: Record<string, unknown>) {
  // The records store is already updated by AppShell's WS handler; currentRecord
  // is a shared Pinia ref so the UI re-renders automatically.
}

const selectedContact = ref<any | null>(null)
const showContactModal = ref(false)
const loadingContactDetail = ref(false)

async function openContactDetail(id: string | null) {
  if (!id) return
  loadingContactDetail.value = true
  showContactModal.value = true
  selectedContact.value = null
  const res = await api.get<any>(`/api/v1/crm/directory/${id}`)
  loadingContactDetail.value = false
  if (res.ok) {
    selectedContact.value = res.data
  }
}

// ---------------------------------------------------------------------------
// Pipeline Fields — inline editing panel
// ---------------------------------------------------------------------------

const categoryFields = computed(() => {
  const record = store.currentRecord
  if (!record?.category_id) return []
  const cat = pipelineStore.getCategoryById(record.category_id)
  if (!cat) return []
  return cat.fields.filter((f) => f.is_visible)
})

/** Which field_keys to skip in the pipeline fields panel (shown elsewhere in sidebar) */
const SIDEBAR_FIELD_KEYS = new Set(['value_currency', 'source'])

/** Visible pipeline fields, excluding those already prominently shown in main details */
const pipelineFields = computed(() => categoryFields.value.filter((f) => !SIDEBAR_FIELD_KEYS.has(f.field_key)))

const editingFieldKey = ref<string | null>(null)
const fieldEditValues = ref<Record<string, string>>({})
const savingField = ref(false)
const fieldEditError = ref<string | null>(null)

function getFieldLabel(fieldKey: string, labelOverride: string): string {
  if (labelOverride) return labelOverride
  const key = `pipeline.fieldKey.${fieldKey}` as any
  return t(key) || fieldKey
}

function formatDateDisplay(isoStr: string | null | undefined): string {
  if (!isoStr) return '—'
  try {
    return new Date(isoStr).toLocaleDateString()
  } catch {
    return isoStr
  }
}

function getFieldDisplayValue(fieldKey: string): string {
  const record = store.currentRecord
  if (!record) return '—'
  switch (fieldKey) {
    case 'expires_at':
      return formatDateDisplay(record.expires_at)
    case 'date_range': {
      const start = formatDateDisplay(record.start_date)
      const end = formatDateDisplay(record.end_date)
      if (!record.start_date && !record.end_date) return '—'
      return `${start} – ${end}`
    }
    case 'notes':
      return record.notes || '—'
    case 'origin_record':
      return record.parent_id ? `#${String(record.parent_id).substring(0, 8)}…` : '—'
    default:
      return '—'
  }
}

function startFieldEdit(fieldKey: string) {
  const record = store.currentRecord
  if (!record) return
  editingFieldKey.value = fieldKey
  // Normalize any ISO datetime/date string to YYYY-MM-DD for <input type="date">
  const toDateInputValue = (v: string | null | undefined): string => {
    if (!v) return ''
    return typeof v === 'string' ? v.substring(0, 10) : ''
  }
  switch (fieldKey) {
    case 'expires_at':
      fieldEditValues.value['expires_at'] = toDateInputValue(record.expires_at)
      break
    case 'date_range':
      fieldEditValues.value['start_date'] = toDateInputValue(record.start_date)
      fieldEditValues.value['end_date'] = toDateInputValue(record.end_date)
      break
    case 'notes':
      fieldEditValues.value['notes'] = record.notes || ''
      break
  }
}

function cancelFieldEdit() {
  editingFieldKey.value = null
  fieldEditValues.value = {}
  fieldEditError.value = null
}

async function saveFieldEdit(fieldKey: string) {
  savingField.value = true
  fieldEditError.value = null
  let payload: Partial<RecordIn> = {}
  switch (fieldKey) {
    case 'expires_at':
      payload = { expires_at: fieldEditValues.value['expires_at'] || null }
      break
    case 'date_range':
      payload = {
        start_date: fieldEditValues.value['start_date'] || null,
        end_date: fieldEditValues.value['end_date'] || null,
      }
      break
    case 'notes':
      payload = { notes: fieldEditValues.value['notes'] || '' }
      break
    default:
      savingField.value = false
      return
  }
  const result = await store.updateRecord(leadId.value, payload)
  savingField.value = false
  if (result.ok) {
    editingFieldKey.value = null
    fieldEditValues.value = {}
    fieldEditError.value = null
    toast.success(t('pipeline.fieldSaved'))
  } else {
    fieldEditError.value = result.error ?? t('pipeline.fieldSaveFailed')
  }
}
</script>

<template>
  <div class="p-6">
    <!-- Breadcrumb -->
    <nav v-if="currentCategory" class="flex items-center gap-1 text-sm text-gray-500 mb-4 flex-wrap" aria-label="breadcrumb">
      <RouterLink
        :to="`/app/records?category_id=${currentCategory.id}`"
        class="flex items-center gap-1 hover:text-red-600 transition-colors"
      >
        <span class="w-2 h-2 rounded-full flex-shrink-0" :style="{ backgroundColor: currentCategory.color || '#94A3B8' }" aria-hidden="true"></span>
        {{ currentCategory.name }}
      </RouterLink>
    </nav>

    <!-- Loading skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-64" />
      <div class="h-24 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="store.currentRecord">
      <!-- Progress bar -->
      <div class="mb-6 bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 rounded-2xl p-4 shadow-sm select-none">
        <!-- Stage-based progress bar (when category is set) -->
        <template v-if="store.currentRecord && store.currentRecord.category_id">
          <div v-if="currentStages.length > 0" class="flex items-center justify-between gap-1 select-none">
            <div v-for="(stage, i) in currentStages" :key="stage.id" class="flex-1 flex flex-col gap-1.5 items-center relative">
              <div
                class="w-full h-1.5 rounded-full transition-all duration-300"
                :style="{
                  backgroundColor: store.currentRecord?.current_stage_id === stage.id || i < currentStages.findIndex((s) => s.id === store.currentRecord?.current_stage_id)
                    ? (stage.color || '#6366f1')
                    : '#e5e7eb',
                  transform: store.currentRecord?.current_stage_id === stage.id ? 'scaleY(1.25)' : 'none',
                }"
              />
              <span
                class="text-[10px] sm:text-xs font-semibold select-none text-center transition-colors"
                :class="store.currentRecord.current_stage_id === stage.id ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 dark:text-gray-600'"
              >
                {{ stage.name }}
              </span>
            </div>
          </div>
          <div v-else class="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
        </template>
        <!-- Status-based progress bar (no category) -->
        <template v-else>
          <div class="flex items-center justify-between gap-1 select-none">
            <div v-for="(s, i) in displayedStatuses" :key="s.value" class="flex-1 flex flex-col gap-1.5 items-center relative">
              <div
                class="w-full h-1.5 rounded-full transition-all duration-300"
                :class="[
                  i <= currentStatusIndex ? getStatusBg(s.value) : 'bg-gray-200 dark:bg-gray-700',
                  i === currentStatusIndex ? 'scale-y-125' : ''
                ]"
                :style="i === currentStatusIndex ? { boxShadow: '0 0 0 2px ' + getStatusHexColor(s.value) + '80' } : {}"
              />
              <span
                class="text-[10px] sm:text-xs font-semibold select-none text-center transition-colors"
                :class="i <= currentStatusIndex ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400 dark:text-gray-600'"
              >
                {{ s.label }}
              </span>
            </div>
          </div>
        </template>
      </div>

      <!-- 2-column layout from the start -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Left Column: Activity Feed & Presets Switcher -->
        <div class="lg:col-span-2">
          <!-- Switchers: Přehled + user presets + Filtry + Akce -->
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

            <!-- Akce button — at the far right, opens a tool dropdown -->
            <div class="relative ml-auto">
              <button
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors shadow-sm"
                @click="akceDropdownOpen = !akceDropdownOpen"
              >
                <PlusIcon class="w-4 h-4" />
                Akce
              </button>

              <!-- Akce dropdown -->
              <div
                v-if="akceDropdownOpen"
                class="absolute right-0 top-full mt-1 z-30 w-52 bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-xl py-2 overflow-hidden"
              >
                <template v-for="group in (sidebarPickerRef?.groupedActionItems ?? [])" :key="group.key">
                  <div class="px-3 pt-2 pb-0.5">
                    <p class="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
                      {{ t(group.labelKey) }}
                    </p>
                  </div>
                  <button
                    v-for="item in group.items"
                    :key="item.value"
                    class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left"
                    @click="openModalTool(item.value)"
                  >
                    <component :is="item.icon" class="w-4 h-4 flex-shrink-0 text-gray-400 dark:text-gray-500" />
                    <span class="flex-1 truncate">{{ item.label }}</span>
                  </button>
                </template>
              </div>
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
            entity-type="record"
            :entity-id="leadId"
            :hide-filter-dropdown="true"
            :override-visible-types="currentVisibleTypes"
          />
        </div>

        <!-- Right Column: Sidebar (details + actions) -->
        <div class="space-y-4">

          <!-- Stage changer (when category is set) -->
          <div
            v-if="store.currentRecord.category_id && currentStages.length > 0"
            class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4"
          >
            <div class="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">{{ t('pipeline.stageLabel') }}</div>
            <!-- Progress bar -->
            <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-3">
              <div
                class="bg-indigo-500 h-1.5 rounded-full transition-all duration-500"
                :style="{ width: stageProgress + '%' }"
              ></div>
            </div>
            <!-- Stage buttons -->
            <div class="flex flex-wrap gap-1">
              <button
                v-for="stage in currentStages"
                :key="stage.id"
                class="px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors"
                :style="store.currentRecord.current_stage_id === stage.id
                  ? { backgroundColor: stage.color + '33', borderColor: stage.color, color: stage.color }
                  : { borderColor: '#e5e7eb', color: '#6b7280' }"
                @click="changeStage(stage.id)"
              >
                {{ stage.name }}
                <span v-if="stage.is_terminal && stage.is_won" class="ml-1 text-green-500">✓</span>
              </button>
            </div>
          </div>

          <!-- Checkpoints panel -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-purple-100 dark:border-purple-900/30 p-4">
            <div class="flex items-center gap-1.5 mb-3">
              <FlagIcon class="w-4 h-4 text-purple-500 flex-shrink-0" />
              <div class="text-xs font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wide">{{ t('pipeline.checkpoints') }}</div>
            </div>
            <div v-if="checkpointsLoading" class="text-xs text-gray-400">{{ t('pipeline.loadingCheckpoints') }}</div>
            <ul v-else class="space-y-1.5 mb-2">
              <li
                v-for="cp in checkpoints"
                :key="cp.id"
                class="flex items-center gap-2 group"
              >
                <button
                  class="w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors"
                  :class="cp.is_completed ? 'bg-purple-500 border-purple-500 text-white' : 'border-purple-300 hover:border-purple-500'"
                  @click="toggleCheckpoint(cp)"
                  :aria-label="cp.is_completed ? 'Mark incomplete' : 'Mark complete'"
                >
                  <span v-if="cp.is_completed" class="text-[8px] font-bold">✓</span>
                </button>
                <span
                  class="text-xs flex-1"
                  :class="cp.is_completed ? 'line-through text-gray-400' : 'text-gray-700 dark:text-gray-300'"
                >{{ cp.name }}</span>
                <span v-if="cp.date" class="text-[10px] text-purple-400 flex-shrink-0">{{ cp.date }}</span>
                <button
                  class="hidden group-hover:block text-gray-300 hover:text-red-400 transition-colors"
                  @click="deleteCheckpoint(cp.id)"
                >×</button>
              </li>
              <li v-if="checkpoints.length === 0" class="text-xs text-gray-400 italic">{{ t('pipeline.noCheckpoints') }}</li>
            </ul>
            <!-- Add checkpoint form -->
            <div class="flex gap-1">
              <input
                v-model="newCheckpointName"
                :placeholder="t('pipeline.newCheckpointPlaceholder')"
                class="flex-1 text-xs border border-purple-200 dark:border-purple-700 rounded-lg px-2 py-1 outline-none focus:ring-1 focus:ring-purple-300 dark:bg-gray-700 dark:text-gray-200"
                @keyup.enter="addCheckpoint"
              />
              <button
                class="px-2 py-1 text-xs bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
                :disabled="addingCheckpoint || !newCheckpointName.trim()"
                @click="addCheckpoint"
              >+</button>
            </div>
          </div>

          <!-- Pipeline Fields panel -->
          <div
            v-if="pipelineFields.length > 0"
            class="bg-white dark:bg-gray-800 rounded-2xl border border-indigo-100 dark:border-indigo-900/30 p-4"
          >
            <div class="flex items-center gap-1.5 mb-3">
              <svg class="w-4 h-4 text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z" />
              </svg>
              <span class="text-xs font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wide">{{ t('pipeline.fieldsTitle') }}</span>
            </div>

            <div class="space-y-3">
              <div
                v-for="field in pipelineFields"
                :key="field.field_key"
                class="group"
              >
                <div class="text-[10px] font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-0.5">
                  {{ getFieldLabel(field.field_key, field.label_override) }}
                </div>

                <!-- View mode (not editing) -->
                <template v-if="editingFieldKey !== field.field_key">
                  <div class="flex items-start justify-between gap-2">
                    <div
                      class="text-sm text-gray-800 dark:text-gray-200 break-words leading-snug"
                      :class="field.field_key === 'notes' ? 'whitespace-pre-wrap max-h-28 overflow-y-auto' : ''"
                    >
                      {{ getFieldDisplayValue(field.field_key) }}
                    </div>
                    <button
                      v-if="field.field_key !== 'origin_record'"
                      class="hidden group-hover:flex flex-shrink-0 items-center gap-0.5 text-[10px] text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors mt-0.5"
                      :title="t('pipeline.fieldEdit')"
                      @click="startFieldEdit(field.field_key)"
                    >
                      <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
                      </svg>
                    </button>
                  </div>
                  <div v-if="field.help_text_override" class="text-[10px] text-gray-400 mt-0.5 italic">
                    {{ field.help_text_override }}
                  </div>
                </template>

                <!-- Edit mode -->
                <template v-else>
                  <!-- expires_at -->
                  <div v-if="field.field_key === 'expires_at'" class="flex flex-col gap-1.5">
                    <input
                      v-model="fieldEditValues['expires_at']"
                      type="date"
                      class="w-full rounded-lg border border-indigo-300 dark:border-indigo-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
                    />
                  </div>

                  <!-- date_range -->
                  <div v-else-if="field.field_key === 'date_range'" class="flex gap-2">
                    <div class="flex-1">
                      <div class="text-[10px] text-gray-400 mb-0.5">{{ t('pipeline.fieldStartDate') }}</div>
                      <input
                        v-model="fieldEditValues['start_date']"
                        type="date"
                        class="w-full rounded-lg border border-indigo-300 dark:border-indigo-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      />
                    </div>
                    <div class="flex-1">
                      <div class="text-[10px] text-gray-400 mb-0.5">{{ t('pipeline.fieldEndDate') }}</div>
                      <input
                        v-model="fieldEditValues['end_date']"
                        type="date"
                        class="w-full rounded-lg border border-indigo-300 dark:border-indigo-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
                      />
                    </div>
                  </div>

                  <!-- notes -->
                  <div v-else-if="field.field_key === 'notes'">
                    <textarea
                      v-model="fieldEditValues['notes']"
                      rows="4"
                      class="w-full rounded-lg border border-indigo-300 dark:border-indigo-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2.5 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-y"
                    />
                  </div>

                  <div class="flex gap-2 mt-1.5">
                    <button
                      :disabled="savingField"
                      class="px-3 py-1 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
                      @click="saveFieldEdit(field.field_key)"
                    >
                      {{ savingField ? t('pipeline.fieldSaving') : t('pipeline.fieldSaveBtn') }}
                    </button>
                    <button
                      class="px-3 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                      @click="cancelFieldEdit"
                    >
                      {{ t('pipeline.cancel') }}
                    </button>
                  </div>
                  <p v-if="fieldEditError && editingFieldKey === field.field_key" class="mt-1 text-xs text-red-600 dark:text-red-400">
                    {{ fieldEditError }}
                  </p>
                </template>

                <div class="border-t border-gray-100 dark:border-gray-700/50 mt-3 last:hidden" />
              </div>
            </div>
          </div>

          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
            <!-- Record title as prominent heading -->
            <h2 class="text-base font-bold text-gray-900 dark:text-gray-100 mb-3 leading-tight">
              {{ store.currentRecord.title }}
            </h2>
            <dl class="space-y-2">
              <div class="flex justify-between items-center">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('recordDetail.overviewStatus') }}</dt>
                <dd class="relative">
                  <button
                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors"
                    :class="getStatusMeta(store.currentRecord.status).color"
                    @click="statusPopupOpen = !statusPopupOpen"
                  >
                    {{ getStatusMeta(store.currentRecord.status).label }}
                    <ChevronDownIcon class="w-3 h-3 opacity-60" />
                  </button>
                  <div
                    v-if="statusPopupOpen"
                    class="absolute right-0 top-8 z-10 w-44 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1"
                  >
                    <button
                      v-for="s in RECORD_STATUSES"
                      :key="s.value"
                      class="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
                      :class="s.value === store.currentRecord.status ? 'font-semibold' : ''"
                      @click="changeStatus(s.value)"
                    >
                      <span class="w-2 h-2 rounded-full flex-shrink-0" :class="s.color.split(' ')[0]" />
                      {{ s.label }}
                    </button>
                  </div>
                </dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('recordDetail.overviewSource') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">{{ store.currentRecord.source.replace('_', ' ') }}</dd>
              </div>
              <div v-if="store.currentRecord.value != null" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('recordDetail.overviewValue') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ store.currentRecord.value }} {{ store.currentRecord.currency }}</dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('recordDetail.overviewCreated') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ new Date(store.currentRecord.created_at).toLocaleDateString() }}</dd>
              </div>
              <div v-if="store.currentRecord.company_name" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">Společnost</dt>
                <dd
                  class="text-sm font-medium text-gray-900 dark:text-gray-100 text-right truncate max-w-[10rem] cursor-pointer hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  @click="openContactDetail(store.currentRecord.company_id)"
                >
                  {{ store.currentRecord.company_name }}
                </dd>
              </div>
              <div v-if="store.currentRecord.contact_person_name" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">Kontaktní osoba</dt>
                <dd
                  class="text-sm font-medium text-gray-900 dark:text-gray-100 text-right truncate max-w-[10rem] cursor-pointer hover:text-red-600 dark:hover:text-red-400 transition-colors"
                  @click="openContactDetail(store.currentRecord.contact_person_id)"
                >
                  {{ store.currentRecord.contact_person_name }}
                </dd>
              </div>
              <!-- Inline-editable description -->
            </dl>
            <div class="flex gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
              <button class="flex-1 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="openEdit">{{ t('recordDetail.edit') }}</button>
              <button class="px-3 py-1.5 rounded-xl border border-red-200 dark:border-red-800 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30" @click="deleteRecord">{{ t('recordDetail.delete') }}</button>
            </div>
          </div>

          <!-- Quick actions card -->
          <EntitySidebarActionPicker
            ref="sidebarPickerRef"
            entity-type="record"
            :entity-id="leadId"
            @tool-selected="openModalTool"
          />

        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400">{{ t('recordDetail.notFound') }}</div>
  </div>

  <!-- Streamline Create Modal — opened from sidebar picker and Akce button -->
  <StreamlineCreateModal
    :model-value="!!activeModalTool"
    :action-type="activeModalTool"
    entity-type="record"
    :entity-id="leadId"
    :team-members="teamMembers"
    :attachment-upload-url="`/api/v1/crm/records/${leadId}/attachments`"
    @update:model-value="(v) => { if (!v) closeModalTool() }"
    @activity-added="activityTimelineRef?.load()"
    @file-uploaded="(f) => { files.unshift(f as any) }"
  />

  <!-- Edit Modal -->
  <Teleport to="body">
    <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showEditModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" aria-labelledby="edit-record-title">
        <h3 id="edit-record-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('recordDetail.editTitle') }}</h3>
        <div v-if="editError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ editError }}</div>
        <form class="space-y-3" @submit.prevent="submitEdit">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('recordDetail.editFormTitle') }}</label>
            <input v-model="editTitle" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>

          <!-- Company & Contact Person Selection -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Společnost</label>
              <select
                v-model="editCompanyId"
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
                v-model="editContactPersonId"
                :disabled="!editCompanyId"
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
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('recordDetail.editFormStatus') }}</label>
              <select v-model="editStatus" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option v-for="s in RECORD_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('recordDetail.editFormSource') }}</label>
              <select v-model="editSource" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
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
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('recordDetail.editFormValue') }}</label>
              <input v-model="editValue" type="number" min="0" step="0.01" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('recordDetail.editFormCurrency') }}</label>
              <input v-model="editCurrency" type="text" maxlength="3" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showEditModal = false">{{ t('recordDetail.editCancel') }}</button>
            <button type="submit" :disabled="editLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ editLoading ? t('recordDetail.editSaving') : t('recordDetail.editSave') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Contact Detail Modal -->
  <Teleport to="body">
    <div v-if="showContactModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showContactModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6 relative" role="dialog" aria-modal="true" aria-label="Contact Details">
        <button
          class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
          @click="showContactModal = false"
        ><XMarkIcon class="w-5 h-5" /></button>

        <h3 class="text-lg font-bold text-gray-900 dark:text-gray-100 mb-4">Detail kontaktu</h3>

        <div v-if="loadingContactDetail" class="animate-pulse space-y-3">
          <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4" />
          <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
          <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-2/3" />
        </div>

        <div v-else-if="selectedContact" class="space-y-3 text-sm text-gray-700 dark:text-gray-300">
          <div v-if="selectedContact.company_name" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">Název firmy</span>
            <span class="font-semibold text-gray-900 dark:text-gray-100 text-right">{{ selectedContact.company_name }}</span>
          </div>
          <div v-if="selectedContact.first_name || selectedContact.last_name" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">Jméno</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">
              {{ [selectedContact.first_name, selectedContact.last_name].filter(Boolean).join(' ') }}
            </span>
          </div>
          <div v-if="selectedContact.email" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">E-mail</span>
            <a :href="`mailto:${selectedContact.email}`" class="text-red-600 dark:text-red-400 hover:underline text-right">{{ selectedContact.email }}</a>
          </div>
          <div v-if="selectedContact.phone" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">Telefon</span>
            <a :href="`tel:${selectedContact.phone}`" class="text-red-600 dark:text-red-400 hover:underline text-right">{{ selectedContact.phone }}</a>
          </div>
          <div v-if="selectedContact.website" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">Web</span>
            <a :href="selectedContact.website" target="_blank" class="text-red-600 dark:text-red-400 hover:underline text-right">{{ selectedContact.website }}</a>
          </div>
          <div v-if="selectedContact.ico" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">IČO</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">{{ selectedContact.ico }}</span>
          </div>
          <div v-if="selectedContact.dic" class="flex justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
            <span class="text-xs text-gray-400">DIČ</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">{{ selectedContact.dic }}</span>
          </div>
          <div v-if="selectedContact.address_street || selectedContact.address_city" class="flex flex-col border-b border-gray-100 dark:border-gray-800 pb-2 gap-1">
            <span class="text-xs text-gray-400">Adresa</span>
            <span class="font-medium text-gray-900 dark:text-gray-100 text-right">
              {{ [selectedContact.address_street, selectedContact.address_city, selectedContact.address_zip].filter(Boolean).join(', ') }}
            </span>
          </div>
        </div>

        <div v-else class="text-center text-sm text-gray-500 py-4">Kontakt nebyl nalezen.</div>

        <div class="flex pt-4">
          <button
            class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 transition-colors"
            @click="showContactModal = false"
          >Zavřít</button>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Status popup backdrop -->
  <div v-if="statusPopupOpen" class="fixed inset-0 z-5" @click="statusPopupOpen = false" />

  <!-- Akce dropdown backdrop -->
  <div v-if="akceDropdownOpen" class="fixed inset-0 z-20" @click="closeAkceDropdown" />

  <ConfirmDeleteModal
    :open="!!confirmDeleteAttachmentId"
    @confirm="doDeleteFile(confirmDeleteAttachmentId!); confirmDeleteAttachmentId = null"
    @cancel="confirmDeleteAttachmentId = null"
  />
</template>

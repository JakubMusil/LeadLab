<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLeadsStore, LEAD_STATUSES, getStatusMeta } from '@/stores/leads'
import { useToast } from '@/composables/useToast'
import { useWebSocket } from '@/composables/useWebSocket'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import DOMPurify from 'dompurify'
import {
  ChatBubbleLeftIcon,
  PhoneIcon,
  UsersIcon,
  PaperAirplaneIcon,
  InboxArrowDownIcon,
  ClipboardDocumentListIcon,
  CheckIcon,
  CheckCircleIcon,
  CalendarDaysIcon,
  UserIcon,
  BellIcon,
  TrashIcon,
  DocumentIcon,
  DocumentTextIcon,
  DocumentCheckIcon,
  ArrowsRightLeftIcon,
  CloudArrowUpIcon,
  PaperClipIcon,
  ChevronDownIcon,
} from '@heroicons/vue/24/outline'

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

// Map icon name strings (from the Streamline Tool Registry) to Heroicon components
const heroIconMap: Record<string, Component> = {
  ChatBubbleLeftIcon,
  PhoneIcon,
  UsersIcon,
  PaperAirplaneIcon,
  InboxArrowDownIcon,
  ArrowsRightLeftIcon,
  PaperClipIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  DocumentCheckIcon,
}

// Map activity_type to an i18n translation key (preserves multi-language support)
const activityTypeLabelKey: Record<string, string> = {
  comment: 'leadDetail.typeComment',
  call: 'leadDetail.typeCall',
  meeting: 'leadDetail.typeMeeting',
  email_out: 'leadDetail.typeEmailOut',
  email_in: 'leadDetail.typeEmailIn',
}

const route = useRoute()
const router = useRouter()
const store = useLeadsStore()
const toast = useToast()
const firmStore = useFirmStore()
const authStore = useAuthStore()
const { on, off } = useWebSocket()
const { t } = useI18n()

const leadId = computed(() => route.params.id as string)
type Tab = 'overview' | 'tasks' | 'files' | 'proposals'
const activeTab = ref<Tab>('overview')

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

// Streamline Tool Registry — loaded from the backend on mount
interface StreamlineTool {
  activity_type: string
  label: string
  icon: string
  form_schema: {
    type: string
    properties?: Record<string, unknown>
    required?: string[]
  }
}
const streamlineTools = ref<StreamlineTool[]>([])
// Toolbar tools for lead entity — loaded from the entity-toolbar registry endpoint
const leadToolbarTools = ref<StreamlineTool[]>([])

async function loadStreamlineTools() {
  const [toolsRes, toolbarRes] = await Promise.all([
    api.get<StreamlineTool[]>('/api/v1/streamline/tools'),
    api.get<StreamlineTool[]>('/api/v1/streamline/entity-toolbar/lead'),
  ])
  if (toolsRes.ok) streamlineTools.value = toolsRes.data
  if (toolbarRes.ok) leadToolbarTools.value = toolbarRes.data
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
  parent_task_id?: string | null
  subtask_count?: number
  subtasks_completed?: number
  checklist_count?: number
  checklist_checked?: number
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

// Sidebar quick-action composer
const sidebarActionType = ref('')
const sidebarActivityText = ref('')
const sidebarActivitySubmitting = ref(false)
const sidebarRichEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const sidebarTaskTitle = ref('')
const sidebarTaskDueDate = ref('')
const sidebarTaskAssigneeId = ref('')
const sidebarTaskWatcherIds = ref<string[]>([])
const sidebarTaskDescription = ref('')
const sidebarTaskEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const sidebarTaskSubmitting = ref(false)

// Extra metadata fields rendered from the tool's form_schema (all props except content_text / mentions)
const sidebarExtraFields = ref<Record<string, unknown>>({})

// Fields that appear ABOVE the rich-text body (e.g. email subject / recipient)
const TOP_FIELD_KEYS = new Set(['subject', 'to', 'from_address'])
// Fields that are auto-populated by integrations and should not appear in the manual form
const SKIP_FIELD_KEYS = new Set(['content_text', 'mentions', 'recording_filename', 'recording_size_bytes'])

interface SchemaProp {
  key: string
  title: string
  type: string
  format?: string
  enum?: string[]
  minimum?: number
}

const sidebarSchemaPropsAll = computed<SchemaProp[]>(() => {
  const tool = leadToolbarTools.value.find((t) => t.activity_type === sidebarActionType.value)
  if (!tool?.form_schema?.properties) return []
  return Object.entries(tool.form_schema.properties as Record<string, Record<string, unknown>>)
    .filter(([key]) => !SKIP_FIELD_KEYS.has(key))
    .map(([key, schema]) => ({
      key,
      title: (schema.title as string) || key,
      type: (schema.type as string) || 'string',
      format: schema.format as string | undefined,
      enum: schema.enum as string[] | undefined,
      minimum: schema.minimum as number | undefined,
    }))
})

// Fields shown BEFORE the rich-text editor (email header-like fields)
const sidebarSchemaPropsTop = computed(() =>
  sidebarSchemaPropsAll.value.filter((p) => TOP_FIELD_KEYS.has(p.key)),
)
// Fields shown AFTER the rich-text editor (call duration, recording URL, transcript, etc.)
const sidebarSchemaPropsBottom = computed(() =>
  sidebarSchemaPropsAll.value.filter((p) => !TOP_FIELD_KEYS.has(p.key)),
)

// Whether the current tool schema includes a content_text field (rendered by RichTextEditor)
const sidebarToolHasContentText = computed(() => {
  const tool = leadToolbarTools.value.find((t) => t.activity_type === sidebarActionType.value)
  return !!(tool?.form_schema?.properties as Record<string, unknown> | undefined)?.content_text
})

const sidebarHasPlainText = computed(() =>
  Boolean(sidebarActivityText.value.replace(/<[^>]*>/g, '').trim()),
)

// Whether the currently selected sidebar action type requires content_text
const sidebarToolRequiresText = computed(() => {
  const tool = leadToolbarTools.value.find((t) => t.activity_type === sidebarActionType.value)
  return tool?.form_schema.required?.includes('content_text') ?? false
})

function sidebarRequiresField(key: string): boolean {
  const tool = leadToolbarTools.value.find((t) => t.activity_type === sidebarActionType.value)
  return tool?.form_schema.required?.includes(key) ?? false
}

const sidebarSubmitDisabled = computed(() => {
  if (sidebarActivitySubmitting.value) return true
  if (sidebarToolRequiresText.value && !sidebarHasPlainText.value) return true
  // Check that all required non-content_text fields are filled
  const tool = leadToolbarTools.value.find((t) => t.activity_type === sidebarActionType.value)
  for (const key of (tool?.form_schema.required ?? [])) {
    if (key === 'content_text') continue
    const val = sidebarExtraFields.value[key]
    if (val === undefined || val === null || val === '') return true
  }
  return false
})

function openSidebarAction(type: string) {
  sidebarActionType.value = type
  sidebarActivityText.value = ''
  sidebarExtraFields.value = {}
}

function closeSidebarAction() {
  sidebarActionType.value = ''
  sidebarExtraFields.value = {}
}

// Build action items directly from the Lead entity-toolbar registry.
// The backend Lead.TOOLBAR_TOOLS class attribute controls which tools appear
// and in what order — no front-end filtering/hard-coding needed.
const sidebarActionItems = computed<{ value: string; label: string; icon: Component }[]>(() => {
  return leadToolbarTools.value.map((tool) => {
    const i18nKey = activityTypeLabelKey[tool.activity_type]
    return {
      value: tool.activity_type,
      label: i18nKey ? t(i18nKey) : tool.label,
      icon: heroIconMap[tool.icon] ?? ClipboardDocumentListIcon,
    }
  })
})

const sidebarActionIcon = computed(
  () => sidebarActionItems.value.find((i) => i.value === sidebarActionType.value)?.icon ?? ClipboardDocumentListIcon,
)

// Files
interface FileItem { id: string; original_filename: string; content_type: string; size_bytes: number; url: string; created_at: string }
const files = ref<FileItem[]>([])
const filesLoading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadingFile = ref(false)
const uploadProgress = ref(0)
const isDraggingOver = ref(false)

// Edit form
const showEditModal = ref(false)
const editTitle = ref('')
const editDescription = ref('')
const editStatus = ref('')
const editSource = ref('')
const editValue = ref('')
const editCurrency = ref('')
const editError = ref('')
const editLoading = ref(false)
const statusPopupOpen = ref(false)

// Inline description editing
const editingDescription = ref(false)
const inlineDescription = ref('')
const descriptionEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const savingDescription = ref(false)

function startEditDescription() {
  inlineDescription.value = store.currentLead?.description ?? ''
  editingDescription.value = true
}

async function saveDescription() {
  if (!store.currentLead) return
  savingDescription.value = true
  const result = await store.updateLead(leadId.value, { description: inlineDescription.value })
  savingDescription.value = false
  if (result.ok) {
    editingDescription.value = false
    toast.success(t('leadDetail.updated'))
  } else {
    toast.error(result.error ?? t('leadDetail.failedToUpdate'))
  }
}

function cancelEditDescription() {
  editingDescription.value = false
}

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const res = await api.get<Task[]>(`/api/v1/crm/tasks?page_size=100`)
    if (res.ok) {
      tasks.value = res.data.filter(
        (task) => task.lead_id === leadId.value && !task.parent_task_id,
      )
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
    const res = await api.get<FileItem[]>(`/api/v1/crm/opportunities/${leadId.value}/attachments?page_size=50`)
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
    toast.success(t('leadDetail.taskCreated'))
  } else {
    toast.error(t('leadDetail.taskFailed'))
  }
}

function toggleTaskWatcher(userId: string) {
  const idx = newTaskWatcherIds.value.indexOf(userId)
  if (idx !== -1) newTaskWatcherIds.value.splice(idx, 1)
  else newTaskWatcherIds.value.push(userId)
}

async function completeTask(id: string) {
  const res = await api.post<Task>(`/api/v1/crm/tasks/${id}/complete`)
  if (res.ok) {
    const idx = tasks.value.findIndex((task) => task.id === id)
    if (idx !== -1) tasks.value[idx] = res.data
    toast.success(t('leadDetail.taskCompleted'))
  } else {
    toast.error(t('leadDetail.taskCompleteFailed'))
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
    xhr.open('POST', `/api/v1/crm/opportunities/${leadId.value}/attachments`)
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
          toast.success(t('leadDetail.fileUploaded'))
        } catch {
          toast.error('Upload response parse error.')
        }
      } else {
        toast.error(t('leadDetail.fileUploadFailed'))
      }
      resolve()
    }
    xhr.onerror = () => {
      uploadingFile.value = false
      uploadProgress.value = 0
      toast.error(t('leadDetail.fileUploadFailed'))
      resolve()
    }
    xhr.send(fd)
  })
}

async function deleteFile(id: string) {
  const res = await api.delete(`/api/v1/crm/opportunities/${leadId.value}/attachments/${id}`)
  if (res.ok || res.status === 204) {
    files.value = files.value.filter((f) => f.id !== id)
    toast.success('File deleted.')
  } else {
    toast.error('Failed to delete file.')
  }
}

async function changeStatus(newStatus: string) {
  statusPopupOpen.value = false
  const result = await store.patchStatus(leadId.value, newStatus)
  if (!result.ok) toast.error(result.error ?? 'Failed to update status.')
  else activityTimelineRef.value?.load()
}

async function sidebarAddActivity() {
  if (sidebarToolRequiresText.value && !sidebarHasPlainText.value) return
  sidebarActivitySubmitting.value = true
  const mentionedIds = sidebarActionType.value === 'comment'
    ? (sidebarRichEditorRef.value?.getMentionedIds() ?? [])
    : []
  const metadata: Record<string, unknown> = {
    ...sidebarExtraFields.value,
    ...(mentionedIds.length ? { mentions: mentionedIds } : {}),
  }
  const res = await api.post('/api/v1/crm/activities', {
    lead_id: leadId.value,
    type: sidebarActionType.value,
    content_text: sidebarActivityText.value,
    metadata,
  })
  sidebarActivitySubmitting.value = false
  if (res.ok) {
    sidebarActivityText.value = ''
    sidebarActionType.value = ''
    sidebarExtraFields.value = {}
    activityTimelineRef.value?.load()
    toast.success(t('leadDetail.activityAdded'))
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

function defaultSidebarTaskAssigneeId(): string {
  return authStore.user ? String(authStore.user.id) : ''
}

async function sidebarAddTask() {
  if (!sidebarTaskTitle.value.trim()) return
  sidebarTaskSubmitting.value = true
  const payload: Record<string, unknown> = {
    lead_id: leadId.value,
    title: sidebarTaskTitle.value.trim(),
    assigned_to_id: sidebarTaskAssigneeId.value || null,
    watcher_ids: sidebarTaskWatcherIds.value,
  }
  if (sidebarTaskDueDate.value) payload.due_date = new Date(sidebarTaskDueDate.value).toISOString()
  const res = await api.post('/api/v1/crm/tasks', payload)
  if (res.ok) {
    // If a description was entered, post it as the first comment on the lead timeline
    const descText = sidebarTaskDescription.value
    if (descText && descText.replace(/<[^>]*>/g, '').trim()) {
      const mentionedIds = sidebarTaskEditorRef.value?.getMentionedIds() ?? []
      const metadata: Record<string, unknown> = mentionedIds.length ? { mentions: mentionedIds } : {}
      await api.post('/api/v1/crm/activities', {
        lead_id: leadId.value,
        type: 'comment',
        content_text: descText,
        metadata,
      })
    }
    sidebarTaskTitle.value = ''
    sidebarTaskDueDate.value = ''
    sidebarTaskAssigneeId.value = defaultSidebarTaskAssigneeId()
    sidebarTaskWatcherIds.value = []
    sidebarTaskDescription.value = ''
    sidebarActionType.value = ''
    activityTimelineRef.value?.load()
    toast.success(t('leadDetail.taskCreated'))
  } else {
    toast.error(t('leadDetail.taskFailed'))
  }
  sidebarTaskSubmitting.value = false
}

function toggleSidebarTaskWatcher(userId: string) {
  const idx = sidebarTaskWatcherIds.value.indexOf(userId)
  if (idx !== -1) sidebarTaskWatcherIds.value.splice(idx, 1)
  else sidebarTaskWatcherIds.value.push(userId)
}

function openEdit() {
  const lead = store.currentLead
  if (!lead) return
  editTitle.value = lead.title
  editDescription.value = lead.description
  editStatus.value = lead.status
  editSource.value = lead.source
  editValue.value = lead.value != null ? String(lead.value) : ''
  editCurrency.value = lead.currency
  editError.value = ''
  showEditModal.value = true
}

async function submitEdit() {
  if (!editTitle.value.trim()) { editError.value = t('leadDetail.editTitleRequired'); return }
  editLoading.value = true
  const result = await store.updateLead(leadId.value, {
    title: editTitle.value.trim(),
    description: editDescription.value,
    status: editStatus.value,
    source: editSource.value,
    value: editValue.value ? parseFloat(editValue.value) : null,
    currency: editCurrency.value,
  })
  editLoading.value = false
  if (result.ok) {
    showEditModal.value = false
    toast.success(t('leadDetail.updated'))
  } else {
    editError.value = result.error ?? 'Failed to update.'
  }
}

async function deleteLead() {
  const result = await store.deleteLead(leadId.value)
  if (result.ok) {
    toast.success(t('leadDetail.deleted'))
    router.push('/app/opportunities')
  } else {
    toast.error(result.error ?? 'Failed to delete.')
  }
}

onMounted(async () => {
  await store.fetchLead(leadId.value)
  loadTeamMembers()
  await loadStreamlineTools()
  if (activeTab.value === 'tasks') await loadTasks()
  else if (activeTab.value === 'files') await loadFiles()

  // Default sidebar task assignee = currently logged-in user
  sidebarTaskAssigneeId.value = defaultSidebarTaskAssigneeId()

  on('lead.updated', onWsLeadUpdated)
})

onUnmounted(() => {
  off('lead.updated', onWsLeadUpdated)
})

function onWsLeadUpdated(_payload: Record<string, unknown>) {
  // The leads store is already updated by AppShell's WS handler; currentLead
  // is a shared Pinia ref so the UI re-renders automatically.
}

async function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'tasks' && tasks.value.length === 0) await loadTasks()
  else if (tab === 'files' && files.value.length === 0) await loadFiles()
  else if (tab === 'proposals') router.push(`/app/opportunities/${leadId.value}/proposals`)
}

function getTabLabel(tab: string): string {
  const keyMap: Record<string, string> = {
    overview: 'leadDetail.tabOverview',
    tasks: 'leadDetail.tabTasks',
    files: 'leadDetail.tabFiles',
  }
  const key = keyMap[tab]
  return key ? t(key) : tab.charAt(0).toUpperCase() + tab.slice(1)
}
</script>

<template>
  <div class="p-6">
    <!-- Back -->
    <RouterLink to="/app/opportunities" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4">
      {{ t('leadDetail.backToLeads') }}
    </RouterLink>

    <!-- Loading skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-64" />
      <div class="h-24 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="store.currentLead">
      <!-- Tabs -->
      <div class="flex gap-1 mb-4 bg-gray-100 rounded-xl p-1 w-fit">
        <button
          v-for="tab in (['overview', 'tasks', 'files', 'proposals'] as Tab[])"
          :key="tab"
          class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize"
          :class="activeTab === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="switchTab(tab)"
        >{{ getTabLabel(tab) }}</button>
      </div>

      <!-- OVERVIEW TAB: 2-column layout (stream + sidebar) -->
      <div v-if="activeTab === 'overview'" class="grid grid-cols-1 lg:grid-cols-3 gap-6">

        <!-- Main: chronological activity stream with filter -->
        <div class="lg:col-span-2">
          <ActivityTimeline
            ref="activityTimelineRef"
            :hide-composer="true"
            entity-type="lead"
            :entity-id="leadId"
          />
        </div>

        <!-- Sidebar: lead details + quick actions -->
        <div class="space-y-4">

          <!-- Lead details card (shown first) -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
            <!-- Lead title as prominent heading (replaces "Detaily příležitosti" label) -->
            <h2 class="text-base font-bold text-gray-900 dark:text-gray-100 mb-3 leading-tight">
              {{ store.currentLead.title }}
            </h2>
            <dl class="space-y-2">
              <div class="flex justify-between items-center">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('leadDetail.overviewStatus') }}</dt>
                <dd class="relative">
                  <button
                    class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors"
                    :class="getStatusMeta(store.currentLead.status).color"
                    @click="statusPopupOpen = !statusPopupOpen"
                  >
                    {{ getStatusMeta(store.currentLead.status).label }}
                    <ChevronDownIcon class="w-3 h-3 opacity-60" />
                  </button>
                  <div
                    v-if="statusPopupOpen"
                    class="absolute right-0 top-8 z-10 w-44 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1"
                  >
                    <button
                      v-for="s in LEAD_STATUSES"
                      :key="s.value"
                      class="w-full text-left px-3 py-1.5 text-xs text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
                      :class="s.value === store.currentLead.status ? 'font-semibold' : ''"
                      @click="changeStatus(s.value)"
                    >
                      <span class="w-2 h-2 rounded-full flex-shrink-0" :class="s.color.split(' ')[0]" />
                      {{ s.label }}
                    </button>
                  </div>
                </dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('leadDetail.overviewSource') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 capitalize">{{ store.currentLead.source.replace('_', ' ') }}</dd>
              </div>
              <div v-if="store.currentLead.value != null" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('leadDetail.overviewValue') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ store.currentLead.value }} {{ store.currentLead.currency }}</dd>
              </div>
              <div class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('leadDetail.overviewCreated') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ new Date(store.currentLead.created_at).toLocaleDateString() }}</dd>
              </div>
              <div v-if="store.currentLead.created_by_name" class="flex justify-between items-baseline">
                <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('leadDetail.overviewCreatedBy') }}</dt>
                <dd class="text-sm font-medium text-gray-900 dark:text-gray-100 text-right truncate max-w-[10rem]">{{ store.currentLead.created_by_name }}</dd>
              </div>
              <!-- Inline-editable description -->
              <div class="pt-2 border-t border-gray-100 dark:border-gray-700">
                <div class="flex items-center justify-between mb-1">
                  <dt class="text-xs text-gray-500 dark:text-gray-400">{{ t('leadDetail.description') }}</dt>
                  <button
                    v-if="!editingDescription"
                    class="text-[10px] text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                    @click="startEditDescription"
                  >{{ t('leadDetail.edit') }}</button>
                </div>
                <template v-if="editingDescription">
                  <RichTextEditor
                    ref="descriptionEditorRef"
                    v-model="inlineDescription"
                    :members="teamMembers"
                    :upload-url="`/api/v1/crm/opportunities/${leadId}/attachments`"
                    :placeholder="t('leadDetail.descriptionPlaceholder')"
                    @file-uploaded="(f) => { files.unshift(f) }"
                  />
                  <div class="flex justify-end gap-2 mt-1.5">
                    <button
                      class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                      @click="cancelEditDescription"
                    >{{ t('leadDetail.editCancel') }}</button>
                    <button
                      :disabled="savingDescription"
                      class="px-3 py-1 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                      @click="saveDescription"
                    >{{ savingDescription ? t('leadDetail.saving') : t('leadDetail.save') }}</button>
                  </div>
                </template>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <dd v-else-if="store.currentLead.description" class="text-xs text-gray-700 dark:text-gray-300 prose prose-xs dark:prose-invert max-w-none" v-html="sanitizeHtml(store.currentLead.description)" />
                <dd v-else class="text-xs text-gray-400 dark:text-gray-500 italic cursor-pointer hover:text-gray-600 dark:hover:text-gray-300" @click="startEditDescription">
                  {{ t('leadDetail.descriptionPlaceholder') }}
                </dd>
              </div>
            </dl>
            <div class="flex gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
              <button class="flex-1 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="openEdit">{{ t('leadDetail.edit') }}</button>
              <button class="px-3 py-1.5 rounded-xl border border-red-200 dark:border-red-800 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30" @click="deleteLead">{{ t('leadDetail.delete') }}</button>
            </div>
          </div>

          <!-- Quick actions card -->
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
            <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
              {{ t('leadDetail.quickActions') }}
            </p>

            <!-- Step 1: action type picker -->
            <div v-if="!sidebarActionType" class="flex flex-col gap-1.5">
              <button
                v-for="item in sidebarActionItems"
                :key="item.value"
                class="flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:border-red-400 hover:text-red-600 dark:hover:text-red-400 transition-colors text-left"
                @click="openSidebarAction(item.value)"
              >
                <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
                {{ item.label }}
              </button>
            </div>

            <!-- Step 2a: activity form (comment / call / meeting / email etc.) -->
            <div v-else-if="sidebarActionType !== 'task'" class="space-y-2">
              <div class="flex items-center gap-2 mb-2">
                <component :is="sidebarActionIcon" class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {{ sidebarActionItems.find(i => i.value === sidebarActionType)?.label }}
                </span>
                <button
                  class="ml-auto text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                  @click="closeSidebarAction"
                >← {{ t('leadDetail.changeType') }}</button>
              </div>

              <!-- "Header" fields: subject, to, from_address — shown above the message body -->
              <template v-for="prop in sidebarSchemaPropsTop" :key="prop.key">
                <div>
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ prop.title }}<span v-if="sidebarRequiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
                  </label>
                  <input
                    v-model="sidebarExtraFields[prop.key]"
                    :type="prop.format === 'email' ? 'email' : prop.format === 'uri' ? 'url' : 'text'"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  />
                </div>
              </template>

              <!-- Message body (rich text) — only when tool schema includes content_text -->
              <RichTextEditor
                v-if="sidebarToolHasContentText"
                ref="sidebarRichEditorRef"
                v-model="sidebarActivityText"
                :placeholder="sidebarActionType === 'comment' ? t('leadDetail.commentPlaceholder') : t('leadDetail.notePlaceholder')"
                :disabled="sidebarActivitySubmitting"
                :members="sidebarActionType === 'comment' ? teamMembers : []"
                :upload-url="sidebarActionType === 'comment' ? `/api/v1/crm/opportunities/${leadId}/attachments` : undefined"
                @file-uploaded="(f) => { files.unshift(f) }"
              />

              <!-- "Footer" fields: duration, recording URL, transcript, etc. — shown below body -->
              <template v-for="prop in sidebarSchemaPropsBottom" :key="prop.key">
                <div>
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ prop.title }}<span v-if="sidebarRequiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
                  </label>
                  <!-- Numeric field (e.g. duration_minutes) -->
                  <input
                    v-if="prop.type === 'integer' || prop.type === 'number'"
                    v-model.number="sidebarExtraFields[prop.key]"
                    type="number"
                    :min="prop.minimum ?? 0"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  />
                  <!-- Enum select -->
                  <select
                    v-else-if="prop.enum"
                    v-model="sidebarExtraFields[prop.key]"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  >
                    <option value="">—</option>
                    <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <!-- Long text field (e.g. transcript) -->
                  <textarea
                    v-else-if="prop.key === 'transcript'"
                    v-model="sidebarExtraFields[prop.key]"
                    rows="3"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
                  />
                  <!-- Regular text / url / email input -->
                  <input
                    v-else
                    v-model="sidebarExtraFields[prop.key]"
                    :type="prop.format === 'email' ? 'email' : prop.format === 'uri' ? 'url' : 'text'"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  />
                </div>
              </template>

              <div class="flex justify-end">
                <button
                  :disabled="sidebarSubmitDisabled"
                  class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                  @click="sidebarAddActivity"
                >{{ sidebarActivitySubmitting ? '…' : t('leadDetail.activitySubmit') }}</button>
              </div>
            </div>

            <!-- Step 2b: task quick-create form -->
            <div v-else class="space-y-2">
              <div class="flex items-center gap-2 mb-2">
                <ClipboardDocumentListIcon class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('leadDetail.typeTask') }}</span>
                <button
                  class="ml-auto text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
                  @click="closeSidebarAction"
                >← {{ t('leadDetail.changeType') }}</button>
              </div>
              <input
                v-model="sidebarTaskTitle"
                type="text"
                :placeholder="t('leadDetail.taskTitle')"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
              <input
                v-model="sidebarTaskDueDate"
                type="date"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
              <div>
                <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.assignee') }}</label>
                <select
                  v-model="sidebarTaskAssigneeId"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
                >
                  <option value="">{{ t('tasks.noAssignee') }}</option>
                  <option v-for="m in teamMembers" :key="m.id" :value="m.id">{{ m.label }}</option>
                </select>
              </div>
              <div v-if="teamMembers.length">
                <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.watchers') }}</label>
                <div class="flex flex-wrap gap-1.5">
                  <label
                    v-for="m in teamMembers"
                    :key="m.id"
                    class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
                    :class="sidebarTaskWatcherIds.includes(m.id)
                      ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                      : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
                  >
                    <input type="checkbox" class="hidden" :checked="sidebarTaskWatcherIds.includes(m.id)" @change="toggleSidebarTaskWatcher(m.id)" />
                    <BellIcon class="w-3.5 h-3.5" /> {{ m.label }}
                  </label>
                </div>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                  {{ t('leadDetail.descriptionLabel') }}
                </label>
                <RichTextEditor
                  ref="sidebarTaskEditorRef"
                  v-model="sidebarTaskDescription"
                  :members="teamMembers"
                  :placeholder="t('leadDetail.addMentionPlaceholder')"
                  class="min-h-[60px]"
                />
              </div>
              <div class="flex justify-end">
                <button
                  :disabled="sidebarTaskSubmitting || !sidebarTaskTitle.trim()"
                  class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                  @click="sidebarAddTask"
                >{{ sidebarTaskSubmitting ? '…' : t('leadDetail.addTask') }}</button>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- TASKS TAB -->
      <div v-else-if="activeTab === 'tasks'" class="space-y-4">
        <div v-if="tasksLoading" class="animate-pulse space-y-2">
          <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>
        <div v-else-if="tasks.length === 0" class="text-center py-10 text-gray-400 text-sm">{{ t('leadDetail.noTasks') }}</div>
        <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
          <div v-for="task in tasks" :key="task.id">
            <!-- Root task row -->
            <div class="flex items-start gap-3 p-4">
              <button
                class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors mt-0.5"
                :class="task.is_completed ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300 hover:border-green-400'"
                :disabled="task.is_completed"
                @click="completeTask(task.id)"
              >
                <CheckIcon v-if="task.is_completed" class="w-3 h-3" />
              </button>
              <div class="flex-1 min-w-0">
                <p class="text-sm text-gray-900 dark:text-gray-100" :class="task.is_completed ? 'line-through text-gray-400' : ''">{{ task.title }}</p>
                <!-- eslint-disable-next-line vue/no-v-html -->
                <div v-if="task.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 prose prose-xs max-w-none" v-html="sanitizeHtml(task.description)" />
                <div class="flex flex-wrap gap-3 mt-1 text-xs">
                  <span v-if="task.due_date" class="inline-flex items-center gap-1" :class="!task.is_completed && new Date(task.due_date) < new Date() ? 'text-red-500 font-semibold' : 'text-gray-400'">
                    <CalendarDaysIcon class="w-3.5 h-3.5" />
                    {{ new Date(task.due_date).toLocaleDateString() }}
                  </span>
                  <span v-if="task.assigned_to_id" class="inline-flex items-center gap-1 text-blue-500">
                    <UserIcon class="w-3.5 h-3.5" />
                    {{ teamMembers.find(m => m.id === task.assigned_to_id)?.label ?? task.assigned_to_id }}
                  </span>
                  <span v-if="task.watcher_ids?.length" class="inline-flex items-center gap-1 text-gray-400 dark:text-gray-500">
                    <BellIcon class="w-3.5 h-3.5" />
                    {{ task.watcher_ids.length }}
                  </span>
                </div>
              </div>
              <!-- Expand/collapse button for tasks with subtasks or checklist -->
              <button
                v-if="(task.subtask_count ?? 0) > 0 || (task.checklist_count ?? 0) > 0"
                class="flex-shrink-0 flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors px-1.5 py-0.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                @click="toggleExpand(task.id)"
              >
                <ChevronDownIcon
                  class="w-3.5 h-3.5 transition-transform"
                  :class="expandedTasks.has(task.id) ? 'rotate-180' : ''"
                />
                <span v-if="(task.subtask_count ?? 0) > 0" class="tabular-nums">{{ task.subtasks_completed ?? 0 }}/{{ task.subtask_count }}</span>
                <span v-if="(task.checklist_count ?? 0) > 0 && (task.subtask_count ?? 0) > 0" class="text-gray-300">·</span>
                <span v-if="(task.checklist_count ?? 0) > 0" class="tabular-nums">{{ task.checklist_checked ?? 0 }}/{{ task.checklist_count }} ✓</span>
              </button>
            </div>

            <!-- Tree details (expanded) -->
            <div
              v-if="expandedTasks.has(task.id)"
              class="ml-8 mr-4 mb-3 border-l-2 border-gray-100 dark:border-gray-700 pl-4 space-y-3"
            >
              <div v-if="taskDetailsLoadingSet.has(task.id)" class="animate-pulse h-8 bg-gray-100 dark:bg-gray-700 rounded-lg" />
              <template v-else-if="taskDetailsMap.has(task.id)">
                <!-- Subtasks -->
                <div v-if="taskDetailsMap.get(task.id)!.subtasks.length > 0">
                  <p class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1.5">{{ t('tasks.subtasks') }}</p>
                  <div class="space-y-1">
                    <div
                      v-for="sub in taskDetailsMap.get(task.id)!.subtasks"
                      :key="sub.id"
                      class="flex items-center gap-2 text-sm"
                    >
                      <span
                        class="w-3.5 h-3.5 rounded-full border flex-shrink-0"
                        :class="sub.is_completed ? 'bg-green-400 border-green-400' : 'border-gray-300 dark:border-gray-600'"
                      />
                      <span :class="sub.is_completed ? 'line-through text-gray-400' : 'text-gray-700 dark:text-gray-300'">{{ sub.title }}</span>
                      <span v-if="sub.due_date" class="text-xs text-gray-400 ml-auto flex-shrink-0">{{ new Date(sub.due_date).toLocaleDateString() }}</span>
                    </div>
                  </div>
                </div>

                <!-- Checklist -->
                <div v-if="taskDetailsMap.get(task.id)!.checklist.length > 0">
                  <p class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1.5">{{ t('tasks.checklist') }}</p>
                  <div class="space-y-1">
                    <div
                      v-for="item in taskDetailsMap.get(task.id)!.checklist.slice().sort((a, b) => a.position - b.position)"
                      :key="item.id"
                      class="flex items-center gap-2 text-sm"
                    >
                      <span
                        class="w-3.5 h-3.5 rounded border flex-shrink-0 flex items-center justify-center text-white text-xs"
                        :class="item.is_checked ? 'bg-green-400 border-green-400' : 'border-gray-300 dark:border-gray-600'"
                      >{{ item.is_checked ? '✓' : '' }}</span>
                      <span :class="item.is_checked ? 'line-through text-gray-400' : 'text-gray-700 dark:text-gray-300'">{{ item.text }}</span>
                    </div>
                  </div>
                </div>

                <!-- Dependencies -->
                <div v-if="taskDetailsMap.get(task.id)!.dependencies.length > 0">
                  <p class="text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1.5">{{ t('tasks.dependencies') }}</p>
                  <div class="space-y-1">
                    <div
                      v-for="dep in taskDetailsMap.get(task.id)!.dependencies"
                      :key="dep.id"
                      class="flex items-center gap-2 text-sm"
                    >
                      <span class="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                        :class="dep.type === 'blocks'
                          ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400'
                          : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'"
                      >
                        {{ dep.type === 'blocks' ? t('tasks.dependencyBlocks') : t('tasks.dependencyRelatedTo') }}
                      </span>
                      <span class="text-gray-700 dark:text-gray-300 truncate">
                        {{ dep.from_task_id === task.id ? dep.to_task_title : dep.from_task_title }}
                      </span>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- FILES TAB -->
      <div v-else-if="activeTab === 'files'" class="space-y-4">
        <!-- Upload zone -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
          <div
            class="flex flex-col items-center justify-center border-2 border-dashed rounded-xl py-8 cursor-pointer transition-colors"
            :class="isDraggingOver
              ? 'border-red-400 bg-red-50 dark:bg-red-900/20'
              : 'border-gray-200 dark:border-gray-600 hover:border-red-300 dark:hover:border-red-500'"
            role="button"
            aria-label="File upload drop zone. Click or drag and drop files here."
            tabindex="0"
            @click="fileInput?.click()"
            @keydown.enter="fileInput?.click()"
            @dragover.prevent="isDraggingOver = true"
            @dragleave.prevent="isDraggingOver = false"
            @drop.prevent="onFileDrop"
          >
            <CloudArrowUpIcon class="w-10 h-10 mb-3" :class="isDraggingOver ? 'text-red-400' : 'text-gray-300 dark:text-gray-600'" aria-hidden="true" />
            <span class="text-sm font-medium" :class="isDraggingOver ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'">
              {{ isDraggingOver ? t('leadDetail.dropToUpload') : t('leadDetail.clickOrDrop') }}
            </span>
            <span class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('leadDetail.maxSize') }}</span>
            <input ref="fileInput" type="file" class="hidden" aria-hidden="true" @change="uploadFile" />
          </div>

          <!-- Progress bar -->
          <div v-if="uploadingFile" class="mt-3">
            <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
              <span>{{ t('leadDetail.uploading') }}</span>
              <span>{{ uploadProgress }}%</span>
            </div>
            <div class="w-full h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                class="h-full bg-red-500 rounded-full transition-all duration-200"
                :style="{ width: `${uploadProgress}%` }"
                role="progressbar"
                :aria-valuenow="uploadProgress"
                aria-valuemin="0"
                aria-valuemax="100"
              />
            </div>
          </div>
        </div>

        <div v-if="filesLoading" class="animate-pulse space-y-2">
          <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>
        <div v-else-if="files.length === 0" class="flex flex-col items-center justify-center py-12 text-center">
          <div class="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-3">
            <PaperClipIcon class="w-6 h-6 text-gray-400" aria-hidden="true" />
          </div>
          <p class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">{{ t('leadDetail.noFiles') }}</p>
          <p class="text-xs text-gray-400 dark:text-gray-500">{{ t('leadDetail.noFilesHint') }}</p>
        </div>
        <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
          <div v-for="file in files" :key="file.id" class="flex items-center gap-3 p-4 group">
            <!-- Image preview or file icon -->
            <div class="w-10 h-10 rounded-xl flex-shrink-0 overflow-hidden bg-gray-100 dark:bg-gray-700 flex items-center justify-center">
              <img
                v-if="file.content_type.startsWith('image/')"
                :src="file.url"
                :alt="file.original_filename"
                class="w-full h-full object-cover"
              />
              <DocumentIcon v-else class="w-5 h-5 text-gray-400" aria-hidden="true" />
            </div>
            <div class="flex-1 min-w-0">
              <a :href="file.url" target="_blank" rel="noopener noreferrer" class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 truncate block">{{ file.original_filename }}</a>
              <p class="text-xs text-gray-400 dark:text-gray-500">{{ fmtBytes(file.size_bytes) }} · {{ new Date(file.created_at).toLocaleDateString() }}</p>
            </div>
            <button
              class="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 transition-opacity"
              :aria-label="`Delete ${file.original_filename}`"
              @click="deleteFile(file.id)"
            >
              <TrashIcon class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400">{{ t('leadDetail.notFound') }}</div>
  </div>

  <!-- Edit Modal -->
  <Teleport to="body">
    <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showEditModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" aria-labelledby="edit-lead-title">
        <h3 id="edit-lead-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('leadDetail.editTitle') }}</h3>
        <div v-if="editError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ editError }}</div>
        <form class="space-y-3" @submit.prevent="submitEdit">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leadDetail.editFormTitle') }}</label>
            <input v-model="editTitle" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
            <textarea v-model="editDescription" rows="2" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leadDetail.editFormStatus') }}</label>
              <select v-model="editStatus" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option v-for="s in LEAD_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leadDetail.editFormSource') }}</label>
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
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leadDetail.editFormValue') }}</label>
              <input v-model="editValue" type="number" min="0" step="0.01" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('leadDetail.editFormCurrency') }}</label>
              <input v-model="editCurrency" type="text" maxlength="3" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showEditModal = false">{{ t('leadDetail.editCancel') }}</button>
            <button type="submit" :disabled="editLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ editLoading ? t('leadDetail.editSaving') : t('leadDetail.editSave') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Status popup backdrop -->
  <div v-if="statusPopupOpen" class="fixed inset-0 z-5" @click="statusPopupOpen = false" />
</template>

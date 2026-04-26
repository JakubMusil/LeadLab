<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLeadsStore, LEAD_STATUSES, getStatusMeta } from '@/stores/leads'
import { useToast } from '@/composables/useToast'
import { useWebSocket } from '@/composables/useWebSocket'
import { api } from '@/api'
import RichTextEditor from '@/components/RichTextEditor.vue'
import DOMPurify from 'dompurify'

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

function hasPlainText(html: string): boolean {
  return Boolean(html.replace(/<[^>]*>/g, '').trim())
}

const route = useRoute()
const router = useRouter()
const store = useLeadsStore()
const toast = useToast()
const { on, off } = useWebSocket()

const leadId = computed(() => route.params.id as string)
type Tab = 'overview' | 'activities' | 'tasks' | 'files'
const activeTab = ref<Tab>('overview')

// Activities
interface Activity { id: string; lead_id: string; type: string; content_text: string; metadata: Record<string, unknown>; created_at: string; user_id: string | null }
const activities = ref<Activity[]>([])
const activitiesLoading = ref(false)
const activitiesPage = ref(1)
const activitiesHasMore = ref(true)
const newActivityType = ref('comment')
const newActivityText = ref('')
const activitySubmitting = ref(false)

// Tasks
interface Task { id: string; lead_id: string; title: string; due_date: string | null; is_completed: boolean; created_at: string }
const tasks = ref<Task[]>([])
const tasksLoading = ref(false)
const newTaskTitle = ref('')
const newTaskDueDate = ref('')
const taskSubmitting = ref(false)

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

const activityIcons: Record<string, string> = {
  comment: '💬', email_out: '📧', email_in: '📥', call: '📞',
  meeting: '🤝', status_change: '🔄', file_upload: '📎',
  task_assigned: '📋', task_completed: '✅',
}

const activityTypes = [
  { value: 'comment', label: 'Comment' },
  { value: 'call', label: 'Call' },
  { value: 'meeting', label: 'Meeting' },
  { value: 'email_out', label: 'Email (Out)' },
  { value: 'email_in', label: 'Email (In)' },
]

function formatTime(ts: string) {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / (1024 * 1024)).toFixed(1)} MB`
}

async function loadActivities(page = 1) {
  activitiesLoading.value = true
  try {
    const res = await api.get<Activity[]>(`/api/v1/crm/leads/${leadId.value}/activities?page=${page}&page_size=20`)
    if (res.ok) {
      if (page === 1) activities.value = res.data
      else activities.value = [...activities.value, ...res.data]
      activitiesPage.value = page
      activitiesHasMore.value = res.data.length === 20
    }
  } finally {
    activitiesLoading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const res = await api.get<Task[]>(`/api/v1/crm/tasks?page_size=100`)
    if (res.ok) {
      tasks.value = res.data.filter((t) => t.lead_id === leadId.value)
    }
  } finally {
    tasksLoading.value = false
  }
}

async function loadFiles() {
  filesLoading.value = true
  try {
    const res = await api.get<FileItem[]>(`/api/v1/crm/leads/${leadId.value}/attachments?page_size=50`)
    if (res.ok) files.value = res.data
  } finally {
    filesLoading.value = false
  }
}

async function addActivity() {
  if (!hasPlainText(newActivityText.value) && newActivityType.value === 'comment') return
  activitySubmitting.value = true
  const res = await api.post<Activity>('/api/v1/crm/activities', {
    lead_id: leadId.value,
    type: newActivityType.value,
    content_text: newActivityText.value,
  })
  activitySubmitting.value = false
  if (res.ok) {
    activities.value.unshift(res.data)
    newActivityText.value = ''
    toast.success('Activity added.')
  } else {
    toast.error('Failed to add activity.')
  }
}

async function addTask() {
  if (!newTaskTitle.value.trim()) return
  taskSubmitting.value = true
  const payload: Record<string, unknown> = { lead_id: leadId.value, title: newTaskTitle.value.trim() }
  if (newTaskDueDate.value) payload.due_date = new Date(newTaskDueDate.value).toISOString()
  const res = await api.post<Task>('/api/v1/crm/tasks', payload)
  taskSubmitting.value = false
  if (res.ok) {
    tasks.value.push(res.data)
    newTaskTitle.value = ''
    newTaskDueDate.value = ''
    toast.success('Task created.')
  } else {
    toast.error('Failed to create task.')
  }
}

async function completeTask(id: string) {
  const res = await api.post<Task>(`/api/v1/crm/tasks/${id}/complete`)
  if (res.ok) {
    const idx = tasks.value.findIndex((t) => t.id === id)
    if (idx !== -1) tasks.value[idx] = res.data
    toast.success('Task completed.')
  } else {
    toast.error('Failed to complete task.')
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
    xhr.open('POST', `/api/v1/crm/leads/${leadId.value}/attachments`)
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
          toast.success('File uploaded.')
        } catch {
          toast.error('Upload response parse error.')
        }
      } else {
        toast.error('Failed to upload file.')
      }
      resolve()
    }
    xhr.onerror = () => {
      uploadingFile.value = false
      uploadProgress.value = 0
      toast.error('Failed to upload file.')
      resolve()
    }
    xhr.send(fd)
  })
}

async function deleteFile(id: string) {
  const res = await api.delete(`/api/v1/crm/leads/${leadId.value}/attachments/${id}`)
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
  else await loadActivities(1)
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
  if (!editTitle.value.trim()) { editError.value = 'Title is required.'; return }
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
    toast.success('Lead updated.')
  } else {
    editError.value = result.error ?? 'Failed to update.'
  }
}

async function deleteLead() {
  const result = await store.deleteLead(leadId.value)
  if (result.ok) {
    toast.success('Lead deleted.')
    router.push('/app/leads')
  } else {
    toast.error(result.error ?? 'Failed to delete.')
  }
}

onMounted(async () => {
  await store.fetchLead(leadId.value)
  if (activeTab.value === 'activities') await loadActivities()
  else if (activeTab.value === 'tasks') await loadTasks()
  else if (activeTab.value === 'files') await loadFiles()

  on('activity.created', onWsActivityCreated)
  on('lead.updated', onWsLeadUpdated)
})

onUnmounted(() => {
  off('activity.created', onWsActivityCreated)
  off('lead.updated', onWsLeadUpdated)
})

function onWsActivityCreated(payload: Record<string, unknown>) {
  const act = payload as unknown as Activity
  // Only react if this activity belongs to the lead currently open
  if (act.lead_id !== leadId.value) return
  if (activities.value.find((a) => a.id === act.id)) return
  activities.value.unshift(act)
}

function onWsLeadUpdated(_payload: Record<string, unknown>) {
  // The leads store is already updated by AppShell's WS handler; currentLead
  // is a shared Pinia ref so the UI re-renders automatically.
}

async function switchTab(tab: Tab) {
  activeTab.value = tab
  if (tab === 'activities' && activities.value.length === 0) await loadActivities()
  else if (tab === 'tasks' && tasks.value.length === 0) await loadTasks()
  else if (tab === 'files' && files.value.length === 0) await loadFiles()
}
</script>

<template>
  <div class="p-6 max-w-5xl mx-auto">
    <!-- Back -->
    <RouterLink to="/app/leads" class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4">
      ← Leads
    </RouterLink>

    <!-- Loading skeleton -->
    <div v-if="store.loadingDetail" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-64" />
      <div class="h-24 bg-gray-100 rounded-2xl" />
    </div>

    <template v-else-if="store.currentLead">
      <!-- Lead header -->
      <div class="bg-white rounded-2xl border border-gray-100 p-5 mb-5">
        <div class="flex items-start gap-4 flex-wrap">
          <div class="flex-1 min-w-0">
            <h2 class="text-xl font-semibold text-gray-900">{{ store.currentLead.title }}</h2>
            <p v-if="store.currentLead.description" class="text-sm text-gray-500 mt-1">{{ store.currentLead.description }}</p>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <!-- Status badge (inline editor) -->
            <div class="relative">
              <button
                class="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-sm font-medium transition-colors"
                :class="getStatusMeta(store.currentLead.status).color"
                @click="statusPopupOpen = !statusPopupOpen"
              >
                {{ getStatusMeta(store.currentLead.status).label }}
                <span class="text-xs opacity-60">▾</span>
              </button>
              <div
                v-if="statusPopupOpen"
                class="absolute right-0 top-9 z-10 w-40 bg-white rounded-xl border border-gray-200 shadow-lg py-1"
              >
                <button
                  v-for="s in LEAD_STATUSES"
                  :key="s.value"
                  class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 flex items-center gap-2"
                  :class="s.value === store.currentLead.status ? 'font-semibold' : ''"
                  @click="changeStatus(s.value)"
                >
                  <span class="w-2 h-2 rounded-full" :class="s.color.split(' ')[0]" />
                  {{ s.label }}
                </button>
              </div>
            </div>
            <button class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50" @click="openEdit">Edit</button>
            <button class="px-3 py-1.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50" @click="deleteLead">Delete</button>
          </div>
        </div>

        <!-- Meta -->
        <div class="flex flex-wrap gap-4 mt-4 text-xs text-gray-500">
          <span><span class="font-medium text-gray-700">Source:</span> {{ store.currentLead.source.replace('_', ' ') }}</span>
          <span v-if="store.currentLead.value != null"><span class="font-medium text-gray-700">Value:</span> {{ store.currentLead.value }} {{ store.currentLead.currency }}</span>
          <span><span class="font-medium text-gray-700">Created:</span> {{ new Date(store.currentLead.created_at).toLocaleDateString() }}</span>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 mb-4 bg-gray-100 rounded-xl p-1 w-fit">
        <button
          v-for="tab in (['overview', 'activities', 'tasks', 'files'] as Tab[])"
          :key="tab"
          class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize"
          :class="activeTab === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
          @click="switchTab(tab)"
        >{{ tab }}</button>
      </div>

      <!-- OVERVIEW TAB -->
      <div v-if="activeTab === 'overview'" class="bg-white rounded-2xl border border-gray-100 p-5">
        <h3 class="text-sm font-semibold text-gray-900 mb-3">Lead Details</h3>
        <dl class="grid grid-cols-2 gap-4 text-sm">
          <div><dt class="text-xs text-gray-500 mb-0.5">Status</dt><dd class="font-medium">{{ getStatusMeta(store.currentLead.status).label }}</dd></div>
          <div><dt class="text-xs text-gray-500 mb-0.5">Source</dt><dd class="font-medium capitalize">{{ store.currentLead.source.replace('_', ' ') }}</dd></div>
          <div><dt class="text-xs text-gray-500 mb-0.5">Value</dt><dd class="font-medium">{{ store.currentLead.value != null ? `${store.currentLead.value} ${store.currentLead.currency}` : '—' }}</dd></div>
          <div><dt class="text-xs text-gray-500 mb-0.5">Created</dt><dd class="font-medium">{{ new Date(store.currentLead.created_at).toLocaleDateString() }}</dd></div>
          <div v-if="store.currentLead.description" class="col-span-2"><dt class="text-xs text-gray-500 mb-0.5">Description</dt><dd>{{ store.currentLead.description }}</dd></div>
        </dl>
      </div>

      <!-- ACTIVITIES TAB -->
      <div v-else-if="activeTab === 'activities'" class="space-y-4">
        <!-- Add activity form -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
          <div class="flex gap-2 mb-2">
            <select v-model="newActivityType" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400">
              <option v-for="t in activityTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>
          <div class="flex flex-col gap-2">
            <RichTextEditor
              v-model="newActivityText"
              :placeholder="newActivityType === 'comment' ? 'Write a comment…' : 'Add a note, call log, or email…'"
              :disabled="activitySubmitting"
            />
            <div class="flex justify-end">
              <button
                :disabled="activitySubmitting || !hasPlainText(newActivityText)"
                class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                @click="addActivity"
              >{{ activitySubmitting ? '…' : 'Add' }}</button>
            </div>
          </div>
        </div>

        <!-- Activity list -->
        <div v-if="activitiesLoading" class="animate-pulse space-y-2">
          <div v-for="i in 3" :key="i" class="h-16 bg-gray-100 rounded-xl" />
        </div>
        <div v-else-if="activities.length === 0" class="text-center py-10 text-gray-400 text-sm">No activities yet.</div>
        <div v-else class="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50">
          <div v-for="act in activities" :key="act.id" class="flex items-start gap-3 p-4">
            <span class="text-lg mt-0.5 flex-shrink-0">{{ activityIcons[act.type] ?? '📌' }}</span>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-semibold text-gray-700 capitalize">{{ act.type.replace(/_/g, ' ') }}</span>
                <span class="text-xs text-gray-400">{{ formatTime(act.created_at) }}</span>
              </div>
              <p v-if="act.content_text" class="text-sm text-gray-700 dark:text-gray-300 mt-0.5 prose prose-sm dark:prose-invert max-w-none" v-html="sanitizeHtml(act.content_text)" />
              <p v-if="act.type === 'status_change'" class="text-sm text-gray-500 mt-0.5">
                {{ (act.metadata as Record<string, string>).old_status }} → {{ (act.metadata as Record<string, string>).new_status }}
              </p>
            </div>
          </div>
        </div>
        <button
          v-if="activitiesHasMore"
          class="w-full py-2 text-sm text-gray-500 hover:text-red-600 border border-gray-200 rounded-xl"
          @click="loadActivities(activitiesPage + 1)"
        >Load more</button>
      </div>

      <!-- TASKS TAB -->
      <div v-else-if="activeTab === 'tasks'" class="space-y-4">
        <!-- Add task form -->
        <div class="bg-white rounded-2xl border border-gray-100 p-4">
          <div class="flex gap-2 flex-wrap">
            <input v-model="newTaskTitle" type="text" placeholder="Task title…" class="flex-1 min-w-40 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            <input v-model="newTaskDueDate" type="date" class="rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            <button :disabled="taskSubmitting || !newTaskTitle.trim()" class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50" @click="addTask">
              {{ taskSubmitting ? '…' : 'Add Task' }}
            </button>
          </div>
        </div>

        <div v-if="tasksLoading" class="animate-pulse space-y-2">
          <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 rounded-xl" />
        </div>
        <div v-else-if="tasks.length === 0" class="text-center py-10 text-gray-400 text-sm">No tasks yet.</div>
        <div v-else class="bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50">
          <div v-for="task in tasks" :key="task.id" class="flex items-center gap-3 p-4">
            <button
              class="w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors"
              :class="task.is_completed ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300 hover:border-green-400'"
              :disabled="task.is_completed"
              @click="completeTask(task.id)"
            >
              <span v-if="task.is_completed" class="text-xs">✓</span>
            </button>
            <div class="flex-1 min-w-0">
              <p class="text-sm text-gray-900" :class="task.is_completed ? 'line-through text-gray-400' : ''">{{ task.title }}</p>
              <p v-if="task.due_date" class="text-xs mt-0.5" :class="!task.is_completed && new Date(task.due_date) < new Date() ? 'text-red-500' : 'text-gray-400'">
                Due: {{ new Date(task.due_date).toLocaleDateString() }}
              </p>
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
            <svg class="w-10 h-10 mb-3" :class="isDraggingOver ? 'text-red-400' : 'text-gray-300 dark:text-gray-600'" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <span class="text-sm font-medium" :class="isDraggingOver ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'">
              {{ isDraggingOver ? 'Drop to upload' : 'Click or drag & drop a file' }}
            </span>
            <span class="text-xs text-gray-400 dark:text-gray-500 mt-1">Max 20 MB</span>
            <input ref="fileInput" type="file" class="hidden" aria-hidden="true" @change="uploadFile" />
          </div>

          <!-- Progress bar -->
          <div v-if="uploadingFile" class="mt-3">
            <div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
              <span>Uploading…</span>
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
            <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </div>
          <p class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">No files attached</p>
          <p class="text-xs text-gray-400 dark:text-gray-500">Upload files to keep them with this lead.</p>
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
              <span v-else class="text-xl" aria-hidden="true">📄</span>
            </div>
            <div class="flex-1 min-w-0">
              <a :href="file.url" target="_blank" rel="noopener noreferrer" class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 truncate block">{{ file.original_filename }}</a>
              <p class="text-xs text-gray-400 dark:text-gray-500">{{ fmtBytes(file.size_bytes) }} · {{ new Date(file.created_at).toLocaleDateString() }}</p>
            </div>
            <button
              class="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 transition-opacity"
              :aria-label="`Delete ${file.original_filename}`"
              @click="deleteFile(file.id)"
            >🗑</button>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400">Lead not found.</div>
  </div>

  <!-- Edit Modal -->
  <Teleport to="body">
    <div v-if="showEditModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showEditModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" aria-labelledby="edit-lead-title">
        <h3 id="edit-lead-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">Edit Lead</h3>
        <div v-if="editError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ editError }}</div>
        <form class="space-y-3" @submit.prevent="submitEdit">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Title *</label>
            <input v-model="editTitle" type="text" required class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Description</label>
            <textarea v-model="editDescription" rows="2" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Status</label>
              <select v-model="editStatus" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                <option v-for="s in LEAD_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Source</label>
              <select v-model="editSource" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
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
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Value</label>
              <input v-model="editValue" type="number" min="0" step="0.01" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Currency</label>
              <input v-model="editCurrency" type="text" maxlength="3" class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
            </div>
          </div>
          <div class="flex gap-3 pt-2">
            <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showEditModal = false">Cancel</button>
            <button type="submit" :disabled="editLoading" class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {{ editLoading ? 'Saving…' : 'Save' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>

  <!-- Status popup backdrop -->
  <div v-if="statusPopupOpen" class="fixed inset-0 z-5" @click="statusPopupOpen = false" />
</template>

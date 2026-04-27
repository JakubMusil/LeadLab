<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useTasksStore, type TaskOut, type TaskCommentOut, type TaskAttachmentOut } from '@/stores/tasks'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import DOMPurify from 'dompurify'

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

function hasPlainText(html: string): boolean {
  const div = document.createElement('div')
  div.innerHTML = DOMPurify.sanitize(html)
  return Boolean(div.textContent?.trim())
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const tasksStore = useTasksStore()
const toast = useToast()
const { t } = useI18n()

const taskId = computed(() => route.params.id as string)

// ---------------------------------------------------------------------------
// Team members (for @mention and assignee selectors)
// ---------------------------------------------------------------------------
interface Member {
  id: string
  user_id: string
  user_email: string
  user_full_name: string
  role: string
}
const members = ref<Member[]>([])
const teamMembers = ref<MentionUser[]>([])

async function loadMembers() {
  const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''
  if (!firmId) return
  const res = await api.get<Member[]>(`/api/v1/firms/${firmId}/members`)
  if (res.ok) {
    members.value = res.data
    teamMembers.value = res.data.map((m) => ({
      id: m.user_id,
      label: m.user_full_name?.trim() || m.user_email,
    }))
  }
}

function memberLabel(m: Member) {
  return m.user_full_name?.trim() || m.user_email
}

const currentMember = computed(() =>
  members.value.find((m) => m.user_email === authStore.user?.email),
)
const isAdmin = computed(() =>
  currentMember.value?.role === 'admin' || currentMember.value?.role === 'owner',
)

// ---------------------------------------------------------------------------
// Task
// ---------------------------------------------------------------------------
const task = ref<TaskOut | null>(null)
const taskLoading = ref(false)
const taskError = ref('')

async function loadTask() {
  taskLoading.value = true
  taskError.value = ''
  const result = await tasksStore.fetchTask(taskId.value)
  taskLoading.value = false
  if (result.ok && result.data) {
    task.value = result.data
  } else {
    taskError.value = result.error ?? t('tasks.loadFailed')
  }
}

function isOverdue(t: TaskOut) {
  return !t.is_completed && t.due_date && new Date(t.due_date) < new Date()
}

function formatDate(ds: string | null) {
  if (!ds) return '—'
  return new Date(ds).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDateTime(ds: string) {
  return new Date(ds).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// Edit task
// ---------------------------------------------------------------------------
const showEditTask = ref(false)
const editTitle = ref('')
const editDescription = ref('')
const editDueDate = ref('')
const editAssigneeId = ref('')
const editWatcherIds = ref<string[]>([])
const editSubmitting = ref(false)
const editError = ref('')

function openEditTask() {
  if (!task.value) return
  editTitle.value = task.value.title
  editDescription.value = task.value.description
  editDueDate.value = task.value.due_date ? task.value.due_date.split('T')[0] : ''
  editAssigneeId.value = task.value.assigned_to_id ?? ''
  editWatcherIds.value = [...task.value.watcher_ids]
  editError.value = ''
  showEditTask.value = true
}

async function submitEditTask() {
  if (!editTitle.value.trim()) { editError.value = t('tasks.titleRequired'); return }
  if (!task.value) return
  editSubmitting.value = true
  editError.value = ''
  const result = await tasksStore.updateTask(task.value.id, {
    title: editTitle.value.trim(),
    description: editDescription.value,
    assigned_to_id: editAssigneeId.value || null,
    watcher_ids: editWatcherIds.value,
    due_date: editDueDate.value ? new Date(editDueDate.value).toISOString() : null,
    clear_due_date: !editDueDate.value,
  })
  editSubmitting.value = false
  if (result.ok && result.data) {
    task.value = result.data
    showEditTask.value = false
    toast.success(t('tasks.taskUpdated'))
  } else {
    editError.value = result.error ?? t('tasks.updateFailed')
  }
}

function toggleWatcher(watcherIds: string[], userId: string) {
  const idx = watcherIds.indexOf(userId)
  if (idx !== -1) watcherIds.splice(idx, 1)
  else watcherIds.push(userId)
}

// ---------------------------------------------------------------------------
// Complete task
// ---------------------------------------------------------------------------
const completing = ref(false)

async function completeTask() {
  if (!task.value || task.value.is_completed) return
  completing.value = true
  const result = await tasksStore.completeTask(task.value.id)
  completing.value = false
  if (result.ok) {
    toast.success(t('tasks.taskCompleted'))
    await loadTask()
  } else {
    toast.error(result.error ?? t('tasks.completeFailed'))
  }
}

// ---------------------------------------------------------------------------
// Comments
// ---------------------------------------------------------------------------
const comments = ref<TaskCommentOut[]>([])
const commentsLoading = ref(false)
const commentEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const newCommentHtml = ref('')
const commentSubmitting = ref(false)

// Per-comment editing state
const editingCommentId = ref<string | null>(null)
const editCommentHtml = ref('')
const editCommentEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const editCommentSubmitting = ref(false)

async function loadComments() {
  commentsLoading.value = true
  const result = await tasksStore.fetchTaskComments(taskId.value)
  commentsLoading.value = false
  if (result.ok && result.data) comments.value = result.data
}

async function submitComment() {
  if (!hasPlainText(newCommentHtml.value)) return
  commentSubmitting.value = true
  const result = await tasksStore.createTaskComment(taskId.value, newCommentHtml.value)
  commentSubmitting.value = false
  if (result.ok && result.data) {
    comments.value.push(result.data)
    newCommentHtml.value = ''
  } else {
    toast.error(result.error ?? t('tasks.commentFailed'))
  }
}

function startEditComment(comment: TaskCommentOut) {
  editingCommentId.value = comment.id
  editCommentHtml.value = comment.content_html
}

function cancelEditComment() {
  editingCommentId.value = null
  editCommentHtml.value = ''
}

async function submitEditComment(commentId: string) {
  if (!hasPlainText(editCommentHtml.value)) return
  editCommentSubmitting.value = true
  const result = await tasksStore.updateTaskComment(taskId.value, commentId, editCommentHtml.value)
  editCommentSubmitting.value = false
  if (result.ok && result.data) {
    const idx = comments.value.findIndex((c) => c.id === commentId)
    if (idx !== -1) comments.value[idx] = result.data
    editingCommentId.value = null
    editCommentHtml.value = ''
  } else {
    toast.error(result.error ?? t('tasks.commentUpdateFailed'))
  }
}

async function deleteComment(commentId: string) {
  const result = await tasksStore.deleteTaskComment(taskId.value, commentId)
  if (result.ok) {
    comments.value = comments.value.filter((c) => c.id !== commentId)
  } else {
    toast.error(result.error ?? t('tasks.commentDeleteFailed'))
  }
}

function canEditComment(comment: TaskCommentOut): boolean {
  return isAdmin.value || String(comment.author_id) === String(authStore.user?.id)
}

// ---------------------------------------------------------------------------
// Attachments
// ---------------------------------------------------------------------------
const attachments = ref<TaskAttachmentOut[]>([])
const attachmentsLoading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadingFile = ref(false)
const isDraggingOver = ref(false)

async function loadAttachments() {
  attachmentsLoading.value = true
  const result = await tasksStore.fetchTaskAttachments(taskId.value)
  attachmentsLoading.value = false
  if (result.ok && result.data) attachments.value = result.data
}

async function uploadFile(file: File) {
  uploadingFile.value = true
  const result = await tasksStore.uploadTaskAttachment(taskId.value, file)
  uploadingFile.value = false
  if (result.ok && result.data) {
    attachments.value.unshift(result.data)
    toast.success(t('tasks.fileUploaded'))
  } else {
    toast.error(result.error ?? t('tasks.fileUploadFailed'))
  }
}

async function deleteAttachment(attachmentId: string) {
  const result = await tasksStore.deleteTaskAttachment(taskId.value, attachmentId)
  if (result.ok) {
    attachments.value = attachments.value.filter((a) => a.id !== attachmentId)
    toast.success(t('tasks.fileDeleted'))
  } else {
    toast.error(result.error ?? t('tasks.fileDeleteFailed'))
  }
}

function onFileSelected(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files?.length) uploadFile(files[0])
}

function onDrop(e: DragEvent) {
  isDraggingOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) uploadFile(file)
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
onMounted(async () => {
  await Promise.all([loadMembers(), loadTask(), loadComments(), loadAttachments()])
})
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto">
    <!-- Back button -->
    <button
      class="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 mb-4 flex items-center gap-1"
      @click="router.push('/app/tasks')"
    >
      ← {{ t('tasks.backToTasks') }}
    </button>

    <!-- Loading -->
    <div v-if="taskLoading" class="space-y-4 animate-pulse">
      <div class="h-8 bg-gray-200 dark:bg-gray-700 rounded-xl w-2/3" />
      <div class="h-4 bg-gray-100 dark:bg-gray-800 rounded-xl w-1/2" />
    </div>

    <!-- Error -->
    <div v-else-if="taskError" class="text-red-500 text-sm py-8 text-center">{{ taskError }}</div>

    <!-- Content -->
    <template v-else-if="task">
      <!-- ===================== TASK HEADER ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <div class="flex items-start gap-4">
          <!-- Completion checkbox -->
          <button
            class="w-6 h-6 rounded border flex-shrink-0 flex items-center justify-center transition-colors mt-0.5"
            :class="task.is_completed
              ? 'bg-green-500 border-green-500 text-white cursor-default'
              : 'border-gray-300 hover:border-green-400'"
            :disabled="task.is_completed || completing"
            :title="task.is_completed ? '' : t('tasks.complete')"
            @click="!task.is_completed && completeTask()"
          >
            <span v-if="task.is_completed" class="text-sm">✓</span>
          </button>

          <div class="flex-1 min-w-0">
            <!-- Title row -->
            <div class="flex items-start justify-between gap-3">
              <h1
                class="text-xl font-bold text-gray-900 dark:text-gray-100"
                :class="task.is_completed ? 'line-through text-gray-400' : ''"
              >
                {{ task.title }}
              </h1>
              <div class="flex gap-2 flex-shrink-0">
                <button
                  v-if="!task.is_completed"
                  class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                  @click="openEditTask"
                >
                  {{ t('tasks.edit') }}
                </button>
                <button
                  v-if="!task.is_completed"
                  class="px-3 py-1.5 rounded-xl border border-green-200 text-xs text-green-600 hover:bg-green-50"
                  :disabled="completing"
                  @click="completeTask"
                >
                  {{ completing ? '…' : t('tasks.complete') }}
                </button>
                <span v-if="task.is_completed" class="px-3 py-1.5 rounded-xl bg-green-50 text-xs text-green-600 font-medium">
                  ✓ {{ t('tasks.done') }}
                </span>
              </div>
            </div>

            <!-- Description -->
            <p v-if="task.description" class="mt-2 text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap">
              {{ task.description }}
            </p>

            <!-- Meta grid -->
            <div class="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 text-xs text-gray-500 dark:text-gray-400">
              <!-- Lead -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.lead') }}</span>
                <RouterLink
                  :to="`/app/leads/${task.lead_id}`"
                  class="text-blue-500 hover:underline truncate"
                >
                  {{ task.lead_title || task.lead_id }}
                </RouterLink>
              </div>
              <!-- Assignee -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.assignee') }}</span>
                <span>{{ task.assigned_to_name || t('tasks.noAssignee') }}</span>
              </div>
              <!-- Due date -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.deadline') }}</span>
                <span :class="isOverdue(task) ? 'text-red-500 font-semibold' : ''">
                  {{ formatDate(task.due_date) }}
                  <span v-if="isOverdue(task)">({{ t('tasks.overdue') }})</span>
                </span>
              </div>
              <!-- Created by -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.createdBy') }}</span>
                <span>{{ task.created_by_name || '—' }}</span>
              </div>
              <!-- Created at -->
              <div class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.createdAt') }}</span>
                <span>{{ formatDateTime(task.created_at) }}</span>
              </div>
              <!-- Watchers -->
              <div v-if="task.watcher_ids.length" class="flex items-center gap-1.5">
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ t('tasks.watchers') }}</span>
                <span>🔔 {{ task.watcher_ids.length }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===================== COMMENTS ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 mb-6">
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          💬 {{ t('tasks.comments') }}
          <span v-if="comments.length" class="text-sm font-normal text-gray-400">({{ comments.length }})</span>
        </h2>

        <!-- Comment list -->
        <div v-if="commentsLoading" class="space-y-3 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-16 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <div v-else-if="comments.length === 0" class="text-sm text-gray-400 dark:text-gray-500 mb-4">
          {{ t('tasks.noComments') }}
        </div>

        <div v-else class="space-y-4 mb-6">
          <div
            v-for="comment in comments"
            :key="comment.id"
            class="group border border-gray-100 dark:border-gray-700 rounded-xl p-4"
          >
            <!-- Comment header -->
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                  {{ (comment.author_name || '?').charAt(0).toUpperCase() }}
                </span>
                <span class="font-medium text-gray-700 dark:text-gray-300">{{ comment.author_name || t('tasks.unknownAuthor') }}</span>
                <span>·</span>
                <span :title="formatDateTime(comment.updated_at)">
                  {{ formatDateTime(comment.created_at) }}
                  <span v-if="comment.updated_at !== comment.created_at" class="italic ml-1">({{ t('tasks.edited') }})</span>
                </span>
              </div>
              <!-- Actions (author or admin) -->
              <div v-if="canEditComment(comment)" class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  class="text-xs text-gray-400 hover:text-blue-500 px-2 py-0.5 rounded"
                  @click="startEditComment(comment)"
                >
                  {{ t('tasks.editComment') }}
                </button>
                <button
                  class="text-xs text-gray-400 hover:text-red-500 px-2 py-0.5 rounded"
                  @click="deleteComment(comment.id)"
                >
                  {{ t('tasks.deleteComment') }}
                </button>
              </div>
            </div>

            <!-- Comment content (view or edit mode) -->
            <div v-if="editingCommentId !== comment.id">
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="prose prose-sm dark:prose-invert max-w-none" v-html="sanitizeHtml(comment.content_html)" />
            </div>
            <div v-else class="space-y-2">
              <RichTextEditor
                ref="editCommentEditorRef"
                v-model="editCommentHtml"
                :members="teamMembers"
                :placeholder="t('tasks.editCommentPlaceholder')"
              />
              <div class="flex justify-end gap-2">
                <button
                  class="px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
                  @click="cancelEditComment"
                >
                  {{ t('tasks.cancel') }}
                </button>
                <button
                  :disabled="editCommentSubmitting || !hasPlainText(editCommentHtml)"
                  class="px-3 py-1.5 rounded-xl bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                  @click="submitEditComment(comment.id)"
                >
                  {{ editCommentSubmitting ? t('tasks.saving') : t('tasks.save') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- New comment composer -->
        <div class="space-y-2">
          <RichTextEditor
            ref="commentEditorRef"
            v-model="newCommentHtml"
            :members="teamMembers"
            :placeholder="t('tasks.commentPlaceholder')"
          />
          <div class="flex justify-end">
            <button
              :disabled="commentSubmitting || !hasPlainText(newCommentHtml)"
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="submitComment"
            >
              {{ commentSubmitting ? t('tasks.saving') : t('tasks.addComment') }}
            </button>
          </div>
        </div>
      </div>

      <!-- ===================== ATTACHMENTS ===================== -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
        <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-4">
          📎 {{ t('tasks.attachments') }}
          <span v-if="attachments.length" class="text-sm font-normal text-gray-400">({{ attachments.length }})</span>
        </h2>

        <!-- Drop zone -->
        <div
          class="relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors mb-4"
          :class="isDraggingOver
            ? 'border-red-400 bg-red-50 dark:bg-red-900/20'
            : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'"
          @click="fileInput?.click()"
          @dragover.prevent="isDraggingOver = true"
          @dragleave="isDraggingOver = false"
          @drop.prevent="onDrop"
        >
          <input ref="fileInput" type="file" class="hidden" @change="onFileSelected" />
          <p v-if="uploadingFile" class="text-sm text-gray-500 dark:text-gray-400">{{ t('leadDetail.uploading') }}</p>
          <template v-else>
            <p v-if="isDraggingOver" class="text-sm font-medium text-red-500">{{ t('leadDetail.dropToUpload') }}</p>
            <template v-else>
              <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('leadDetail.clickOrDrop') }}</p>
              <p class="text-xs text-gray-400 mt-1">{{ t('leadDetail.maxSize') }}</p>
            </template>
          </template>
        </div>

        <!-- Attachment list -->
        <div v-if="attachmentsLoading" class="space-y-2 animate-pulse">
          <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
        </div>

        <div v-else-if="attachments.length === 0" class="text-sm text-gray-400 dark:text-gray-500 text-center py-2">
          {{ t('tasks.noAttachments') }}
        </div>

        <ul v-else class="space-y-2">
          <li
            v-for="att in attachments"
            :key="att.id"
            class="flex items-center gap-3 p-3 rounded-xl border border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 group"
          >
            <span class="text-lg flex-shrink-0">📄</span>
            <div class="flex-1 min-w-0">
              <a
                :href="att.url"
                target="_blank"
                rel="noopener"
                class="text-sm font-medium text-blue-500 hover:underline truncate block"
              >
                {{ att.original_filename }}
              </a>
              <p class="text-xs text-gray-400">{{ formatFileSize(att.size_bytes) }} · {{ formatDateTime(att.created_at) }}</p>
            </div>
            <button
              class="text-xs text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
              :title="t('tasks.deleteAttachment')"
              @click="deleteAttachment(att.id)"
            >
              🗑
            </button>
          </li>
        </ul>
      </div>
    </template>

    <!-- ===================== EDIT TASK MODAL ===================== -->
    <Teleport to="body">
      <div
        v-if="showEditTask"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        @click.self="showEditTask = false"
      >
        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-lg p-6 space-y-4">
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.editTask') }}</h2>

          <div v-if="editError" class="text-sm text-red-600 bg-red-50 dark:bg-red-900/30 rounded-xl px-3 py-2">
            {{ editError }}
          </div>

          <!-- Title -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.taskTitle') }}</label>
            <input
              v-model="editTitle"
              type="text"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>

          <!-- Description -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.description') }}</label>
            <textarea
              v-model="editDescription"
              rows="3"
              class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
            />
          </div>

          <!-- Due date + Assignee row -->
          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.deadline') }}</label>
              <input
                v-model="editDueDate"
                type="date"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
              />
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.assignee') }}</label>
              <select
                v-model="editAssigneeId"
                class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
              >
                <option value="">{{ t('tasks.noAssignee') }}</option>
                <option v-for="m in members" :key="m.user_id" :value="m.user_id">
                  {{ memberLabel(m) }}
                </option>
              </select>
            </div>
          </div>

          <!-- Watchers -->
          <div>
            <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.watchers') }}</label>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="m in members"
                :key="m.user_id"
                class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
                :class="editWatcherIds.includes(m.user_id)
                  ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
              >
                <input
                  type="checkbox"
                  class="hidden"
                  :checked="editWatcherIds.includes(m.user_id)"
                  @change="toggleWatcher(editWatcherIds, m.user_id)"
                />
                🔔 {{ memberLabel(m) }}
              </label>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex justify-end gap-2 pt-2">
            <button
              class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="showEditTask = false"
            >
              {{ t('tasks.cancel') }}
            </button>
            <button
              :disabled="editSubmitting"
              class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="submitEditTask"
            >
              {{ editSubmitting ? t('tasks.saving') : t('tasks.save') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

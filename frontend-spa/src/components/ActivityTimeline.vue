<script setup lang="ts">
/**
 * ActivityTimeline — unified timeline composer + feed.
 *
 * Works identically for Lead, Realization and Management.
 * The consumer just passes entityType + entityId.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useWebSocket } from '@/composables/useWebSocket'
import { useFirmStore } from '@/stores/firm'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import DOMPurify from 'dompurify'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
const props = defineProps<{
  entityType: 'lead' | 'realization' | 'management'
  entityId: string
}>()

// ---------------------------------------------------------------------------
// Shared setup
// ---------------------------------------------------------------------------
const { t } = useI18n()
const { on, off } = useWebSocket()
const firmStore = useFirmStore()
const toast = useToast()

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Activity {
  id: string
  entity_type: string
  entity_id: string
  lead_id: string | null
  user_id: string | null
  type: string
  content_text: string
  metadata: Record<string, unknown>
  created_at: string
}

// ---------------------------------------------------------------------------
// Team members for @mentions
// ---------------------------------------------------------------------------
const teamMembers = ref<MentionUser[]>([])

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

// ---------------------------------------------------------------------------
// Activities state
// ---------------------------------------------------------------------------
const activities = ref<Activity[]>([])
const activitiesLoading = ref(false)
const activitiesPage = ref(1)
const activitiesHasMore = ref(true)

// Composer state
const selectedActionType = ref('')
const newActivityText = ref('')
const activitySubmitting = ref(false)
const richTextEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)

// Task sub-form state
const newTaskTitle = ref('')
const newTaskDueDate = ref('')
const newTaskDescription = ref('')
const newTaskAssigneeId = ref('')
const newTaskWatcherIds = ref<string[]>([])
const taskEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const taskSubmitting = ref(false)

// ---------------------------------------------------------------------------
// Config maps
// ---------------------------------------------------------------------------
const activityIcons: Record<string, string> = {
  comment: '💬', email_out: '📧', email_in: '📥', call: '📞',
  meeting: '🤝', status_change: '🔄', file_upload: '📎',
  task_assigned: '📋', task_completed: '✅', task: '📋',
  proposal_created: '📄', proposal_accepted: '✅', proposal_rejected: '❌',
}

const actionPickerItems = [
  { value: 'comment',   label: t('leadDetail.typeComment'),  icon: '💬' },
  { value: 'call',      label: t('leadDetail.typeCall'),     icon: '📞' },
  { value: 'meeting',   label: t('leadDetail.typeMeeting'),  icon: '🤝' },
  { value: 'email_out', label: t('leadDetail.typeEmailOut'), icon: '📧' },
  { value: 'email_in',  label: t('leadDetail.typeEmailIn'),  icon: '📥' },
  { value: 'task',      label: t('leadDetail.typeTask'),     icon: '📋' },
]

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
function listUrl(page: number): string {
  if (props.entityType === 'lead') return `/api/v1/crm/opportunities/${props.entityId}/activities?page=${page}&page_size=20`
  if (props.entityType === 'realization') return `/api/v1/crm/realizations/${props.entityId}/activities?page=${page}&page_size=20`
  return `/api/v1/crm/management/${props.entityId}/activities?page=${page}&page_size=20`
}

function entityIdKey(): string {
  if (props.entityType === 'lead') return 'lead_id'
  if (props.entityType === 'realization') return 'realization_id'
  return 'management_id'
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------
async function loadActivities(page = 1) {
  activitiesLoading.value = true
  try {
    const res = await api.get<Activity[]>(listUrl(page))
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

// ---------------------------------------------------------------------------
// Adding activities
// ---------------------------------------------------------------------------
function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

function hasPlainText(html: string): boolean {
  return Boolean(html.replace(/<[^>]*>/g, '').trim())
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function addActivity() {
  if (selectedActionType.value === 'comment' && !hasPlainText(newActivityText.value)) return
  activitySubmitting.value = true
  const mentionedIds = selectedActionType.value === 'comment'
    ? (richTextEditorRef.value?.getMentionedIds() ?? [])
    : []
  const metadata: Record<string, unknown> = mentionedIds.length ? { mentions: mentionedIds } : {}
  const res = await api.post<Activity>('/api/v1/crm/activities', {
    [entityIdKey()]: props.entityId,
    type: selectedActionType.value,
    content_text: newActivityText.value,
    metadata,
  })
  activitySubmitting.value = false
  if (res.ok) {
    activities.value.unshift(res.data)
    newActivityText.value = ''
    selectedActionType.value = ''
    toast.success(t('leadDetail.activityAdded'))
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

async function addTask() {
  if (!newTaskTitle.value.trim()) return
  taskSubmitting.value = true
  const mentionedIds = taskEditorRef.value?.getMentionedIds() ?? []
  const payload: Record<string, unknown> = {
    [entityIdKey()]: props.entityId,
    title: newTaskTitle.value.trim(),
    description: newTaskDescription.value,
    assigned_to_id: newTaskAssigneeId.value || null,
    watcher_ids: newTaskWatcherIds.value,
  }
  if (newTaskDueDate.value) payload.due_date = new Date(newTaskDueDate.value).toISOString()
  if (mentionedIds.length > 0) payload.metadata = { mentions: mentionedIds }
  const res = await api.post('/api/v1/crm/tasks', payload)
  taskSubmitting.value = false
  if (res.ok) {
    newTaskTitle.value = ''
    newTaskDueDate.value = ''
    newTaskDescription.value = ''
    newTaskAssigneeId.value = ''
    newTaskWatcherIds.value = []
    selectedActionType.value = ''
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

// ---------------------------------------------------------------------------
// WebSocket real-time update
// ---------------------------------------------------------------------------
function onWsActivityCreated(payload: Record<string, unknown>) {
  const act = payload as unknown as Activity
  // Only react if this activity belongs to the currently open entity
  if (act.entity_type !== props.entityType || act.entity_id !== props.entityId) return
  if (activities.value.find((a) => a.id === act.id)) return
  activities.value.unshift(act)
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(async () => {
  await Promise.all([loadActivities(), loadTeamMembers()])
  on('activity.created', onWsActivityCreated)
})

onUnmounted(() => {
  off('activity.created', onWsActivityCreated)
})

// Expose for parent lazy-load pattern (call load() when tab becomes active)
defineExpose({ load: () => loadActivities(1) })
</script>

<template>
  <div class="space-y-4">
    <!-- ================================================================ -->
    <!-- Unified action composer                                           -->
    <!-- ================================================================ -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">

      <!-- Step 1: Action type picker -->
      <div v-if="!selectedActionType">
        <p class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2.5">{{ t('leadDetail.chooseActionType') }}</p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="item in actionPickerItems"
            :key="item.value"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:border-red-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
            @click="selectedActionType = item.value; newActivityText = ''"
          >
            <span>{{ item.icon }}</span>
            {{ item.label }}
          </button>
        </div>
      </div>

      <!-- Step 2a: Activity form (comment / call / meeting / email) -->
      <div v-else-if="selectedActionType !== 'task'" class="flex flex-col gap-2">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-base">{{ activityIcons[selectedActionType] ?? '📌' }}</span>
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">
            {{ actionPickerItems.find(i => i.value === selectedActionType)?.label }}
          </span>
          <button
            class="ml-auto text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
            @click="selectedActionType = ''"
          >← {{ t('leadDetail.changeType') }}</button>
        </div>
        <RichTextEditor
          ref="richTextEditorRef"
          v-model="newActivityText"
          :placeholder="selectedActionType === 'comment' ? t('leadDetail.commentPlaceholder') : t('leadDetail.notePlaceholder')"
          :disabled="activitySubmitting"
          :members="selectedActionType === 'comment' ? teamMembers : []"
        />
        <div class="flex justify-end">
          <button
            :disabled="activitySubmitting || !hasPlainText(newActivityText)"
            class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="addActivity"
          >{{ activitySubmitting ? '…' : t('leadDetail.activitySubmit') }}</button>
        </div>
      </div>

      <!-- Step 2b: Task creation form -->
      <div v-else class="space-y-3">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-base">📋</span>
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('leadDetail.typeTask') }}</span>
          <button
            class="ml-auto text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
            @click="selectedActionType = ''"
          >← {{ t('leadDetail.changeType') }}</button>
        </div>
        <div class="flex gap-2 flex-wrap">
          <input
            v-model="newTaskTitle"
            type="text"
            :placeholder="t('leadDetail.taskTitle')"
            class="flex-1 min-w-40 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
          <input
            v-model="newTaskDueDate"
            type="date"
            class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.assignee') }}</label>
          <select
            v-model="newTaskAssigneeId"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('tasks.noAssignee') }}</option>
            <option v-for="m in teamMembers" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
        </div>
        <div v-if="teamMembers.length">
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.watchers') }}</label>
          <div class="flex flex-wrap gap-2">
            <label
              v-for="m in teamMembers"
              :key="m.id"
              class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
              :class="newTaskWatcherIds.includes(m.id)
                ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
            >
              <input type="checkbox" class="hidden" :checked="newTaskWatcherIds.includes(m.id)" @change="toggleTaskWatcher(m.id)" />
              🔔 {{ m.label }}
            </label>
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ t('leadDetail.descriptionLabel') }}
          </label>
          <RichTextEditor
            ref="taskEditorRef"
            v-model="newTaskDescription"
            :members="teamMembers"
            :placeholder="t('leadDetail.addMentionPlaceholder')"
            class="min-h-[72px]"
          />
        </div>
        <div class="flex justify-end">
          <button
            :disabled="taskSubmitting || !newTaskTitle.trim()"
            class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="addTask"
          >{{ taskSubmitting ? '…' : t('leadDetail.addTask') }}</button>
        </div>
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- Activity feed                                                      -->
    <!-- ================================================================ -->
    <div v-if="activitiesLoading" class="animate-pulse space-y-2">
      <div v-for="i in 3" :key="i" class="h-16 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <div v-else-if="activities.length === 0" class="text-center py-10 text-gray-400 text-sm">
      {{ t('leadDetail.noActivities') }}
    </div>

    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
      <div v-for="act in activities" :key="act.id" class="flex items-start gap-3 p-4">
        <span class="text-lg mt-0.5 flex-shrink-0">{{ activityIcons[act.type] ?? '📌' }}</span>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-semibold text-gray-700 dark:text-gray-300 capitalize">{{ act.type.replace(/_/g, ' ') }}</span>
            <span class="text-xs text-gray-400">{{ formatTime(act.created_at) }}</span>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <p v-if="act.content_text" class="text-sm text-gray-700 dark:text-gray-300 mt-0.5 prose prose-sm dark:prose-invert max-w-none" v-html="sanitizeHtml(act.content_text)" />
          <p v-if="act.type === 'status_change'" class="text-sm text-gray-500 mt-0.5">
            {{ (act.metadata as Record<string, string>).old_status }} → {{ (act.metadata as Record<string, string>).new_status }}
          </p>
          <RouterLink
            v-if="act.type === 'proposal_created' && act.metadata?.proposal_id"
            :to="`/app/proposals/${act.metadata.proposal_id}`"
            class="text-xs text-red-600 hover:text-red-700 mt-0.5 inline-block"
          >
            Zobrazit nabídku →
          </RouterLink>
        </div>
      </div>
    </div>

    <button
      v-if="activitiesHasMore && !activitiesLoading"
      class="w-full py-2 text-sm text-gray-500 hover:text-red-600 border border-gray-200 dark:border-gray-700 rounded-xl"
      @click="loadActivities(activitiesPage + 1)"
    >{{ t('leadDetail.loadMore') }}</button>
  </div>
</template>

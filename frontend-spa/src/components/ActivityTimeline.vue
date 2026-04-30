<script setup lang="ts">
/**
 * ActivityTimeline — unified timeline composer + feed.
 *
 * Works identically for Lead, Realization, Management, Customer, and Proposal.
 * The consumer just passes entityType + entityId.
 */
import { ref, computed, onMounted, onUnmounted, type Component } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useWebSocket } from '@/composables/useWebSocket'
import { useFirmStore } from '@/stores/firm'
import { useStreamlinePreferencesStore } from '@/stores/streamlinePreferences'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import StreamlineFilterDropdown from '@/components/StreamlineFilterDropdown.vue'
import DOMPurify from 'dompurify'
import {
  ChatBubbleLeftIcon,
  ChatBubbleLeftRightIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  PhoneIcon,
  UsersIcon,
  PaperAirplaneIcon,
  InboxArrowDownIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  CheckIcon,
  ArrowsRightLeftIcon,
  PaperClipIcon,
  DocumentTextIcon,
  DocumentCheckIcon,
  PencilSquareIcon,
  QuestionMarkCircleIcon,
  BellIcon,
  FlagIcon,
  UserCircleIcon,
  CalendarIcon,
  CalendarDaysIcon,
  Squares2X2Icon,
  PlusCircleIcon,
  ArchiveBoxIcon,
  ShieldExclamationIcon,
  ShieldCheckIcon,
  ClockIcon,
  MicrophoneIcon,
  DevicePhoneMobileIcon,
  LinkIcon,
  BanknotesIcon,
  CheckBadgeIcon,
  EyeIcon,
  SparklesIcon,
  LightBulbIcon,
  InformationCircleIcon,
  TagIcon,
  AtSymbolIcon,
  BookmarkIcon,
  BookmarkSlashIcon,
  FaceSmileIcon,
  DocumentCurrencyDollarIcon,
} from '@heroicons/vue/24/outline'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
const props = defineProps<{
  entityType: 'lead' | 'realization' | 'management' | 'customer' | 'proposal' | 'task'
  entityId: string
  hideComposer?: boolean
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
interface ReactionSummary {
  emoji: string
  count: number
  user_ids: string[]
  reacted_by_me: boolean
}

interface Activity {
  id: string
  entity_type: string
  entity_id: string
  lead_id: string | null
  user_id: string | null
  user_name: string | null
  user_avatar_url: string | null
  type: string
  content_text: string
  metadata: Record<string, unknown>
  is_internal: boolean
  created_at: string
  tool_payload: Record<string, unknown> | null
  reactions?: ReactionSummary[]
}

interface StreamlineTool {
  activity_type: string
  label: string
  icon: string
  category: string
  default_visibility: 'important' | 'secondary'
  form_schema: {
    type: string
    properties?: Record<string, unknown>
    required?: string[]
  }
}

// Map icon name strings (from the Streamline Tool Registry) to Heroicon components
const heroIconMap: Record<string, Component> = {
  ChatBubbleLeftIcon,
  ChatBubbleLeftRightIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  PhoneIcon,
  UsersIcon,
  PaperAirplaneIcon,
  InboxArrowDownIcon,
  ArrowsRightLeftIcon,
  PaperClipIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  CheckIcon,
  DocumentTextIcon,
  DocumentCheckIcon,
  PencilSquareIcon,
  FlagIcon,
  UserCircleIcon,
  CalendarIcon,
  CalendarDaysIcon,
  Squares2X2Icon,
  PlusCircleIcon,
  ArchiveBoxIcon,
  ShieldExclamationIcon,
  ShieldCheckIcon,
  ClockIcon,
  MicrophoneIcon,
  DevicePhoneMobileIcon,
  LinkIcon,
  BanknotesIcon,
  DocumentCurrencyDollarIcon,
  CheckBadgeIcon,
  EyeIcon,
  SparklesIcon,
  LightBulbIcon,
  InformationCircleIcon,
  TagIcon,
  AtSymbolIcon,
  BookmarkIcon,
  BookmarkSlashIcon,
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

// Filter state — set of activity_type values that are currently visible.
// Sourced from the streamline preferences store (per-user, persisted on the
// backend) and falls back to per-tool `default_visibility` when the user has
// never customised the filter.
const streamlinePrefs = useStreamlinePreferencesStore()

const visibleTypes = computed<Set<string>>(() => {
  // Build effective visible set from saved prefs + tool defaults.
  return streamlinePrefs.effectiveVisible(streamlineTools.value)
})

// Activity types covered by the synthetic "task" group (kept for backwards
// compatibility with bare task activities — `task` is a pseudo-type for which
// no dedicated tool is registered, so include it whenever any task_* type is
// visible).
const _taskGroupTypes = ['task_assigned', 'task_completed', 'task_created'] as const

const filteredActivities = computed(() => {
  // If the user has hidden literally everything, render nothing.
  if (visibleTypes.value.size === 0) return []
  return activities.value.filter((a) => {
    if (visibleTypes.value.has(a.type)) return true
    // Bare 'task' activity rows ride along with any task_* type so users who
    // tick a task type still see related synthetic 'task' rows.
    if (a.type === 'task' && _taskGroupTypes.some((t) => visibleTypes.value.has(t))) {
      return true
    }
    return false
  })
})

/**
 * Apply a new visible-types selection from the filter dropdown.
 *
 * `next` semantics:
 *   - `null`        → reset to per-tool defaults (clears saved prefs).
 *   - `string[]`    → persist this exact set as the user's saved prefs.
 *
 * The change is persisted via the streamline preferences store, so it
 * applies across every streamline view for this user.
 */
async function onFilterChange(next: string[] | null) {
  await streamlinePrefs.save(next)
}

// Composer state
const selectedActionType = ref('')
const newActivityText = ref('')
const newActivityIsInternal = ref(false)
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
// Streamline Tool Registry
// ---------------------------------------------------------------------------
const streamlineTools = ref<StreamlineTool[]>([])

async function loadStreamlineTools() {
  const res = await api.get<StreamlineTool[]>('/api/v1/streamline/tools')
  if (res.ok) streamlineTools.value = res.data
}

// ---------------------------------------------------------------------------
// Config maps
// ---------------------------------------------------------------------------
const activityIconMap: Record<string, Component> = {
  comment: ChatBubbleLeftIcon,
  email_out: PaperAirplaneIcon,
  email_in: InboxArrowDownIcon,
  call: PhoneIcon,
  meeting: UsersIcon,
  status_change: ArrowsRightLeftIcon,
  file_upload: PaperClipIcon,
  task_assigned: ClipboardDocumentListIcon,
  task_completed: CheckCircleIcon,
  task: ClipboardDocumentListIcon,
  proposal_created: DocumentTextIcon,
  proposal_accepted: DocumentCheckIcon,
  proposal_rejected: DocumentTextIcon,
  entity_change: PencilSquareIcon,
  // Phase 1 task tools
  priority_change: FlagIcon,
  assignee_change: UserCircleIcon,
  due_date_change: CalendarIcon,
  sub_task_added: Squares2X2Icon,
  task_created: PlusCircleIcon,
  task_archived: ArchiveBoxIcon,
  approval_requested: ShieldExclamationIcon,
  approval_resolved: ShieldCheckIcon,
  time_logged: ClockIcon,
  checklist_item_checked: CheckIcon,
  voice_memo: MicrophoneIcon,
  // Phase 6 bonus tools
  sms_out: DevicePhoneMobileIcon,
  sms_in: DevicePhoneMobileIcon,
  whatsapp_out: ChatBubbleOvalLeftEllipsisIcon,
  whatsapp_in: ChatBubbleOvalLeftEllipsisIcon,
  chat: ChatBubbleLeftRightIcon,
  meeting_scheduled: CalendarDaysIcon,
  call_scheduled: PhoneIcon,
  task_expired: ClockIcon,
  link: LinkIcon,
  payment_received: BanknotesIcon,
  invoice_sent: DocumentCurrencyDollarIcon,
  signature_requested: PencilSquareIcon,
  signature_completed: CheckBadgeIcon,
  proposal_viewed: EyeIcon,
  ai_summary: SparklesIcon,
  ai_suggested_action: LightBulbIcon,
  system_note: InformationCircleIcon,
  tag_added: TagIcon,
  tag_removed: TagIcon,
  mention: AtSymbolIcon,
  pinned: BookmarkIcon,
  unpinned: BookmarkSlashIcon,
}

function activityIcon(type: string): Component {
  const tool = streamlineTools.value.find((t) => t.activity_type === type)
  if (tool) return heroIconMap[tool.icon] ?? QuestionMarkCircleIcon
  return activityIconMap[type] ?? QuestionMarkCircleIcon
}

function activityTypeLabel(type: string): string {
  const map: Record<string, string> = {
    comment: t('leadDetail.typeComment'),
    call: t('leadDetail.typeCall'),
    meeting: t('leadDetail.typeMeeting'),
    email_out: t('leadDetail.typeEmailOut'),
    email_in: t('leadDetail.typeEmailIn'),
    task: t('leadDetail.typeTask'),
    task_assigned: t('leadDetail.typeTaskAssigned'),
    task_completed: t('leadDetail.typeTaskCompleted'),
    status_change: t('leadDetail.typeStatusChange'),
    file_upload: t('leadDetail.typeFileUpload'),
    proposal_created: t('leadDetail.typeProposalCreated'),
    proposal_accepted: t('leadDetail.typeProposalAccepted'),
    proposal_rejected: t('leadDetail.typeProposalRejected'),
    entity_change: t('leadDetail.typeEntityChange'),
    sms_out: t('leadDetail.typeSmsOut'),
    sms_in: t('leadDetail.typeSmsIn'),
    whatsapp_out: t('leadDetail.typeWhatsAppOut'),
    whatsapp_in: t('leadDetail.typeWhatsAppIn'),
    meeting_scheduled: t('leadDetail.typeMeetingScheduled'),
    call_scheduled: t('leadDetail.typeCallScheduled'),
    task_expired: t('leadDetail.typeTaskExpired'),
    link: t('leadDetail.typeLink'),
    voice_memo: t('leadDetail.typeVoiceMemo'),
    system_note: t('leadDetail.typeSystemNote'),
  }
  if (map[type]) return map[type]
  const tool = streamlineTools.value.find((t) => t.activity_type === type)
  if (tool) return tool.label
  return type.replace(/_/g, ' ')
}

// ---------------------------------------------------------------------------
// Calendar / Task unification helpers
// ---------------------------------------------------------------------------
// When a scheduled-activity tool (meeting_scheduled / call_scheduled) creates
// its parent Task, ``tool_payload.task_status`` carries the live status so we
// can render an inline pill without a second request.
const _SCHEDULED_TASK_STATUS_CLASSES: Record<string, string> = {
  todo: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  in_progress: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  done: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  cancelled: 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300',
  expired: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  blocked: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
}

function scheduledTaskStatusBadgeClass(status: string | null | undefined): string {
  if (!status) return ''
  return _SCHEDULED_TASK_STATUS_CLASSES[status] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
}

// Whether content_text is required for the currently selected action type
const activityTextRequired = computed(() => {
  const tool = streamlineTools.value.find((t) => t.activity_type === selectedActionType.value)
  // Default to false (not required) if the tool is not yet loaded or has no schema info
  return tool?.form_schema.required?.includes('content_text') ?? false
})

const actionPickerItems = computed<{ value: string; label: string; icon: Component }[]>(() => {
  const registryItems = streamlineTools.value
    .filter((tool) => tool.form_schema.properties?.['content_text'] !== undefined)
    .map((tool) => ({
      value: tool.activity_type,
      label: tool.label,
      icon: heroIconMap[tool.icon] ?? QuestionMarkCircleIcon,
    }))
  // The task creation pseudo-tool only makes sense on entities that can own tasks
  if (props.entityType === 'task') return registryItems
  return [
    ...registryItems,
    { value: 'task', label: t('leadDetail.typeTask'), icon: ClipboardDocumentListIcon },
  ]
})

function translateLeadStatus(status: string): string {
  const map: Record<string, string> = {
    new: t('leads.statusNew'),
    contacted: t('leads.statusContacted'),
    proposal: t('leads.statusProposal'),
    negotiation: t('leads.statusNegotiation'),
    won: t('leads.statusWon'),
    lost: t('leads.statusLost'),
    canceled: t('leads.statusCanceled'),
  }
  return map[status] ?? status
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
function listUrl(page: number): string {
  if (props.entityType === 'lead') return `/api/v1/crm/opportunities/${props.entityId}/activities?page=${page}&page_size=20`
  if (props.entityType === 'realization') return `/api/v1/crm/realizations/${props.entityId}/activities?page=${page}&page_size=20`
  if (props.entityType === 'customer') return `/api/v1/crm/directory/${props.entityId}/activities?page=${page}&page_size=20`
  if (props.entityType === 'proposal') return `/api/v1/crm/proposals/${props.entityId}/activities?page=${page}&page_size=20`
  if (props.entityType === 'task') return `/api/v1/crm/tasks/${props.entityId}/activities?page=${page}&page_size=20`
  return `/api/v1/crm/management/${props.entityId}/activities?page=${page}&page_size=20`
}

function entityIdKey(): string {
  if (props.entityType === 'lead') return 'lead_id'
  if (props.entityType === 'realization') return 'realization_id'
  if (props.entityType === 'customer') return 'customer_id'
  if (props.entityType === 'proposal') return 'proposal_id'
  if (props.entityType === 'task') return 'task_id'
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

function userInitials(name: string | null): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  if (parts.length >= 2) {
    const first = parts[0] ?? ''
    const last = parts[parts.length - 1] ?? ''
    return ((first[0] ?? '') + (last[0] ?? '')).toUpperCase() || '?'
  }
  return (name[0] ?? '?').toUpperCase()
}

/**
 * Strip legacy ``TypeName:value`` prefix written by the old _normalize() helper.
 * New values are already clean strings; old values in the DB may still carry
 * the prefix (e.g. "Decimal:50000.00" → "50000.00", "str:hello" → "hello").
 * Also removes unnecessary trailing zeros from numeric strings.
 */
function cleanFieldValue(raw: string | undefined | null): string {
  if (!raw) return '—'
  // Strip "TypeName:" prefix (e.g. "Decimal:", "int:", "str:", "NoneType:", etc.)
  const colonIdx = raw.indexOf(':')
  if (colonIdx !== -1) {
    const typePart = raw.substring(0, colonIdx)
    // Only strip if the prefix looks like a Python type name (no spaces, all word chars)
    if (/^\w+$/.test(typePart)) {
      raw = raw.substring(colonIdx + 1)
    }
  }
  // Remove trailing zeros from decimal-looking strings (e.g. "50000.00" → "50000")
  if (/^\d+\.\d+$/.test(raw)) {
    raw = parseFloat(raw).toString()
  }
  return raw || '—'
}

async function addActivity() {
  if (activityTextRequired.value && !hasPlainText(newActivityText.value)) return
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
    is_internal: newActivityIsInternal.value,
  })
  activitySubmitting.value = false
  if (res.ok) {
    activities.value.unshift(res.data)
    newActivityText.value = ''
    newActivityIsInternal.value = false
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
    description_html: newTaskDescription.value,
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
// Reactions (emoji)
// ---------------------------------------------------------------------------
const COMMON_EMOJIS = ['👍', '❤️', '😂', '😮', '👏', '🎉', '🔥', '✅']
const emojiPickerActivityId = ref<string | null>(null)

// Voice-memo: per-activity toggle for the (optional) transcript collapse.
const expandedTranscriptIds = ref<Set<string>>(new Set())

function toggleTranscript(activityId: string) {
  const next = new Set(expandedTranscriptIds.value)
  if (next.has(activityId)) next.delete(activityId)
  else next.add(activityId)
  expandedTranscriptIds.value = next
}

function formatVoiceMemoDuration(value: unknown): string {
  const total = Math.max(0, Math.floor(Number(value) || 0))
  const minutes = Math.floor(total / 60).toString().padStart(2, '0')
  const seconds = (total % 60).toString().padStart(2, '0')
  return `${minutes}:${seconds}`
}

function openEmojiPicker(activityId: string) {
  emojiPickerActivityId.value = emojiPickerActivityId.value === activityId ? null : activityId
}

async function toggleReaction(activityId: string, emoji: string) {
  const res = await api.post<ReactionSummary>(`/api/v1/crm/activities/${activityId}/reactions`, { emoji })
  emojiPickerActivityId.value = null
  if (!res.ok) {
    toast.error(t('leadDetail.activityFailed'))
    return
  }
  const activity = activities.value.find((a) => a.id === activityId)
  if (!activity) return
  if (!activity.reactions) activity.reactions = []
  const idx = activity.reactions.findIndex((r) => r.emoji === emoji)
  if (idx === -1) {
    if (res.data.count > 0) activity.reactions.push(res.data)
  } else {
    if (res.data.count === 0) activity.reactions.splice(idx, 1)
    else activity.reactions[idx] = res.data
  }
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
  await Promise.all([
    loadActivities(),
    loadTeamMembers(),
    loadStreamlineTools(),
    streamlinePrefs.load(),
  ])
  on('activity.created', onWsActivityCreated)
})

onUnmounted(() => {
  off('activity.created', onWsActivityCreated)
})

// Expose for parent lazy-load pattern (call load() when tab becomes active)
defineExpose({ load: () => loadActivities(1) })
</script>

<template>
  <div class="space-y-4" data-testid="activity-timeline">
    <!-- ================================================================ -->
    <!-- Unified action composer (hidden when hideComposer=true)          -->
    <!-- ================================================================ -->
    <div v-if="!hideComposer" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4" data-testid="activity-timeline-composer">

      <!-- Step 1: Action type picker -->
      <div v-if="!selectedActionType">
        <p class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2.5">{{ t('leadDetail.chooseActionType') }}</p>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="item in actionPickerItems"
            :key="item.value"
            data-testid="activity-action-option"
            :data-action="item.value"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:border-red-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
            @click="selectedActionType = item.value; newActivityText = ''"
          >
            <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
            {{ item.label }}
          </button>
        </div>
      </div>

      <!-- Step 2a: Activity form (comment / call / meeting / email) -->
      <div v-else-if="selectedActionType !== 'task'" class="flex flex-col gap-2">
        <div class="flex items-center gap-2 mb-1">
          <component :is="activityIcon(selectedActionType)" class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
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
        <div class="flex items-center justify-between gap-2">
          <label class="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300 select-none cursor-pointer">
            <input
              v-model="newActivityIsInternal"
              type="checkbox"
              data-testid="activity-composer-internal"
              class="rounded border-gray-300 dark:border-gray-600 text-red-600 focus:ring-red-400"
            />
            <span>{{ t('leadDetail.markInternal') }}</span>
          </label>
          <button
            :disabled="activitySubmitting || (activityTextRequired && !hasPlainText(newActivityText))"
            data-testid="activity-composer-submit"
            class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="addActivity"
          >{{ activitySubmitting ? '…' : t('leadDetail.activitySubmit') }}</button>
        </div>
      </div>

      <!-- Step 2b: Task creation form -->
      <div v-else class="space-y-3">
        <div class="flex items-center gap-2 mb-1">
          <ClipboardDocumentListIcon class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
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
              <BellIcon class="w-3.5 h-3.5" /> {{ m.label }}
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
            data-testid="activity-composer-task-submit"
            class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="addTask"
          >{{ taskSubmitting ? '…' : t('leadDetail.addTask') }}</button>
        </div>
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- Activity feed                                                      -->
    <!-- ================================================================ -->

    <!-- Filter dropdown -->
    <div class="flex items-center justify-end">
      <StreamlineFilterDropdown
        :tools="streamlineTools"
        :model-value="visibleTypes"
        :is-customised="streamlinePrefs.isCustomised"
        @update:visible="onFilterChange"
      />
    </div>

    <div v-if="activitiesLoading" class="animate-pulse space-y-2" data-testid="activity-timeline-loading">
      <div v-for="i in 3" :key="i" class="h-16 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <div v-else-if="filteredActivities.length === 0" class="text-center py-10 text-gray-400 text-sm" data-testid="activity-timeline-empty">
      {{ activities.length > 0 ? t('leadDetail.noActivitiesForFilter') : t('leadDetail.noActivities') }}
    </div>

    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700" data-testid="activity-timeline-list">
      <div
        v-for="act in filteredActivities"
        :key="act.id"
        class="flex items-start gap-3 p-4"
        data-testid="activity-item"
        :data-activity-id="act.id"
        :data-activity-type="act.type"
        :data-activity-internal="act.is_internal ? 'true' : 'false'"
      >
        <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5"
          :class="act.type === 'task_completed' ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
            : act.type === 'status_change' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
            : act.type === 'comment' ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'"
        >
          <component :is="activityIcon(act.type)" class="w-4 h-4" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-xs font-semibold text-gray-700 dark:text-gray-300">
              {{ activityTypeLabel(act.type) }}
              <template v-if="act.type === 'entity_change' && act.tool_payload && ((act.tool_payload as Record<string, string>).field_label || (act.tool_payload as Record<string, string>).field)">
                {{ (act.tool_payload as Record<string, string>).field_label || (act.tool_payload as Record<string, string>).field }}
              </template>
            </span>
            <!-- Calendar / Task unification — status pill for scheduled activities (meeting/call) -->
            <template v-if="act.type === 'meeting_scheduled' || act.type === 'call_scheduled'">
              <span
                v-if="(act.tool_payload as Record<string, unknown> | null)?.task_status"
                data-testid="scheduled-task-status-badge"
                class="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide"
                :class="scheduledTaskStatusBadgeClass(((act.tool_payload as Record<string, unknown>).task_status as string))"
              >{{ t(`leadDetail.scheduledTaskStatus.${((act.tool_payload as Record<string, unknown>).task_status as string)}`) }}</span>
            </template>
            <span
              v-if="act.is_internal"
              data-testid="activity-internal-badge"
              class="inline-flex items-center px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 text-[10px] font-semibold uppercase tracking-wide"
              :title="t('leadDetail.activityInternalTooltip')"
            >{{ t('leadDetail.activityInternal') }}</span>
            <span v-if="act.user_name" class="relative group/avatar flex items-center">
              <span
                class="inline-flex items-center justify-center w-5 h-5 rounded-full overflow-hidden bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-[10px] font-semibold flex-shrink-0 cursor-default"
                :title="act.user_name"
              >
                <img
                  v-if="act.user_avatar_url"
                  :src="act.user_avatar_url"
                  :alt="act.user_name"
                  class="w-full h-full object-cover"
                />
                <template v-else>{{ userInitials(act.user_name) }}</template>
              </span>
              <!-- Tooltip bubble shown on hover -->
              <span
                class="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded-lg bg-gray-900 dark:bg-gray-700 px-2 py-0.5 text-[10px] text-white opacity-0 group-hover/avatar:opacity-100 transition-opacity z-10"
              >{{ act.user_name }}</span>
            </span>
            <span class="text-xs text-gray-400">{{ formatTime(act.created_at) }}</span>
          </div>
          <!-- eslint-disable-next-line vue/no-v-html -->
          <p v-if="act.content_text" class="text-sm text-gray-700 dark:text-gray-300 mt-0.5 prose prose-sm dark:prose-invert max-w-none" v-html="sanitizeHtml(act.content_text)" />
          <p v-if="act.type === 'status_change'" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
            {{ t('leadDetail.statusChangedArrow', {
              from: translateLeadStatus((act.metadata as Record<string, string>).old_status ?? ''),
              to: translateLeadStatus((act.metadata as Record<string, string>).new_status ?? ''),
            }) }}
          </p>
          <p v-else-if="act.type === 'task_completed' && (act.metadata as Record<string, string>).title" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
            {{ (act.metadata as Record<string, string>).title }}
          </p>
          <p v-else-if="act.type === 'task_assigned' && (act.metadata as Record<string, string>).task_title" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
            {{ (act.metadata as Record<string, string>).task_title }}
          </p>
          <p v-else-if="act.type === 'entity_change' && act.tool_payload" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
            <span class="line-through text-red-500 dark:text-red-400">{{ cleanFieldValue((act.tool_payload as Record<string, string>).old_value) }}</span>
            →
            <span class="font-medium text-green-600 dark:text-green-400">{{ cleanFieldValue((act.tool_payload as Record<string, string>).new_value) }}</span>
          </p>
          <RouterLink
            v-if="act.type === 'proposal_created' && act.metadata?.proposal_id"
            :to="`/app/proposals/${act.metadata.proposal_id}`"
            class="text-xs text-red-600 hover:text-red-700 mt-0.5 inline-block"
          >
            {{ t('leadDetail.viewProposal') }} →
          </RouterLink>

          <!-- Voice memo player + (optional) transcript collapse -->
          <div
            v-if="act.type === 'voice_memo' && (act.metadata as Record<string, string>)?.url"
            class="mt-2 space-y-1.5"
            data-testid="voice-memo-player"
            :data-activity-id="act.id"
          >
            <div class="flex items-center gap-2">
              <audio
                :src="(act.metadata as Record<string, string>).url"
                controls
                preload="metadata"
                class="flex-1 min-w-0 max-w-md"
              />
              <span
                v-if="(act.metadata as Record<string, unknown>).duration_seconds !== undefined && (act.metadata as Record<string, unknown>).duration_seconds !== null && (act.metadata as Record<string, unknown>).duration_seconds !== ''"
                class="text-xs text-gray-500 dark:text-gray-400 tabular-nums flex-shrink-0"
                data-testid="voice-memo-duration"
              >{{ formatVoiceMemoDuration((act.metadata as Record<string, unknown>).duration_seconds) }}</span>
            </div>
            <div
              v-if="(act.metadata as Record<string, string>)?.transcript"
              data-testid="voice-memo-transcript-wrapper"
            >
              <button
                type="button"
                class="text-xs text-red-600 hover:text-red-700 dark:text-red-400 inline-flex items-center gap-1"
                data-testid="voice-memo-transcript-toggle"
                @click="toggleTranscript(act.id)"
              >
                {{ expandedTranscriptIds.has(act.id)
                  ? t('voiceMemo.hideTranscript')
                  : t('voiceMemo.showTranscript') }}
              </button>
              <p
                v-if="expandedTranscriptIds.has(act.id)"
                class="mt-1 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap"
                data-testid="voice-memo-transcript"
              >{{ (act.metadata as Record<string, string>).transcript }}</p>
            </div>
          </div>

          <!-- Reactions row (visible only for comment activities) -->
          <div
            v-if="act.type === 'comment'"
            class="flex flex-wrap items-center gap-1.5 mt-2"
            data-testid="activity-reactions-row"
          >
            <button
              v-for="r in (act.reactions ?? [])"
              :key="r.emoji"
              data-testid="activity-reaction-chip"
              :data-emoji="r.emoji"
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs transition-colors"
              :class="r.reacted_by_me
                ? 'border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300'
                : 'border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:border-gray-300'"
              @click="toggleReaction(act.id, r.emoji)"
            >
              <span>{{ r.emoji }}</span>
              <span class="tabular-nums">{{ r.count }}</span>
            </button>
            <div class="relative">
              <button
                data-testid="activity-add-reaction"
                class="inline-flex items-center justify-center w-6 h-6 rounded-full border border-dashed border-gray-300 dark:border-gray-600 text-gray-400 hover:text-red-500 hover:border-red-300 transition-colors"
                :title="t('leadDetail.addReaction')"
                @click="openEmojiPicker(act.id)"
              >
                <FaceSmileIcon class="w-3.5 h-3.5" />
              </button>
              <div
                v-if="emojiPickerActivityId === act.id"
                data-testid="activity-emoji-picker"
                class="absolute z-20 mt-1 left-0 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl shadow-lg p-1 flex gap-0.5"
              >
                <button
                  v-for="emoji in COMMON_EMOJIS"
                  :key="emoji"
                  data-testid="activity-emoji-option"
                  :data-emoji="emoji"
                  class="w-7 h-7 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-base"
                  @click="toggleReaction(act.id, emoji)"
                >{{ emoji }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <button
      v-if="activitiesHasMore && !activitiesLoading"
      data-testid="activity-timeline-load-more"
      class="w-full py-2 text-sm text-gray-500 hover:text-red-600 border border-gray-200 dark:border-gray-700 rounded-xl"
      @click="loadActivities(activitiesPage + 1)"
    >{{ t('leadDetail.loadMore') }}</button>
  </div>
</template>

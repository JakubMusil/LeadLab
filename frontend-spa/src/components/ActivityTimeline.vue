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
import { useAuthStore } from '@/stores/auth'
import { useStreamlinePreferencesStore } from '@/stores/streamlinePreferences'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import StreamlineFilterDropdown from '@/components/StreamlineFilterDropdown.vue'
import TaskCard from '@/components/TaskCard.vue'
import { sanitizeHtml } from '@/utils/sanitizeHtml'
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
  PhotoIcon,
  DocumentIcon,
  DocumentTextIcon,
  DocumentCheckIcon,
  PencilSquareIcon,
  QuestionMarkCircleIcon,
  BellIcon,
  FlagIcon,
  UserCircleIcon,
  CalendarIcon,
  CalendarDaysIcon,
  MapPinIcon,
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
  ArrowUturnLeftIcon,
  FaceSmileIcon,
  TrashIcon,
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
const authStore = useAuthStore()
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
  // soft-delete
  is_deleted?: boolean
  deleted_at?: string | null
  deleted_by_name?: string | null
}

// Unified feed item — either an Activity or a Task (for Lead feed)
interface FeedItem {
  item_type: 'activity' | 'task'
  created_at: string
  activity: Activity | null
  task: Record<string, unknown> | null
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
  MapPinIcon,
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
  ArrowUturnLeftIcon,
  TrashIcon,
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
// Feed items for the unified lead feed (activities + tasks merged)
const feedItems = ref<FeedItem[]>([])
const useFeed = computed(() => props.entityType === 'lead')

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
const _taskGroupTypes = ['task_assigned', 'task_completed', 'task_created', 'task_reopened'] as const

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

// ---------------------------------------------------------------------------
// displayItems — unified list for the template v-for
// Merges task feed items (for Lead) with filtered activity items.
// Each item carries _type, _key and _created_at for template branching.
// ---------------------------------------------------------------------------
type DisplayItem = (Activity & { _type: 'activity'; _key: string; _created_at: string; _task?: never }) |
  { _type: 'task'; _key: string; _created_at: string; _task: Record<string, unknown> } & Record<string, unknown>

const displayItems = computed<DisplayItem[]>(() => {
  if (useFeed.value) {
    return feedItems.value
      .filter((item) => {
        if (item.item_type === 'task') {
          // Task cards are controlled by the 'task' pseudo-type in the filter.
          // If the user has never customised the filter, visibleTypes contains
          // all 'important' activity types but NOT the 'task' pseudo-type
          // (which has no default_visibility in the registry).
          // We treat task cards as visible when either:
          //   a) the user explicitly enabled 'task' in their filter, OR
          //   b) the filter is in its default state (no customisation)
          const prefs = streamlinePrefs
          if (!prefs.isCustomised) return true
          return visibleTypes.value.has('task')
        }
        if (!item.activity) return false
        return visibleTypes.value.has(item.activity.type)
      })
      .map((item): DisplayItem => {
        if (item.item_type === 'task') {
          return {
            _type: 'task',
            _key: `task-${(item.task as Record<string, unknown>)?.id}`,
            _created_at: item.created_at,
            _task: item.task as Record<string, unknown>,
          } as DisplayItem
        }
        const act = item.activity as Activity
        return { ...act, _type: 'activity', _key: act.id, _created_at: act.created_at } as DisplayItem
      })
  }
  // Non-lead entities — plain activity list
  return filteredActivities.value.map((a) => ({
    ...a,
    _type: 'activity' as const,
    _key: a.id,
    _created_at: a.created_at,
  })) as DisplayItem[]
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
  task_reopened: ArrowUturnLeftIcon,
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
  event_scheduled: CalendarIcon,
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
    task_reopened: t('leadDetail.typeTaskReopened'),
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
    event_scheduled: t('leadDetail.typeEventScheduled'),
    task_expired: t('leadDetail.typeTaskExpired'),
    link: t('leadDetail.typeLink'),
    voice_memo: t('leadDetail.typeVoiceMemo'),
    system_note: t('leadDetail.typeSystemNote'),
    todo_items_added: t('leadDetail.typeTodoItems'),
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
  // Lead uses the unified feed endpoint (Activity + Task merged)
  if (props.entityType === 'lead') return `/api/v1/crm/opportunities/${props.entityId}/feed?page=${page}&page_size=20`
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
    if (useFeed.value) {
      // Unified feed for Lead — merges Activity + Task
      const res = await api.get<FeedItem[]>(listUrl(page))
      if (res.ok) {
        if (page === 1) feedItems.value = res.data
        else feedItems.value = [...feedItems.value, ...res.data]
        activitiesPage.value = page
        activitiesHasMore.value = res.data.length === 20
        // Keep activities in sync for WebSocket / reaction handling
        activities.value = res.data
          .filter((f) => f.item_type === 'activity' && f.activity)
          .map((f) => f.activity as Activity)
      }
    } else {
      const res = await api.get<Activity[]>(listUrl(page))
      if (res.ok) {
        if (page === 1) activities.value = res.data
        else activities.value = [...activities.value, ...res.data]
        activitiesPage.value = page
        activitiesHasMore.value = res.data.length === 20
      }
    }
  } finally {
    activitiesLoading.value = false
  }
}

// ---------------------------------------------------------------------------
// Adding activities
// ---------------------------------------------------------------------------
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

function voiceMemoMetadata(act: Activity): Record<string, unknown> {
  return (act.metadata as Record<string, unknown> | null) ?? {}
}

function voiceMemoUrl(act: Activity): string {
  const url = voiceMemoMetadata(act).url
  return typeof url === 'string' ? url : ''
}

function voiceMemoTranscript(act: Activity): string {
  const transcript = voiceMemoMetadata(act).transcript
  return typeof transcript === 'string' ? transcript : ''
}

function voiceMemoDurationSeconds(act: Activity): number | null {
  const raw = voiceMemoMetadata(act).duration_seconds
  if (raw === undefined || raw === null || raw === '') return null
  const num = Number(raw)
  return Number.isFinite(num) ? num : null
}

// ---------------------------------------------------------------------------
// File upload helpers (Fáze 7.2)
// ---------------------------------------------------------------------------
//
// The `file_upload` Activity carries the user-facing label in
// `metadata.title`, the storage URL in `metadata.url`, and the
// server-populated technical fields (`filename`, `size_bytes`,
// `mime_type`, `source_kind`, `store_locally`, `fetch_status`) which
// feed into the file-card renderer below.

function fileUploadMetadata(act: Activity): Record<string, unknown> {
  return (act.metadata as Record<string, unknown> | null) ?? {}
}

function fileUploadTitle(act: Activity): string {
  const value = fileUploadMetadata(act).title
  return typeof value === 'string' ? value : ''
}

function fileUploadUrl(act: Activity): string {
  const value = fileUploadMetadata(act).url
  return typeof value === 'string' ? value : ''
}

function fileUploadFilename(act: Activity): string {
  const value = fileUploadMetadata(act).filename
  return typeof value === 'string' ? value : ''
}

function fileUploadMime(act: Activity): string {
  const value = fileUploadMetadata(act).mime_type
  return typeof value === 'string' ? value.toLowerCase() : ''
}

function fileUploadSourceKind(act: Activity): 'url' | 'upload' {
  return fileUploadMetadata(act).source_kind === 'url' ? 'url' : 'upload'
}

function fileUploadIsExternal(act: Activity): boolean {
  if (fileUploadSourceKind(act) !== 'url') return false
  const storeLocally = fileUploadMetadata(act).store_locally
  // Only treat as external when explicitly opted out of local storage
  // *and* the async fetch hasn't already replaced the URL.
  return storeLocally === false
}

function fileUploadFetchPending(act: Activity): boolean {
  if (fileUploadSourceKind(act) !== 'url') return false
  if (fileUploadMetadata(act).store_locally === false) return false
  const status = fileUploadMetadata(act).fetch_status
  return status !== 'ok' && status !== 'failed'
}

function fileUploadSizeBytes(act: Activity): number | null {
  const raw = fileUploadMetadata(act).size_bytes
  if (raw === undefined || raw === null || raw === '') return null
  const num = Number(raw)
  return Number.isFinite(num) && num > 0 ? num : null
}

function fileUploadFormattedSize(act: Activity): string {
  const bytes = fileUploadSizeBytes(act)
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileUploadIcon(act: Activity): Component {
  const mime = fileUploadMime(act)
  const filename = fileUploadFilename(act).toLowerCase()
  if (mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|svg|bmp)$/.test(filename)) {
    return PhotoIcon
  }
  if (
    mime === 'application/pdf' ||
    mime.includes('msword') ||
    mime.includes('officedocument') ||
    /\.(pdf|docx?|xlsx?|pptx?|odt|ods|odp)$/.test(filename)
  ) {
    return DocumentTextIcon
  }
  return DocumentIcon
}

function fileUploadIsImage(act: Activity): boolean {
  const mime = fileUploadMime(act)
  const filename = fileUploadFilename(act).toLowerCase()
  return mime.startsWith('image/') || /\.(png|jpe?g|gif|webp|bmp)$/.test(filename)
}

function fileUploadIsVideo(act: Activity): boolean {
  const mime = fileUploadMime(act)
  const filename = fileUploadFilename(act).toLowerCase()
  return mime.startsWith('video/') || /\.(mp4|webm|mov|avi|mkv|m4v)$/.test(filename)
}

// ---------------------------------------------------------------------------
// Event scheduled helpers (Fáze 7.3)
// ---------------------------------------------------------------------------
//
// `event_scheduled` carries calendar metadata in `act.metadata`:
//   - `start_at` / `end_at` (ISO datetime, or ISO date when `all_day`)
//   - `all_day` (bool)
//   - `location` (string)
//   - `attendees` (string[]) — user IDs or external email/handles
//   - `description` (string, multiline)
//
// We also surface the linked Task's `task_status` via `tool_payload` (see
// `_ScheduledActivityTool.render_payload`) so the dedicated card can show
// "Done"/"Expired" without an extra request.

function eventScheduledMeta(act: Activity): Record<string, unknown> {
  return (act.metadata as Record<string, unknown> | null) ?? {}
}

function eventScheduledIsAllDay(act: Activity): boolean {
  return Boolean(eventScheduledMeta(act).all_day)
}

function eventScheduledLocation(act: Activity): string {
  const value = eventScheduledMeta(act).location
  return typeof value === 'string' ? value : ''
}

function eventScheduledDescription(act: Activity): string {
  const value = eventScheduledMeta(act).description
  return typeof value === 'string' ? value : ''
}

function eventScheduledAttendees(act: Activity): string[] {
  const raw = eventScheduledMeta(act).attendees
  if (!Array.isArray(raw)) return []
  return raw.map((x) => String(x)).filter((s) => s.length > 0)
}

function eventScheduledRange(act: Activity): string {
  const meta = eventScheduledMeta(act)
  const startRaw = meta.start_at
  const endRaw = meta.end_at
  const start = typeof startRaw === 'string' && startRaw ? new Date(startRaw) : null
  const end = typeof endRaw === 'string' && endRaw ? new Date(endRaw) : null
  if (!start || Number.isNaN(start.getTime())) return ''
  // All-day events show just the date (one date when start === end day).
  if (eventScheduledIsAllDay(act)) {
    const startDate = start.toLocaleDateString()
    if (!end || Number.isNaN(end.getTime())) return startDate
    const endDate = end.toLocaleDateString()
    return startDate === endDate ? startDate : `${startDate} – ${endDate}`
  }
  const startStr = start.toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
  if (!end || Number.isNaN(end.getTime()) || end.getTime() === start.getTime()) {
    return startStr
  }
  const sameDay =
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth() &&
    start.getDate() === end.getDate()
  const endStr = sameDay
    ? end.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : end.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
  return `${startStr} – ${endStr}`
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

// Find the first task_created/task_assigned/task_reopened activity in the
// feed that references a given task ID — used to attach reactions to task cards.
function taskLinkedActivity(taskId: string): Activity | null {
  if (!useFeed.value) return null
  for (const item of feedItems.value) {
    if (item.item_type !== 'activity' || !item.activity) continue
    const a = item.activity as Activity
    const meta = a.metadata as Record<string, unknown>
    if (
      ['task_created', 'task_assigned', 'task_reopened'].includes(a.type) &&
      String(meta.task_id ?? '') === taskId
    ) {
      return a
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// WebSocket real-time update
function canDelete(act: Activity): boolean {
  if (act.is_deleted) return false
  const currentUserId = authStore.user ? String(authStore.user.id) : ''
  const isAuthor = act.user_id ? act.user_id === currentUserId : false
  const isAdmin = ['admin', 'owner'].includes(authStore.membership?.role ?? '')
  return isAuthor || isAdmin
}

async function deleteActivity(activityId: string) {
  const res = await api.delete<Activity>(`/api/v1/crm/activities/${activityId}`)
  if (!res.ok) {
    toast.error(t('leadDetail.activityDeleteFailed'))
    return
  }
  // Replace in-place with tombstone from response
  const updated = res.data as Activity
  const replaceInList = (list: Activity[]) => {
    const idx = list.findIndex((a) => a.id === activityId)
    if (idx !== -1) list[idx] = updated
  }
  replaceInList(activities.value)
  if (useFeed.value) {
    const fi = feedItems.value.find((f) => f.item_type === 'activity' && f.activity?.id === activityId)
    if (fi) fi.activity = updated
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

    <!-- Empty state -->
    <div
      v-else-if="displayItems.length === 0"
      class="text-center py-10 text-gray-400 text-sm"
      data-testid="activity-timeline-empty"
    >
      {{ activities.length > 0 ? t('leadDetail.noActivitiesForFilter') : t('leadDetail.noActivities') }}
    </div>

    <!-- Unified feed list — works for both Lead (Activity+Task) and other entities (Activity only) -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700" data-testid="activity-timeline-list">
      <template v-for="item in displayItems" :key="item._key">

        <!-- Task card row -->
        <div
          v-if="item._type === 'task'"
          class="flex items-start gap-3 px-4 pt-3 pb-3"
          data-testid="feed-task-item"
        >
          <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400">
            <ClipboardDocumentListIcon class="w-4 h-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs font-semibold text-gray-700 dark:text-gray-300">{{ t('leadDetail.typeTask') }}</span>
              <span class="text-xs text-gray-400">{{ formatTime(item._created_at) }}</span>
            </div>
            <TaskCard
              :task="item._task"
              @refreshed="loadActivities(1)"
            />
            <!-- Reactions — bound to the linked task_created/task_assigned activity -->
            <template v-if="taskLinkedActivity(String((item._task as Record<string,unknown>).id ?? ''))">
              <div class="flex flex-wrap items-center gap-1.5 mt-2">
                <button
                  v-for="r in (taskLinkedActivity(String((item._task as Record<string,unknown>).id ?? ''))?.reactions ?? [])"
                  :key="r.emoji"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs transition-colors"
                  :class="r.reacted_by_me
                    ? 'border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300'
                    : 'border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:border-gray-300'"
                  @click="toggleReaction(taskLinkedActivity(String((item._task as Record<string,unknown>).id ?? ''))!.id, r.emoji)"
                >
                  <span>{{ r.emoji }}</span>
                  <span class="tabular-nums">{{ r.count }}</span>
                </button>
                <div class="relative">
                  <button
                    class="inline-flex items-center justify-center w-6 h-6 rounded-full border border-dashed border-gray-300 dark:border-gray-600 text-gray-400 hover:text-red-500 hover:border-red-300 transition-colors"
                    :title="t('leadDetail.addReaction')"
                    @click="openEmojiPicker(taskLinkedActivity(String((item._task as Record<string,unknown>).id ?? ''))!.id)"
                  >
                    <FaceSmileIcon class="w-3.5 h-3.5" />
                  </button>
                  <div
                    v-if="emojiPickerActivityId === taskLinkedActivity(String((item._task as Record<string,unknown>).id ?? ''))?.id"
                    class="absolute z-20 mt-1 left-0 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl shadow-lg p-1 flex gap-0.5"
                  >
                    <button
                      v-for="emoji in COMMON_EMOJIS"
                      :key="emoji"
                      class="w-7 h-7 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-base"
                      @click="toggleReaction(taskLinkedActivity(String((item._task as Record<string,unknown>).id ?? ''))!.id, emoji)"
                    >{{ emoji }}</button>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Activity row -->
        <div
          v-else
          class="flex items-start gap-3 p-4 group/row"
          data-testid="activity-item"
          :data-activity-id="item.id"
          :data-activity-type="item.type"
          :data-activity-internal="item.is_internal ? 'true' : 'false'"
        >
          <!-- Tombstone — soft-deleted activity -->
          <template v-if="(item as unknown as Activity).is_deleted">
            <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5 bg-gray-100 dark:bg-gray-700 text-gray-400">
              <TrashIcon class="w-4 h-4" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-xs text-gray-400 dark:text-gray-500 italic">
                {{ t('leadDetail.activityDeleted', {
                  user: (item as unknown as Activity).deleted_by_name ?? t('leadDetail.unknownUser'),
                  date: formatTime((item as unknown as Activity).deleted_at ?? item.created_at),
                }) }}
              </p>
            </div>
          </template>

          <!-- Normal activity content -->
          <template v-else>
          <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5"
            :class="item.type === 'task_completed' ? 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400'
              : item.type === 'status_change' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
              : item.type === 'comment' ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'"
          >
            <component :is="activityIcon(item.type)" class="w-4 h-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs font-semibold text-gray-700 dark:text-gray-300">
                {{ activityTypeLabel(item.type) }}
                <template v-if="item.type === 'entity_change' && item.tool_payload && ((item.tool_payload as Record<string, string>).field_label || (item.tool_payload as Record<string, string>).field)">
                  {{ (item.tool_payload as Record<string, string>).field_label || (item.tool_payload as Record<string, string>).field }}
                </template>
              </span>
              <template v-if="item.type === 'meeting_scheduled' || item.type === 'call_scheduled' || item.type === 'event_scheduled'">
                <span
                  v-if="(item.tool_payload as Record<string, unknown> | null)?.task_status"
                  data-testid="scheduled-task-status-badge"
                  class="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide"
                  :class="scheduledTaskStatusBadgeClass(((item.tool_payload as Record<string, unknown>).task_status as string))"
                >{{ t(`leadDetail.scheduledTaskStatus.${((item.tool_payload as Record<string, unknown>).task_status as string)}`) }}</span>
              </template>
              <span
                v-if="item.is_internal"
                data-testid="activity-internal-badge"
                class="inline-flex items-center px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 text-[10px] font-semibold uppercase tracking-wide"
                :title="t('leadDetail.activityInternalTooltip')"
              >{{ t('leadDetail.activityInternal') }}</span>
              <span v-if="item.user_name" class="relative group/avatar flex items-center">
                <span
                  class="inline-flex items-center justify-center w-5 h-5 rounded-full overflow-hidden bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-[10px] font-semibold flex-shrink-0 cursor-default"
                  :title="item.user_name"
                >
                  <img
                    v-if="item.user_avatar_url"
                    :src="item.user_avatar_url"
                    :alt="item.user_name"
                    class="w-full h-full object-cover"
                  />
                  <template v-else>{{ userInitials(item.user_name) }}</template>
                </span>
                <span
                  class="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 whitespace-nowrap rounded-lg bg-gray-900 dark:bg-gray-700 px-2 py-0.5 text-[10px] text-white opacity-0 group-hover/avatar:opacity-100 transition-opacity z-10"
                >{{ item.user_name }}</span>
              </span>
              <span class="text-xs text-gray-400">{{ formatTime(item.created_at) }}</span>
              <!-- Delete button — visible on hover for author or admin -->
              <button
                v-if="canDelete(item as unknown as Activity)"
                class="ml-auto opacity-0 group-hover/row:opacity-100 transition-opacity text-gray-300 hover:text-red-500 dark:hover:text-red-400 flex-shrink-0"
                :title="t('leadDetail.deleteActivity')"
                @click.stop="deleteActivity(item.id)"
              >
                <TrashIcon class="w-3.5 h-3.5" />
              </button>
            </div>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <p v-if="item.content_text" class="text-sm text-gray-700 dark:text-gray-300 mt-0.5 prose prose-sm dark:prose-invert max-w-none" v-html="sanitizeHtml(item.content_text)" />
            <p v-if="item.type === 'status_change'" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
              {{ t('leadDetail.statusChangedArrow', {
                from: translateLeadStatus((item.metadata as Record<string, string>).old_status ?? ''),
                to: translateLeadStatus((item.metadata as Record<string, string>).new_status ?? ''),
              }) }}
            </p>
            <p v-else-if="item.type === 'task_completed' && (item.metadata as Record<string, string>).title" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
              {{ (item.metadata as Record<string, string>).title }}
            </p>
            <p v-else-if="item.type === 'task_assigned' && (item.metadata as Record<string, string>).task_title" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
              {{ (item.metadata as Record<string, string>).task_title }}
            </p>
            <p v-else-if="item.type === 'entity_change' && item.tool_payload" class="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
              <span class="line-through text-red-500 dark:text-red-400">{{ cleanFieldValue((item.tool_payload as Record<string, string>).old_value) }}</span>
              →
              <span class="font-medium text-green-600 dark:text-green-400">{{ cleanFieldValue((item.tool_payload as Record<string, string>).new_value) }}</span>
            </p>
            <RouterLink
              v-if="item.type === 'proposal_created' && item.metadata?.proposal_id"
              :to="`/app/proposals/${item.metadata.proposal_id}`"
              class="text-xs text-red-600 hover:text-red-700 mt-0.5 inline-block"
            >
              {{ t('leadDetail.viewProposal') }} →
            </RouterLink>

            <!-- Voice memo player -->
            <div
              v-if="item.type === 'voice_memo' && voiceMemoUrl(item as unknown as Activity)"
              class="mt-2 space-y-1.5"
              data-testid="voice-memo-player"
              :data-activity-id="item.id"
            >
              <div class="flex items-center gap-2">
                <audio
                  :src="voiceMemoUrl(item as unknown as Activity)"
                  controls
                  preload="metadata"
                  class="flex-1 min-w-0 max-w-md"
                />
                <span
                  v-if="voiceMemoDurationSeconds(item as unknown as Activity) !== null"
                  class="text-xs text-gray-500 dark:text-gray-400 tabular-nums flex-shrink-0"
                  data-testid="voice-memo-duration"
                >{{ formatVoiceMemoDuration(voiceMemoDurationSeconds(item as unknown as Activity)) }}</span>
              </div>
              <div v-if="voiceMemoTranscript(item as unknown as Activity)" data-testid="voice-memo-transcript-wrapper">
                <button
                  type="button"
                  class="text-xs text-red-600 hover:text-red-700 dark:text-red-400 inline-flex items-center gap-1"
                  data-testid="voice-memo-transcript-toggle"
                  @click="toggleTranscript(item.id)"
                >
                  {{ expandedTranscriptIds.has(item.id) ? t('voiceMemo.hideTranscript') : t('voiceMemo.showTranscript') }}
                </button>
                <p
                  v-if="expandedTranscriptIds.has(item.id)"
                  class="mt-1 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap"
                  data-testid="voice-memo-transcript"
                >{{ voiceMemoTranscript(item as unknown as Activity) }}</p>
              </div>
            </div>

            <!-- File upload card — three variants: image thumbnail, video player, generic file -->
            <div
              v-if="item.type === 'file_upload' && fileUploadUrl(item as unknown as Activity)"
              class="mt-2"
              data-testid="file-upload-card"
              :data-activity-id="item.id"
              :data-source-kind="fileUploadSourceKind(item as unknown as Activity)"
            >
              <!-- Image: thumbnail with link to full size -->
              <template v-if="fileUploadIsImage(item as unknown as Activity)">
                <a
                  :href="fileUploadUrl(item as unknown as Activity)"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="block"
                >
                  <img
                    :src="fileUploadUrl(item as unknown as Activity)"
                    :alt="fileUploadTitle(item as unknown as Activity) || fileUploadFilename(item as unknown as Activity)"
                    class="max-h-64 max-w-full rounded-xl border border-gray-200 dark:border-gray-600 object-cover hover:opacity-90 transition-opacity"
                    loading="lazy"
                  />
                </a>
                <p v-if="fileUploadFilename(item as unknown as Activity)" class="mt-1 text-xs text-gray-400 dark:text-gray-500 truncate">
                  {{ fileUploadTitle(item as unknown as Activity) || fileUploadFilename(item as unknown as Activity) }}
                  <span v-if="fileUploadFormattedSize(item as unknown as Activity)" class="ml-1">· {{ fileUploadFormattedSize(item as unknown as Activity) }}</span>
                </p>
              </template>

              <!-- Video: inline player -->
              <template v-else-if="fileUploadIsVideo(item as unknown as Activity)">
                <video
                  :src="fileUploadUrl(item as unknown as Activity)"
                  controls
                  preload="metadata"
                  class="max-h-64 max-w-full rounded-xl border border-gray-200 dark:border-gray-600"
                />
                <p v-if="fileUploadFilename(item as unknown as Activity)" class="mt-1 text-xs text-gray-400 dark:text-gray-500 truncate">
                  {{ fileUploadTitle(item as unknown as Activity) || fileUploadFilename(item as unknown as Activity) }}
                  <span v-if="fileUploadFormattedSize(item as unknown as Activity)" class="ml-1">· {{ fileUploadFormattedSize(item as unknown as Activity) }}</span>
                </p>
              </template>

              <!-- Generic file: icon + title + metadata -->
              <template v-else>
                <a
                  :href="fileUploadUrl(item as unknown as Activity)"
                  :target="fileUploadIsExternal(item as unknown as Activity) ? '_blank' : '_self'"
                  :rel="fileUploadIsExternal(item as unknown as Activity) ? 'noopener noreferrer' : undefined"
                  :download="fileUploadIsExternal(item as unknown as Activity) ? undefined : (fileUploadFilename(item as unknown as Activity) || true)"
                  class="flex items-center gap-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 px-3 py-2 hover:border-red-300 dark:hover:border-red-500/60 transition-colors"
                >
                  <component :is="fileUploadIcon(item as unknown as Activity)" class="w-6 h-6 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {{ fileUploadTitle(item as unknown as Activity) || fileUploadFilename(item as unknown as Activity) || t('fileUpload.untitled') }}
                    </p>
                    <p class="text-xs text-gray-500 dark:text-gray-400 truncate">
                      <span v-if="fileUploadFilename(item as unknown as Activity)">{{ fileUploadFilename(item as unknown as Activity) }}</span>
                      <span v-if="fileUploadFilename(item as unknown as Activity) && fileUploadFormattedSize(item as unknown as Activity)" class="mx-1">·</span>
                      <span v-if="fileUploadFormattedSize(item as unknown as Activity)" class="tabular-nums">{{ fileUploadFormattedSize(item as unknown as Activity) }}</span>
                      <span v-if="fileUploadIsExternal(item as unknown as Activity)" class="ml-1 inline-flex items-center px-1.5 py-0.5 rounded-md bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 text-[10px] font-semibold uppercase tracking-wide" data-testid="file-upload-external-badge">{{ t('fileUpload.externalLink') }}</span>
                      <span v-else-if="fileUploadFetchPending(item as unknown as Activity)" class="ml-1 inline-flex items-center px-1.5 py-0.5 rounded-md bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 text-[10px] font-semibold uppercase tracking-wide" data-testid="file-upload-fetching-badge">{{ t('fileUpload.fetching') }}</span>
                    </p>
                  </div>
                </a>
              </template>
            </div>

            <!-- Link card -->
            <a
              v-if="item.type === 'link' && (item.tool_payload as Record<string,unknown> | null)?.url"
              :href="(item.tool_payload as Record<string,string>).url"
              target="_blank"
              rel="noopener noreferrer"
              class="mt-2 flex items-start gap-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 px-3 py-2 hover:border-blue-300 dark:hover:border-blue-500/60 transition-colors"
              data-testid="link-card"
            >
              <LinkIcon class="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5" />
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-blue-600 dark:text-blue-400 truncate hover:underline">
                  {{ (item.tool_payload as Record<string,string>).title || (item.tool_payload as Record<string,string>).url }}
                </p>
                <p v-if="(item.tool_payload as Record<string,string>).description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                  {{ (item.tool_payload as Record<string,string>).description }}
                </p>
                <p class="text-xs text-gray-400 dark:text-gray-500 truncate mt-0.5">
                  {{ (item.tool_payload as Record<string,string>).url }}
                </p>
              </div>
            </a>

            <!-- Event scheduled card -->
            <div
              v-if="item.type === 'event_scheduled'"
              class="mt-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 px-3 py-2 space-y-1"
              data-testid="event-scheduled-card"
              :data-activity-id="item.id"
            >
              <div v-if="eventScheduledRange(item as unknown as Activity)" class="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-100" data-testid="event-scheduled-time">
                <CalendarIcon class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                <span class="font-medium tabular-nums">{{ eventScheduledRange(item as unknown as Activity) }}</span>
                <span v-if="eventScheduledIsAllDay(item as unknown as Activity)" class="inline-flex items-center px-1.5 py-0.5 rounded-md bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 text-[10px] font-semibold uppercase tracking-wide" data-testid="event-scheduled-all-day-badge">{{ t('event.allDay') }}</span>
              </div>
              <div v-if="eventScheduledLocation(item as unknown as Activity)" class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300" data-testid="event-scheduled-location">
                <MapPinIcon class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
                <span class="truncate">{{ eventScheduledLocation(item as unknown as Activity) }}</span>
              </div>
              <div v-if="eventScheduledAttendees(item as unknown as Activity).length" class="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300" data-testid="event-scheduled-attendees">
                <UsersIcon class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0 mt-0.5" />
                <div class="flex flex-wrap gap-1">
                  <span v-for="a in eventScheduledAttendees(item as unknown as Activity)" :key="a" class="inline-flex items-center px-2 py-0.5 rounded-lg bg-white dark:bg-gray-600 border border-gray-200 dark:border-gray-500 text-xs">{{ a }}</span>
                </div>
              </div>
              <p v-if="eventScheduledDescription(item as unknown as Activity)" class="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap" data-testid="event-scheduled-description">{{ eventScheduledDescription(item as unknown as Activity) }}</p>
            </div>

            <!-- Reactions row — available for every activity type -->
            <div class="flex flex-wrap items-center gap-1.5 mt-2" data-testid="activity-reactions-row">
              <button
                v-for="r in ((item as unknown as Activity).reactions ?? [])"
                :key="r.emoji"
                data-testid="activity-reaction-chip"
                :data-emoji="r.emoji"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs transition-colors"
                :class="r.reacted_by_me
                  ? 'border-red-300 bg-red-50 text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300'
                  : 'border-gray-200 bg-gray-50 text-gray-600 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 hover:border-gray-300'"
                @click="toggleReaction(item.id, r.emoji)"
              >
                <span>{{ r.emoji }}</span>
                <span class="tabular-nums">{{ r.count }}</span>
              </button>
              <div class="relative">
                <button
                  data-testid="activity-add-reaction"
                  class="inline-flex items-center justify-center w-6 h-6 rounded-full border border-dashed border-gray-300 dark:border-gray-600 text-gray-400 hover:text-red-500 hover:border-red-300 transition-colors"
                  :title="t('leadDetail.addReaction')"
                  @click="openEmojiPicker(item.id)"
                >
                  <FaceSmileIcon class="w-3.5 h-3.5" />
                </button>
                <div
                  v-if="emojiPickerActivityId === item.id"
                  data-testid="activity-emoji-picker"
                  class="absolute z-20 mt-1 left-0 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl shadow-lg p-1 flex gap-0.5"
                >
                  <button
                    v-for="emoji in COMMON_EMOJIS"
                    :key="emoji"
                    data-testid="activity-emoji-option"
                    :data-emoji="emoji"
                    class="w-7 h-7 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-base"
                    @click="toggleReaction(item.id, emoji)"
                  >{{ emoji }}</button>
                </div>
              </div>
            </div>
          </div>
          </template><!-- end normal activity content -->
        </div>
      </template>
    </div>

    <button
      v-if="activitiesHasMore && !activitiesLoading"
      data-testid="activity-timeline-load-more"
      class="w-full py-2 text-sm text-gray-500 hover:text-red-600 border border-gray-200 dark:border-gray-700 rounded-xl"
      @click="loadActivities(activitiesPage + 1)"
    >{{ t('leadDetail.loadMore') }}</button>
  </div>
</template>

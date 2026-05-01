<script setup lang="ts">
import { ref, computed, watch, onMounted, type Component } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useAuthStore } from '@/stores/auth'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import VoiceMemoRecorder from '@/components/VoiceMemoRecorder.vue'
import FileUploadComposer from '@/components/FileUploadComposer.vue'
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
  DocumentTextIcon,
  DocumentCheckIcon,
  ArrowsRightLeftIcon,
  PaperClipIcon,
  BellIcon,
  DevicePhoneMobileIcon,
  CalendarDaysIcon,
  LinkIcon,
  MicrophoneIcon,
  InformationCircleIcon,
  QuestionMarkCircleIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'

/**
 * EntitySidebarActionPicker — generic, entity-agnostic Quick Actions composer.
 *
 * Loads the toolbar tools for a given entity from
 * ``GET /api/v1/streamline/entity-toolbar/{entityType}`` and renders a
 * grouped, schema-driven UI:
 *   - tools are grouped into UX categories (communication / planning /
 *     files / system) — each category is a labelled section with its own
 *     accent colour
 *   - clicking an action opens a schema-driven form (top fields above the
 *     RichTextEditor body, footer fields below it)
 *   - the special-cased "task" pseudo-tool POSTs to ``/api/v1/crm/tasks``
 *     instead of ``/api/v1/crm/activities``
 *
 * The form renderer handles every JSON-Schema primitive used by the
 * registered Streamline tools today:
 *   - ``string`` / ``string + format=email|uri|date|date-time`` → typed input
 *   - ``integer`` / ``number`` (with ``minimum`` / ``maximum``) → numeric input
 *   - ``string + enum`` → ``<select>``
 *   - ``array`` → tag-style chip input (comma / Enter separated)
 *   - long-form fields (``transcript``, ``description``, ``notes``,
 *     ``message``) are auto-rendered as a ``<textarea>``.
 *
 * Emits ``activity-added`` / ``task-created`` / ``file-uploaded`` so the
 * parent can react (reload timeline, refresh task list, …).
 */

interface StreamlineTool {
  activity_type: string
  label: string
  icon: string
  channel?: string
  direction?: string
  form_schema: {
    type: string
    properties?: Record<string, unknown>
    required?: string[]
  }
}

const props = withDefaults(
  defineProps<{
    entityType: 'lead' | 'customer' | 'realization' | 'management' | 'proposal'
    entityId: string
    teamMembers?: MentionUser[]
    /**
     * Upload URL passed to RichTextEditor for inline file attachments inside
     * the comment composer. Emitted back via `file-uploaded`.
     */
    attachmentUploadUrl?: string
  }>(),
  {
    teamMembers: () => [],
    attachmentUploadUrl: undefined,
  },
)

const emit = defineEmits<{
  (e: 'activity-added'): void
  (e: 'task-created'): void
  (e: 'file-uploaded', file: unknown): void
}>()

const { t } = useI18n()
const toast = useToast()
const authStore = useAuthStore()

// Map icon name strings (from the Streamline Tool Registry) to Heroicon components.
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
  DocumentTextIcon,
  DocumentCheckIcon,
  DevicePhoneMobileIcon,
  CalendarDaysIcon,
  LinkIcon,
  MicrophoneIcon,
  InformationCircleIcon,
}

// Map activity_type → i18n key (preserves multi-language support).
const activityTypeLabelKey: Record<string, string> = {
  comment: 'leadDetail.typeComment',
  call: 'leadDetail.typeCall',
  meeting: 'leadDetail.typeMeeting',
  email_out: 'leadDetail.typeEmailOut',
  email_in: 'leadDetail.typeEmailIn',
  task: 'leadDetail.typeTask',
  sms_out: 'leadDetail.typeSmsOut',
  sms_in: 'leadDetail.typeSmsIn',
  whatsapp_out: 'leadDetail.typeWhatsAppOut',
  whatsapp_in: 'leadDetail.typeWhatsAppIn',
  meeting_scheduled: 'leadDetail.typeMeetingScheduled',
  event_scheduled: 'leadDetail.typeEventScheduled',
  link: 'leadDetail.typeLink',
  voice_memo: 'leadDetail.typeVoiceMemo',
  system_note: 'leadDetail.typeSystemNote',
  file_upload: 'leadDetail.typeFileUpload',
  todo_items: 'leadDetail.typeTodoItems',
  // Pseudo-tool for the unified messaging composer (no real activity_type).
  message: 'leadDetail.typeMessage',
}

// Short helper text shown below the action header so the user knows what
// the activity is for. Keys point at `leadDetail.toolHelp.<activity_type>`.
const activityTypeHelpKey: Record<string, string> = {
  comment: 'leadDetail.toolHelp.comment',
  call: 'leadDetail.toolHelp.call',
  meeting: 'leadDetail.toolHelp.meeting',
  meeting_scheduled: 'leadDetail.toolHelp.meeting_scheduled',
  event_scheduled: 'leadDetail.toolHelp.event_scheduled',
  email_out: 'leadDetail.toolHelp.email_out',
  email_in: 'leadDetail.toolHelp.email_in',
  sms_out: 'leadDetail.toolHelp.sms_out',
  sms_in: 'leadDetail.toolHelp.sms_in',
  whatsapp_out: 'leadDetail.toolHelp.whatsapp_out',
  whatsapp_in: 'leadDetail.toolHelp.whatsapp_in',
  link: 'leadDetail.toolHelp.link',
  file_upload: 'leadDetail.toolHelp.file_upload',
  voice_memo: 'leadDetail.toolHelp.voice_memo',
  system_note: 'leadDetail.toolHelp.system_note',
  task: 'leadDetail.toolHelp.task',
  todo_items: 'leadDetail.toolHelp.todo_items',
  message: 'leadDetail.toolHelp.message',
}

// ─── Tool category grouping (UX layout) ────────────────────────────────────
//
// The flat list of tools coming from the backend is grouped into four UX
// buckets so the sidebar isn't a wall of identical-looking buttons.  Each
// bucket has:
//   - an i18n label key
//   - an accent CSS class for the inactive-state ring/text
//   - a hover accent class
// The grouping is purely a frontend concern; the backend toolbar list still
// drives which tools exist and in which order they are inserted.

interface ToolCategory {
  key: 'communication' | 'planning' | 'files' | 'system' | 'other'
  labelKey: string
  // Activity types that belong to this category (in display order).
  activityTypes: string[]
  // Tailwind colour token used for the section header bar.
  accent: string
}

const TOOL_CATEGORIES: ToolCategory[] = [
  {
    key: 'communication',
    labelKey: 'leadDetail.toolCategory.communication',
    // Note: the 6 channel-specific email/SMS/WhatsApp tools (and `chat`) are
    // *not* listed here individually any more — they are replaced by the
    // unified pseudo-tool `'message'` further down, which surfaces
    // a Channel + Direction picker on top of the per-channel form schema.
    activityTypes: [
      'comment',
      'call',
      'meeting',
      'message',
    ],
    accent: 'red',
  },
  {
    key: 'planning',
    labelKey: 'leadDetail.toolCategory.planning',
    activityTypes: ['meeting_scheduled', 'event_scheduled', 'task', 'todo_items'],
    accent: 'blue',
  },
  {
    key: 'files',
    labelKey: 'leadDetail.toolCategory.files',
    activityTypes: ['file_upload', 'voice_memo', 'link'],
    accent: 'emerald',
  },
  {
    key: 'system',
    labelKey: 'leadDetail.toolCategory.system',
    activityTypes: ['system_note'],
    accent: 'amber',
  },
]

// ─── Toolbar loading ───────────────────────────────────────────────────────

const toolbarTools = ref<StreamlineTool[]>([])

async function loadToolbar() {
  const res = await api.get<StreamlineTool[]>(`/api/v1/streamline/entity-toolbar/${props.entityType}`)
  if (res.ok) toolbarTools.value = res.data
}

onMounted(() => {
  loadToolbar()
})

// Reload if the entity type changes (rare but possible via parent re-mount).
watch(() => props.entityType, () => {
  toolbarTools.value = []
  loadToolbar()
})

// ─── Unified "Message" composer ────────────────────────────────────────────
//
// The 6 channel-specific email/SMS/WhatsApp tools (and the generic `chat`
// tool) all live behind a single pseudo-tool `'message'`.  When the user
// picks "Message" from the action grid, we render a Channel + Direction
// selector that resolves to a concrete StreamlineTool from the toolbar
// registry — its activity_type and form_schema are then used verbatim by
// the existing schema-driven form & submit pipeline.
//
// Channels that aren't backed by a registered tool for the current entity
// type are filtered out, so the picker only ever offers channels the
// backend will actually accept.

interface MessageChannelOption {
  value: string                // 'email' | 'sms' | 'whatsapp' | 'chat'
  labelKey: string
  // Direction options that have a registered tool for this channel.
  directions: { value: 'out' | 'in'; labelKey: string }[]
}

// All possible channel/direction combinations (filtered later by registry).
const MESSAGE_CHANNEL_LABEL: Record<string, string> = {
  email: 'messageComposer.channelEmail',
  sms: 'messageComposer.channelSms',
  whatsapp: 'messageComposer.channelWhatsapp',
  chat: 'messageComposer.channelChat',
}
const _CHANNEL_ORDER = ['email', 'sms', 'whatsapp', 'chat'] as const

/** Tools available behind the unified composer (`channel != 'none'`). */
const messagingTools = computed(() =>
  toolbarTools.value.filter((t) => t.channel && t.channel !== 'none'),
)

/** Whether at least one messaging tool exists, i.e. the unified entry should be rendered. */
const hasMessagingTools = computed(() => messagingTools.value.length > 0)

/**
 * Channels the user can pick from in the unified composer, alongside the
 * directions actually supported by the backend for each channel.  A channel
 * with `direction = 'none'` (e.g. `chat`, which captures direction inside
 * its own form schema) is exposed without a Direction toggle.
 */
const messageChannelOptions = computed<MessageChannelOption[]>(() => {
  const byChannel = new Map<string, StreamlineTool[]>()
  for (const tool of messagingTools.value) {
    const ch = tool.channel ?? 'none'
    if (!byChannel.has(ch)) byChannel.set(ch, [])
    byChannel.get(ch)!.push(tool)
  }
  const result: MessageChannelOption[] = []
  for (const ch of _CHANNEL_ORDER) {
    const tools = byChannel.get(ch)
    if (!tools || tools.length === 0) continue
    const directions: { value: 'out' | 'in'; labelKey: string }[] = []
    if (tools.some((t) => t.direction === 'out')) {
      directions.push({ value: 'out', labelKey: 'messageComposer.directionOut' })
    }
    if (tools.some((t) => t.direction === 'in')) {
      directions.push({ value: 'in', labelKey: 'messageComposer.directionIn' })
    }
    result.push({ value: ch, labelKey: MESSAGE_CHANNEL_LABEL[ch] ?? ch, directions })
  }
  return result
})

// Composer selection state (only used while sidebarActionType === 'message').
const messageChannel = ref<string>('')
const messageDirection = ref<'out' | 'in' | ''>('')

/**
 * Resolve the user's (channel, direction) selection to a concrete registered
 * tool.  Falls back to the first matching channel tool when the channel has
 * no direction toggle (e.g. `chat`).  Returns ``null`` until a viable
 * combination is selected.
 */
const resolvedMessageTool = computed<StreamlineTool | null>(() => {
  if (!messageChannel.value) return null
  const candidates = messagingTools.value.filter((t) => t.channel === messageChannel.value)
  if (candidates.length === 0) return null
  const channelOption = messageChannelOptions.value.find((c) => c.value === messageChannel.value)
  // Channels without a direction toggle (e.g. `chat`) collapse to their
  // single tool regardless of any leftover direction state.
  if (!channelOption || channelOption.directions.length === 0) return candidates[0] ?? null
  if (!messageDirection.value) return null
  return (
    candidates.find((t) => t.direction === messageDirection.value) ?? null
  )
})

function pickMessageChannel(channel: string) {
  messageChannel.value = channel
  // Channels that capture direction inside their own form schema (e.g. chat)
  // expose no direction toggle, so any leftover direction selection from a
  // previously chosen channel must be cleared.
  const opt = messageChannelOptions.value.find((c) => c.value === channel)
  if (!opt || opt.directions.length === 0) messageDirection.value = ''
}

function pickMessageDirection(direction: 'out' | 'in') {
  messageDirection.value = direction
}

// ─── Activity composer state ───────────────────────────────────────────────

const sidebarActionType = ref('')
const sidebarActivityText = ref('')
const sidebarActivitySubmitting = ref(false)
const sidebarRichEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
type FieldValue = string | number | string[] | null
const sidebarExtraFields = ref<Record<string, FieldValue>>({})
// Boolean schema fields (e.g. ``event_scheduled.all_day``) are stored
// in a separate ref because ``<input type="checkbox" v-model>`` requires
// a boolean target whereas the text/array inputs above require strings.
// At submit time we merge `sidebarBoolFields` back into the metadata
// payload alongside `sidebarExtraFields`.
const sidebarBoolFields = ref<Record<string, boolean>>({})

// Task quick-create state
const sidebarTaskTitle = ref('')
const sidebarTaskDueDate = ref('')
const sidebarTaskAssigneeId = ref('')
const sidebarTaskWatcherIds = ref<string[]>([])
const sidebarTaskDescription = ref('')
const sidebarTaskEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const sidebarTaskSubmitting = ref(false)

// Fields that appear ABOVE the rich-text body (e.g. email subject / recipient).
// Generic across tools — anything that semantically scopes the body goes on top.
const TOP_FIELD_KEYS = new Set([
  'subject',
  'to',
  'from_address',
  'from_number',
  'from_handle',
  'to_handle',
  'channel',
  'direction',
  'url', // for `link` tool — URL leads, the description body follows
])
// Fields that are auto-populated by integrations (e.g. webhook callbacks) and
// should not appear in the manual-entry form.
const SKIP_FIELD_KEYS = new Set([
  'content_text',
  'mentions',
  'recording_filename',
  'recording_size_bytes',
  'provider_message_id',
  'provider_event_id',
  'provider_request_id',
  'message_id',
  'viewer_ip',
  'user_agent',
  'source_activity_ids',
])
// Fields that should render as a multi-line textarea regardless of explicit
// schema hints (no current tool sets `format: 'textarea'` so we use a key
// heuristic — these names always carry long-form prose).
const MULTILINE_FIELD_KEYS = new Set([
  'transcript',
  'description',
  'notes',
  'message',
  'text',
])

interface SchemaProp {
  key: string
  title: string
  type: string
  format?: string
  enum?: string[]
  minimum?: number
  maximum?: number
  items?: { type?: string }
}

/**
 * The StreamlineTool currently being composed.  When the user picks the
 * unified "Message" pseudo-tool, this resolves to whichever channel-specific
 * tool matches the (channel, direction) selection — so the rest of the
 * form/submit pipeline can treat both flows identically.
 */
const currentTool = computed<StreamlineTool | null>(() => {
  if (!sidebarActionType.value) return null
  if (sidebarActionType.value === 'message') return resolvedMessageTool.value
  return toolbarTools.value.find((x) => x.activity_type === sidebarActionType.value) ?? null
})

const sidebarSchemaPropsAll = computed<SchemaProp[]>(() => {
  const tool = currentTool.value
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
      maximum: schema.maximum as number | undefined,
      items: schema.items as { type?: string } | undefined,
    }))
})

const sidebarSchemaPropsTop = computed(() =>
  sidebarSchemaPropsAll.value.filter((p) => TOP_FIELD_KEYS.has(p.key)),
)
const sidebarSchemaPropsBottom = computed(() =>
  sidebarSchemaPropsAll.value.filter((p) => !TOP_FIELD_KEYS.has(p.key)),
)

const sidebarToolHasContentText = computed(() => {
  const tool = currentTool.value
  return !!(tool?.form_schema?.properties as Record<string, unknown> | undefined)?.content_text
})

const sidebarHasPlainText = computed(() =>
  Boolean(sidebarActivityText.value.replace(/<[^>]*>/g, '').trim()),
)

const sidebarToolRequiresText = computed(() => {
  return currentTool.value?.form_schema.required?.includes('content_text') ?? false
})

function sidebarRequiresField(key: string): boolean {
  return currentTool.value?.form_schema.required?.includes(key) ?? false
}

const sidebarSubmitDisabled = computed(() => {
  if (sidebarActivitySubmitting.value) return true
  // For the unified message composer: until the user picks a channel
  // (and direction, when applicable) we have no tool to submit against.
  if (sidebarActionType.value === 'message' && !currentTool.value) return true
  if (sidebarToolRequiresText.value && !sidebarHasPlainText.value) return true
  for (const key of currentTool.value?.form_schema.required ?? []) {
    if (key === 'content_text') continue
    const val = sidebarExtraFields.value[key]
    if (val === undefined || val === null || val === '') return true
    if (Array.isArray(val) && val.length === 0) return true
  }
  return false
})

/**
 * Build the per-key default values for whatever tool is currently active.
 * Pulled out so we can re-run it when the user changes channel / direction
 * inside the unified composer (each channel has a different schema).
 */
function _initFieldsForTool(tool: StreamlineTool | null): Record<string, FieldValue> {
  const fields: Record<string, FieldValue> = {}
  const bools: Record<string, boolean> = {}
  if (tool?.form_schema?.properties) {
    for (const [key, raw] of Object.entries(
      tool.form_schema.properties as Record<string, Record<string, unknown>>,
    )) {
      if (SKIP_FIELD_KEYS.has(key)) continue
      const propType = raw.type as string | undefined
      if (propType === 'array') {
        fields[key] = []
      } else if (propType === 'boolean') {
        // Honour explicit schema `default` (e.g. `event_scheduled.all_day`),
        // otherwise start unchecked so the form has a deterministic state.
        bools[key] = (raw.default as boolean | undefined) ?? false
      } else {
        fields[key] = ''
      }
    }
  }
  sidebarBoolFields.value = bools
  return fields
}

function openSidebarAction(type: string) {
  sidebarActionType.value = type
  sidebarActivityText.value = ''
  if (type === 'message') {
    // Reset the channel/direction picker — schema fields are populated
    // lazily once the user resolves to a concrete channel+direction.
    messageChannel.value = ''
    messageDirection.value = ''
    sidebarExtraFields.value = {}
    sidebarBoolFields.value = {}
    return
  }
  // Pre-initialise schema keys so Vue's Proxy reactivity tracks them from start.
  const tool = toolbarTools.value.find((x) => x.activity_type === type)
  sidebarExtraFields.value = _initFieldsForTool(tool ?? null)
  if (type === 'task') {
    sidebarTaskAssigneeId.value = authStore.user ? String(authStore.user.id) : ''
  }
}

// Re-initialise the schema-driven form whenever the user resolves to a new
// concrete tool inside the unified messaging composer.  Carry the message
// body across so switching between e.g. "Email Outbound" and "SMS Outbound"
// doesn't wipe what the user has already typed.
watch(resolvedMessageTool, (next, prev) => {
  if (sidebarActionType.value !== 'message') return
  if (next?.activity_type === prev?.activity_type) return
  sidebarExtraFields.value = _initFieldsForTool(next)
  tagDrafts.value = {}
})

function closeSidebarAction() {
  sidebarActionType.value = ''
  sidebarExtraFields.value = {}
  sidebarBoolFields.value = {}
  messageChannel.value = ''
  messageDirection.value = ''
}

// Build action items directly from the entity-toolbar registry, then group
// them into our four UX categories. Tools that don't fit any category fall
// into a synthetic "other" bucket so we never silently drop a backend tool.
interface ActionItem {
  value: string
  label: string
  icon: Component
  helpKey: string | undefined
}

const _toolByActivityType = computed(() => {
  const map = new Map<string, StreamlineTool>()
  for (const tool of toolbarTools.value) map.set(tool.activity_type, tool)
  // Inject the synthetic "message" pseudo-tool whenever the backend toolbar
  // exposes any channel-specific messaging tool, so the action grid can
  // render a single "Message" entry in place of the 6+ channel buttons.
  if (hasMessagingTools.value) {
    map.set('message', {
      activity_type: 'message',
      label: t('leadDetail.typeMessage'),
      // Generic icon — the real channel icon is shown only after the user
      // resolves to a concrete tool inside the composer.
      icon: 'ChatBubbleLeftRightIcon',
      channel: 'none',
      direction: 'none',
      form_schema: { type: 'object', properties: {} },
    })
  }
  return map
})

function _toActionItem(tool: StreamlineTool): ActionItem {
  const i18nKey = activityTypeLabelKey[tool.activity_type]
  return {
    value: tool.activity_type,
    label: i18nKey ? t(i18nKey) : tool.label,
    icon: heroIconMap[tool.icon] ?? QuestionMarkCircleIcon,
    helpKey: activityTypeHelpKey[tool.activity_type],
  }
}

interface ToolGroup extends ToolCategory {
  items: ActionItem[]
}

const groupedActionItems = computed<ToolGroup[]>(() => {
  const used = new Set<string>()
  const groups: ToolGroup[] = TOOL_CATEGORIES.map((cat) => {
    const items: ActionItem[] = []
    for (const at of cat.activityTypes) {
      const tool = _toolByActivityType.value.get(at)
      if (tool) {
        items.push(_toActionItem(tool))
        used.add(at)
      }
    }
    return { ...cat, items }
  }).filter((g) => g.items.length > 0)

  // Anything the backend exposed that we haven't categorised → "other".
  // Messaging tools (channel != 'none') are intentionally hidden here —
  // they are surfaced via the unified `'message'` pseudo-tool instead.
  const leftover = toolbarTools.value
    .filter((t) => !used.has(t.activity_type) && (!t.channel || t.channel === 'none'))
    .map(_toActionItem)
  if (leftover.length) {
    groups.push({
      key: 'other',
      labelKey: 'leadDetail.toolCategory.other',
      activityTypes: leftover.map((i) => i.value),
      accent: 'gray',
      items: leftover,
    })
  }
  return groups
})

const sidebarActionIcon = computed(() => {
  // When composing a message, swap the generic chat icon for the resolved
  // channel-specific icon as soon as the user has picked a channel.
  if (sidebarActionType.value === 'message' && currentTool.value) {
    return heroIconMap[currentTool.value.icon] ?? ChatBubbleLeftRightIcon
  }
  for (const g of groupedActionItems.value) {
    const it = g.items.find((i) => i.value === sidebarActionType.value)
    if (it) return it.icon
  }
  return ClipboardDocumentListIcon
})

const sidebarActionLabel = computed(() => {
  for (const g of groupedActionItems.value) {
    const it = g.items.find((i) => i.value === sidebarActionType.value)
    if (it) return it.label
  }
  return ''
})

const sidebarActionHelp = computed(() => {
  const helpKey = activityTypeHelpKey[sidebarActionType.value]
  if (!helpKey) return ''
  const translated = t(helpKey)
  // useI18n returns the key itself when missing — surface only real strings.
  return translated === helpKey ? '' : translated
})

// ─── Tag (array) input helpers ─────────────────────────────────────────────

const tagDrafts = ref<Record<string, string>>({})

function addTag(fieldKey: string) {
  const draft = (tagDrafts.value[fieldKey] ?? '').trim()
  if (!draft) return
  const current = sidebarExtraFields.value[fieldKey]
  const list = Array.isArray(current) ? [...current] : []
  // Allow comma-separated bulk paste: "a@x.com, b@y.com" → 2 tags.
  for (const piece of draft.split(',').map((s) => s.trim()).filter(Boolean)) {
    if (!list.includes(piece)) list.push(piece)
  }
  sidebarExtraFields.value[fieldKey] = list
  tagDrafts.value[fieldKey] = ''
}

function removeTag(fieldKey: string, tag: string) {
  const current = sidebarExtraFields.value[fieldKey]
  if (!Array.isArray(current)) return
  sidebarExtraFields.value[fieldKey] = current.filter((x) => x !== tag)
}

function onTagKey(event: KeyboardEvent, fieldKey: string) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault()
    addTag(fieldKey)
  } else if (
    event.key === 'Backspace' &&
    !(tagDrafts.value[fieldKey] ?? '').length
  ) {
    const current = sidebarExtraFields.value[fieldKey]
    if (Array.isArray(current) && current.length) {
      sidebarExtraFields.value[fieldKey] = current.slice(0, -1)
    }
  }
}

// ─── Submit handlers ───────────────────────────────────────────────────────

const entityIdField = computed(() => `${props.entityType}_id`)

async function sidebarAddActivity() {
  if (sidebarToolRequiresText.value && !sidebarHasPlainText.value) return
  // For the unified message composer the user must have resolved to a
  // concrete (channel, direction) combination before submitting.
  const resolvedType = sidebarActionType.value === 'message'
    ? resolvedMessageTool.value?.activity_type
    : sidebarActionType.value
  if (!resolvedType) return
  sidebarActivitySubmitting.value = true
  const mentionedIds = resolvedType === 'comment'
    ? (sidebarRichEditorRef.value?.getMentionedIds() ?? [])
    : []
  // Drop empty values so the backend metadata stays compact.
  const cleanFields: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(sidebarExtraFields.value)) {
    if (v === '' || v === null || v === undefined) continue
    if (Array.isArray(v) && v.length === 0) continue
    cleanFields[k] = v
  }
  // Boolean schema fields (e.g. ``event_scheduled.all_day``) are kept
  // in their own ref so they can drive UI state independently — fold
  // them back into metadata so the backend tool sees them.
  for (const [k, v] of Object.entries(sidebarBoolFields.value)) {
    cleanFields[k] = v
  }
  const metadata: Record<string, unknown> = {
    ...cleanFields,
    ...(mentionedIds.length ? { mentions: mentionedIds } : {}),
  }
  const payload: Record<string, unknown> = {
    [entityIdField.value]: props.entityId,
    type: resolvedType,
    content_text: sidebarActivityText.value,
    metadata,
  }
  const res = await api.post('/api/v1/crm/activities', payload)
  sidebarActivitySubmitting.value = false
  if (res.ok) {
    sidebarActivityText.value = ''
    sidebarActionType.value = ''
    sidebarExtraFields.value = {}
    sidebarBoolFields.value = {}
    messageChannel.value = ''
    messageDirection.value = ''
    tagDrafts.value = {}
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

// ─── Voice memo recorder integration ───────────────────────────────────────
//
// The voice-memo composer is a special-case form (a `MediaRecorder`-based
// recorder UI lives in `VoiceMemoRecorder.vue`); on save the recorder
// uploads the audio blob to the dedicated audio endpoint and emits the
// final metadata, which we wrap into a regular `voice_memo` Activity POST.
// The endpoint accepts a single optional entity-id query parameter so the
// resulting Document is linked to the active entity.

const voiceMemoUploadUrl = computed(() => {
  const params = new URLSearchParams({
    [`${props.entityType}_id`]: props.entityId,
  })
  return `/api/v1/crm/voice-memos/upload?${params.toString()}`
})

interface VoiceMemoSubmitPayload {
  url: string
  duration_seconds: number
  size_bytes: number
  filename: string
  content_type: string
}

async function sidebarSubmitVoiceMemo(payload: VoiceMemoSubmitPayload) {
  sidebarActivitySubmitting.value = true
  const metadata: Record<string, unknown> = {
    url: payload.url,
    filename: payload.filename,
    content_type: payload.content_type,
    size_bytes: payload.size_bytes,
    duration_seconds: payload.duration_seconds,
  }
  const res = await api.post('/api/v1/crm/activities', {
    [entityIdField.value]: props.entityId,
    type: 'voice_memo',
    content_text: '',
    metadata,
  })
  sidebarActivitySubmitting.value = false
  if (res.ok) {
    sidebarActionType.value = ''
    sidebarExtraFields.value = {}
    sidebarBoolFields.value = {}
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

function sidebarCancelVoiceMemo() {
  closeSidebarAction()
}

// ─── File upload composer integration ──────────────────────────────────────
//
// Like the voice-memo composer, the `file_upload` tool replaces the
// schema-driven form with a richer UI (URL ↔ Upload pill switcher,
// drop-zone + multi-file). The composer owns the upload step and emits
// one Activity-ready payload per successfully-stored file (or one
// payload total for the URL branch). For the URL branch with
// `store_locally=true` the backend Celery task fetches the file
// asynchronously and patches `metadata` in place once done.

const fileUploadUrl = computed(() => {
  const params = new URLSearchParams({
    [`${props.entityType}_id`]: props.entityId,
  })
  return `/api/v1/crm/file-uploads/upload?${params.toString()}`
})

interface FileUploadSubmitPayload {
  title: string
  url: string
  filename: string
  size_bytes: number
  mime_type: string
  source_kind: 'url' | 'upload'
  store_locally: boolean
}

async function sidebarSubmitFileUpload(payload: FileUploadSubmitPayload) {
  sidebarActivitySubmitting.value = true
  // Strip empty optional fields so backend metadata stays compact.
  const metadata: Record<string, unknown> = {
    title: payload.title,
    url: payload.url,
    source_kind: payload.source_kind,
    store_locally: payload.store_locally,
  }
  if (payload.filename) metadata.filename = payload.filename
  if (payload.size_bytes) metadata.size_bytes = payload.size_bytes
  if (payload.mime_type) metadata.mime_type = payload.mime_type

  const res = await api.post('/api/v1/crm/activities', {
    [entityIdField.value]: props.entityId,
    type: 'file_upload',
    content_text: '',
    metadata,
  })
  sidebarActivitySubmitting.value = false
  if (res.ok) {
    // We only close the composer after the *whole batch* has been
    // processed — multi-file uploads will fire `submit` once per file
    // and we want the panel to stay open between them. The composer
    // itself stays mounted and only resets when closed manually below.
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
    sidebarActionType.value = ''
    sidebarExtraFields.value = {}
    sidebarBoolFields.value = {}
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

function sidebarCancelFileUpload() {
  closeSidebarAction()
}

async function sidebarAddTask() {
  if (!sidebarTaskTitle.value.trim()) return
  sidebarTaskSubmitting.value = true
  const payload: Record<string, unknown> = {
    [entityIdField.value]: props.entityId,
    title: sidebarTaskTitle.value.trim(),
    assigned_to_id: sidebarTaskAssigneeId.value || null,
    watcher_ids: sidebarTaskWatcherIds.value,
  }
  if (sidebarTaskDueDate.value) payload.due_date = new Date(sidebarTaskDueDate.value).toISOString()
  const res = await api.post('/api/v1/crm/tasks', payload)
  if (res.ok) {
    // If a description was entered, post it as the first comment on the parent timeline.
    const descText = sidebarTaskDescription.value
    if (descText && descText.replace(/<[^>]*>/g, '').trim()) {
      const mentionedIds = sidebarTaskEditorRef.value?.getMentionedIds() ?? []
      const metadata: Record<string, unknown> = mentionedIds.length ? { mentions: mentionedIds } : {}
      await api.post('/api/v1/crm/activities', {
        [entityIdField.value]: props.entityId,
        type: 'comment',
        content_text: descText,
        metadata,
      })
    }
    sidebarTaskTitle.value = ''
    sidebarTaskDueDate.value = ''
    sidebarTaskAssigneeId.value = authStore.user ? String(authStore.user.id) : ''
    sidebarTaskWatcherIds.value = []
    sidebarTaskDescription.value = ''
    sidebarActionType.value = ''
    emit('task-created')
    emit('activity-added')
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

function onFileUploaded(file: unknown) {
  emit('file-uploaded', file)
}

// ─── Template helpers for input rendering ──────────────────────────────────

function isMultilineProp(prop: SchemaProp): boolean {
  return MULTILINE_FIELD_KEYS.has(prop.key)
}

function inputTypeFor(prop: SchemaProp): string {
  if (prop.format === 'email') return 'email'
  if (prop.format === 'uri') return 'url'
  if (prop.format === 'date') return 'date'
  if (prop.format === 'date-time') {
    // For the `event_scheduled` tool, the dedicated "All day" toggle
    // collapses the date-time pickers down to plain date pickers — the
    // backend accepts an ISO date and treats it as a midnight slot.
    if (
      sidebarActionType.value === 'event_scheduled'
      && (prop.key === 'start_at' || prop.key === 'end_at')
      && sidebarBoolFields.value.all_day === true
    ) {
      return 'date'
    }
    return 'datetime-local'
  }
  return 'text'
}

function placeholderFor(prop: SchemaProp): string {
  if (prop.format === 'email') return 'name@example.com'
  if (prop.format === 'uri') return 'https://…'
  if (prop.key === 'to' || prop.key === 'from_number') return '+420…'
  return ''
}

// Each category's accent class set, computed once per group instance.
function accentClasses(accent: string): { ring: string; text: string; hover: string } {
  switch (accent) {
    case 'blue':
      return {
        ring: 'border-blue-200 dark:border-blue-700/50',
        text: 'text-blue-600 dark:text-blue-400',
        hover: 'hover:border-blue-400 hover:text-blue-700 dark:hover:text-blue-300',
      }
    case 'emerald':
      return {
        ring: 'border-emerald-200 dark:border-emerald-700/50',
        text: 'text-emerald-600 dark:text-emerald-400',
        hover: 'hover:border-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300',
      }
    case 'amber':
      return {
        ring: 'border-amber-200 dark:border-amber-700/50',
        text: 'text-amber-600 dark:text-amber-400',
        hover: 'hover:border-amber-400 hover:text-amber-700 dark:hover:text-amber-300',
      }
    case 'gray':
      return {
        ring: 'border-gray-200 dark:border-gray-700/50',
        text: 'text-gray-600 dark:text-gray-400',
        hover: 'hover:border-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
      }
    case 'red':
    default:
      // Red is the brand accent used for `communication`, also the safe
      // fallback for any unrecognised accent value.
      return {
        ring: 'border-red-200 dark:border-red-700/50',
        text: 'text-red-600 dark:text-red-400',
        hover: 'hover:border-red-400 hover:text-red-700 dark:hover:text-red-300',
      }
  }
}
</script>

<template>
  <div
    class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4"
    data-testid="entity-sidebar-action-picker"
  >
    <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
      {{ t('leadDetail.quickActions') }}
    </p>

    <!-- Step 1: action type picker (grouped by UX category) -->
    <div v-if="!sidebarActionType" class="flex flex-col gap-3" data-testid="entity-sidebar-action-groups">
      <div
        v-for="group in groupedActionItems"
        :key="group.key"
        class="flex flex-col gap-1.5"
        data-testid="entity-sidebar-action-group"
        :data-group="group.key"
      >
        <p
          class="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 px-1"
          :class="accentClasses(group.accent).text"
        >
          {{ t(group.labelKey) }}
        </p>
        <div class="flex flex-col gap-1.5">
          <button
            v-for="item in group.items"
            :key="item.value"
            data-testid="entity-sidebar-action-option"
            :data-action="item.value"
            class="flex items-center gap-2 px-3 py-2 rounded-xl border text-sm text-gray-700 dark:text-gray-300 transition-colors text-left"
            :class="[accentClasses(group.accent).ring, accentClasses(group.accent).hover]"
            @click="openSidebarAction(item.value)"
          >
            <component :is="item.icon" class="w-4 h-4 flex-shrink-0" :class="accentClasses(group.accent).text" />
            <span class="flex-1 truncate">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Step 2a: activity form (comment / call / meeting / email / sms / etc.) -->
    <div v-else-if="sidebarActionType !== 'task'" class="space-y-2">
      <div class="flex items-center gap-2 mb-1">
        <component :is="sidebarActionIcon" class="w-4 h-4 text-gray-500 dark:text-gray-400 flex-shrink-0" />
        <span class="text-sm font-medium text-gray-700 dark:text-gray-300" data-testid="entity-sidebar-action-current">
          {{ sidebarActionLabel }}
        </span>
        <button
          class="ml-auto text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
          @click="closeSidebarAction"
        >← {{ t('leadDetail.changeType') }}</button>
      </div>
      <p
        v-if="sidebarActionHelp"
        class="text-xs text-gray-500 dark:text-gray-400 mb-2 px-0.5 leading-snug"
        data-testid="entity-sidebar-action-help"
      >
        {{ sidebarActionHelp }}
      </p>

      <!-- Voice memo recorder: dedicated diktafonové UI replaces the
           generic schema-driven form (filename / size / duration /
           transcript are all populated server-side or by the recorder). -->
      <VoiceMemoRecorder
        v-if="sidebarActionType === 'voice_memo'"
        :upload-url="voiceMemoUploadUrl"
        @submit="sidebarSubmitVoiceMemo"
        @cancel="sidebarCancelVoiceMemo"
      />

      <!-- File upload composer: URL ↔ Upload switcher, multi-file drop-
           zone, plan-aware client-side limits.  Owns its own upload
           step — emits one activity-ready payload per stored file. -->
      <FileUploadComposer
        v-else-if="sidebarActionType === 'file_upload'"
        :upload-url="fileUploadUrl"
        @submit="sidebarSubmitFileUpload"
        @cancel="sidebarCancelFileUpload"
      />

      <!-- Generic schema-driven form (everything except voice_memo and
           file_upload, which use their own composers above). -->
      <template v-if="sidebarActionType !== 'voice_memo' && sidebarActionType !== 'file_upload'">
      <!-- Unified message composer: Channel + Direction picker.
           Only rendered for the synthetic 'message' pseudo-tool. -->
      <div
        v-if="sidebarActionType === 'message'"
        class="space-y-2 pb-2 border-b border-gray-100 dark:border-gray-700"
        data-testid="message-composer-channel-picker"
      >
        <div data-field="message-channel">
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ t('messageComposer.channelLabel') }}<span class="text-red-500 ml-0.5">*</span>
          </label>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="ch in messageChannelOptions"
              :key="ch.value"
              type="button"
              data-testid="message-composer-channel-option"
              :data-channel="ch.value"
              :data-active="messageChannel === ch.value ? 'true' : 'false'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors"
              :class="messageChannel === ch.value
                ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-red-300'"
              @click="pickMessageChannel(ch.value)"
            >{{ t(ch.labelKey) }}</button>
          </div>
        </div>

        <!-- Direction toggle — hidden for channels that capture direction inside their own schema (e.g. chat). -->
        <div
          v-if="messageChannel"
          v-show="(messageChannelOptions.find((c) => c.value === messageChannel)?.directions.length ?? 0) > 0"
          data-field="message-direction"
        >
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ t('messageComposer.directionLabel') }}<span class="text-red-500 ml-0.5">*</span>
          </label>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="dir in (messageChannelOptions.find((c) => c.value === messageChannel)?.directions ?? [])"
              :key="dir.value"
              type="button"
              data-testid="message-composer-direction-option"
              :data-direction="dir.value"
              :data-active="messageDirection === dir.value ? 'true' : 'false'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors"
              :class="messageDirection === dir.value
                ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-red-300'"
              @click="pickMessageDirection(dir.value)"
            >{{ t(dir.labelKey) }}</button>
          </div>
        </div>
      </div>

      <!-- "Header" fields: subject, to, from, channel, … — shown above the body -->
      <template v-for="prop in sidebarSchemaPropsTop" :key="prop.key">
        <div :data-field="prop.key">
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ prop.title }}<span v-if="sidebarRequiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
          </label>
          <select
            v-if="prop.enum"
            v-model="sidebarExtraFields[prop.key]"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('leadDetail.selectOption') }}</option>
            <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <input
            v-else
            v-model="sidebarExtraFields[prop.key]"
            :type="inputTypeFor(prop)"
            :placeholder="placeholderFor(prop)"
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
        :upload-url="sidebarActionType === 'comment' ? attachmentUploadUrl : undefined"
        @file-uploaded="onFileUploaded"
      />

      <!-- "Footer" fields: duration, recording URL, transcript, etc. — shown below body -->
      <template v-for="prop in sidebarSchemaPropsBottom" :key="prop.key">
        <div :data-field="prop.key">
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ prop.title }}<span v-if="sidebarRequiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
          </label>

          <!-- Numeric -->
          <input
            v-if="prop.type === 'integer' || prop.type === 'number'"
            v-model.number="sidebarExtraFields[prop.key]"
            type="number"
            :min="prop.minimum"
            :max="prop.maximum"
            :step="prop.type === 'integer' ? 1 : 'any'"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />

          <!-- Enum dropdown -->
          <select
            v-else-if="prop.enum"
            v-model="sidebarExtraFields[prop.key]"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('leadDetail.selectOption') }}</option>
            <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
          </select>

          <!-- Array → tag-style chip input -->
          <div
            v-else-if="prop.type === 'array'"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1.5 text-sm focus-within:border-red-400 flex flex-wrap items-center gap-1"
          >
            <span
              v-for="tag in (Array.isArray(sidebarExtraFields[prop.key]) ? (sidebarExtraFields[prop.key] as string[]) : [])"
              :key="tag"
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-gray-100 dark:bg-gray-600 text-gray-700 dark:text-gray-200 text-xs"
            >
              {{ tag }}
              <button
                type="button"
                class="hover:text-red-500"
                :aria-label="`remove ${tag}`"
                @click="removeTag(prop.key, tag)"
              >
                <XMarkIcon class="w-3 h-3" />
              </button>
            </span>
            <input
              v-model="tagDrafts[prop.key]"
              type="text"
              class="flex-1 min-w-[80px] bg-transparent border-0 px-1 py-0.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none"
              :placeholder="t('leadDetail.tagInputPlaceholder')"
              @keydown="(e) => onTagKey(e, prop.key)"
              @blur="addTag(prop.key)"
            />
          </div>

          <!-- Boolean → checkbox toggle -->
          <label
            v-else-if="prop.type === 'boolean'"
            class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 cursor-pointer select-none"
          >
            <input
              v-model="sidebarBoolFields[prop.key]"
              type="checkbox"
              class="rounded border-gray-300 text-red-600 focus:ring-red-500"
            />
            <span>{{ prop.title }}</span>
          </label>

          <!-- Multi-line free text -->
          <textarea
            v-else-if="isMultilineProp(prop)"
            v-model="sidebarExtraFields[prop.key]"
            rows="3"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
          />

          <!-- Default: typed string input (covers email / uri / date / date-time / plain text) -->
          <input
            v-else
            v-model="sidebarExtraFields[prop.key]"
            :type="inputTypeFor(prop)"
            :placeholder="placeholderFor(prop)"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>
      </template>

      <div class="flex justify-end pt-1">
        <button
          :disabled="sidebarSubmitDisabled"
          data-testid="entity-sidebar-action-submit"
          class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          @click="sidebarAddActivity"
        >{{ sidebarActivitySubmitting ? '…' : t('leadDetail.activitySubmit') }}</button>
      </div>
      </template>
    </div>

    <!-- Step 2b: task quick-create form -->
    <div v-else class="space-y-2">
      <div class="flex items-center gap-2 mb-1">
        <ClipboardDocumentListIcon class="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
        <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('leadDetail.typeTask') }}</span>
        <button
          class="ml-auto text-xs text-gray-400 hover:text-red-500 dark:hover:text-red-400 transition-colors"
          @click="closeSidebarAction"
        >← {{ t('leadDetail.changeType') }}</button>
      </div>
      <p
        v-if="t('leadDetail.toolHelp.task') !== 'leadDetail.toolHelp.task'"
        class="text-xs text-gray-500 dark:text-gray-400 mb-2 px-0.5 leading-snug"
      >
        {{ t('leadDetail.toolHelp.task') }}
      </p>
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
      <div class="flex justify-end pt-1">
        <button
          :disabled="sidebarTaskSubmitting || !sidebarTaskTitle.trim()"
          data-testid="entity-sidebar-task-submit"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          @click="sidebarAddTask"
        >{{ sidebarTaskSubmitting ? '…' : t('leadDetail.addTask') }}</button>
      </div>
    </div>
  </div>
</template>

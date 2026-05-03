<!-- Updated for todo_items_added -->
<script setup lang="ts">
import { ref, computed, watch, onMounted, type Component } from 'vue'
import { api } from '@/api'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import RichTextEditor from '@/components/RichTextEditor.vue'
import type { MentionUser } from '@/components/RichTextEditor.vue'
import StreamlineCreateModal from '@/components/StreamlineCreateModal.vue'
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
  DevicePhoneMobileIcon,
  CalendarDaysIcon,
  LinkIcon,
  MicrophoneIcon,
  InformationCircleIcon,
  QuestionMarkCircleIcon,
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
    entityType: 'lead' | 'record' | 'customer' | 'realization' | 'management' | 'proposal'
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
  call_scheduled: 'leadDetail.typeCallScheduled',
  event_scheduled: 'leadDetail.typeEventScheduled',
  link: 'leadDetail.typeLink',
  voice_memo: 'leadDetail.typeVoiceMemo',
  system_note: 'leadDetail.typeSystemNote',
  file_upload: 'leadDetail.typeFileUpload',
  todo_items: 'leadDetail.typeTodoItems',
  proposal: 'leadDetail.typeProposal',
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
    activityTypes: ['meeting_scheduled', 'call_scheduled', 'event_scheduled', 'task', 'todo_items_added', 'proposal'],
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

// ─── Inline form ────────────────────────────────────────────────────────────
//
// After the user picks an action from the grid, the action grid is replaced by
// an inline composer panel that renders the schema-driven form for the chosen
// tool directly inside the sidebar (without a modal/teleport).  This keeps
// the elements reachable for component tests and provides a tight UX.

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

const TOP_FIELD_KEYS = new Set([
  'subject', 'to', 'from_address', 'from_number', 'from_handle', 'to_handle', 'channel', 'direction', 'url',
])
const SKIP_FIELD_KEYS = new Set([
  'content_text', 'mentions', 'recording_filename', 'recording_size_bytes',
  'provider_message_id', 'provider_event_id', 'provider_request_id',
  'message_id', 'viewer_ip', 'user_agent', 'source_activity_ids',
])
const MULTILINE_FIELD_KEYS = new Set(['transcript', 'description', 'notes', 'message', 'text'])

const activeActionType = ref('')
type FieldValue = string | number | string[] | null
const extraFields = ref<Record<string, FieldValue>>({})
const boolFields = ref<Record<string, boolean>>({})
const activityText = ref('')
const activitySubmitting = ref(false)
const richEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)

const currentTool = computed<StreamlineTool | null>(() => {
  if (!activeActionType.value) return null
  if (activeActionType.value === 'message') return resolvedMessageTool.value
  return toolbarTools.value.find((x) => x.activity_type === activeActionType.value) ?? null
})

const schemaPropsAll = computed<SchemaProp[]>(() => {
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

const schemaPropsTop = computed(() => schemaPropsAll.value.filter((p) => TOP_FIELD_KEYS.has(p.key)))
const schemaPropsBottom = computed(() => schemaPropsAll.value.filter((p) => !TOP_FIELD_KEYS.has(p.key)))

const toolHasContentText = computed(() => {
  const tool = currentTool.value
  return !!(tool?.form_schema?.properties as Record<string, unknown> | undefined)?.content_text
})

function inputTypeFor(prop: SchemaProp): string {
  if (prop.format === 'email') return 'email'
  if (prop.format === 'uri') return 'url'
  if (prop.format === 'date') return 'date'
  if (prop.format === 'date-time') {
    if (
      activeActionType.value === 'event_scheduled' &&
      (prop.key === 'start_at' || prop.key === 'end_at') &&
      boolFields.value.all_day === true
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

function requiresField(key: string): boolean {
  return currentTool.value?.form_schema.required?.includes(key) ?? false
}

function isMultilineProp(prop: SchemaProp): boolean {
  return MULTILINE_FIELD_KEYS.has(prop.key)
}

function _initFieldsForTool(tool: StreamlineTool | null) {
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
        bools[key] = (raw.default as boolean | undefined) ?? false
      } else {
        fields[key] = ''
      }
    }
  }
  extraFields.value = fields
  boolFields.value = bools
}

// Re-init schema fields when the user changes channel/direction inside the
// unified messaging composer (each channel has a different form schema).
watch(resolvedMessageTool, (next, prev) => {
  if (activeActionType.value !== 'message') return
  if (next?.activity_type === prev?.activity_type) return
  _initFieldsForTool(next)
})

function openInlineForm(type: string) {
  activeActionType.value = type
  activityText.value = ''
  activitySubmitting.value = false
  if (type === 'message') {
    messageChannel.value = ''
    messageDirection.value = ''
    extraFields.value = {}
    boolFields.value = {}
  } else {
    const tool = toolbarTools.value.find((x) => x.activity_type === type)
    _initFieldsForTool(tool ?? null)
  }
}

async function addActivity() {
  const resolvedType =
    activeActionType.value === 'message'
      ? resolvedMessageTool.value?.activity_type
      : activeActionType.value
  if (!resolvedType) return
  activitySubmitting.value = true
  const mentionedIds =
    resolvedType === 'comment' ? (richEditorRef.value?.getMentionedIds() ?? []) : []
  const cleanFields: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(extraFields.value)) {
    if (v === '' || v === null || v === undefined) continue
    if (Array.isArray(v) && v.length === 0) continue
    cleanFields[k] = v
  }
  for (const [k, v] of Object.entries(boolFields.value)) {
    cleanFields[k] = v
  }
  const metadata: Record<string, unknown> = {
    ...cleanFields,
    ...(mentionedIds.length ? { mentions: mentionedIds } : {}),
  }
  const res = await api.post('/api/v1/crm/activities', {
    [`${props.entityType}_id`]: props.entityId,
    type: resolvedType,
    content_text: activityText.value,
    metadata,
  })
  activitySubmitting.value = false
  if (res.ok) {
    toast.success(t('leads.activityAdded'))
    emit('activity-added')
    activeActionType.value = ''
  } else {
    const msg = (res.data as Record<string, string> | null)?.detail ?? t('leads.activityFailed')
    toast.error(msg)
  }
}

// ─── Modal state ───────────────────────────────────────────────────────────

const modalOpen = ref(false)
const modalActionType = ref('')

function openModal(type: string) {
  modalActionType.value = type
  modalOpen.value = true
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

    <!-- Action type picker (grouped by UX category) — shown when no inline form is active -->
    <div v-if="!activeActionType" class="flex flex-col gap-3" data-testid="entity-sidebar-action-groups">
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
            @click="openInlineForm(item.value)"
          >
            <component :is="item.icon" class="w-4 h-4 flex-shrink-0" :class="accentClasses(group.accent).text" />
            <span class="flex-1 truncate">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Inline composer panel — shown after an action is picked -->
    <div v-else class="flex flex-col gap-3 mt-1">
      <!-- Back button -->
      <button
        type="button"
        class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 -mb-1"
        @click="activeActionType = ''"
      >
        ← {{ t('common.back', 'Zpět') }}
      </button>

      <!-- Unified message composer: Channel + Direction picker -->
      <div
        v-if="activeActionType === 'message'"
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
              :class="
                messageChannel === ch.value
                  ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-red-300'
              "
              @click="pickMessageChannel(ch.value)"
            >
              {{ t(ch.labelKey) }}
            </button>
          </div>
        </div>

        <div
          v-if="messageChannel"
          data-field="message-direction"
        >
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ t('messageComposer.directionLabel') }}<span class="text-red-500 ml-0.5">*</span>
          </label>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="dir in messageChannelOptions.find((c) => c.value === messageChannel)?.directions ?? []"
              :key="dir.value"
              type="button"
              data-testid="message-composer-direction-option"
              :data-direction="dir.value"
              :data-active="messageDirection === dir.value ? 'true' : 'false'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors"
              :class="
                messageDirection === dir.value
                  ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
                  : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-red-300'
              "
              @click="pickMessageDirection(dir.value)"
            >
              {{ t(dir.labelKey) }}
            </button>
          </div>
        </div>
      </div>

      <!-- Schema "top" fields (subject, to, from_address, …) -->
      <template v-for="prop in schemaPropsTop" :key="prop.key">
        <div :data-field="prop.key">
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ prop.title }}<span v-if="requiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
          </label>
          <select
            v-if="prop.enum"
            v-model="extraFields[prop.key]"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('leadDetail.selectOption') }}</option>
            <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <input
            v-else
            v-model="extraFields[prop.key]"
            :type="inputTypeFor(prop)"
            :placeholder="placeholderFor(prop)"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>
      </template>

      <!-- Rich-text body — only when tool schema includes content_text -->
      <RichTextEditor
        v-if="toolHasContentText"
        ref="richEditorRef"
        v-model="activityText"
        :placeholder="
          activeActionType === 'comment'
            ? t('leadDetail.commentPlaceholder')
            : t('leadDetail.notePlaceholder')
        "
        :disabled="activitySubmitting"
        :members="activeActionType === 'comment' ? teamMembers : []"
        :upload-url="activeActionType === 'comment' ? attachmentUploadUrl : undefined"
        @file-uploaded="(f) => emit('file-uploaded', f)"
      />

      <!-- Schema "bottom" fields (all_day, start_at, duration, transcript, …) -->
      <template v-for="prop in schemaPropsBottom" :key="prop.key">
        <div :data-field="prop.key">
          <label
            v-if="prop.type !== 'boolean'"
            class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1"
          >
            {{ prop.title }}<span v-if="requiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
          </label>

          <!-- Numeric -->
          <input
            v-if="prop.type === 'integer' || prop.type === 'number'"
            v-model.number="extraFields[prop.key]"
            type="number"
            :min="prop.minimum"
            :max="prop.maximum"
            :step="prop.type === 'integer' ? 1 : 'any'"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />

          <!-- Enum dropdown -->
          <select
            v-else-if="prop.enum"
            v-model="extraFields[prop.key]"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('leadDetail.selectOption') }}</option>
            <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
          </select>

          <!-- Boolean → checkbox -->
          <label
            v-else-if="prop.type === 'boolean'"
            class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 cursor-pointer select-none"
          >
            <input
              v-model="boolFields[prop.key]"
              type="checkbox"
              class="rounded border-gray-300 text-red-600 focus:ring-red-500"
            />
            <span>{{ prop.title }}</span>
          </label>

          <!-- Multi-line text -->
          <textarea
            v-else-if="isMultilineProp(prop)"
            v-model="extraFields[prop.key]"
            rows="3"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
          />

          <!-- Default: typed string input -->
          <input
            v-else
            v-model="extraFields[prop.key]"
            :type="inputTypeFor(prop)"
            :placeholder="placeholderFor(prop)"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>
      </template>

      <!-- Submit -->
      <button
        type="button"
        data-testid="entity-sidebar-action-submit"
        :disabled="activitySubmitting"
        class="w-full px-4 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors"
        @click="addActivity()"
      >
        {{ activitySubmitting ? '…' : t('leadDetail.activitySubmit') }}
      </button>
    </div>

    <StreamlineCreateModal
      v-model="modalOpen"
      :action-type="modalActionType"
      :entity-type="entityType"
      :entity-id="entityId"
      :team-members="teamMembers"
      :attachment-upload-url="attachmentUploadUrl"
      @activity-added="emit('activity-added')"
      @task-created="emit('task-created')"
      @file-uploaded="(f) => emit('file-uploaded', f)"
    />
  </div>
</template>

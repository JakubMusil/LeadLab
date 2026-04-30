<script setup lang="ts">
import { ref, computed, watch, onMounted, type Component } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useAuthStore } from '@/stores/auth'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
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
  link: 'leadDetail.typeLink',
  voice_memo: 'leadDetail.typeVoiceMemo',
  system_note: 'leadDetail.typeSystemNote',
  file_upload: 'leadDetail.typeFileUpload',
}

// Short helper text shown below the action header so the user knows what
// the activity is for. Keys point at `leadDetail.toolHelp.<activity_type>`.
const activityTypeHelpKey: Record<string, string> = {
  comment: 'leadDetail.toolHelp.comment',
  call: 'leadDetail.toolHelp.call',
  meeting: 'leadDetail.toolHelp.meeting',
  meeting_scheduled: 'leadDetail.toolHelp.meeting_scheduled',
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
    activityTypes: [
      'comment',
      'call',
      'meeting',
      'email_out',
      'email_in',
      'sms_out',
      'sms_in',
      'whatsapp_out',
      'whatsapp_in',
      'chat',
    ],
    accent: 'red',
  },
  {
    key: 'planning',
    labelKey: 'leadDetail.toolCategory.planning',
    activityTypes: ['meeting_scheduled', 'task'],
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

// ─── Activity composer state ───────────────────────────────────────────────

const sidebarActionType = ref('')
const sidebarActivityText = ref('')
const sidebarActivitySubmitting = ref(false)
const sidebarRichEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
type FieldValue = string | number | string[] | null
const sidebarExtraFields = ref<Record<string, FieldValue>>({})

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

const sidebarSchemaPropsAll = computed<SchemaProp[]>(() => {
  const tool = toolbarTools.value.find((x) => x.activity_type === sidebarActionType.value)
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
  const tool = toolbarTools.value.find((x) => x.activity_type === sidebarActionType.value)
  return !!(tool?.form_schema?.properties as Record<string, unknown> | undefined)?.content_text
})

const sidebarHasPlainText = computed(() =>
  Boolean(sidebarActivityText.value.replace(/<[^>]*>/g, '').trim()),
)

const sidebarToolRequiresText = computed(() => {
  const tool = toolbarTools.value.find((x) => x.activity_type === sidebarActionType.value)
  return tool?.form_schema.required?.includes('content_text') ?? false
})

function sidebarRequiresField(key: string): boolean {
  const tool = toolbarTools.value.find((x) => x.activity_type === sidebarActionType.value)
  return tool?.form_schema.required?.includes(key) ?? false
}

const sidebarSubmitDisabled = computed(() => {
  if (sidebarActivitySubmitting.value) return true
  if (sidebarToolRequiresText.value && !sidebarHasPlainText.value) return true
  const tool = toolbarTools.value.find((x) => x.activity_type === sidebarActionType.value)
  for (const key of tool?.form_schema.required ?? []) {
    if (key === 'content_text') continue
    const val = sidebarExtraFields.value[key]
    if (val === undefined || val === null || val === '') return true
    if (Array.isArray(val) && val.length === 0) return true
  }
  return false
})

function openSidebarAction(type: string) {
  sidebarActionType.value = type
  sidebarActivityText.value = ''
  // Pre-initialise schema keys so Vue's Proxy reactivity tracks them from start.
  const tool = toolbarTools.value.find((x) => x.activity_type === type)
  const fields: Record<string, FieldValue> = {}
  if (tool?.form_schema?.properties) {
    for (const [key, raw] of Object.entries(
      tool.form_schema.properties as Record<string, Record<string, unknown>>,
    )) {
      if (SKIP_FIELD_KEYS.has(key)) continue
      // Arrays default to an empty list so the tag-input renders correctly.
      fields[key] = (raw.type as string | undefined) === 'array' ? [] : ''
    }
  }
  sidebarExtraFields.value = fields
  if (type === 'task') {
    sidebarTaskAssigneeId.value = authStore.user ? String(authStore.user.id) : ''
  }
}

function closeSidebarAction() {
  sidebarActionType.value = ''
  sidebarExtraFields.value = {}
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
  const leftover = toolbarTools.value
    .filter((t) => !used.has(t.activity_type))
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
  sidebarActivitySubmitting.value = true
  const mentionedIds = sidebarActionType.value === 'comment'
    ? (sidebarRichEditorRef.value?.getMentionedIds() ?? [])
    : []
  // Drop empty values so the backend metadata stays compact.
  const cleanFields: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(sidebarExtraFields.value)) {
    if (v === '' || v === null || v === undefined) continue
    if (Array.isArray(v) && v.length === 0) continue
    cleanFields[k] = v
  }
  const metadata: Record<string, unknown> = {
    ...cleanFields,
    ...(mentionedIds.length ? { mentions: mentionedIds } : {}),
  }
  const payload: Record<string, unknown> = {
    [entityIdField.value]: props.entityId,
    type: sidebarActionType.value,
    content_text: sidebarActivityText.value,
    metadata,
  }
  const res = await api.post('/api/v1/crm/activities', payload)
  sidebarActivitySubmitting.value = false
  if (res.ok) {
    sidebarActivityText.value = ''
    sidebarActionType.value = ''
    sidebarExtraFields.value = {}
    tagDrafts.value = {}
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
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
  if (prop.format === 'date-time') return 'datetime-local'
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

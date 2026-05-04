<script setup lang="ts">
/**
 * StreamlineCreateModal — schema-driven "create activity" form in a modal.
 *
 * Extracted from EntitySidebarActionPicker (Step 2).  The sidebar now always
 * shows the action-grid; clicking any action opens this modal instead of
 * replacing the grid inline.
 *
 * Supports all action types handled by EntitySidebarActionPicker:
 *   comment, call, meeting, message (unified composer), email_out/in,
 *   sms_out/in, whatsapp_out/in, link, meeting_scheduled, event_scheduled,
 *   voice_memo, file_upload, task, todo_items_added, proposal, system_note …
 *
 * Emits: update:modelValue, activity-added, task-created, file-uploaded
 */
import { ref, computed, watch, type Component } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useAuthStore } from '@/stores/auth'
import { useMoney } from '@/composables/useMoney'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import VoiceMemoRecorder from '@/components/VoiceMemoRecorder.vue'
import FileUploadComposer from '@/components/FileUploadComposer.vue'
import CurrencySelect from '@/components/CurrencySelect.vue'
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

// ─── Interfaces ───────────────────────────────────────────────────────────────

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

interface MessageChannelOption {
  value: string
  labelKey: string
  directions: { value: 'out' | 'in'; labelKey: string }[]
}

interface VoiceMemoSubmitPayload {
  url: string
  duration_seconds: number
  size_bytes: number
  filename: string
  content_type: string
}

interface FileUploadSubmitPayload {
  title: string
  url: string
  filename: string
  size_bytes: number
  mime_type: string
  source_kind: 'url' | 'upload'
  store_locally: boolean
}

// ─── Props / Emits ────────────────────────────────────────────────────────────

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    actionType: string
    entityType: 'record' | 'customer' | 'realization' | 'management' | 'proposal'
    entityId: string
    teamMembers?: MentionUser[]
    attachmentUploadUrl?: string
  }>(),
  {
    teamMembers: () => [],
    attachmentUploadUrl: undefined,
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'activity-added'): void
  (e: 'task-created'): void
  (e: 'file-uploaded', file: unknown): void
}>()

const { t } = useI18n()
const toast = useToast()
const authStore = useAuthStore()
const { firmCurrency } = useMoney()

// ─── Icon map ─────────────────────────────────────────────────────────────────

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

// ─── Label / help maps ────────────────────────────────────────────────────────

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
  todo_items_added: 'leadDetail.typeTodoItems',
  proposal: 'leadDetail.typeProposal',
  message: 'leadDetail.typeMessage',
}

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
  todo_items_added: 'leadDetail.toolHelp.todo_items',
  message: 'leadDetail.toolHelp.message',
}

// ─── Toolbar loading ──────────────────────────────────────────────────────────

const toolbarTools = ref<StreamlineTool[]>([])

async function loadToolbar() {
  const res = await api.get<StreamlineTool[]>(
    `/api/v1/streamline/entity-toolbar/${props.entityType}`,
  )
  if (res.ok) toolbarTools.value = res.data
}

watch(() => props.entityType, loadToolbar, { immediate: true })

// ─── Unified message composer ─────────────────────────────────────────────────

const MESSAGE_CHANNEL_LABEL: Record<string, string> = {
  email: 'messageComposer.channelEmail',
  sms: 'messageComposer.channelSms',
  whatsapp: 'messageComposer.channelWhatsapp',
  chat: 'messageComposer.channelChat',
}
const _CHANNEL_ORDER = ['email', 'sms', 'whatsapp', 'chat'] as const

const messagingTools = computed(() =>
  toolbarTools.value.filter((tool) => tool.channel && tool.channel !== 'none'),
)

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
    if (tools.some((tool) => tool.direction === 'out'))
      directions.push({ value: 'out', labelKey: 'messageComposer.directionOut' })
    if (tools.some((tool) => tool.direction === 'in'))
      directions.push({ value: 'in', labelKey: 'messageComposer.directionIn' })
    result.push({ value: ch, labelKey: MESSAGE_CHANNEL_LABEL[ch] ?? ch, directions })
  }
  return result
})

const messageChannel = ref<string>('')
const messageDirection = ref<'out' | 'in' | ''>('')

const resolvedMessageTool = computed<StreamlineTool | null>(() => {
  if (!messageChannel.value) return null
  const candidates = messagingTools.value.filter((t) => t.channel === messageChannel.value)
  if (candidates.length === 0) return null
  const channelOption = messageChannelOptions.value.find((c) => c.value === messageChannel.value)
  if (!channelOption || channelOption.directions.length === 0) return candidates[0] ?? null
  if (!messageDirection.value) return null
  return candidates.find((t) => t.direction === messageDirection.value) ?? null
})

function pickMessageChannel(channel: string) {
  messageChannel.value = channel
  const opt = messageChannelOptions.value.find((c) => c.value === channel)
  if (!opt || opt.directions.length === 0) messageDirection.value = ''
}

function pickMessageDirection(direction: 'out' | 'in') {
  messageDirection.value = direction
}

// ─── Field-key sets ───────────────────────────────────────────────────────────

const TOP_FIELD_KEYS = new Set([
  'subject', 'to', 'from_address', 'from_number', 'from_handle', 'to_handle', 'channel',
  'direction', 'url',
])
const SKIP_FIELD_KEYS = new Set([
  'content_text', 'mentions', 'recording_filename', 'recording_size_bytes',
  'provider_message_id', 'provider_event_id', 'provider_request_id',
  'message_id', 'viewer_ip', 'user_agent', 'source_activity_ids',
])
const MULTILINE_FIELD_KEYS = new Set(['transcript', 'description', 'notes', 'message', 'text'])

// ─── Current tool ─────────────────────────────────────────────────────────────

const currentTool = computed<StreamlineTool | null>(() => {
  if (!props.actionType) return null
  if (props.actionType === 'message') return resolvedMessageTool.value
  return toolbarTools.value.find((x) => x.activity_type === props.actionType) ?? null
})

// ─── Schema computeds ─────────────────────────────────────────────────────────

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
const schemaPropsBottom = computed(() =>
  schemaPropsAll.value.filter((p) => !TOP_FIELD_KEYS.has(p.key)),
)

const toolHasContentText = computed(() => {
  const tool = currentTool.value
  return !!(tool?.form_schema?.properties as Record<string, unknown> | undefined)?.content_text
})

// ─── Form state ───────────────────────────────────────────────────────────────

type FieldValue = string | number | string[] | null
const extraFields = ref<Record<string, FieldValue>>({})
const boolFields = ref<Record<string, boolean>>({})
const activityText = ref('')
const activitySubmitting = ref(false)
const richEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)

const taskTitle = ref('')
const taskDueDate = ref('')
const taskAssigneeId = ref('')
const taskWatcherIds = ref<string[]>([])
const taskDescription = ref('')
const taskEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const taskSubmitting = ref(false)

const proposalTitle = ref('')
const proposalCurrency = ref(firmCurrency.value)
const proposalSubmitting = ref(false)

const tagDrafts = ref<Record<string, string>>({})

// ─── Field initialisation ─────────────────────────────────────────────────────

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
        bools[key] = (raw.default as boolean | undefined) ?? false
      } else {
        fields[key] = ''
      }
    }
  }
  boolFields.value = bools
  return fields
}

function resetForm() {
  activityText.value = ''
  tagDrafts.value = {}
  activitySubmitting.value = false
  taskSubmitting.value = false
  proposalSubmitting.value = false

  if (props.actionType === 'message') {
    messageChannel.value = ''
    messageDirection.value = ''
    extraFields.value = {}
    boolFields.value = {}
    return
  }

  const tool = toolbarTools.value.find((x) => x.activity_type === props.actionType)
  extraFields.value = _initFieldsForTool(tool ?? null)

  if (props.actionType === 'task' || props.actionType === 'todo_items_added') {
    taskTitle.value = ''
    taskDueDate.value = ''
    taskAssigneeId.value = authStore.user ? String(authStore.user.id) : ''
    taskWatcherIds.value = []
    taskDescription.value = ''
  } else if (props.actionType === 'proposal') {
    proposalTitle.value = ''
    proposalCurrency.value = firmCurrency.value
  }
}

// Reset when the modal opens or actionType changes while open.
watch(
  () => props.modelValue,
  (open) => {
    if (open) resetForm()
  },
)
watch(
  () => props.actionType,
  () => {
    if (props.modelValue) resetForm()
  },
)
// Also reset once toolbar tools finish loading (async) while modal is already open.
watch(toolbarTools, () => {
  if (props.modelValue) resetForm()
})

// Re-initialise schema fields when the user changes channel/direction inside
// the unified messaging composer (each channel has a different form schema).
watch(resolvedMessageTool, (next, prev) => {
  if (props.actionType !== 'message') return
  if (next?.activity_type === prev?.activity_type) return
  extraFields.value = _initFieldsForTool(next)
  tagDrafts.value = {}
})

// ─── Tag (array) input helpers ────────────────────────────────────────────────

function addTag(fieldKey: string) {
  const draft = (tagDrafts.value[fieldKey] ?? '').trim()
  if (!draft) return
  const current = extraFields.value[fieldKey]
  const list = Array.isArray(current) ? [...current] : []
  for (const piece of draft.split(',').map((s) => s.trim()).filter(Boolean)) {
    if (!list.includes(piece)) list.push(piece)
  }
  extraFields.value[fieldKey] = list
  tagDrafts.value[fieldKey] = ''
}

function removeTag(fieldKey: string, tag: string) {
  const current = extraFields.value[fieldKey]
  if (!Array.isArray(current)) return
  extraFields.value[fieldKey] = current.filter((x) => x !== tag)
}

function onTagKey(event: KeyboardEvent, fieldKey: string) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault()
    addTag(fieldKey)
  } else if (event.key === 'Backspace' && !(tagDrafts.value[fieldKey] ?? '').length) {
    const current = extraFields.value[fieldKey]
    if (Array.isArray(current) && current.length) {
      extraFields.value[fieldKey] = current.slice(0, -1)
    }
  }
}

// ─── Computed helpers ─────────────────────────────────────────────────────────

const entityIdField = computed(() => `${props.entityType}_id`)

const hasPlainText = computed(() =>
  Boolean(activityText.value.replace(/<[^>]*>/g, '').trim()),
)

const toolRequiresText = computed(() =>
  currentTool.value?.form_schema.required?.includes('content_text') ?? false,
)

function requiresField(key: string): boolean {
  return currentTool.value?.form_schema.required?.includes(key) ?? false
}

const activitySubmitDisabled = computed(() => {
  if (activitySubmitting.value) return true
  if (props.actionType === 'message' && !currentTool.value) return true
  if (toolRequiresText.value && !hasPlainText.value) return true
  for (const key of currentTool.value?.form_schema.required ?? []) {
    if (key === 'content_text') continue
    const val = extraFields.value[key]
    if (val === undefined || val === null || val === '') return true
    if (Array.isArray(val) && val.length === 0) return true
  }
  return false
})

const submitDisabled = computed(() => {
  if (props.actionType === 'task' || props.actionType === 'todo_items_added') {
    return taskSubmitting.value || !taskTitle.value.trim()
  }
  if (props.actionType === 'proposal') {
    return proposalSubmitting.value || !proposalTitle.value.trim()
  }
  return activitySubmitDisabled.value
})

const isSubmitting = computed(() => {
  if (props.actionType === 'task' || props.actionType === 'todo_items_added')
    return taskSubmitting.value
  if (props.actionType === 'proposal') return proposalSubmitting.value
  return activitySubmitting.value
})

// ─── Template field-rendering helpers ────────────────────────────────────────

function isMultilineProp(prop: SchemaProp): boolean {
  return MULTILINE_FIELD_KEYS.has(prop.key)
}

function inputTypeFor(prop: SchemaProp): string {
  if (prop.format === 'email') return 'email'
  if (prop.format === 'uri') return 'url'
  if (prop.format === 'date') return 'date'
  if (prop.format === 'date-time') {
    if (
      props.actionType === 'event_scheduled' &&
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

// ─── Upload URLs ──────────────────────────────────────────────────────────────

const voiceMemoUploadUrl = computed(() => {
  const params = new URLSearchParams({ [`${props.entityType}_id`]: props.entityId })
  return `/api/v1/crm/voice-memos/upload?${params.toString()}`
})

const fileUploadUrl = computed(() => {
  const params = new URLSearchParams({ [`${props.entityType}_id`]: props.entityId })
  return `/api/v1/crm/file-uploads/upload?${params.toString()}`
})

// ─── Date helpers ─────────────────────────────────────────────────────────────

/** Safely convert a date-input string to ISO-8601; returns null for invalid/empty values. */
function toIsoOrNull(dateStr: string): string | null {
  if (!dateStr) return null
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? null : d.toISOString()
}

// ─── Submit handlers ──────────────────────────────────────────────────────────

async function addActivity() {
  if (toolRequiresText.value && !hasPlainText.value) return
  const resolvedType =
    props.actionType === 'message'
      ? resolvedMessageTool.value?.activity_type
      : props.actionType
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
    [entityIdField.value]: props.entityId,
    type: resolvedType,
    content_text: activityText.value,
    metadata,
  })
  activitySubmitting.value = false
  if (res.ok) {
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
    close()
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

async function submitVoiceMemo(payload: VoiceMemoSubmitPayload) {
  activitySubmitting.value = true
  const res = await api.post('/api/v1/crm/activities', {
    [entityIdField.value]: props.entityId,
    type: 'voice_memo',
    content_text: '',
    metadata: {
      url: payload.url,
      filename: payload.filename,
      content_type: payload.content_type,
      size_bytes: payload.size_bytes,
      duration_seconds: payload.duration_seconds,
    },
  })
  activitySubmitting.value = false
  if (res.ok) {
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
    close()
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

async function submitFileUpload(payload: FileUploadSubmitPayload) {
  activitySubmitting.value = true
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
  activitySubmitting.value = false
  if (res.ok) {
    emit('activity-added')
    toast.success(t('leadDetail.activityAdded'))
    close()
  } else {
    toast.error(t('leadDetail.activityFailed'))
  }
}

async function addTask() {
  if (!taskTitle.value.trim()) return
  taskSubmitting.value = true

  if (props.actionType === 'todo_items_added') {
    const res = await api.post('/api/v1/crm/activities', {
      [entityIdField.value]: props.entityId,
      type: 'todo_items_added',
      content_text: '',
      metadata: {
        text: taskTitle.value.trim(),
        assigned_to_id: taskAssigneeId.value || null,
        watcher_ids: taskWatcherIds.value,
        due_date: toIsoOrNull(taskDueDate.value),
      },
    })
    if (res.ok) {
      emit('activity-added')
      toast.success(t('leadDetail.activityAdded'))
      close()
    } else {
      toast.error(t('leadDetail.activityFailed'))
    }
  } else {
    const payload: Record<string, unknown> = {
      [entityIdField.value]: props.entityId,
      title: taskTitle.value.trim(),
      description_html: taskDescription.value,
      assigned_to_id: taskAssigneeId.value || null,
      watcher_ids: taskWatcherIds.value,
    }
    if (taskDueDate.value) payload.due_date = toIsoOrNull(taskDueDate.value)
    const res = await api.post('/api/v1/crm/tasks', payload)
    if (res.ok) {
      emit('task-created')
      emit('activity-added')
      toast.success(t('leadDetail.taskCreated'))
      close()
    } else {
      toast.error(t('leadDetail.taskFailed'))
    }
  }
  taskSubmitting.value = false
}

async function addProposal() {
  if (!proposalTitle.value.trim()) return
  proposalSubmitting.value = true
  const res = await api.post('/api/v1/crm/proposals', {
    title: proposalTitle.value.trim(),
    currency: proposalCurrency.value,
    [entityIdField.value]: props.entityId,
  })
  if (res.ok) {
    emit('activity-added')
    toast.success(t('proposals.successCreate') || 'Proposal created')
    close()
  } else {
    toast.error(t('proposals.errorCreate') || 'Failed to create proposal')
  }
  proposalSubmitting.value = false
}

function toggleTaskWatcher(userId: string) {
  const idx = taskWatcherIds.value.indexOf(userId)
  if (idx !== -1) taskWatcherIds.value.splice(idx, 1)
  else taskWatcherIds.value.push(userId)
}

function onFileUploaded(file: unknown) {
  emit('file-uploaded', file)
}

function handleSubmit() {
  if (props.actionType === 'task' || props.actionType === 'todo_items_added') {
    addTask()
  } else if (props.actionType === 'proposal') {
    addProposal()
  } else {
    addActivity()
  }
}

// ─── Modal header ─────────────────────────────────────────────────────────────

const actionIcon = computed<Component>(() => {
  if (props.actionType === 'message' && currentTool.value) {
    return heroIconMap[currentTool.value.icon] ?? ChatBubbleLeftRightIcon
  }
  const tool = toolbarTools.value.find((x) => x.activity_type === props.actionType)
  if (tool) return heroIconMap[tool.icon] ?? QuestionMarkCircleIcon
  if (props.actionType === 'task' || props.actionType === 'todo_items_added')
    return ClipboardDocumentListIcon
  if (props.actionType === 'proposal') return DocumentTextIcon
  return ClipboardDocumentListIcon
})

const actionLabel = computed(() => {
  const i18nKey = activityTypeLabelKey[props.actionType]
  if (i18nKey) {
    const translated = t(i18nKey)
    if (translated !== i18nKey) return translated
  }
  const tool = toolbarTools.value.find((x) => x.activity_type === props.actionType)
  return tool?.label ?? props.actionType
})

const actionHelp = computed(() => {
  const helpKey = activityTypeHelpKey[props.actionType]
  if (!helpKey) return ''
  const translated = t(helpKey)
  return translated === helpKey ? '' : translated
})

const submitLabel = computed(() => {
  if (isSubmitting.value) return '…'
  if (props.actionType === 'task' || props.actionType === 'todo_items_added')
    return t('leadDetail.addTask')
  if (props.actionType === 'proposal') return t('proposals.create') || 'Create'
  return t('leadDetail.activitySubmit')
})

// ─── Close ────────────────────────────────────────────────────────────────────

function close() {
  emit('update:modelValue', false)
}

// Keyboard Escape support
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
)
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        @mousedown.self="close"
      >
        <!-- Overlay -->
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close" />

        <!-- Modal card -->
        <Transition
          enter-active-class="transition-all duration-200"
          enter-from-class="opacity-0 scale-95 translate-y-2"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition-all duration-150"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 translate-y-2"
          appear
        >
          <div
            v-if="modelValue"
            class="relative z-10 w-full max-w-2xl bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden flex flex-col max-h-[90vh]"
            @click.stop
          >
            <!-- Header -->
            <div
              class="flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/60 flex-shrink-0"
            >
              <div
                class="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center flex-shrink-0"
              >
                <component :is="actionIcon" class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  {{ actionLabel }}
                </p>
                <p v-if="actionHelp" class="text-xs text-gray-500 dark:text-gray-400">
                  {{ actionHelp }}
                </p>
              </div>
              <button
                class="ml-auto text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors rounded-lg p-1"
                :title="t('common.close', 'Zavřít')"
                @click="close"
              >
                <XMarkIcon class="w-5 h-5" />
              </button>
            </div>

            <!-- Form body -->
            <div class="flex-1 overflow-y-auto px-5 py-4 space-y-3">
              <!-- Voice memo recorder -->
              <VoiceMemoRecorder
                v-if="actionType === 'voice_memo'"
                :upload-url="voiceMemoUploadUrl"
                @submit="submitVoiceMemo"
                @cancel="close"
              />

              <!-- File upload composer -->
              <FileUploadComposer
                v-else-if="actionType === 'file_upload'"
                :upload-url="fileUploadUrl"
                @submit="submitFileUpload"
                @cancel="close"
              />

              <!-- Task / todo_items_added form -->
              <template v-else-if="actionType === 'task' || actionType === 'todo_items_added'">
                <textarea
                  v-if="actionType === 'todo_items_added'"
                  v-model="taskTitle"
                  rows="4"
                  :placeholder="t('leadDetail.taskTitleBulk')"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
                />
                <input
                  v-else
                  v-model="taskTitle"
                  type="text"
                  :placeholder="t('leadDetail.taskTitle')"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                />
                <input
                  v-model="taskDueDate"
                  type="date"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                />
                <div>
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ t('tasks.assignee') }}
                  </label>
                  <select
                    v-model="taskAssigneeId"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400"
                  >
                    <option value="">{{ t('tasks.noAssignee') }}</option>
                    <option v-for="m in teamMembers" :key="m.id" :value="m.id">
                      {{ m.label }}
                    </option>
                  </select>
                </div>
                <div v-if="teamMembers.length">
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ t('tasks.watchers') }}
                  </label>
                  <div class="flex flex-wrap gap-1.5">
                    <label
                      v-for="m in teamMembers"
                      :key="m.id"
                      class="flex items-center gap-1.5 text-xs cursor-pointer px-2 py-1 rounded-lg border transition-colors"
                      :class="
                        taskWatcherIds.includes(m.id)
                          ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                          : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'
                      "
                    >
                      <input
                        type="checkbox"
                        class="hidden"
                        :checked="taskWatcherIds.includes(m.id)"
                        @change="toggleTaskWatcher(m.id)"
                      />
                      <BellIcon class="w-3.5 h-3.5" /> {{ m.label }}
                    </label>
                  </div>
                </div>
                <div v-if="actionType === 'task'">
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ t('leadDetail.descriptionLabel') }}
                  </label>
                  <RichTextEditor
                    ref="taskEditorRef"
                    v-model="taskDescription"
                    :members="teamMembers"
                    :placeholder="t('leadDetail.addMentionPlaceholder')"
                    class="min-h-[60px]"
                  />
                </div>
              </template>

              <!-- Proposal form -->
              <template v-else-if="actionType === 'proposal'">
                <div>
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ t('proposals.nameLabel') || 'Name' }}
                  </label>
                  <input
                    v-model="proposalTitle"
                    type="text"
                    :placeholder="t('proposals.namePlaceholder') || 'Proposal title...'"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  />
                </div>
                <div>
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ t('proposals.currency') || 'Currency' }}
                  </label>
                  <CurrencySelect :model-value="proposalCurrency" @update:model-value="proposalCurrency = $event" />
                </div>
              </template>

              <!-- Generic activity form (comment / call / meeting / message / email / etc.) -->
              <template v-else>
                <!-- Unified message composer: Channel + Direction picker -->
                <div
                  v-if="actionType === 'message'"
                  class="space-y-2 pb-2 border-b border-gray-100 dark:border-gray-700"
                  data-testid="message-composer-channel-picker"
                >
                  <div data-field="message-channel">
                    <label
                      class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1"
                    >
                      {{ t('messageComposer.channelLabel')
                      }}<span class="text-red-500 ml-0.5">*</span>
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

                  <!-- Direction toggle — hidden for channels with no direction toggle (e.g. chat). -->
                  <div
                    v-if="messageChannel"
                    v-show="
                      (messageChannelOptions.find((c) => c.value === messageChannel)?.directions
                        .length ?? 0) > 0
                    "
                    data-field="message-direction"
                  >
                    <label
                      class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1"
                    >
                      {{ t('messageComposer.directionLabel')
                      }}<span class="text-red-500 ml-0.5">*</span>
                    </label>
                    <div class="flex flex-wrap gap-1.5">
                      <button
                        v-for="dir in messageChannelOptions.find(
                          (c) => c.value === messageChannel,
                        )?.directions ?? []"
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

                <!-- "Header" fields: subject, to, from, … — shown above the body -->
                <template v-for="prop in schemaPropsTop" :key="prop.key">
                  <div :data-field="prop.key">
                    <label
                      class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1"
                    >
                      {{ prop.title
                      }}<span v-if="requiresField(prop.key)" class="text-red-500 ml-0.5"
                        >*</span
                      >
                    </label>
                    <select
                      v-if="prop.enum"
                      v-model="extraFields[prop.key]"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                    >
                      <option value="">{{ t('leadDetail.selectOption') }}</option>
                      <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
                    </select>
                    <textarea
                      v-else-if="isMultilineProp(prop)"
                      v-model="extraFields[prop.key]"
                      :placeholder="placeholderFor(prop)"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                      rows="3"
                    />
                    <input
                      v-else
                      v-model="extraFields[prop.key]"
                      :type="inputTypeFor(prop)"
                      :placeholder="placeholderFor(prop)"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                    />
                  </div>
                </template>

                <!-- Rich text body — only when tool schema includes content_text -->
                <RichTextEditor
                  v-if="toolHasContentText"
                  ref="richEditorRef"
                  v-model="activityText"
                  :placeholder="
                    actionType === 'comment'
                      ? t('leadDetail.commentPlaceholder')
                      : t('leadDetail.notePlaceholder')
                  "
                  :disabled="activitySubmitting"
                  :members="actionType === 'comment' ? teamMembers : []"
                  :upload-url="actionType === 'comment' ? attachmentUploadUrl : undefined"
                  @file-uploaded="onFileUploaded"
                />

                <!-- "Footer" fields: duration, transcript, recording URL, … — shown below body -->
                <template v-for="prop in schemaPropsBottom" :key="prop.key">
                  <div :data-field="prop.key">
                    <label
                      class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1"
                    >
                      {{ prop.title
                      }}<span v-if="requiresField(prop.key)" class="text-red-500 ml-0.5"
                        >*</span
                      >
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

                    <!-- Array → tag-style chip input -->
                    <div
                      v-else-if="prop.type === 'array'"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1.5 text-sm focus-within:border-red-400 flex flex-wrap items-center gap-1"
                    >
                      <span
                        v-for="tag in Array.isArray(extraFields[prop.key])
                          ? (extraFields[prop.key] as string[])
                          : []"
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
                        v-model="boolFields[prop.key]"
                        type="checkbox"
                        class="rounded border-gray-300 text-red-600 focus:ring-red-500"
                      />
                      <span>{{ prop.title }}</span>
                    </label>

                    <!-- Multi-line free text -->
                    <textarea
                      v-else-if="isMultilineProp(prop)"
                      v-model="extraFields[prop.key]"
                      rows="3"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
                    />

                    <!-- Default: typed string input (email / uri / date / date-time / text) -->
                    <input
                      v-else
                      v-model="extraFields[prop.key]"
                      :type="inputTypeFor(prop)"
                      :placeholder="placeholderFor(prop)"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                    />
                  </div>
                </template>
              </template>
            </div>

            <!-- Footer — hidden for voice_memo and file_upload (they own their own buttons) -->
            <div
              v-if="actionType !== 'voice_memo' && actionType !== 'file_upload'"
              class="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/60 flex-shrink-0"
            >
              <button
                type="button"
                class="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
                @click="close"
              >
                {{ t('common.cancel', 'Zrušit') }}
              </button>
              <button
                type="button"
                data-testid="streamline-create-modal-submit"
                :disabled="submitDisabled"
                class="px-5 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shadow-sm"
                @click="handleSubmit"
              >
                {{ submitLabel }}
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

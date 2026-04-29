<script setup lang="ts">
import { ref, computed, watch, onMounted, type Component } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useAuthStore } from '@/stores/auth'
import RichTextEditor, { type MentionUser } from '@/components/RichTextEditor.vue'
import {
  ChatBubbleLeftIcon,
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
} from '@heroicons/vue/24/outline'

/**
 * EntitySidebarActionPicker — generic, entity-agnostic Quick Actions composer.
 *
 * Loads the toolbar tools for a given entity from
 * ``GET /api/v1/streamline/entity-toolbar/{entityType}`` and renders:
 *   - a list of action-type buttons (one per registered tool)
 *   - a schema-driven form for the selected tool (fields above / below the
 *     RichTextEditor, depending on which slot they belong to)
 *   - a special-cased "task" quick-create form that POSTs to
 *     ``/api/v1/crm/tasks`` (instead of ``/api/v1/crm/activities``)
 *
 * Submit posts to ``POST /api/v1/crm/activities`` with the correct
 * ``{entityType}_id`` field. Emits ``activity-added`` / ``task-created`` so the
 * parent can reload its timeline.
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

// Map activity_type → i18n key (preserves multi-language support).
const activityTypeLabelKey: Record<string, string> = {
  comment: 'leadDetail.typeComment',
  call: 'leadDetail.typeCall',
  meeting: 'leadDetail.typeMeeting',
  email_out: 'leadDetail.typeEmailOut',
  email_in: 'leadDetail.typeEmailIn',
  task: 'leadDetail.typeTask',
}

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
const sidebarExtraFields = ref<Record<string, unknown>>({})

// Task quick-create state
const sidebarTaskTitle = ref('')
const sidebarTaskDueDate = ref('')
const sidebarTaskAssigneeId = ref('')
const sidebarTaskWatcherIds = ref<string[]>([])
const sidebarTaskDescription = ref('')
const sidebarTaskEditorRef = ref<InstanceType<typeof RichTextEditor> | null>(null)
const sidebarTaskSubmitting = ref(false)

// Fields that appear ABOVE the rich-text body (e.g. email subject / recipient).
const TOP_FIELD_KEYS = new Set(['subject', 'to', 'from_address'])
// Fields that are auto-populated by integrations (e.g. webhook callbacks) and
// should not appear in the manual-entry form.
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
  }
  return false
})

function openSidebarAction(type: string) {
  sidebarActionType.value = type
  sidebarActivityText.value = ''
  // Pre-initialise schema keys so Vue's Proxy reactivity tracks them from start.
  const tool = toolbarTools.value.find((x) => x.activity_type === type)
  const fields: Record<string, unknown> = {}
  if (tool?.form_schema?.properties) {
    for (const key of Object.keys(tool.form_schema.properties as object)) {
      if (!SKIP_FIELD_KEYS.has(key)) fields[key] = ''
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

// Build action items directly from the entity-toolbar registry.
const sidebarActionItems = computed<{ value: string; label: string; icon: Component }[]>(() => {
  return toolbarTools.value.map((tool) => {
    const i18nKey = activityTypeLabelKey[tool.activity_type]
    return {
      value: tool.activity_type,
      label: i18nKey ? t(i18nKey) : tool.label,
      icon: heroIconMap[tool.icon] ?? ClipboardDocumentListIcon,
    }
  })
})

const sidebarActionIcon = computed(
  () =>
    sidebarActionItems.value.find((i) => i.value === sidebarActionType.value)?.icon ??
    ClipboardDocumentListIcon,
)

// ─── Submit handlers ───────────────────────────────────────────────────────

const entityIdField = computed(() => `${props.entityType}_id`)

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
</script>

<template>
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
        :upload-url="sidebarActionType === 'comment' ? attachmentUploadUrl : undefined"
        @file-uploaded="onFileUploaded"
      />

      <!-- "Footer" fields: duration, recording URL, transcript, etc. — shown below body -->
      <template v-for="prop in sidebarSchemaPropsBottom" :key="prop.key">
        <div>
          <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
            {{ prop.title }}<span v-if="sidebarRequiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
          </label>
          <input
            v-if="prop.type === 'integer' || prop.type === 'number'"
            v-model.number="sidebarExtraFields[prop.key]"
            type="number"
            :min="prop.minimum ?? 0"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
          <select
            v-else-if="prop.enum"
            v-model="sidebarExtraFields[prop.key]"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('leadDetail.selectOption') }}</option>
            <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <textarea
            v-else-if="prop.key === 'transcript'"
            v-model="sidebarExtraFields[prop.key]"
            rows="3"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none"
          />
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
</template>

<script setup lang="ts">
/**
 * ActivityEditModal — Edit an existing Streamline Activity.
 *
 * Displays a modal dialog pre-populated with the existing activity's
 * content_text and metadata fields, rendered via the same schema-driven
 * form logic used by EntitySidebarActionPicker for creating new activities.
 *
 * Supported activity types: comment, call, meeting.
 * Emits 'saved' with the updated Activity object on success.
 */
import { ref, computed, watch, nextTick } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { XMarkIcon, PencilSquareIcon } from '@heroicons/vue/24/outline'

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
  reactions?: unknown[]
  is_deleted?: boolean
  deleted_at?: string | null
  deleted_by_name?: string | null
  is_edited?: boolean
  edited_at?: string | null
}

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

interface SchemaProp {
  key: string
  title: string
  type: string
  format?: string
  enum?: string[]
  minimum?: number
  maximum?: number
}

const props = defineProps<{
  activity: Activity | null
  entityType: 'lead' | 'record' | 'customer' | 'realization' | 'management' | 'proposal' | 'task'
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'saved', activity: Activity): void
}>()

const { t } = useI18n()
const toast = useToast()

// ─── Tool registry (loaded once for this entity type) ────────────────────────

const toolRegistry = ref<StreamlineTool[]>([])

async function loadTools() {
  const res = await api.get<StreamlineTool[]>(`/api/v1/streamline/entity-toolbar/${props.entityType}`)
  if (res.ok) toolRegistry.value = res.data
}

watch(() => props.entityType, loadTools, { immediate: true })

// ─── Current tool resolution ─────────────────────────────────────────────────

const currentTool = computed<StreamlineTool | null>(() => {
  if (!props.activity) return null
  return toolRegistry.value.find((t) => t.activity_type === props.activity!.type) ?? null
})

// ─── Form field helpers (identical logic to EntitySidebarActionPicker) ────────

const SKIP_FIELD_KEYS = new Set([
  'content_text', 'mentions', 'recording_filename', 'recording_size_bytes',
  'provider_message_id', 'provider_event_id', 'provider_request_id',
  'message_id', 'viewer_ip', 'user_agent', 'source_activity_ids',
])

const TOP_FIELD_KEYS = new Set([
  'subject', 'to', 'from_address', 'from_number', 'from_handle', 'to_handle',
  'channel', 'direction', 'url',
])

const MULTILINE_FIELD_KEYS = new Set(['transcript', 'description', 'notes', 'message', 'text'])

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
    }))
})

const schemaPropsTop = computed(() => schemaPropsAll.value.filter((p) => TOP_FIELD_KEYS.has(p.key)))
const schemaPropsBottom = computed(() => schemaPropsAll.value.filter((p) => !TOP_FIELD_KEYS.has(p.key)))

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
  return ''
}

function requiresField(key: string): boolean {
  return currentTool.value?.form_schema.required?.includes(key) ?? false
}

// ─── Form state ───────────────────────────────────────────────────────────────

type FieldValue = string | number | string[] | null
const contentText = ref('')
const extraFields = ref<Record<string, FieldValue>>({})
const submitting = ref(false)

const toolHasContentText = computed(() => {
  const tool = currentTool.value
  return !!(tool?.form_schema?.properties as Record<string, unknown> | undefined)?.content_text
})

/** Pre-fill the form from the existing activity's data. */
function populateForm() {
  if (!props.activity) return
  contentText.value = props.activity.content_text ?? ''
  const fields: Record<string, FieldValue> = {}
  const meta = props.activity.metadata ?? {}
  for (const prop of schemaPropsAll.value) {
    const existing = meta[prop.key]
    if (prop.type === 'array') {
      fields[prop.key] = Array.isArray(existing) ? [...(existing as string[])] : []
    } else {
      fields[prop.key] = existing !== undefined && existing !== null ? String(existing) : ''
    }
  }
  extraFields.value = fields
  // The RichTextEditor syncs via v-model; setting contentText will propagate automatically.
}

// Whenever the modal opens or the activity changes, re-populate the form.
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      // Wait for the tool registry and schema to be available.
      nextTick(populateForm)
    }
  },
)

watch(
  () => props.activity?.id,
  () => {
    if (props.modelValue) nextTick(populateForm)
  },
)

// Also re-populate after the tool registry loads (async).
watch(toolRegistry, () => {
  if (props.modelValue) nextTick(populateForm)
})

// ─── Tag (array) input helpers ────────────────────────────────────────────────

const tagDrafts = ref<Record<string, string>>({})

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

// ─── Submit ───────────────────────────────────────────────────────────────────

const hasPlainText = computed(() =>
  Boolean(contentText.value.replace(/<[^>]*>/g, '').trim()),
)

const toolRequiresText = computed(() =>
  currentTool.value?.form_schema.required?.includes('content_text') ?? false,
)

const submitDisabled = computed(() => {
  if (submitting.value) return true
  if (toolRequiresText.value && !hasPlainText.value) return true
  return false
})

async function save() {
  if (!props.activity) return
  if (toolRequiresText.value && !hasPlainText.value) return

  submitting.value = true

  let body: Record<string, unknown>
  if (props.activity.type === 'checklist') {
    // For checklist, send metadata (title + text) instead of content_text
    const meta: Record<string, unknown> = {}
    for (const prop of schemaPropsAll.value) {
      const val = extraFields.value[prop.key]
      if (val !== undefined && val !== null && val !== '') meta[prop.key] = val
    }
    body = { metadata: meta }
  } else {
    body = { content_text: contentText.value }
  }

  const res = await api.patch<Activity>(`/api/v1/crm/activities/${props.activity.id}`, body)
  submitting.value = false

  if (res.ok) {
    toast.success(t('recordDetail.activityUpdated', 'Příspěvek byl upraven'))
    emit('saved', res.data as Activity)
    close()
  } else {
    toast.error(t('recordDetail.activityFailed', 'Nepodařilo se uložit změny'))
  }
}

function close() {
  emit('update:modelValue', false)
}

// ─── Activity type label ──────────────────────────────────────────────────────

const activityTypeLabelKey: Record<string, string> = {
  comment: 'recordDetail.typeComment',
  call: 'recordDetail.typeCall',
  meeting: 'recordDetail.typeMeeting',
  checklist: 'recordDetail.typeChecklist',
}

const activityTypeLabel = computed(() => {
  if (!props.activity) return ''
  const key = activityTypeLabelKey[props.activity.type]
  return key ? t(key) : props.activity.type
})
</script>

<template>
  <!-- Backdrop -->
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
            <div class="flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/60 flex-shrink-0">
              <div class="w-8 h-8 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center flex-shrink-0">
                <PencilSquareIcon class="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-gray-800 dark:text-gray-200">
                  {{ t('recordDetail.editActivity', 'Upravit příspěvek') }}
                </p>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ activityTypeLabel }}</p>
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
              <!-- Top schema fields (e.g. subject, to, …) -->
              <template v-for="prop in schemaPropsTop" :key="prop.key">
                <div :data-field="prop.key">
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ prop.title }}<span v-if="requiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
                  </label>
                  <select
                    v-if="prop.enum"
                    v-model="extraFields[prop.key]"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  >
                    <option value="">{{ t('recordDetail.selectOption', 'Vyberte…') }}</option>
                    <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
                  </select>
                  <textarea
                    v-else-if="isMultilineProp(prop)"
                    v-model="extraFields[prop.key]"
                    :placeholder="placeholderFor(prop)"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                    rows="3"
                  />
                  <input
                    v-else
                    v-model="extraFields[prop.key]"
                    :type="inputTypeFor(prop)"
                    :placeholder="placeholderFor(prop)"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  />
                </div>
              </template>

              <!-- Rich text body -->
              <div v-if="toolHasContentText || !schemaPropsAll.length">
                <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                  {{ t('recordDetail.editorPlaceholder', 'Obsah…') }}
                </label>
                <div class="rounded-xl border border-gray-200 dark:border-gray-600 overflow-hidden">
                  <RichTextEditor
                    v-model="contentText"
                    :placeholder="t('recordDetail.editorPlaceholder', 'Napište obsah…')"
                    class="min-h-[120px]"
                  />
                </div>
              </div>

              <!-- Bottom schema fields (e.g. duration, notes, …) -->
              <template v-for="prop in schemaPropsBottom" :key="prop.key">
                <div :data-field="prop.key">
                  <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                    {{ prop.title }}<span v-if="requiresField(prop.key)" class="text-red-500 ml-0.5">*</span>
                  </label>

                  <!-- Array / tag input -->
                  <template v-if="prop.type === 'array'">
                    <div class="flex flex-wrap gap-1.5 mb-1">
                      <span
                        v-for="tag in (Array.isArray(extraFields[prop.key]) ? extraFields[prop.key] as string[] : [])"
                        :key="tag"
                        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 text-xs font-medium"
                      >
                        {{ tag }}
                        <button type="button" @click="removeTag(prop.key, tag)" class="hover:text-red-500 ml-0.5">×</button>
                      </span>
                    </div>
                    <input
                      v-model="tagDrafts[prop.key]"
                      :placeholder="t('recordDetail.tagPlaceholder', 'Přidat… (Enter nebo čárka)')"
                      class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                      @keydown="onTagKey($event, prop.key)"
                      @blur="addTag(prop.key)"
                    />
                  </template>

                  <!-- Enum select -->
                  <select
                    v-else-if="prop.enum"
                    v-model="extraFields[prop.key]"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  >
                    <option value="">{{ t('recordDetail.selectOption', 'Vyberte…') }}</option>
                    <option v-for="opt in prop.enum" :key="opt" :value="opt">{{ opt }}</option>
                  </select>

                  <!-- Multiline textarea -->
                  <textarea
                    v-else-if="isMultilineProp(prop)"
                    v-model="extraFields[prop.key]"
                    :placeholder="placeholderFor(prop)"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
                    rows="3"
                  />

                  <!-- Generic input -->
                  <input
                    v-else
                    v-model="extraFields[prop.key]"
                    :type="inputTypeFor(prop)"
                    :placeholder="placeholderFor(prop)"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                  />
                </div>
              </template>
            </div>

            <!-- Footer -->
            <div class="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/60 flex-shrink-0">
              <button
                type="button"
                class="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
                @click="close"
              >
                {{ t('common.cancel', 'Zrušit') }}
              </button>
              <button
                type="button"
                :disabled="submitDisabled"
                class="px-5 py-2 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl transition-colors shadow-sm"
                @click="save"
              >
                <span v-if="submitting">{{ t('common.saving', 'Ukládám…') }}</span>
                <span v-else>{{ t('common.save', 'Uložit') }}</span>
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

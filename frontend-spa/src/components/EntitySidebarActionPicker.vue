<script setup lang="ts">
import { ref, computed, watch, onMounted, type Component } from 'vue'
import { api } from '@/api'
import { useI18n } from '@/composables/useI18n'
import {
  ChatBubbleLeftIcon,
  ChatBubbleLeftRightIcon,
  ChatBubbleOvalLeftEllipsisIcon,
  PhoneIcon,
  UsersIcon,
  PaperAirplaneIcon,
  InboxArrowDownIcon,
  ClipboardDocumentListIcon,
  ClipboardDocumentCheckIcon,
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
  AtSymbolIcon,
  ClockIcon,
  ShieldExclamationIcon,
  ShieldCheckIcon,
  CheckBadgeIcon,
  BanknotesIcon,
  DocumentCurrencyDollarIcon,
  PencilSquareIcon,
} from '@heroicons/vue/24/outline'

/**
 * EntitySidebarActionPicker — entity-agnostic Quick Actions grid.
 *
 * Loads the toolbar tools for a given entity from
 * ``GET /api/v1/streamline/entity-toolbar/{entityType}`` and renders a
 * grouped button grid (communication / planning / files / system categories).
 *
 * Clicking any action button emits ``tool-selected`` with the action type so
 * the parent can open ``StreamlineCreateModal`` with the correct tool.
 *
 * The 6 channel-specific messaging tools (email/SMS/WhatsApp/chat) are
 * replaced in the grid by a single ``message`` pseudo-tool; the modal handles
 * the channel + direction selection inside.
 *
 * Exposes ``groupedActionItems`` so the parent can render the same tool list
 * elsewhere (e.g. an "Akce" quick-add dropdown in the feed header).
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

const props = defineProps<{
  entityType: 'record' | 'customer' | 'realization' | 'management' | 'proposal'
  entityId: string
}>()

const emit = defineEmits<{
  (e: 'tool-selected', type: string): void
}>()

const { t } = useI18n()

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
  ClipboardDocumentCheckIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  DocumentCheckIcon,
  DevicePhoneMobileIcon,
  CalendarDaysIcon,
  LinkIcon,
  MicrophoneIcon,
  InformationCircleIcon,
  AtSymbolIcon,
  ClockIcon,
  ShieldExclamationIcon,
  ShieldCheckIcon,
  CheckBadgeIcon,
  BanknotesIcon,
  DocumentCurrencyDollarIcon,
  PencilSquareIcon,
}

// Map activity_type → i18n key (preserves multi-language support).
const activityTypeLabelKey: Record<string, string> = {
  comment: 'recordDetail.typeComment',
  call: 'recordDetail.typeCall',
  meeting: 'recordDetail.typeMeeting',
  email_out: 'recordDetail.typeEmailOut',
  email_in: 'recordDetail.typeEmailIn',
  task: 'recordDetail.typeTask',
  sms_out: 'recordDetail.typeSmsOut',
  sms_in: 'recordDetail.typeSmsIn',
  whatsapp_out: 'recordDetail.typeWhatsAppOut',
  whatsapp_in: 'recordDetail.typeWhatsAppIn',
  chat: 'recordDetail.typeChat',
  mention: 'recordDetail.typeMention',
  meeting_scheduled: 'recordDetail.typeMeetingScheduled',
  call_scheduled: 'recordDetail.typeCallScheduled',
  event_scheduled: 'recordDetail.typeEventScheduled',
  checklist: 'recordDetail.typeChecklist',
  todo_items_added: 'recordDetail.typeTodoItems',
  time_logged: 'recordDetail.typeTimeLogged',
  approval_requested: 'recordDetail.typeApprovalRequested',
  approval_resolved: 'recordDetail.typeApprovalResolved',
  link: 'recordDetail.typeLink',
  voice_memo: 'recordDetail.typeVoiceMemo',
  file_upload: 'recordDetail.typeFileUpload',
  payment_received: 'recordDetail.typePaymentReceived',
  invoice_sent: 'recordDetail.typeInvoiceSent',
  signature_requested: 'recordDetail.typeSignatureRequested',
  signature_completed: 'recordDetail.typeSignatureCompleted',
  todo_items: 'recordDetail.typeTodoItems',
  proposal: 'recordDetail.typeProposal',
  system_note: 'recordDetail.typeSystemNote',
  // Pseudo-tool for the unified messaging composer (no real activity_type).
  message: 'recordDetail.typeMessage',
}

// ─── Tool category grouping (UX layout) ────────────────────────────────────

interface ToolCategory {
  key: 'communication' | 'planning' | 'files' | 'commerce' | 'system' | 'other'
  labelKey: string
  activityTypes: string[]
  accent: string
}

const TOOL_CATEGORIES: ToolCategory[] = [
  {
    key: 'communication',
    labelKey: 'recordDetail.toolCategory.communication',
    activityTypes: ['comment', 'call', 'meeting', 'message', 'mention'],
    accent: 'red',
  },
  {
    key: 'planning',
    labelKey: 'recordDetail.toolCategory.planning',
    activityTypes: ['meeting_scheduled', 'call_scheduled', 'event_scheduled', 'task', 'checklist', 'todo_items_added', 'proposal', 'time_logged', 'approval_requested', 'approval_resolved'],
    accent: 'blue',
  },
  {
    key: 'files',
    labelKey: 'recordDetail.toolCategory.files',
    activityTypes: ['file_upload', 'voice_memo', 'link'],
    accent: 'emerald',
  },
  {
    key: 'commerce',
    labelKey: 'recordDetail.toolCategory.commerce',
    activityTypes: ['payment_received', 'invoice_sent', 'signature_requested', 'signature_completed'],
    accent: 'purple',
  },
  {
    key: 'system',
    labelKey: 'recordDetail.toolCategory.system',
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

watch(() => props.entityType, () => {
  toolbarTools.value = []
  loadToolbar()
})

// ─── Unified "Message" pseudo-tool ─────────────────────────────────────────
// Messaging tools (channel != 'none') are replaced in the grid by a single
// "Message" pseudo-tool that opens StreamlineCreateModal with actionType='message'.

const messagingTools = computed(() =>
  toolbarTools.value.filter((t) => t.channel && t.channel !== 'none'),
)

const hasMessagingTools = computed(() => messagingTools.value.length > 0)

// ─── Action grid ───────────────────────────────────────────────────────────

interface ActionItem {
  value: string
  label: string
  icon: Component
}

const _toolByActivityType = computed(() => {
  const map = new Map<string, StreamlineTool>()
  for (const tool of toolbarTools.value) map.set(tool.activity_type, tool)
  if (hasMessagingTools.value) {
    map.set('message', {
      activity_type: 'message',
      label: t('recordDetail.typeMessage'),
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

  const leftover = toolbarTools.value
    .filter((t) => !used.has(t.activity_type) && (!t.channel || t.channel === 'none'))
    .map(_toActionItem)
  if (leftover.length) {
    groups.push({
      key: 'other',
      labelKey: 'recordDetail.toolCategory.other',
      activityTypes: leftover.map((i) => i.value),
      accent: 'gray',
      items: leftover,
    })
  }
  return groups
})

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
    case 'purple':
      return {
        ring: 'border-purple-200 dark:border-purple-700/50',
        text: 'text-purple-600 dark:text-purple-400',
        hover: 'hover:border-purple-400 hover:text-purple-700 dark:hover:text-purple-300',
      }
    case 'red':
    default:
      return {
        ring: 'border-red-200 dark:border-red-700/50',
        text: 'text-red-600 dark:text-red-400',
        hover: 'hover:border-red-400 hover:text-red-700 dark:hover:text-red-300',
      }
  }
}

defineExpose({ groupedActionItems })
</script>

<template>
  <div
    class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4"
    data-testid="entity-sidebar-action-picker"
  >
    <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
      {{ t('recordDetail.quickActions') }}
    </p>

    <!-- Action grid — always visible; clicking opens StreamlineCreateModal in parent -->
    <div class="flex flex-col gap-3" data-testid="entity-sidebar-action-groups">
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
            @click="emit('tool-selected', item.value)"
          >
            <component :is="item.icon" class="w-4 h-4 flex-shrink-0" :class="accentClasses(group.accent).text" />
            <span class="flex-1 truncate">{{ item.label }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

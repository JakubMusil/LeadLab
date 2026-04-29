<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/composables/useI18n'

const toast = useToast()
const firmStore = useFirmStore()
const authStore = useAuthStore()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AutomationCondition {
  field: string
  operator: string
  value: string
}

interface AutomationAction {
  type: string
  [key: string]: string | number | string[]
}

interface AutomationRule {
  id: string
  name: string
  is_active: boolean
  trigger: string
  trigger_config: Record<string, unknown>
  conditions: AutomationCondition[]
  condition_logic: 'and' | 'or'
  actions: AutomationAction[]
  created_at: string
  updated_at: string
}

interface AutomationTemplate {
  id: string
  name: string
  description: string
  trigger: string
  trigger_config: Record<string, unknown>
  conditions: AutomationCondition[]
  actions: AutomationAction[]
}

interface AutomationRun {
  id: string
  rule_id: string
  status: 'success' | 'failure' | 'skipped'
  triggered_at: string
  context: Record<string, unknown>
  error_message: string
}

interface FirmMember {
  user_id: string
  user_email: string
  user_name: string
  role: string
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TRIGGER_LABELS = computed<Record<string, string>>(() => ({
  lead_created: t('automations.triggerLeadCreated'),
  lead_status_change: t('automations.triggerLeadStatusChanged'),
  task_overdue: t('automations.triggerTaskOverdue'),
  task_created: t('automations.triggerTaskCreated'),
  task_completed: t('automations.triggerTaskCompleted'),
  proposal_sent: t('automations.triggerProposalSent'),
  proposal_accepted: t('automations.triggerProposalAccepted'),
  lead_inactive: t('automations.triggerInactiveLead'),
  webhook_received: t('automations.triggerWebhookReceived'),
  realization_status_change: t('automations.triggerRealizationStatusChange'),
  sla_expiring: t('automations.triggerSlaExpiring'),
  contact_created: t('automations.triggerContactCreated'),
  milestone_completed: t('automations.triggerMilestoneCompleted'),
}))

const TRIGGER_DESCRIPTIONS: Record<string, string> = {
  lead_created: 'Fires when a new lead is created in the CRM.',
  lead_status_change: 'Fires when a lead\'s status changes (e.g. new → won).',
  task_overdue: 'Fires periodically for tasks that are past their due date.',
  task_created: 'Fires when a new task is created.',
  task_completed: 'Fires when a task is marked as completed — useful for chaining tasks.',
  proposal_sent: 'Fires when a proposal is sent to a customer.',
  proposal_accepted: 'Fires when a customer accepts a proposal.',
  lead_inactive: 'Fires for leads with no activity for a configurable number of days.',
  webhook_received: 'Fires when a custom webhook event is received.',
  // Phase 4.6
  realization_status_change: 'Fires when a realization\'s status changes (e.g. planned → done).',
  sla_expiring: 'Fires periodically for management records whose SLA/warranty is expiring within the configured number of days.',
  contact_created: 'Fires when a new contact (person or company) is added to the directory.',
  milestone_completed: 'Fires when a milestone is marked as completed in a realization.',
}

const ACTION_TYPE_LABELS = computed<Record<string, string>>(() => ({
  send_email: t('automations.actionSendEmail'),
  create_task: t('automations.actionCreateTask'),
  update_field: t('automations.actionUpdateField'),
  call_webhook: t('automations.actionWebhook'),
  run_plugin_action: t('automations.actionRunPluginAction'),
  set_task_status: t('automations.actionUpdateTaskStatus'),
  assign_tag: t('automations.actionAddTag'),
  create_realization: t('automations.actionCreateRealization'),
  create_management: t('automations.actionCreateManagement'),
}))

const OPERATOR_LABELS: Record<string, string> = {
  eq: '=',
  neq: '≠',
  gt: '>',
  gte: '≥',
  lt: '<',
  lte: '≤',
  contains: 'contains',
}

const TASK_STATUS_OPTIONS = [
  { value: 'todo', label: 'To Do' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'done', label: 'Done' },
  { value: 'cancelled', label: 'Cancelled' },
]

const PRIORITY_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const automationRules = ref<AutomationRule[]>([])
const automationTemplates = ref<AutomationTemplate[]>([])
const firmMembers = ref<FirmMember[]>([])
const automationsLoading = ref(false)
const showTemplates = ref(false)
const expandedRuleRuns = ref<string | null>(null)
const ruleRunsMap = ref<Record<string, AutomationRun[]>>({})
const ruleRunsLoading = ref(false)

// New / edit rule form
const showRuleForm = ref(false)
const editingRule = ref<AutomationRule | null>(null)
const ruleFormName = ref('')
const ruleFormTrigger = ref('task_created')
const ruleFormTriggerConfig = ref<Record<string, unknown>>({})
const ruleFormConditions = ref<AutomationCondition[]>([])
const ruleFormConditionLogic = ref<'and' | 'or'>('and')
const ruleFormActions = ref<AutomationAction[]>([])
const ruleSaving = ref(false)

// ---------------------------------------------------------------------------
// Default action factory
// ---------------------------------------------------------------------------

function defaultAction(type: string): AutomationAction {
  const defaults: Record<string, AutomationAction> = {
    send_email: { type: 'send_email', to: 'owner', subject: '', body: '' },
    create_task: { type: 'create_task', title_template: '', due_days_offset: 0, priority: 'medium', assign_to_user_id: 'inherit', tags: [] },
    update_field: { type: 'update_field', field: 'status', value: '' },
    call_webhook: { type: 'call_webhook', url: '', method: 'POST' },
    run_plugin_action: { type: 'run_plugin_action', plugin_name: '', action: '' },
    set_task_status: { type: 'set_task_status', status: 'done' },
    assign_tag: { type: 'assign_tag', tag: '', target_type: 'task' },
  }
  return defaults[type] ?? { type }
}

async function loadAutomations() {
  automationsLoading.value = true
  const res = await api.get<AutomationRule[]>('/api/v1/crm/automations')
  automationsLoading.value = false
  if (res.ok && Array.isArray(res.data)) automationRules.value = res.data
}

async function loadAutomationTemplates() {
  const res = await api.get<AutomationTemplate[]>('/api/v1/crm/automations/templates')
  if (res.ok && Array.isArray(res.data)) automationTemplates.value = res.data
}

async function loadFirmMembers() {
  if (!firmStore.activeFirm) return
  const res = await api.get<FirmMember[]>(`/api/v1/firms/${firmStore.activeFirm.id}/members`)
  if (res.ok && Array.isArray(res.data)) firmMembers.value = res.data
}

onMounted(() => {
  loadAutomations()
  loadAutomationTemplates()
  loadFirmMembers()
})

// ---------------------------------------------------------------------------
// Rule form helpers
// ---------------------------------------------------------------------------

function openNewRuleForm() {
  editingRule.value = null
  ruleFormName.value = ''
  ruleFormTrigger.value = 'task_created'
  ruleFormTriggerConfig.value = {}
  ruleFormConditions.value = []
  ruleFormConditionLogic.value = 'and'
  ruleFormActions.value = [defaultAction('create_task')]
  showRuleForm.value = true
  showTemplates.value = false
}

function openEditRuleForm(rule: AutomationRule) {
  editingRule.value = rule
  ruleFormName.value = rule.name
  ruleFormTrigger.value = rule.trigger
  ruleFormTriggerConfig.value = { ...rule.trigger_config }
  ruleFormConditions.value = rule.conditions.map((c) => ({ ...c }))
  ruleFormConditionLogic.value = rule.condition_logic ?? 'and'
  ruleFormActions.value = rule.actions.map((a) => ({ ...a }))
  showRuleForm.value = true
  showTemplates.value = false
  expandedRuleRuns.value = null
}

function cancelRuleForm() {
  showRuleForm.value = false
  editingRule.value = null
}

function addCondition() {
  ruleFormConditions.value.push({ field: 'task_status', operator: 'eq', value: '' })
}

function removeCondition(i: number) {
  ruleFormConditions.value.splice(i, 1)
}

function addAction() {
  ruleFormActions.value.push(defaultAction('create_task'))
}

function removeAction(i: number) {
  ruleFormActions.value.splice(i, 1)
}

function onActionTypeChange(i: number, newType: string) {
  ruleFormActions.value[i] = defaultAction(newType)
}

function getActionTagsString(action: AutomationAction): string {
  const tags = action.tags
  if (Array.isArray(tags)) return tags.join(', ')
  if (typeof tags === 'string') return tags
  return ''
}

function setActionTagsFromString(i: number, value: string) {
  ruleFormActions.value[i].tags = value.split(',').map((t) => t.trim()).filter(Boolean)
}

// ---------------------------------------------------------------------------
// Save / toggle / delete
// ---------------------------------------------------------------------------

async function saveRule() {
  if (!ruleFormName.value.trim()) {
    toast.error(t('automations.ruleNameRequired'))
    return
  }
  ruleSaving.value = true
  const body = {
    name: ruleFormName.value.trim(),
    trigger: ruleFormTrigger.value,
    trigger_config: ruleFormTriggerConfig.value,
    conditions: ruleFormConditions.value,
    condition_logic: ruleFormConditionLogic.value,
    actions: ruleFormActions.value,
  }
  const res = editingRule.value
    ? await api.patch<AutomationRule>(`/api/v1/crm/automations/${editingRule.value.id}`, body)
    : await api.post<AutomationRule>('/api/v1/crm/automations', { ...body, is_active: true })
  ruleSaving.value = false
  if (res.ok && res.data) {
    if (editingRule.value) {
      const idx = automationRules.value.findIndex((r) => r.id === editingRule.value!.id)
      if (idx !== -1) automationRules.value.splice(idx, 1, res.data)
    } else {
      automationRules.value.unshift(res.data)
    }
    toast.success(editingRule.value ? t('automations.ruleUpdated') : t('automations.ruleCreated'))
    cancelRuleForm()
  } else {
    toast.error(t('automations.failedToSaveRule'))
  }
}

async function toggleRule(rule: AutomationRule) {
  const res = await api.patch<AutomationRule>(`/api/v1/crm/automations/${rule.id}`, {
    is_active: !rule.is_active,
  })
  if (res.ok && res.data) {
    const idx = automationRules.value.findIndex((r) => r.id === rule.id)
    if (idx !== -1) automationRules.value.splice(idx, 1, res.data)
    toast.success(res.data.is_active ? t('automations.ruleEnabled') : t('automations.ruleDisabled'))
  } else {
    toast.error(t('automations.failedToUpdateRule'))
  }
}

async function deleteRule(rule: AutomationRule) {
  if (!confirm(t('automations.deleteConfirm', { name: rule.name }))) return
  const res = await api.delete(`/api/v1/crm/automations/${rule.id}`)
  if (res.ok || res.status === 204) {
    automationRules.value = automationRules.value.filter((r) => r.id !== rule.id)
    if (expandedRuleRuns.value === rule.id) expandedRuleRuns.value = null
    toast.success(t('automations.ruleDeleted'))
  } else {
    toast.error(t('automations.failedToDeleteRule'))
  }
}

// ---------------------------------------------------------------------------
// Execution log
// ---------------------------------------------------------------------------

async function toggleRuleRuns(rule: AutomationRule) {
  if (expandedRuleRuns.value === rule.id) {
    expandedRuleRuns.value = null
    return
  }
  expandedRuleRuns.value = rule.id
  if (!ruleRunsMap.value[rule.id]) {
    ruleRunsLoading.value = true
    const res = await api.get<AutomationRun[]>(`/api/v1/crm/automations/${rule.id}/runs?limit=20`)
    ruleRunsLoading.value = false
    if (res.ok && Array.isArray(res.data)) ruleRunsMap.value[rule.id] = res.data
  }
}

async function refreshRuleRuns(ruleId: string) {
  ruleRunsLoading.value = true
  const res = await api.get<AutomationRun[]>(`/api/v1/crm/automations/${ruleId}/runs?limit=20`)
  ruleRunsLoading.value = false
  if (res.ok && Array.isArray(res.data)) ruleRunsMap.value[ruleId] = res.data
}

// ---------------------------------------------------------------------------
// Templates
// ---------------------------------------------------------------------------

async function createFromTemplate(tmpl: AutomationTemplate) {
  const res = await api.post<AutomationRule>(
    `/api/v1/crm/automations/from-template/${tmpl.id}`,
  )
  if (res.ok && res.data) {
    automationRules.value.unshift(res.data)
    toast.success(t('automations.ruleCreatedFromTemplate', { name: res.data.name }))
    showTemplates.value = false
  } else {
    toast.error(t('automations.failedToCreateFromTemplate'))
  }
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

function ruleReadableSummary(rule: AutomationRule): string {
  const triggerLabel = TRIGGER_LABELS.value[rule.trigger] ?? rule.trigger
  const condCount = rule.conditions.length
  const actCount = rule.actions.length
  const logic = rule.condition_logic === 'or' ? 'OR' : 'AND'
  const condPart = condCount > 1
    ? ` + ${condCount} conditions (${logic})`
    : condCount === 1 ? ' + 1 condition' : ''
  const actPart = `${actCount} action${actCount !== 1 ? 's' : ''}`
  return `${triggerLabel}${condPart} → ${actPart}`
}

function actionSummary(action: AutomationAction): string {
  const label = ACTION_TYPE_LABELS.value[action.type] ?? action.type
  if (action.type === 'send_email') return `${label} to ${action.to}`
  if (action.type === 'create_task') {
    const title = action.title_template || action.title || '…'
    return `${label}: "${title}"`
  }
  if (action.type === 'update_field') return `${label}: ${action.field} = ${action.value}`
  if (action.type === 'call_webhook') return `${label}: ${action.url}`
  if (action.type === 'run_plugin_action') return `${label}: ${action.plugin_name}.${action.action}`
  if (action.type === 'set_task_status') return `${label}: → ${action.status}`
  if (action.type === 'assign_tag') return `${label}: "${action.tag}" on ${action.target_type}`
  return label
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function lastRunLabel(rule: AutomationRule): string {
  const runs = ruleRunsMap.value[rule.id]
  if (!runs || runs.length === 0) return ''
  return `Last run: ${formatDate(runs[0].triggered_at)}`
}
</script>

<template>
  <div class="p-6 space-y-5">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">{{ t('automations.title') }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          {{ t('automations.subtitle') }}
        </p>
      </div>
      <div class="flex gap-2">
        <button
          class="text-sm text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-xl px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          @click="showTemplates = !showTemplates; showRuleForm = false"
        >{{ showTemplates ? t('automations.hideTemplates') : t('automations.templates') }}</button>
        <button
          class="text-sm bg-red-600 text-white rounded-xl px-4 py-2 hover:bg-red-700 transition-colors font-medium"
          @click="openNewRuleForm"
        >{{ t('automations.newRule') }}</button>
      </div>
    </div>

    <!-- Built-in templates picker -->
    <div
      v-if="showTemplates"
      class="bg-white dark:bg-gray-800 rounded-2xl border border-dashed border-gray-200 dark:border-gray-600 p-5 space-y-3"
    >
      <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {{ t('automations.readyToUseTemplates') }}
      </p>
      <div v-if="automationTemplates.length === 0" class="text-sm text-gray-400 py-2 text-center">{{ t('automations.loadingTemplates') }}</div>
      <div
        v-for="tmpl in automationTemplates"
        :key="tmpl.id"
        class="flex items-start gap-3 p-4 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-700"
      >
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-800 dark:text-gray-100">{{ tmpl.name }}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ tmpl.description }}</p>
          <p class="text-xs text-gray-400 dark:text-gray-500 mt-1 font-mono">
            {{ t('automations.trigger') }} {{ TRIGGER_LABELS[tmpl.trigger] ?? tmpl.trigger }}
          </p>
        </div>
        <button
          class="flex-shrink-0 text-xs bg-red-600 text-white rounded-lg px-3 py-1.5 hover:bg-red-700"
          @click="createFromTemplate(tmpl)"
        >{{ t('automations.useTemplate') }}</button>
      </div>
    </div>

    <!-- Rule editor form (create / edit) -->
    <div
      v-if="showRuleForm"
      class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-600 p-5 space-y-5"
    >
      <p class="text-sm font-semibold text-gray-700 dark:text-gray-200">
        {{ editingRule ? t('automations.editRuleTitle') : t('automations.newRuleTitle') }}
      </p>

      <!-- Name -->
      <div>
        <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('automations.ruleName') }}</label>
        <input
          v-model="ruleFormName"
          type="text"
          :placeholder="t('automations.ruleNamePlaceholder')"
          class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
      </div>

      <!-- Trigger -->
      <div>
        <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('automations.triggerLabel') }}</label>
        <select
          v-model="ruleFormTrigger"
          class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        >
          <option v-for="(label, key) in TRIGGER_LABELS" :key="key" :value="key">{{ label }}</option>
        </select>
        <p v-if="TRIGGER_DESCRIPTIONS[ruleFormTrigger]" class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          {{ TRIGGER_DESCRIPTIONS[ruleFormTrigger] }}
        </p>
      </div>

      <!-- Trigger config: inactive_days / warning_days -->
      <div v-if="ruleFormTrigger === 'lead_inactive'" class="flex items-center gap-3">
        <label class="text-xs font-medium text-gray-700 dark:text-gray-300 w-36">{{ t('automations.inactiveDays') }}</label>
        <input
          :value="(ruleFormTriggerConfig['inactive_days'] as string | number) ?? 30"
          type="number"
          min="1"
          class="w-24 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
          @input="ruleFormTriggerConfig['inactive_days'] = Number(($event.target as HTMLInputElement).value)"
        />
        <span class="text-xs text-gray-400">{{ t('automations.daysWithoutActivity') }}</span>
      </div>
      <div v-else-if="ruleFormTrigger === 'task_overdue'" class="flex items-center gap-3">
        <label class="text-xs font-medium text-gray-700 dark:text-gray-300 w-36">{{ t('automations.warningWindow') }}</label>
        <input
          :value="(ruleFormTriggerConfig['warning_days'] as string | number) ?? 1"
          type="number"
          min="0"
          class="w-24 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
          @input="ruleFormTriggerConfig['warning_days'] = Number(($event.target as HTMLInputElement).value)"
        />
        <span class="text-xs text-gray-400">{{ t('automations.daysBeforeDue') }}</span>
      </div>

      <!-- Conditions -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-3">
            <label class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('automations.conditions') }}</label>
            <!-- AND / OR toggle -->
            <div v-if="ruleFormConditions.length > 1" class="flex rounded-lg border border-gray-200 dark:border-gray-600 overflow-hidden text-xs">
              <button
                :class="ruleFormConditionLogic === 'and' ? 'bg-red-500 text-white' : 'bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600'"
                class="px-2.5 py-1 font-medium transition-colors"
                @click="ruleFormConditionLogic = 'and'"
              >AND</button>
              <button
                :class="ruleFormConditionLogic === 'or' ? 'bg-red-500 text-white' : 'bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600'"
                class="px-2.5 py-1 font-medium transition-colors"
                @click="ruleFormConditionLogic = 'or'"
              >OR</button>
            </div>
            <span v-else class="text-xs text-gray-400">{{ t('automations.conditionsHint') }}</span>
          </div>
          <button
            class="text-xs text-red-600 hover:text-red-700 font-medium"
            @click="addCondition"
          >{{ t('automations.addCondition') }}</button>
        </div>
        <div v-if="ruleFormConditions.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic py-1">
          {{ t('automations.noConditions') }}
        </div>
        <div
          v-for="(cond, i) in ruleFormConditions"
          :key="i"
          class="flex gap-2 mb-2 items-center flex-wrap"
        >
          <!-- AND/OR badge between conditions -->
          <div v-if="i > 0" class="w-full flex items-center gap-2 -mt-1 mb-1">
            <div class="h-px flex-1 bg-gray-100 dark:bg-gray-700" />
            <span class="text-xs font-semibold px-2 py-0.5 rounded" :class="ruleFormConditionLogic === 'or' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' : 'bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'">
              {{ ruleFormConditionLogic.toUpperCase() }}
            </span>
            <div class="h-px flex-1 bg-gray-100 dark:bg-gray-700" />
          </div>
          <input
            v-model="cond.field"
            type="text"
            placeholder="field (e.g. task_status, lead_status)"
            class="flex-1 min-w-[140px] rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
          />
          <select
            v-model="cond.operator"
            class="rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
          >
            <option v-for="(label, op) in OPERATOR_LABELS" :key="op" :value="op">{{ label }}</option>
          </select>
          <input
            v-model="cond.value"
            type="text"
            placeholder="value"
            class="flex-1 min-w-[100px] rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
          />
          <button class="text-gray-300 hover:text-red-400 text-sm flex-shrink-0" @click="removeCondition(i)">✕</button>
        </div>
      </div>

      <!-- Actions -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('automations.actionsLabel') }} <span class="font-normal text-gray-400">{{ t('automations.actionsRunInOrder') }}</span></label>
          <button
            class="text-xs text-red-600 hover:text-red-700 font-medium"
            @click="addAction"
          >{{ t('automations.addAction') }}</button>
        </div>
        <div v-if="ruleFormActions.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic py-1">
          {{ t('automations.noActions') }}
        </div>
        <div
          v-for="(action, i) in ruleFormActions"
          :key="i"
          class="mb-3 p-4 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-700 space-y-3"
        >
          <!-- Action type selector -->
          <div class="flex items-center gap-2">
            <select
              :value="action.type"
              class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              @change="onActionTypeChange(i, ($event.target as HTMLSelectElement).value)"
            >
              <option v-for="(label, key) in ACTION_TYPE_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
            <button class="text-gray-300 hover:text-red-400 text-sm flex-shrink-0" @click="removeAction(i)">✕</button>
          </div>

          <!-- send_email fields -->
          <template v-if="action.type === 'send_email'">
            <div class="flex gap-2 items-center">
              <label class="text-xs text-gray-500 dark:text-gray-400 w-12">{{ t('automations.emailTo') }}</label>
              <select
                v-model="action.to"
                class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              >
                <option value="owner">{{ t('automations.emailOwner') }}</option>
                <option value="assignee">{{ t('automations.emailAssignee') }}</option>
                <option value="customer">{{ t('automations.emailCustomer') }}</option>
              </select>
            </div>
            <input
              v-model="action.subject"
              type="text"
              placeholder="Subject — supports {{lead_title}}, {{task_title}}, {{customer_name}}"
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
            />
            <textarea
              v-model="action.body"
              rows="3"
              placeholder="Email body. Use {{lead_title}}, {{task_title}}, {{customer_name}}, {{assignee_name}}…"
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400 resize-none"
            />
          </template>

          <!-- create_task fields (Phase 4 extended) -->
          <template v-else-if="action.type === 'create_task'">
            <div>
              <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.taskTitleTemplate') }}</label>
              <input
                v-model="action.title_template"
                type="text"
                placeholder="e.g. Follow up with {{customer_name}} on {{lead_title}}"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              />
              <p class="text-[10px] text-gray-400 mt-0.5">Placeholders: <code>{{lead_title}}</code>, <code>{{task_title}}</code>, <code>{{customer_name}}</code>, <code>{{due_date}}</code> (triggering task's due date)</p>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.dueInDays') }}</label>
                <input
                  v-model.number="action.due_days_offset"
                  type="number"
                  min="0"
                  placeholder="0"
                  class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                />
              </div>
              <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.priority') }}</label>
                <select
                  v-model="action.priority"
                  class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                >
                  <option v-for="opt in PRIORITY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.assignTo') }}</label>
              <select
                v-model="action.assign_to_user_id"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              >
                <option value="inherit">{{ t('automations.inheritAssignee') }}</option>
                <option value="">{{ t('automations.unassigned') }}</option>
                <option
                  v-for="m in firmMembers"
                  :key="m.user_id"
                  :value="m.user_id"
                >{{ m.user_name || m.user_email }}</option>
              </select>
            </div>
            <div>
              <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.tagsComma') }}</label>
              <input
                :value="getActionTagsString(action)"
                type="text"
                placeholder="e.g. onboarding, follow-up"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                @input="setActionTagsFromString(i, ($event.target as HTMLInputElement).value)"
              />
            </div>
          </template>

          <!-- set_task_status fields -->
          <template v-else-if="action.type === 'set_task_status'">
            <p class="text-xs text-gray-500 dark:text-gray-400">
              {{ t('automations.setsTaskStatus') }}
            </p>
            <div>
              <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.newStatus') }}</label>
              <select
                v-model="action.status"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              >
                <option v-for="opt in TASK_STATUS_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
          </template>

          <!-- assign_tag fields -->
          <template v-else-if="action.type === 'assign_tag'">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.tag') }}</label>
                <input
                  v-model="action.tag"
                  type="text"
                  placeholder="e.g. vip, priority"
                  class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                />
              </div>
              <div>
                <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('automations.applyTo') }}</label>
                <select
                  v-model="action.target_type"
                  class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                >
                  <option value="task">{{ t('automations.taskFromTrigger') }}</option>
                  <option value="lead">{{ t('automations.leadFromTrigger') }}</option>
                </select>
              </div>
            </div>
          </template>

          <!-- update_field fields -->
          <template v-else-if="action.type === 'update_field'">
            <div class="flex gap-2">
              <select
                v-model="action.field"
                class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              >
                <option value="status">{{ t('automations.leadStatus') }}</option>
                <option value="source">{{ t('automations.leadSource') }}</option>
                <option value="currency">{{ t('automations.currency') }}</option>
                <option value="description">{{ t('automations.description') }}</option>
              </select>
              <input
                v-model="action.value"
                type="text"
                :placeholder="t('automations.newValue')"
                class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              />
            </div>
          </template>

          <!-- call_webhook fields -->
          <template v-else-if="action.type === 'call_webhook'">
            <input
              v-model="action.url"
              type="url"
              placeholder="https://your-server.com/webhook"
              class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
            />
          </template>

          <!-- run_plugin_action fields -->
          <template v-else-if="action.type === 'run_plugin_action'">
            <div class="flex gap-2">
              <input
                v-model="action.plugin_name"
                type="text"
                placeholder="Plugin name"
                class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              />
              <input
                v-model="action.action"
                type="text"
                placeholder="Action name"
                class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              />
            </div>
          </template>
        </div>
      </div>

      <!-- Form buttons -->
      <div class="flex gap-2 pt-1 border-t border-gray-100 dark:border-gray-700">
        <button
          :disabled="ruleSaving || !ruleFormName.trim()"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
          @click="saveRule"
        >{{ ruleSaving ? t('automations.saving') : (editingRule ? t('automations.updateRule') : t('automations.createRule')) }}</button>
        <button
          class="px-5 py-2 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          @click="cancelRuleForm"
        >{{ t('automations.cancel') }}</button>
      </div>
    </div>

    <!-- Rules list -->
    <div v-if="automationsLoading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="h-16 bg-gray-100 dark:bg-gray-700 rounded-2xl animate-pulse" />
    </div>

    <div
      v-else-if="!automationsLoading && automationRules.length === 0 && !showRuleForm"
      class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 py-16 flex flex-col items-center text-center"
    >
      <div class="w-14 h-14 rounded-2xl bg-gray-50 dark:bg-gray-700 flex items-center justify-center mb-4">
        <span class="text-2xl" aria-hidden="true">⚡</span>
      </div>
      <p class="text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">{{ t('automations.noRules') }}</p>
      <p class="text-xs text-gray-400 dark:text-gray-500 max-w-xs mb-5">
        {{ t('automations.noRulesHint') }}
      </p>
      <div class="flex gap-3">
        <button
          class="text-sm bg-red-600 text-white rounded-xl px-4 py-2 hover:bg-red-700 font-medium transition-colors"
          @click="openNewRuleForm"
        >{{ t('automations.newRuleBtn') }}</button>
        <button
          class="text-sm border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 rounded-xl px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          @click="showTemplates = true"
        >{{ t('automations.browseTemplates') }}</button>
      </div>
    </div>

    <div v-else-if="automationRules.length > 0" class="space-y-3">
      <div
        v-for="rule in automationRules"
        :key="rule.id"
        class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden"
      >
        <!-- Rule header row -->
        <div class="flex items-start gap-3 px-5 py-4">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-medium text-gray-800 dark:text-gray-100">{{ rule.name }}</span>
              <span
                :class="rule.is_active
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'"
                class="text-xs px-2 py-0.5 rounded-full font-medium"
              >{{ rule.is_active ? t('automations.active') : t('automations.disabled') }}</span>
            </div>
            <!-- Readable summary -->
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ ruleReadableSummary(rule) }}</p>
            <!-- Last run info -->
            <p v-if="lastRunLabel(rule)" class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ lastRunLabel(rule) }}</p>
            <!-- Action chips -->
            <div class="flex flex-wrap gap-1 mt-1.5">
              <span
                v-for="(action, i) in rule.actions"
                :key="i"
                class="text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-full px-2 py-0.5 border border-blue-100 dark:border-blue-800"
              >{{ actionSummary(action) }}</span>
            </div>
          </div>

          <!-- Actions toolbar -->
          <div class="flex items-center gap-2 flex-shrink-0">
            <button
              class="text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="toggleRuleRuns(rule)"
            >{{ expandedRuleRuns === rule.id ? t('automations.hideLog') : t('automations.log') }}</button>
            <button
              class="text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="openEditRuleForm(rule)"
            >{{ t('automations.edit') }}</button>
            <!-- On/off toggle -->
            <button
              :class="rule.is_active ? 'bg-green-500' : 'bg-gray-200 dark:bg-gray-600'"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0"
              role="switch"
              :aria-checked="rule.is_active"
              :aria-label="`Toggle ${rule.name}`"
              @click="toggleRule(rule)"
            >
              <span
                :class="rule.is_active ? 'translate-x-6' : 'translate-x-1'"
                class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
              />
            </button>
            <button
              class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-400 text-xs transition-colors"
              :aria-label="`Delete rule ${rule.name}`"
              @click="deleteRule(rule)"
            >🗑</button>
          </div>
        </div>

        <!-- Execution log (expanded) -->
        <div v-if="expandedRuleRuns === rule.id" class="border-t border-gray-100 dark:border-gray-700 px-5 py-4">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Execution log</p>
            <button
              class="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              @click="refreshRuleRuns(rule.id)"
            >↻ Refresh</button>
          </div>
          <div v-if="ruleRunsLoading && !ruleRunsMap[rule.id]" class="text-xs text-gray-400 py-2">Loading…</div>
          <div
            v-else-if="!ruleRunsMap[rule.id] || (ruleRunsMap[rule.id]?.length ?? 0) === 0"
            class="text-xs text-gray-400 dark:text-gray-500 py-2"
          >No runs recorded yet.</div>
          <ul v-else class="space-y-2">
            <li
              v-for="run in ruleRunsMap[rule.id]"
              :key="run.id"
              class="flex items-start gap-2 text-xs"
            >
              <span
                :class="{
                  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300': run.status === 'success',
                  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300': run.status === 'failure',
                  'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400': run.status === 'skipped',
                }"
                class="px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0 mt-0.5"
              >{{ run.status }}</span>
              <span class="text-gray-500 dark:text-gray-400 flex-shrink-0">
                {{ formatDate(run.triggered_at) }}
              </span>
              <span v-if="run.error_message" class="text-red-600 dark:text-red-400 truncate">
                {{ run.error_message }}
              </span>
              <span v-else-if="run.context?.task_title" class="text-gray-500 dark:text-gray-400 truncate">
                Task: {{ run.context.task_title as string }}
              </span>
              <span v-else-if="run.context?.lead_title" class="text-gray-500 dark:text-gray-400 truncate">
                Lead: {{ run.context.lead_title as string }}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>

  </div>
</template>

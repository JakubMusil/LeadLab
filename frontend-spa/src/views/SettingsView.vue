<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useToast } from '@/composables/useToast'
import { usePushNotifications } from '@/composables/usePushNotifications'
import { api } from '@/api'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { setLocale, useI18n } from '@/composables/useI18n'
import { useLeadScoringStore, SCORING_FIELDS } from '@/stores/leadScoring'
import { pluginRegistry } from '@/plugins'
import type { ConfigSchemaProperty } from '@/plugins'

const leadScoringStore = useLeadScoringStore()

const authStore = useAuthStore()
const firmStore = useFirmStore()
const toast = useToast()
const router = useRouter()
const { isPro } = storeToRefs(firmStore)
const { locale: currentLocale } = useI18n()
const { isSupported: pushSupported, isSubscribed: pushSubscribed, isLoading: pushLoading, subscribe: subscribePush, unsubscribe: unsubscribePush } = usePushNotifications()

// Branding
const brandColor = ref(firmStore.activeFirm?.primary_color || '#e63946')
const brandLogoPreview = ref<string | null>(null)
const brandLogoInput = ref<HTMLInputElement | null>(null)
const brandSaving = ref(false)
const brandError = ref('')
const brandSuccess = ref(false)

function onBrandLogoChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) {
    brandLogoPreview.value = URL.createObjectURL(file)
  }
}

async function saveBranding() {
  if (!firmStore.activeFirm) return
  brandSaving.value = true
  brandError.value = ''
  brandSuccess.value = false
  try {
    const formData = new FormData()
    formData.append('primary_color', brandColor.value)
    const file = brandLogoInput.value?.files?.[0]
    if (file) formData.append('logo', file)
    const res = await fetch(`/api/v1/firms/${firmStore.activeFirm.id}/branding/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrfToken() },
      body: formData,
    })
    if (res.ok) {
      const data = await res.json()
      firmStore.activeFirm.primary_color = data.primary_color
      if (data.logo_url) firmStore.activeFirm.logo_url = data.logo_url
      brandSuccess.value = true
    } else {
      brandError.value = 'Failed to save branding.'
    }
  } finally {
    brandSaving.value = false
  }
}

function getCsrfToken(): string {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m ? m[1] : ''
}

function changeLocale(code: string) {
  setLocale(code)
}

// Profile
const profileFirstName = ref('')
const profileLastName = ref('')
const profileTimezone = ref('')
const profileLoading = ref(false)
const profileError = ref('')
const profileSuccess = ref(false)

// Avatar
const avatarInput = ref<HTMLInputElement | null>(null)
const avatarPreview = ref<string | null>(null)
const avatarLoading = ref(false)

// Workspace rename
const workspaceName = ref('')
const workspaceLoading = ref(false)
const workspaceError = ref('')
const workspaceSuccess = ref(false)

// Danger zone
const confirmDeleteWorkspace = ref(false)
const dangerLoading = ref(false)
const confirmDeleteText = ref('')

// API Tokens
interface APIToken {
  id: string
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
  is_active: boolean
}
const tokens = ref<APIToken[]>([])
const tokensLoading = ref(false)
const newTokenName = ref('')
const newTokenCreating = ref(false)
const createdTokenValue = ref<string | null>(null)

// Webhooks
interface WebhookEndpoint {
  id: string
  url: string
  events: string[]
  is_active: boolean
  created_at: string
}
const webhooks = ref<WebhookEndpoint[]>([])
const webhooksLoading = ref(false)
const newWebhookUrl = ref('')
const newWebhookEvents = ref('')
const newWebhookCreating = ref(false)

// Weekly digest
const digestEnabled = ref(true)
const digestLoading = ref(false)

async function loadDigestPreference() {
  if (!firmStore.activeFirm) return
  const res = await api.get<{ weekly_digest_enabled: boolean }>('/api/v1/crm/digest-preference')
  if (res.ok && res.data) {
    digestEnabled.value = res.data.weekly_digest_enabled
  }
}

async function toggleDigest() {
  digestLoading.value = true
  const res = await api.patch<{ weekly_digest_enabled: boolean }>(
    '/api/v1/crm/digest-preference',
    { enabled: !digestEnabled.value },
  )
  digestLoading.value = false
  if (res.ok && res.data) {
    digestEnabled.value = res.data.weekly_digest_enabled
    toast.success(
      res.data.weekly_digest_enabled
        ? 'Weekly digest enabled.'
        : 'Weekly digest disabled.',
    )
  } else {
    toast.error('Failed to update digest preference.')
  }
}

// ---- Lead Scoring ----
const newRuleField = ref('status')
const newRuleOperand = ref('')
const newRuleScoreDelta = ref(10)
const ruleError = ref('')
const ruleLoading = ref(false)

async function addScoringRule() {
  if (!newRuleOperand.value.toString().trim()) {
    ruleError.value = 'Operand is required.'
    return
  }
  ruleError.value = ''
  ruleLoading.value = true
  let operand: unknown = newRuleOperand.value
  // coerce numeric operands
  if (newRuleField.value === 'value_gte' || newRuleField.value === 'last_activity_days_lte') {
    const n = parseFloat(String(operand))
    if (isNaN(n)) { ruleError.value = 'Operand must be a number for this field.'; ruleLoading.value = false; return }
    operand = n
  }
  const result = await leadScoringStore.createRule({
    field: newRuleField.value,
    operand,
    score_delta: newRuleScoreDelta.value,
  })
  ruleLoading.value = false
  if (result) {
    toast.success('Scoring rule added.')
    newRuleOperand.value = ''
    newRuleScoreDelta.value = 10
  } else {
    ruleError.value = 'Failed to add rule.'
  }
}

async function removeScoringRule(id: string) {
  await leadScoringStore.deleteRule(id)
  toast.success('Rule deleted.')
}

onMounted(() => {
  if (authStore.user) {
    profileFirstName.value = authStore.user.first_name
    profileLastName.value = authStore.user.last_name
    profileTimezone.value = authStore.user.timezone
  }
  if (firmStore.activeFirm) {
    workspaceName.value = firmStore.activeFirm.name
    loadTokens()
    loadWebhooks()
    loadDigestPreference()
    leadScoringStore.fetchRules()
    loadPropTemplates()
    loadPluginConfigs()
    loadAutomations()
    loadAutomationTemplates()
  }
})

// ---- API Tokens ----
async function loadTokens() {
  if (!firmStore.activeFirm) return
  tokensLoading.value = true
  const res = await api.get<APIToken[]>(`/api/v1/firms/${firmStore.activeFirm.id}/tokens`)
  tokensLoading.value = false
  if (res.ok && Array.isArray(res.data)) {
    tokens.value = res.data
  }
}

async function createToken() {
  if (!firmStore.activeFirm || !newTokenName.value.trim()) return
  newTokenCreating.value = true
  const res = await api.post<APIToken & { token: string }>(
    `/api/v1/firms/${firmStore.activeFirm.id}/tokens`,
    { name: newTokenName.value.trim() }
  )
  newTokenCreating.value = false
  if (res.ok && res.data) {
    createdTokenValue.value = res.data.token
    newTokenName.value = ''
    tokens.value.unshift(res.data)
    toast.success('API token created. Copy it now — it will not be shown again.')
  } else {
    toast.error('Failed to create token.')
  }
}

async function revokeToken(token: APIToken) {
  if (!firmStore.activeFirm) return
  if (!confirm(`Revoke token "${token.name}"? This cannot be undone.`)) return
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/tokens/${token.id}`)
  if (res.ok || res.status === 204) {
    tokens.value = tokens.value.map((t) =>
      t.id === token.id ? { ...t, is_active: false, revoked_at: new Date().toISOString() } : t
    )
    toast.success('Token revoked.')
  } else {
    toast.error('Failed to revoke token.')
  }
}

function copyToken() {
  if (!createdTokenValue.value) return
  navigator.clipboard.writeText(createdTokenValue.value).then(() => {
    toast.success('Token copied to clipboard.')
  })
}

// ---- Webhooks ----
async function loadWebhooks() {
  if (!firmStore.activeFirm) return
  webhooksLoading.value = true
  const res = await api.get<WebhookEndpoint[]>(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks`)
  webhooksLoading.value = false
  if (res.ok && Array.isArray(res.data)) {
    webhooks.value = res.data
  }
}

async function createWebhook() {
  if (!firmStore.activeFirm || !newWebhookUrl.value.trim()) return
  newWebhookCreating.value = true
  const events = newWebhookEvents.value
    .split(',')
    .map((e) => e.trim())
    .filter(Boolean)
  const res = await api.post<WebhookEndpoint>(
    `/api/v1/firms/${firmStore.activeFirm.id}/webhooks`,
    { url: newWebhookUrl.value.trim(), events }
  )
  newWebhookCreating.value = false
  if (res.ok && res.data) {
    webhooks.value.unshift(res.data)
    newWebhookUrl.value = ''
    newWebhookEvents.value = ''
    toast.success('Webhook endpoint created.')
  } else {
    toast.error('Failed to create webhook.')
  }
}

async function toggleWebhook(wh: WebhookEndpoint) {
  if (!firmStore.activeFirm) return
  const res = await api.patch<WebhookEndpoint>(
    `/api/v1/firms/${firmStore.activeFirm.id}/webhooks/${wh.id}`,
    { is_active: !wh.is_active }
  )
  if (res.ok && res.data) {
    const idx = webhooks.value.findIndex((w) => w.id === wh.id)
    if (idx !== -1) webhooks.value.splice(idx, 1, res.data)
    toast.success(res.data.is_active ? 'Webhook enabled.' : 'Webhook disabled.')
  } else {
    toast.error('Failed to update webhook.')
  }
}

async function deleteWebhook(wh: WebhookEndpoint) {
  if (!firmStore.activeFirm) return
  if (!confirm(`Delete webhook for "${wh.url}"?`)) return
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks/${wh.id}`)
  if (res.ok || res.status === 204) {
    webhooks.value = webhooks.value.filter((w) => w.id !== wh.id)
    toast.success('Webhook deleted.')
  } else {
    toast.error('Failed to delete webhook.')
  }
}

async function saveProfile() {
  profileLoading.value = true
  profileError.value = ''
  profileSuccess.value = false
  const res = await api.patch<typeof authStore.user>('/api/v1/users/me', {
    first_name: profileFirstName.value,
    last_name: profileLastName.value,
    timezone: profileTimezone.value,
  })
  profileLoading.value = false
  if (res.ok && res.data) {
    authStore.user = res.data as typeof authStore.user
    profileSuccess.value = true
    toast.success('Profile updated.')
    setTimeout(() => { profileSuccess.value = false }, 3000)
  } else {
    profileError.value = ((res.data as unknown) as Record<string, string> | null)?.detail ?? 'Failed to update profile.'
  }
}

function onAvatarChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => { avatarPreview.value = ev.target?.result as string }
  reader.readAsDataURL(file)
}

async function uploadAvatar() {
  const file = avatarInput.value?.files?.[0]
  if (!file) return
  avatarLoading.value = true
  const fd = new FormData()
  fd.append('avatar', file)
  const res = await api.postForm<typeof authStore.user>('/api/v1/users/me/avatar', fd)
  avatarLoading.value = false
  if (res.ok && res.data) {
    authStore.user = res.data as typeof authStore.user
    toast.success('Avatar updated.')
  } else {
    toast.error('Failed to upload avatar.')
  }
}

async function saveWorkspaceName() {
  if (!firmStore.activeFirm) return
  if (!workspaceName.value.trim()) { workspaceError.value = 'Name is required.'; return }
  workspaceLoading.value = true
  workspaceError.value = ''
  workspaceSuccess.value = false
  const res = await api.patch<{ id: string; name: string; slug: string; subscription_tier: string; subscription_active: boolean; is_active: boolean }>(
    `/api/v1/firms/${firmStore.activeFirm.id}`,
    { name: workspaceName.value.trim() }
  )
  workspaceLoading.value = false
  if (res.ok) {
    // Update firm in store
    const idx = firmStore.firms.findIndex((f) => f.id === firmStore.activeFirm!.id)
    if (idx !== -1) {
      const updated = { ...firmStore.firms[idx]!, name: res.data.name }
      firmStore.firms.splice(idx, 1, updated)
    }
    if (firmStore.activeFirm) {
      // Safe mutation via setActiveFirm — update in-place
      const af = firmStore.activeFirm
      Object.assign(af, { name: res.data.name })
    }
    workspaceSuccess.value = true
    toast.success('Workspace renamed.')
    setTimeout(() => { workspaceSuccess.value = false }, 3000)
  } else {
    workspaceError.value = ((res.data as unknown) as Record<string, string> | null)?.detail ?? 'Failed to rename workspace.'
  }
}

async function deleteWorkspace() {
  if (!firmStore.activeFirm) return
  if (confirmDeleteText.value !== firmStore.activeFirm.name) {
    toast.error('Workspace name does not match.')
    return
  }
  dangerLoading.value = true
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}`)
  dangerLoading.value = false
  if (res.ok || res.status === 204) {
    firmStore.firms = firmStore.firms.filter((f) => f.id !== firmStore.activeFirm!.id)
    firmStore.activeFirm = firmStore.firms[0] ?? null
    localStorage.removeItem('firmId')
    toast.success('Workspace deleted.')
    if (!firmStore.activeFirm) {
      await router.push('/app/onboarding')
    }
  } else {
    toast.error(((res.data as unknown) as Record<string, string> | null)?.detail ?? 'Failed to delete workspace.')
  }
}

// ---------------------------------------------------------------------------
// Proposal Templates
// ---------------------------------------------------------------------------

interface TemplItem {
  id?: string
  description: string
  quantity: number
  unit_price: number
  discount: number
  vat_rate: number
  position: number
}

interface ProposalTemplate {
  id: string
  name: string
  intro_text: string
  closing_text: string
  items: TemplItem[]
}

const propTemplates = ref<ProposalTemplate[]>([])
const propTemplatesLoading = ref(false)
const newTemplateName = ref('')
const newTemplateIntro = ref('')
const newTemplateClosing = ref('')
const newTemplateCreating = ref(false)
const expandedTemplate = ref<string | null>(null)
const newTmplItemDesc = ref('')
const newTmplItemQty = ref(1)
const newTmplItemPrice = ref(0)
const addingTmplItem = ref(false)

async function loadPropTemplates() {
  propTemplatesLoading.value = true
  const res = await api.get<ProposalTemplate[]>('/api/v1/crm/proposal-templates')
  propTemplatesLoading.value = false
  if (res.ok && Array.isArray(res.data)) propTemplates.value = res.data
}

async function createPropTemplate() {
  if (!newTemplateName.value.trim()) return
  newTemplateCreating.value = true
  const res = await api.post<ProposalTemplate>('/api/v1/crm/proposal-templates', {
    name: newTemplateName.value.trim(),
    intro_text: newTemplateIntro.value,
    closing_text: newTemplateClosing.value,
  })
  newTemplateCreating.value = false
  if (res.ok && res.data) {
    propTemplates.value.unshift(res.data)
    newTemplateName.value = ''
    newTemplateIntro.value = ''
    newTemplateClosing.value = ''
    toast.success('Template created.')
  } else {
    toast.error('Failed to create template.')
  }
}

async function deletePropTemplate(id: string) {
  if (!confirm('Delete this template?')) return
  const res = await api.delete(`/api/v1/crm/proposal-templates/${id}`)
  if (res.ok || res.status === 204) {
    propTemplates.value = propTemplates.value.filter((t) => t.id !== id)
    if (expandedTemplate.value === id) expandedTemplate.value = null
    toast.success('Template deleted.')
  } else {
    toast.error('Failed to delete template.')
  }
}

async function addTmplItem(template: ProposalTemplate) {
  if (!newTmplItemDesc.value.trim()) return
  addingTmplItem.value = true
  const res = await api.post<TemplItem>(`/api/v1/crm/proposal-templates/${template.id}/items`, {
    description: newTmplItemDesc.value.trim(),
    quantity: newTmplItemQty.value,
    unit_price: newTmplItemPrice.value,
    discount: 0,
    vat_rate: 0,
    position: template.items.length,
  })
  addingTmplItem.value = false
  if (res.ok) {
    template.items.push(res.data)
    newTmplItemDesc.value = ''
    newTmplItemQty.value = 1
    newTmplItemPrice.value = 0
  } else {
    toast.error('Failed to add item.')
  }
}

async function deleteTmplItem(template: ProposalTemplate, itemId: string) {
  const res = await api.delete(`/api/v1/crm/proposal-templates/${template.id}/items/${itemId}`)
  if (res.ok || res.status === 204) {
    template.items = template.items.filter((i) => i.id !== itemId)
  } else {
    toast.error('Failed to delete item.')
  }
}

// ---------------------------------------------------------------------------
// Plugins (v2.4)
// ---------------------------------------------------------------------------

interface PluginConfigEntry {
  plugin_name: string
  enabled: boolean
  config: Record<string, unknown>
  plugin: {
    name: string
    version: string
    description: string
    icon_url: string
    permissions: string[]
    config_schema: {
      type: string
      properties?: Record<string, ConfigSchemaProperty>
      required?: string[]
    }
  } | null
}

const pluginConfigs = ref<PluginConfigEntry[]>([])
const pluginsLoading = ref(false)
const expandedPlugin = ref<string | null>(null)
const pluginSaving = ref<Record<string, boolean>>({})
const pluginDraftConfigs = ref<Record<string, Record<string, unknown>>>({})

async function loadPluginConfigs() {
  if (!firmStore.activeFirm) return
  pluginsLoading.value = true
  const res = await api.get<PluginConfigEntry[]>(
    `/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/`,
  )
  pluginsLoading.value = false
  if (res.ok && Array.isArray(res.data)) {
    pluginConfigs.value = res.data
    // Seed draft configs with current values
    for (const pc of res.data) {
      pluginDraftConfigs.value[pc.plugin_name] = { ...pc.config }
    }
  }
}

async function togglePlugin(pc: PluginConfigEntry) {
  if (!firmStore.activeFirm) return
  const res = await api.patch<PluginConfigEntry>(
    `/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/${pc.plugin_name}/`,
    { enabled: !pc.enabled },
  )
  if (res.ok && res.data) {
    const idx = pluginConfigs.value.findIndex((p) => p.plugin_name === pc.plugin_name)
    if (idx !== -1) pluginConfigs.value.splice(idx, 1, res.data)
    toast.success(res.data.enabled ? `${pc.plugin_name} enabled.` : `${pc.plugin_name} disabled.`)
  } else {
    toast.error('Failed to update plugin.')
  }
}

async function savePluginConfig(pc: PluginConfigEntry) {
  if (!firmStore.activeFirm) return
  pluginSaving.value[pc.plugin_name] = true
  const config = pluginDraftConfigs.value[pc.plugin_name] ?? {}
  const res = await api.patch<PluginConfigEntry>(
    `/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/${pc.plugin_name}/`,
    { config },
  )
  pluginSaving.value[pc.plugin_name] = false
  if (res.ok && res.data) {
    const idx = pluginConfigs.value.findIndex((p) => p.plugin_name === pc.plugin_name)
    if (idx !== -1) pluginConfigs.value.splice(idx, 1, res.data)
    toast.success('Plugin settings saved.')
    expandedPlugin.value = null
  } else {
    toast.error('Failed to save plugin settings.')
  }
}

function getDraftValue(pluginName: string, key: string): unknown {
  return pluginDraftConfigs.value[pluginName]?.[key] ?? ''
}

function setDraftValue(pluginName: string, key: string, value: unknown) {
  if (!pluginDraftConfigs.value[pluginName]) {
    pluginDraftConfigs.value[pluginName] = {}
  }
  pluginDraftConfigs.value[pluginName][key] = value
}

// Expose installed plugin count from local registry for quick reference
const localPluginCount = computed(() => pluginRegistry.length)

// ---------------------------------------------------------------------------
// Automations (v2.5)
// ---------------------------------------------------------------------------

interface AutomationCondition {
  field: string
  operator: string
  value: string
}

interface AutomationAction {
  type: string
  [key: string]: string | number
}

interface AutomationRule {
  id: string
  name: string
  is_active: boolean
  trigger: string
  trigger_config: Record<string, unknown>
  conditions: AutomationCondition[]
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

const TRIGGER_LABELS: Record<string, string> = {
  lead_created: 'Lead Created',
  lead_status_change: 'Lead Status Changed',
  task_overdue: 'Task Overdue',
  proposal_sent: 'Proposal Sent',
  proposal_accepted: 'Proposal Accepted',
  lead_inactive: 'Lead Inactive (N days)',
  webhook_received: 'Custom Webhook Received',
}

const ACTION_TYPE_LABELS: Record<string, string> = {
  send_email: 'Send email',
  create_task: 'Create task',
  update_field: 'Update field',
  call_webhook: 'Call webhook',
  run_plugin_action: 'Run plugin action',
}

const OPERATOR_LABELS: Record<string, string> = {
  eq: '=',
  neq: '≠',
  gt: '>',
  gte: '≥',
  lt: '<',
  lte: '≤',
  contains: 'contains',
}

const automationRules = ref<AutomationRule[]>([])
const automationTemplates = ref<AutomationTemplate[]>([])
const automationsLoading = ref(false)
const showTemplates = ref(false)
const expandedRuleRuns = ref<string | null>(null)
const ruleRunsMap = ref<Record<string, AutomationRun[]>>({})
const ruleRunsLoading = ref(false)

// New / edit rule form
const showRuleForm = ref(false)
const editingRule = ref<AutomationRule | null>(null)
const ruleFormName = ref('')
const ruleFormTrigger = ref('lead_status_change')
const ruleFormTriggerConfig = ref<Record<string, unknown>>({})
const ruleFormConditions = ref<AutomationCondition[]>([])
const ruleFormActions = ref<AutomationAction[]>([])
const ruleSaving = ref(false)

function openNewRuleForm() {
  editingRule.value = null
  ruleFormName.value = ''
  ruleFormTrigger.value = 'lead_status_change'
  ruleFormTriggerConfig.value = {}
  ruleFormConditions.value = []
  ruleFormActions.value = []
  showRuleForm.value = true
  showTemplates.value = false
}

function openEditRuleForm(rule: AutomationRule) {
  editingRule.value = rule
  ruleFormName.value = rule.name
  ruleFormTrigger.value = rule.trigger
  ruleFormTriggerConfig.value = { ...rule.trigger_config }
  ruleFormConditions.value = rule.conditions.map((c) => ({ ...c }))
  ruleFormActions.value = rule.actions.map((a) => ({ ...a }))
  showRuleForm.value = true
  showTemplates.value = false
}

function cancelRuleForm() {
  showRuleForm.value = false
  editingRule.value = null
}

function addCondition() {
  ruleFormConditions.value.push({ field: 'to_status', operator: 'eq', value: '' })
}

function removeCondition(i: number) {
  ruleFormConditions.value.splice(i, 1)
}

function addAction() {
  ruleFormActions.value.push({ type: 'send_email', to: 'owner', subject: '', body: '' })
}

function removeAction(i: number) {
  ruleFormActions.value.splice(i, 1)
}

function onActionTypeChange(i: number, newType: string) {
  const defaults: Record<string, AutomationAction> = {
    send_email: { type: 'send_email', to: 'owner', subject: '', body: '' },
    create_task: { type: 'create_task', title: '', days_from_now: '3' },
    update_field: { type: 'update_field', field: 'status', value: '' },
    call_webhook: { type: 'call_webhook', url: '', method: 'POST' },
    run_plugin_action: { type: 'run_plugin_action', plugin_name: '', action: '' },
  }
  ruleFormActions.value[i] = defaults[newType] ?? { type: newType }
}

async function loadAutomations() {
  if (!firmStore.activeFirm) return
  automationsLoading.value = true
  const res = await api.get<AutomationRule[]>('/api/v1/crm/automations')
  automationsLoading.value = false
  if (res.ok && Array.isArray(res.data)) automationRules.value = res.data
}

async function loadAutomationTemplates() {
  const res = await api.get<AutomationTemplate[]>('/api/v1/crm/automations/templates')
  if (res.ok && Array.isArray(res.data)) automationTemplates.value = res.data
}

async function saveRule() {
  if (!ruleFormName.value.trim()) {
    toast.error('Rule name is required.')
    return
  }
  ruleSaving.value = true
  const body = {
    name: ruleFormName.value.trim(),
    trigger: ruleFormTrigger.value,
    trigger_config: ruleFormTriggerConfig.value,
    conditions: ruleFormConditions.value,
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
    toast.success(editingRule.value ? 'Rule updated.' : 'Automation rule created.')
    cancelRuleForm()
  } else {
    toast.error('Failed to save rule.')
  }
}

async function toggleRule(rule: AutomationRule) {
  const res = await api.patch<AutomationRule>(`/api/v1/crm/automations/${rule.id}`, {
    is_active: !rule.is_active,
  })
  if (res.ok && res.data) {
    const idx = automationRules.value.findIndex((r) => r.id === rule.id)
    if (idx !== -1) automationRules.value.splice(idx, 1, res.data)
    toast.success(res.data.is_active ? 'Rule enabled.' : 'Rule disabled.')
  } else {
    toast.error('Failed to update rule.')
  }
}

async function deleteRule(rule: AutomationRule) {
  if (!confirm(`Delete automation rule "${rule.name}"? This cannot be undone.`)) return
  const res = await api.delete(`/api/v1/crm/automations/${rule.id}`)
  if (res.ok || res.status === 204) {
    automationRules.value = automationRules.value.filter((r) => r.id !== rule.id)
    if (expandedRuleRuns.value === rule.id) expandedRuleRuns.value = null
    toast.success('Rule deleted.')
  } else {
    toast.error('Failed to delete rule.')
  }
}

async function toggleRuleRuns(rule: AutomationRule) {
  if (expandedRuleRuns.value === rule.id) {
    expandedRuleRuns.value = null
    return
  }
  expandedRuleRuns.value = rule.id
  if (!ruleRunsMap.value[rule.id]) {
    ruleRunsLoading.value = true
    const res = await api.get<AutomationRun[]>(`/api/v1/crm/automations/${rule.id}/runs?limit=10`)
    ruleRunsLoading.value = false
    if (res.ok && Array.isArray(res.data)) ruleRunsMap.value[rule.id] = res.data
  }
}

async function createFromTemplate(tmpl: AutomationTemplate) {
  const res = await api.post<AutomationRule>(
    `/api/v1/crm/automations/from-template/${tmpl.id}`,
  )
  if (res.ok && res.data) {
    automationRules.value.unshift(res.data)
    toast.success(`Rule "${res.data.name}" created from template.`)
    showTemplates.value = false
  } else {
    toast.error('Failed to create rule from template.')
  }
}

function ruleReadableSummary(rule: AutomationRule): string {
  const triggerLabel = TRIGGER_LABELS[rule.trigger] ?? rule.trigger
  const condCount = rule.conditions.length
  const actCount = rule.actions.length
  const condPart = condCount ? ` + ${condCount} condition${condCount > 1 ? 's' : ''}` : ''
  const actPart = `${actCount} action${actCount !== 1 ? 's' : ''}`
  return `${triggerLabel}${condPart} → ${actPart}`
}

function actionSummary(action: AutomationAction): string {
  const label = ACTION_TYPE_LABELS[action.type] ?? action.type
  if (action.type === 'send_email') return `${label} to ${action.to}`
  if (action.type === 'create_task') return `${label}: "${action.title}"`
  if (action.type === 'update_field') return `${label}: ${action.field} = ${action.value}`
  if (action.type === 'call_webhook') return `${label}: ${action.url}`
  if (action.type === 'run_plugin_action') return `${label}: ${action.plugin_name}.${action.action}`
  return label
}
</script>

<template>
  <div class="p-6 max-w-2xl mx-auto space-y-5">

    <!-- Profile -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">Profile</h2>

      <!-- Avatar -->
      <div class="flex items-center gap-4 mb-5">
        <div class="relative w-16 h-16 rounded-2xl bg-red-100 flex items-center justify-center overflow-hidden flex-shrink-0">
          <img v-if="avatarPreview" :src="avatarPreview" alt="Avatar preview" class="w-full h-full object-cover" />
          <span v-else class="text-red-600 text-2xl font-semibold">{{ authStore.user?.first_name?.[0]?.toUpperCase() ?? '?' }}</span>
        </div>
        <div>
          <label class="cursor-pointer text-sm text-red-600 hover:text-red-700 font-medium">
            Change avatar
            <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarChange" />
          </label>
          <button
            v-if="avatarPreview"
            :disabled="avatarLoading"
            class="ml-3 text-sm text-gray-600 border border-gray-200 rounded-lg px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
            @click="uploadAvatar"
          >{{ avatarLoading ? 'Uploading…' : 'Upload' }}</button>
          <p class="text-xs text-gray-400 mt-1">JPEG, PNG, GIF, WebP — max 20 MB</p>
        </div>
      </div>

      <div v-if="profileError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ profileError }}</div>
      <div v-if="profileSuccess" class="mb-3 rounded-xl bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">Profile updated successfully.</div>

      <form class="space-y-3" @submit.prevent="saveProfile">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">First Name</label>
            <input v-model="profileFirstName" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">Last Name</label>
            <input v-model="profileLastName" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Email</label>
          <input :value="authStore.user?.email" type="email" disabled class="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">Timezone</label>
          <input v-model="profileTimezone" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="Europe/Prague" />
        </div>
        <button type="submit" :disabled="profileLoading" class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60">
          {{ profileLoading ? 'Saving…' : 'Save Profile' }}
        </button>
      </form>
    </div>

    <!-- Workspace -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">Workspace</h2>
      <div class="text-xs text-gray-500 mb-1">Slug: <span class="font-mono">{{ firmStore.activeFirm?.slug }}</span></div>
      <div class="text-xs text-gray-500 mb-3">Subscription: <span class="capitalize">{{ firmStore.activeFirm?.subscription_tier }}</span></div>

      <div v-if="workspaceError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ workspaceError }}</div>
      <div v-if="workspaceSuccess" class="mb-3 rounded-xl bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">Workspace renamed.</div>

      <form class="flex gap-2" @submit.prevent="saveWorkspaceName">
        <input
          v-model="workspaceName"
          type="text"
          class="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          placeholder="Workspace name"
        />
        <button type="submit" :disabled="workspaceLoading" class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60">
          {{ workspaceLoading ? 'Saving…' : 'Rename' }}
        </button>
      </form>
    </div>

    <!-- Danger zone -->
    <div class="bg-white rounded-2xl border border-red-200 p-5">
      <h2 class="text-sm font-semibold text-red-600 mb-4">Danger Zone</h2>

      <button
        v-if="!confirmDeleteWorkspace"
        class="px-4 py-2 border border-red-300 text-red-600 rounded-xl text-sm hover:bg-red-50"
        @click="confirmDeleteWorkspace = true"
      >Delete Workspace…</button>

      <div v-else class="space-y-3">
        <p class="text-sm text-gray-700">
          This will permanently delete the <strong>{{ firmStore.activeFirm?.name }}</strong> workspace and all its data. Type the workspace name to confirm.
        </p>
        <input
          v-model="confirmDeleteText"
          type="text"
          :placeholder="firmStore.activeFirm?.name"
          class="w-full rounded-xl border border-red-300 px-3 py-2 text-sm focus:outline-none focus:border-red-500"
        />
        <div class="flex gap-2">
          <button class="flex-1 rounded-xl border border-gray-200 py-2 text-sm" @click="confirmDeleteWorkspace = false; confirmDeleteText = ''">Cancel</button>
          <button
            :disabled="dangerLoading || confirmDeleteText !== firmStore.activeFirm?.name"
            class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="deleteWorkspace"
          >{{ dangerLoading ? 'Deleting…' : 'Delete Workspace' }}</button>
        </div>
      </div>
    </div>

    <!-- API Tokens -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">API Tokens</h2>
      <p class="text-xs text-gray-500 mb-4">
        Generate bearer tokens to authenticate API requests without a browser session.
        Use <code class="font-mono bg-gray-100 px-1 rounded">Authorization: Bearer &lt;token&gt;</code> in your HTTP client.
      </p>

      <!-- Created token banner -->
      <div v-if="createdTokenValue" class="mb-4 rounded-xl bg-green-50 border border-green-200 p-4">
        <p class="text-xs font-semibold text-green-800 mb-2">Token created — copy it now. It will not be shown again.</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 text-xs font-mono bg-white border border-green-200 rounded-lg px-3 py-2 break-all select-all">{{ createdTokenValue }}</code>
          <button
            class="px-3 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 flex-shrink-0"
            @click="copyToken"
          >Copy</button>
        </div>
        <button class="mt-2 text-xs text-green-700 underline" @click="createdTokenValue = null">Dismiss</button>
      </div>

      <!-- Create form -->
      <form class="flex gap-2 mb-4" @submit.prevent="createToken">
        <input
          v-model="newTokenName"
          type="text"
          placeholder="Token name (e.g. CI/CD pipeline)"
          class="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <button
          type="submit"
          :disabled="newTokenCreating || !newTokenName.trim()"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
        >{{ newTokenCreating ? 'Creating…' : 'Create' }}</button>
      </form>

      <!-- Token list -->
      <div v-if="tokensLoading" class="text-sm text-gray-400">Loading…</div>
      <div v-else-if="tokens.length === 0" class="text-sm text-gray-400">No API tokens yet.</div>
      <ul v-else class="divide-y divide-gray-100">
        <li v-for="token in tokens" :key="token.id" class="flex items-center justify-between py-3 gap-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-800">{{ token.name }}</span>
              <span
                :class="token.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                class="text-xs px-2 py-0.5 rounded-full"
              >{{ token.is_active ? 'Active' : 'Revoked' }}</span>
            </div>
            <p class="text-xs text-gray-400 font-mono mt-0.5">{{ token.prefix }}…</p>
            <p class="text-xs text-gray-400 mt-0.5">
              Created {{ new Date(token.created_at).toLocaleDateString() }}
              <template v-if="token.last_used_at"> · Last used {{ new Date(token.last_used_at).toLocaleDateString() }}</template>
            </p>
          </div>
          <button
            v-if="token.is_active"
            class="flex-shrink-0 text-xs text-red-600 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-50"
            @click="revokeToken(token)"
          >Revoke</button>
        </li>
      </ul>
    </div>

    <!-- Outbound Webhooks -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">Outbound Webhooks</h2>
      <p class="text-xs text-gray-500 mb-4">
        Receive signed POST requests when CRM events occur.
        Leave the events field empty to subscribe to all events.
      </p>

      <!-- Create form -->
      <form class="space-y-2 mb-4" @submit.prevent="createWebhook">
        <input
          v-model="newWebhookUrl"
          type="url"
          placeholder="https://your-server.com/webhook"
          class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <input
          v-model="newWebhookEvents"
          type="text"
          placeholder="Events (comma-separated, e.g. lead.created,activity.created)"
          class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <button
          type="submit"
          :disabled="newWebhookCreating || !newWebhookUrl.trim()"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
        >{{ newWebhookCreating ? 'Adding…' : 'Add Endpoint' }}</button>
      </form>

      <!-- Webhook list -->
      <div v-if="webhooksLoading" class="text-sm text-gray-400">Loading…</div>
      <div v-else-if="webhooks.length === 0" class="text-sm text-gray-400">No webhook endpoints configured.</div>
      <ul v-else class="divide-y divide-gray-100">
        <li v-for="wh in webhooks" :key="wh.id" class="py-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm font-mono text-gray-800 break-all">{{ wh.url }}</p>
              <p class="text-xs text-gray-400 mt-0.5">
                Events: <span class="font-medium">{{ wh.events.length ? wh.events.join(', ') : 'all' }}</span>
              </p>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                :class="wh.is_active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                class="text-xs px-2 py-1 rounded-lg"
                @click="toggleWebhook(wh)"
              >{{ wh.is_active ? 'Active' : 'Disabled' }}</button>
              <button
                class="text-xs text-red-600 border border-red-200 rounded-lg px-2 py-1 hover:bg-red-50"
                @click="deleteWebhook(wh)"
              >Delete</button>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <!-- Notifications -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">Notifications</h2>
      <p class="text-xs text-gray-500 mb-4">Manage email and push notification preferences for this workspace.</p>
      <div class="flex items-center justify-between py-3 border-b border-gray-50">
        <div>
          <div class="text-sm font-medium text-gray-800">Weekly pipeline digest</div>
          <div class="text-xs text-gray-400 mt-0.5">A summary email with pipeline stats, sent every Monday.</div>
        </div>
        <button
          :disabled="digestLoading"
          :class="digestEnabled ? 'bg-green-600' : 'bg-gray-200'"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-60 flex-shrink-0"
          role="switch"
          :aria-checked="digestEnabled"
          aria-label="Toggle weekly digest"
          @click="toggleDigest"
        >
          <span
            :class="digestEnabled ? 'translate-x-6' : 'translate-x-1'"
            class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
          />
        </button>
      </div>

      <!-- Push notifications -->
      <div class="flex items-center justify-between py-3">
        <div>
          <div class="text-sm font-medium text-gray-800">Browser push notifications</div>
          <div class="text-xs text-gray-400 mt-0.5">
            Receive alerts when a task is due or a new lead is assigned to you.
          </div>
          <div v-if="!pushSupported" class="text-xs text-amber-600 mt-0.5">
            Not supported in this browser.
          </div>
        </div>
        <button
          v-if="pushSupported"
          :disabled="pushLoading"
          :class="pushSubscribed ? 'bg-green-600' : 'bg-gray-200'"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-60 flex-shrink-0"
          role="switch"
          :aria-checked="pushSubscribed"
          aria-label="Toggle push notifications"
          @click="pushSubscribed ? unsubscribePush() : subscribePush()"
        >
          <span
            :class="pushSubscribed ? 'translate-x-6' : 'translate-x-1'"
            class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
          />
        </button>
      </div>
    </div>

    <!-- Branding (Pro) -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4">
      <div>
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Branding</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Customise the logo and brand colour for your workspace. Available on Pro.</p>
      </div>

      <div v-if="!isPro" class="rounded-xl bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 px-4 py-3 text-sm text-purple-700 dark:text-purple-300">
        Upgrade to <strong>Pro</strong> to unlock white-label branding.
      </div>

      <template v-else>
        <!-- Logo upload -->
        <div class="space-y-2">
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300">Logo</label>
          <div class="flex items-center gap-4">
            <img
              v-if="brandLogoPreview || firmStore.activeFirm?.logo_url"
              :src="brandLogoPreview || firmStore.activeFirm?.logo_url"
              alt="Logo preview"
              class="h-12 w-auto rounded-lg border border-gray-200"
            />
            <div v-else class="h-12 w-24 rounded-lg bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 flex items-center justify-center text-xs text-gray-400">No logo</div>
            <input ref="brandLogoInput" type="file" accept="image/*" class="hidden" @change="onBrandLogoChange" />
            <button class="px-3 py-1.5 border border-gray-200 dark:border-gray-600 text-sm rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700" @click="brandLogoInput?.click()">Upload…</button>
          </div>
        </div>
        <!-- Colour picker -->
        <div class="space-y-2">
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300">Brand colour</label>
          <div class="flex items-center gap-3">
            <input v-model="brandColor" type="color" class="h-9 w-14 cursor-pointer rounded-lg border border-gray-200 p-1" />
            <span class="text-xs font-mono text-gray-600 dark:text-gray-400">{{ brandColor }}</span>
          </div>
        </div>
        <!-- Save button -->
        <button
          :disabled="brandSaving"
          class="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          @click="saveBranding"
        >{{ brandSaving ? 'Saving…' : 'Save branding' }}</button>
        <p v-if="brandError" class="text-xs text-red-600">{{ brandError }}</p>
        <p v-if="brandSuccess" class="text-xs text-green-600">Branding saved!</p>
      </template>
    </div>

    <!-- Language -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4">
      <div>
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Language</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Choose your preferred UI language.</p>
      </div>
      <div class="flex gap-3">
        <button
          v-for="lang in [{ code: 'en', label: '🇬🇧 English' }, { code: 'cs', label: '🇨🇿 Čeština' }]"
          :key="lang.code"
          :class="currentLocale === lang.code ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'"
          class="px-4 py-2 rounded-xl text-sm font-medium transition-colors"
          @click="changeLocale(lang.code)"
        >{{ lang.label }}</button>
      </div>
    </div>

    <!-- ===== LEAD SCORING ===== -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">Lead Scoring Rules</h2>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-5">
        Configure weighted rules that compute a 0–100 score for each lead. Scores appear as colour-coded badges in Leads and Kanban views.
      </p>

      <!-- Existing rules -->
      <div v-if="leadScoringStore.loading" class="animate-pulse space-y-2 mb-4">
        <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>
      <div v-else-if="leadScoringStore.rules.length === 0" class="text-sm text-gray-400 dark:text-gray-500 mb-4">No rules yet. Add your first rule below.</div>
      <ul v-else class="space-y-2 mb-5">
        <li
          v-for="rule in leadScoringStore.rules"
          :key="rule.id"
          class="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700"
        >
          <span class="flex-1 text-sm text-gray-700 dark:text-gray-300">
            <span class="font-medium">{{ SCORING_FIELDS.find((f) => f.value === rule.field)?.label ?? rule.field }}</span>
            <span class="text-gray-400 mx-1">=</span>
            <code class="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs">{{ rule.operand }}</code>
          </span>
          <span
            class="text-xs font-semibold px-2 py-0.5 rounded-full"
            :class="rule.score_delta >= 0 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'"
          >{{ rule.score_delta >= 0 ? '+' : '' }}{{ rule.score_delta }}</span>
          <button
            class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 text-xs"
            :aria-label="`Delete scoring rule for ${rule.field}`"
            @click="removeScoringRule(rule.id)"
          >🗑</button>
        </li>
      </ul>

      <!-- Add new rule -->
      <div class="border-t border-gray-100 dark:border-gray-700 pt-4">
        <h3 class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-3">Add rule</h3>
        <div v-if="ruleError" class="mb-2 text-xs text-red-600 dark:text-red-400" role="alert">{{ ruleError }}</div>
        <div class="flex flex-wrap gap-2 items-end">
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Field</label>
            <select v-model="newRuleField" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400">
              <option v-for="f in SCORING_FIELDS" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Value</label>
            <input
              v-model="newRuleOperand"
              type="text"
              placeholder="e.g. won, web, 5000…"
              class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 w-36 focus:outline-none focus:border-red-400"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Score delta</label>
            <input
              v-model.number="newRuleScoreDelta"
              type="number"
              class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 w-24 focus:outline-none focus:border-red-400"
              placeholder="+10"
            />
          </div>
          <button
            :disabled="ruleLoading"
            class="px-4 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            @click="addScoringRule"
          >
            {{ ruleLoading ? 'Adding…' : '+ Add rule' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Proposal Templates -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">Proposal Templates</h2>

      <!-- Existing templates -->
      <div v-if="propTemplatesLoading" class="animate-pulse space-y-2 mb-4">
        <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 rounded-xl" />
      </div>
      <div v-else-if="propTemplates.length === 0" class="text-sm text-gray-400 mb-4">
        No proposal templates yet.
      </div>
      <div v-else class="mb-4 space-y-2">
        <div v-for="tmpl in propTemplates" :key="tmpl.id" class="border border-gray-100 rounded-xl overflow-hidden">
          <div class="flex items-center gap-2 px-4 py-3">
            <button
              class="flex-1 text-left text-sm font-medium text-gray-800 hover:text-red-600 transition-colors"
              @click="expandedTemplate = expandedTemplate === tmpl.id ? null : tmpl.id"
            >
              {{ tmpl.name }}
              <span class="text-xs text-gray-400 ml-2">({{ tmpl.items.length }} items)</span>
              <span class="text-xs text-gray-400 ml-1">{{ expandedTemplate === tmpl.id ? '▲' : '▼' }}</span>
            </button>
            <button
              class="text-xs text-red-400 hover:text-red-600 px-2"
              @click="deletePropTemplate(tmpl.id)"
            >Delete</button>
          </div>

          <!-- Expanded template items -->
          <div v-if="expandedTemplate === tmpl.id" class="border-t border-gray-100 px-4 pb-3">
            <div v-if="tmpl.items.length === 0" class="text-xs text-gray-400 py-2">No items.</div>
            <table v-else class="w-full text-xs mb-2 mt-2">
              <thead>
                <tr class="border-b border-gray-100 text-gray-500">
                  <th class="text-left pb-1.5">Description</th>
                  <th class="text-right pb-1.5 w-12">Qty</th>
                  <th class="text-right pb-1.5 w-20">Price</th>
                  <th class="w-8"></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in tmpl.items" :key="item.id" class="border-b border-gray-50">
                  <td class="py-1.5 text-gray-700">{{ item.description }}</td>
                  <td class="py-1.5 text-right text-gray-500">{{ item.quantity }}</td>
                  <td class="py-1.5 text-right text-gray-500">{{ Number(item.unit_price).toFixed(2) }}</td>
                  <td class="py-1.5 text-right">
                    <button class="text-gray-300 hover:text-red-400 transition-colors" @click="deleteTmplItem(tmpl, item.id!)">✕</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <!-- Add item to template -->
            <div class="flex gap-2 mt-1">
              <input v-model="newTmplItemDesc" type="text" placeholder="Item description" class="flex-1 rounded-lg border border-gray-200 px-2 py-1 text-xs focus:outline-none focus:border-red-400" />
              <input v-model.number="newTmplItemQty" type="number" min="1" step="1" placeholder="Qty" class="w-14 rounded-lg border border-gray-200 px-2 py-1 text-xs text-right focus:outline-none focus:border-red-400" />
              <input v-model.number="newTmplItemPrice" type="number" min="0" step="0.01" placeholder="Price" class="w-20 rounded-lg border border-gray-200 px-2 py-1 text-xs text-right focus:outline-none focus:border-red-400" />
              <button
                :disabled="addingTmplItem || !newTmplItemDesc.trim()"
                class="px-3 py-1 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                @click="addTmplItem(tmpl)"
              >Add</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Create new template -->
      <div class="border border-dashed border-gray-200 rounded-xl p-4 space-y-2">
        <p class="text-xs font-medium text-gray-500">New Template</p>
        <input v-model="newTemplateName" type="text" placeholder="Template name *" class="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
        <textarea v-model="newTemplateIntro" rows="2" placeholder="Intro text (optional)…" class="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" />
        <textarea v-model="newTemplateClosing" rows="2" placeholder="Closing text (optional)…" class="w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" />
        <button
          :disabled="newTemplateCreating || !newTemplateName.trim()"
          class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          @click="createPropTemplate"
        >{{ newTemplateCreating ? 'Creating…' : '+ Create Template' }}</button>
      </div>
    </div>

    <!-- ===== PLUGINS (v2.4) ===== -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="flex items-center justify-between mb-1">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Plugins</h2>
        <span class="text-xs text-gray-400 dark:text-gray-500">{{ localPluginCount }} installed</span>
      </div>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
        Manage first-party and third-party plugins. Toggle plugins on/off or configure their settings.
        <a href="/docs/plugins/" target="_blank" class="text-red-600 hover:underline">Authoring guide →</a>
      </p>

      <!-- Loading state -->
      <div v-if="pluginsLoading" class="animate-pulse space-y-3">
        <div v-for="i in 3" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>

      <!-- Plugin list -->
      <div v-else-if="pluginConfigs.length === 0" class="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">
        No plugins installed.
        <a href="https://github.com/JakubMusil/LeadLab/tree/main/docs/plugin-registry.json" target="_blank" class="block mt-1 text-red-600 hover:underline text-xs">Browse the plugin registry →</a>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="pc in pluginConfigs"
          :key="pc.plugin_name"
          class="border border-gray-100 dark:border-gray-700 rounded-xl overflow-hidden"
        >
          <!-- Plugin header row -->
          <div class="flex items-center gap-3 px-4 py-3">
            <!-- Icon -->
            <div class="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 overflow-hidden">
              <img
                v-if="pc.plugin?.icon_url"
                :src="pc.plugin.icon_url"
                :alt="pc.plugin_name"
                class="w-full h-full object-cover"
                @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
              />
              <span v-else class="text-lg">🧩</span>
            </div>

            <!-- Name + version + description -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-medium text-gray-800 dark:text-gray-100">{{ pc.plugin_name }}</span>
                <span class="text-xs text-gray-400 dark:text-gray-500">v{{ pc.plugin?.version ?? '?' }}</span>
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ pc.plugin?.description ?? '' }}</p>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2 flex-shrink-0">
              <!-- Configure button (shown when plugin has config schema) -->
              <button
                v-if="pc.plugin && Object.keys(pc.plugin.config_schema?.properties ?? {}).length > 0"
                class="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1"
                @click="expandedPlugin = expandedPlugin === pc.plugin_name ? null : pc.plugin_name"
              >
                {{ expandedPlugin === pc.plugin_name ? 'Close' : 'Configure' }}
              </button>

              <!-- Enable / Disable toggle -->
              <button
                :class="pc.enabled ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-600'"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0"
                role="switch"
                :aria-checked="pc.enabled"
                :aria-label="`Toggle ${pc.plugin_name}`"
                @click="togglePlugin(pc)"
              >
                <span
                  :class="pc.enabled ? 'translate-x-6' : 'translate-x-1'"
                  class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
                />
              </button>
            </div>
          </div>

          <!-- Permissions chips -->
          <div
            v-if="pc.plugin?.permissions?.length"
            class="px-4 pb-2 flex flex-wrap gap-1"
          >
            <span
              v-for="perm in pc.plugin.permissions"
              :key="perm"
              class="text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-full px-2 py-0.5"
            >{{ perm }}</span>
          </div>

          <!-- Config form (expanded) -->
          <div
            v-if="expandedPlugin === pc.plugin_name && pc.plugin"
            class="border-t border-gray-100 dark:border-gray-700 px-4 pb-4 pt-3 space-y-3"
          >
            <template
              v-for="(prop, key) in (pc.plugin.config_schema?.properties ?? {})"
              :key="key"
            >
              <!-- Boolean field -->
              <div v-if="prop.type === 'boolean'" class="flex items-center justify-between">
                <div>
                  <label class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ prop.title ?? key }}</label>
                  <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500">{{ prop.description }}</p>
                </div>
                <input
                  type="checkbox"
                  :checked="Boolean(getDraftValue(pc.plugin_name, key) ?? prop.default ?? false)"
                  class="rounded"
                  @change="setDraftValue(pc.plugin_name, key, ($event.target as HTMLInputElement).checked)"
                />
              </div>

              <!-- Number field -->
              <div v-else-if="prop.type === 'number'">
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ prop.title ?? key }}</label>
                <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ prop.description }}</p>
                <input
                  type="number"
                  :value="getDraftValue(pc.plugin_name, key) ?? prop.default ?? ''"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  @input="setDraftValue(pc.plugin_name, key, Number(($event.target as HTMLInputElement).value))"
                />
              </div>

              <!-- Secret / password field -->
              <div v-else-if="prop.secret">
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ prop.title ?? key }}</label>
                <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ prop.description }}</p>
                <input
                  type="password"
                  autocomplete="new-password"
                  :value="getDraftValue(pc.plugin_name, key) ?? ''"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  placeholder="••••••••"
                  @input="setDraftValue(pc.plugin_name, key, ($event.target as HTMLInputElement).value)"
                />
              </div>

              <!-- String field (default) -->
              <div v-else>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ prop.title ?? key }}</label>
                <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ prop.description }}</p>
                <input
                  type="text"
                  :value="getDraftValue(pc.plugin_name, key) ?? prop.default ?? ''"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  @input="setDraftValue(pc.plugin_name, key, ($event.target as HTMLInputElement).value)"
                />
              </div>
            </template>

            <button
              :disabled="pluginSaving[pc.plugin_name]"
              class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="savePluginConfig(pc)"
            >{{ pluginSaving[pc.plugin_name] ? 'Saving…' : 'Save settings' }}</button>
          </div>
        </div>
      </div>

      <!-- Registry link -->
      <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
        <a
          href="https://github.com/JakubMusil/LeadLab/blob/main/public/plugin-registry.json"
          target="_blank"
          rel="noopener"
          class="text-xs text-red-600 hover:underline"
        >Browse the public plugin registry →</a>
      </div>
    </div>

    <!-- ===== AUTOMATIONS (v2.5) ===== -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="flex items-center justify-between mb-1">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Automations</h2>
        <div class="flex gap-2">
          <button
            class="text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700"
            @click="showTemplates = !showTemplates; showRuleForm = false"
          >{{ showTemplates ? 'Hide templates' : '📋 Templates' }}</button>
          <button
            class="text-xs bg-red-600 text-white rounded-lg px-3 py-1.5 hover:bg-red-700"
            @click="openNewRuleForm"
          >+ New rule</button>
        </div>
      </div>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
        Define trigger → condition → action rules that run automatically. No code required.
      </p>

      <!-- Built-in templates picker -->
      <div v-if="showTemplates" class="mb-4 border border-dashed border-gray-200 dark:border-gray-600 rounded-xl p-4 space-y-2">
        <p class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2">Ready-to-use templates</p>
        <div v-if="automationTemplates.length === 0" class="text-sm text-gray-400">Loading templates…</div>
        <div
          v-for="tmpl in automationTemplates"
          :key="tmpl.id"
          class="flex items-start gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-700"
        >
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-800 dark:text-gray-100">{{ tmpl.name }}</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ tmpl.description }}</p>
            <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5 font-mono">{{ TRIGGER_LABELS[tmpl.trigger] ?? tmpl.trigger }}</p>
          </div>
          <button
            class="flex-shrink-0 text-xs bg-red-600 text-white rounded-lg px-3 py-1.5 hover:bg-red-700"
            @click="createFromTemplate(tmpl)"
          >Use</button>
        </div>
      </div>

      <!-- Rule editor form (create / edit) -->
      <div v-if="showRuleForm" class="mb-4 border border-gray-200 dark:border-gray-600 rounded-xl p-4 space-y-4">
        <p class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide">
          {{ editingRule ? 'Edit rule' : 'New rule' }}
        </p>

        <!-- Name -->
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Rule name *</label>
          <input
            v-model="ruleFormName"
            type="text"
            placeholder="e.g. Notify owner when lead won"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>

        <!-- Trigger -->
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Trigger</label>
          <select
            v-model="ruleFormTrigger"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option v-for="(label, key) in TRIGGER_LABELS" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>

        <!-- Trigger config: inactive_days / warning_days -->
        <div v-if="ruleFormTrigger === 'lead_inactive'" class="flex items-center gap-3">
          <label class="text-xs font-medium text-gray-700 dark:text-gray-300 w-32">Inactive days</label>
          <input
            :value="(ruleFormTriggerConfig['inactive_days'] as string | number) ?? 30"
            type="number"
            min="1"
            class="w-24 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
            @input="ruleFormTriggerConfig['inactive_days'] = Number(($event.target as HTMLInputElement).value)"
          />
        </div>
        <div v-else-if="ruleFormTrigger === 'task_overdue'" class="flex items-center gap-3">
          <label class="text-xs font-medium text-gray-700 dark:text-gray-300 w-32">Warning days</label>
          <input
            :value="(ruleFormTriggerConfig['warning_days'] as string | number) ?? 1"
            type="number"
            min="0"
            class="w-24 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
            @input="ruleFormTriggerConfig['warning_days'] = Number(($event.target as HTMLInputElement).value)"
          />
        </div>

        <!-- Conditions -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-medium text-gray-700 dark:text-gray-300">Conditions (all must match)</label>
            <button
              class="text-xs text-red-600 hover:text-red-700"
              @click="addCondition"
            >+ Add condition</button>
          </div>
          <div v-if="ruleFormConditions.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic">
            No conditions — rule fires on every trigger event.
          </div>
          <div
            v-for="(cond, i) in ruleFormConditions"
            :key="i"
            class="flex gap-2 mb-2 items-center flex-wrap"
          >
            <input
              v-model="cond.field"
              type="text"
              placeholder="field (e.g. to_status)"
              class="flex-1 min-w-[120px] rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
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
            <button class="text-gray-300 hover:text-red-400 text-sm" @click="removeCondition(i)">✕</button>
          </div>
        </div>

        <!-- Actions -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-xs font-medium text-gray-700 dark:text-gray-300">Actions (run in order)</label>
            <button
              class="text-xs text-red-600 hover:text-red-700"
              @click="addAction"
            >+ Add action</button>
          </div>
          <div v-if="ruleFormActions.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic">
            No actions — add at least one action.
          </div>
          <div
            v-for="(action, i) in ruleFormActions"
            :key="i"
            class="mb-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-700 space-y-2"
          >
            <div class="flex items-center gap-2">
              <select
                :value="action.type"
                class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                @change="onActionTypeChange(i, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="(label, key) in ACTION_TYPE_LABELS" :key="key" :value="key">{{ label }}</option>
              </select>
              <button class="text-gray-300 hover:text-red-400 text-sm" @click="removeAction(i)">✕</button>
            </div>

            <!-- send_email fields -->
            <template v-if="action.type === 'send_email'">
              <div class="flex gap-2">
                <label class="text-xs text-gray-500 dark:text-gray-400 w-10 pt-1.5">To</label>
                <select
                  v-model="action.to"
                  class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                >
                  <option value="owner">Owner</option>
                  <option value="assignee">Assignee</option>
                  <option value="customer">Customer</option>
                </select>
              </div>
              <input
                v-model="action.subject"
                type="text"
                placeholder="Subject"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              />
              <textarea
                v-model="action.body"
                rows="3"
                placeholder="Email body. Use {{lead_title}}, {{customer_name}}, {{assignee_name}}…"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400 resize-none"
              />
            </template>

            <!-- create_task fields -->
            <template v-else-if="action.type === 'create_task'">
              <input
                v-model="action.title"
                type="text"
                placeholder="Task title (supports {{lead_title}})"
                class="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
              />
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500 dark:text-gray-400">Due in</label>
                <input
                  v-model.number="action.days_from_now"
                  type="number"
                  min="0"
                  class="w-20 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                />
                <span class="text-xs text-gray-500 dark:text-gray-400">days</span>
              </div>
            </template>

            <!-- update_field fields -->
            <template v-else-if="action.type === 'update_field'">
              <div class="flex gap-2">
                <select
                  v-model="action.field"
                  class="flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400"
                >
                  <option value="status">Status</option>
                  <option value="source">Source</option>
                  <option value="currency">Currency</option>
                  <option value="description">Description</option>
                </select>
                <input
                  v-model="action.value"
                  type="text"
                  placeholder="New value"
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
        <div class="flex gap-2 pt-1">
          <button
            :disabled="ruleSaving || !ruleFormName.trim()"
            class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="saveRule"
          >{{ ruleSaving ? 'Saving…' : (editingRule ? 'Update rule' : 'Create rule') }}</button>
          <button
            class="px-4 py-2 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
            @click="cancelRuleForm"
          >Cancel</button>
        </div>
      </div>

      <!-- Rules list -->
      <div v-if="automationsLoading" class="animate-pulse space-y-3">
        <div v-for="i in 2" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>
      <div v-else-if="!automationsLoading && automationRules.length === 0 && !showRuleForm" class="text-sm text-gray-400 dark:text-gray-500 py-4 text-center">
        No automation rules yet. Create your first rule or pick a template above.
      </div>

      <div v-else-if="automationRules.length > 0" class="space-y-2">
        <div
          v-for="rule in automationRules"
          :key="rule.id"
          class="border border-gray-100 dark:border-gray-700 rounded-xl overflow-hidden"
        >
          <!-- Rule header row -->
          <div class="flex items-start gap-3 px-4 py-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-medium text-gray-800 dark:text-gray-100">{{ rule.name }}</span>
                <span
                  :class="rule.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'"
                  class="text-xs px-2 py-0.5 rounded-full"
                >{{ rule.is_active ? 'Active' : 'Disabled' }}</span>
              </div>
              <!-- Readable summary sentence -->
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ ruleReadableSummary(rule) }}</p>
              <!-- Actions summary chips -->
              <div class="flex flex-wrap gap-1 mt-1">
                <span
                  v-for="(action, i) in rule.actions"
                  :key="i"
                  class="text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-full px-2 py-0.5"
                >{{ actionSummary(action) }}</span>
              </div>
            </div>

            <!-- Actions toolbar -->
            <div class="flex items-center gap-1.5 flex-shrink-0">
              <button
                class="text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-700"
                @click="toggleRuleRuns(rule)"
              >{{ expandedRuleRuns === rule.id ? 'Hide log' : 'Log' }}</button>
              <button
                class="text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-700"
                @click="openEditRuleForm(rule)"
              >Edit</button>
              <!-- On/off toggle -->
              <button
                :class="rule.is_active ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-600'"
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
                class="p-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-400 text-xs"
                :aria-label="`Delete rule ${rule.name}`"
                @click="deleteRule(rule)"
              >🗑</button>
            </div>
          </div>

          <!-- Execution log (expanded) -->
          <div v-if="expandedRuleRuns === rule.id" class="border-t border-gray-100 dark:border-gray-700 px-4 py-3">
            <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Last runs</p>
            <div v-if="ruleRunsLoading && !ruleRunsMap[rule.id]" class="text-xs text-gray-400">Loading…</div>
            <div v-else-if="!ruleRunsMap[rule.id] || ruleRunsMap[rule.id].length === 0" class="text-xs text-gray-400 dark:text-gray-500">No runs yet.</div>
            <ul v-else class="space-y-1.5">
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
                  class="px-1.5 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0"
                >{{ run.status }}</span>
                <span class="text-gray-500 dark:text-gray-400 flex-shrink-0">
                  {{ new Date(run.triggered_at).toLocaleString() }}
                </span>
                <span v-if="run.error_message" class="text-red-600 dark:text-red-400 truncate">{{ run.error_message }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

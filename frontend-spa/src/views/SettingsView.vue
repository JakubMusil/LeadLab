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
import { CheckIcon, TrashIcon, StarIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'
import { useMoney, SUPPORTED_CURRENCIES, CURRENCY_DEFAULT_LOCALE } from '@/composables/useMoney'
import CurrencySelect from '@/components/CurrencySelect.vue'

const leadScoringStore = useLeadScoringStore()

const authStore = useAuthStore()
const firmStore = useFirmStore()
const toast = useToast()
const router = useRouter()
const { isPro } = storeToRefs(firmStore)
const { locale: currentLocale, t } = useI18n()
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
  return m?.[1] ?? ''
}

function changeLocale(code: string) {
  setLocale(code)
}

// Profile
const profileFirstName = ref('')
const profileLastName = ref('')
const profileTimezone = ref('')
const profileNumberLocale = ref('')
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

// Settings tab: 'user' | 'workspace'
const activeTab = ref<'user' | 'workspace'>('user')

// Danger zone
const confirmDeleteWorkspace = ref(false)
const dangerLoading = ref(false)
const confirmDeleteText = ref('')

// Currency & formatting settings
const { firmCurrency, formatAmount } = useMoney()
const currencyDefaultCurrency = ref(firmStore.activeFirm?.default_currency ?? 'CZK')
const currencyNumberLocale = ref(firmStore.activeFirm?.number_locale ?? 'cs-CZ')
const currencyExchangeRateMode = ref(firmStore.activeFirm?.exchange_rate_mode ?? 'auto')
const currencyLoading = ref(false)
const currencyError = ref('')
const currencySuccess = ref(false)

const NUMBER_LOCALES = [
  { value: 'cs-CZ', label: 'cs-CZ – 12 500,50 Kč' },
  { value: 'sk-SK', label: 'sk-SK – 12 500,50 €' },
  { value: 'de-DE', label: 'de-DE – 12.500,50 €' },
  { value: 'en-US', label: 'en-US – $12,500.50' },
  { value: 'en-GB', label: 'en-GB – £12,500.50' },
  { value: 'pl-PL', label: 'pl-PL – 12 500,50 zł' },
  { value: 'fr-FR', label: 'fr-FR – 12 500,50 €' },
  { value: 'hu-HU', label: 'hu-HU – 12 500,50 Ft' },
  { value: 'nb-NO', label: 'nb-NO – kr 12 500,50' },
  { value: 'sv-SE', label: 'sv-SE – 12 500,50 kr' },
]

const currencyPreview = computed(() => {
  try {
    return new Intl.NumberFormat(currencyNumberLocale.value, {
      style: 'currency',
      currency: currencyDefaultCurrency.value,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(12500.5)
  } catch {
    return '—'
  }
})

function onDefaultCurrencyChange(code: string) {
  currencyDefaultCurrency.value = code
  // Auto-set locale to the currency's default, but only if not manually overridden
  const defaultLocale = CURRENCY_DEFAULT_LOCALE[code]
  if (defaultLocale) {
    currencyNumberLocale.value = defaultLocale
  }
}

async function saveCurrencySettings() {
  if (!firmStore.activeFirm) return
  currencyLoading.value = true
  currencyError.value = ''
  currencySuccess.value = false
  try {
    const res = await api.patch<{ default_currency: string; number_locale: string; exchange_rate_mode: string }>(
      `/api/v1/firms/${firmStore.activeFirm.id}/currency`,
      {
        default_currency: currencyDefaultCurrency.value,
        number_locale: currencyNumberLocale.value,
        exchange_rate_mode: currencyExchangeRateMode.value,
      }
    )
    if (res.ok && res.data && firmStore.activeFirm) {
      firmStore.activeFirm.default_currency = res.data.default_currency
      firmStore.activeFirm.number_locale = res.data.number_locale
      firmStore.activeFirm.exchange_rate_mode = res.data.exchange_rate_mode
      currencySuccess.value = true
      setTimeout(() => { currencySuccess.value = false }, 3000)
    } else {
      currencyError.value = ((res.data as unknown) as { detail?: string })?.detail ?? 'Failed to save currency settings.'
    }
  } finally {
    currencyLoading.value = false
  }
}

// Exchange Rate Management
interface ExchangeRateOut {
  id: string
  from_currency: string
  to_currency: string
  rate: string
  source: string
  valid_from: string
  valid_to: string | null
  note: string
  created_by_email: string | null
  created_at: string
}

const exchangeRates = ref<ExchangeRateOut[]>([])
const exchangeRatesHistory = ref<ExchangeRateOut[]>([])
const exchangeRatesLoading = ref(false)
const exchangeRatesHistoryLoading = ref(false)
const showExchangeRateHistory = ref(false)

// New rate form
const newRateFromCurrency = ref('')
const newRateValue = ref('')
const newRateValidFrom = ref(new Date().toISOString().slice(0, 10))
const newRateNote = ref('')
const newRateLoading = ref(false)
const newRateError = ref('')
const newRateSuccess = ref(false)

// Edit note
const editingNoteId = ref<string | null>(null)
const editingNoteValue = ref('')

async function loadExchangeRates() {
  if (!firmStore.activeFirm) return
  exchangeRatesLoading.value = true
  try {
    const res = await api.get<ExchangeRateOut[]>(
      `/api/v1/firms/${firmStore.activeFirm.id}/exchange-rates/`
    )
    if (res.ok && res.data) exchangeRates.value = res.data
  } finally {
    exchangeRatesLoading.value = false
  }
}

async function loadExchangeRatesHistory() {
  if (!firmStore.activeFirm) return
  exchangeRatesHistoryLoading.value = true
  try {
    const res = await api.get<ExchangeRateOut[]>(
      `/api/v1/firms/${firmStore.activeFirm.id}/exchange-rates/?include_history=true`
    )
    if (res.ok && res.data) exchangeRatesHistory.value = res.data
  } finally {
    exchangeRatesHistoryLoading.value = false
  }
}

async function saveNewRate() {
  if (!firmStore.activeFirm) return
  newRateError.value = ''
  newRateSuccess.value = false
  if (!newRateFromCurrency.value || !newRateValue.value) {
    newRateError.value = t('exchangeRates.errorRequired')
    return
  }
  newRateLoading.value = true
  try {
    const res = await api.post<ExchangeRateOut>(
      `/api/v1/firms/${firmStore.activeFirm.id}/exchange-rates/`,
      {
        from_currency: newRateFromCurrency.value,
        rate: newRateValue.value,
        valid_from: newRateValidFrom.value,
        note: newRateNote.value,
      }
    )
    if (res.ok && res.data) {
      exchangeRates.value.unshift(res.data)
      newRateFromCurrency.value = ''
      newRateValue.value = ''
      newRateNote.value = ''
      newRateValidFrom.value = new Date().toISOString().slice(0, 10)
      newRateSuccess.value = true
      setTimeout(() => { newRateSuccess.value = false }, 3000)
    } else {
      newRateError.value = ((res.data as unknown) as { detail?: string })?.detail ?? t('exchangeRates.errorSave')
    }
  } finally {
    newRateLoading.value = false
  }
}

async function deleteExchangeRate(rateId: string) {
  if (!firmStore.activeFirm) return
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/exchange-rates/${rateId}/`)
  if (res.ok) {
    exchangeRates.value = exchangeRates.value.filter(r => r.id !== rateId)
  }
}

async function saveEditNote(rateId: string) {
  if (!firmStore.activeFirm) return
  const res = await api.patch<ExchangeRateOut>(
    `/api/v1/firms/${firmStore.activeFirm.id}/exchange-rates/${rateId}/`,
    { note: editingNoteValue.value }
  )
  if (res.ok && res.data) {
    const idx = exchangeRates.value.findIndex(r => r.id === rateId)
    if (idx >= 0) exchangeRates.value[idx] = res.data
    editingNoteId.value = null
  }
}

function toggleExchangeRateHistory() {
  showExchangeRateHistory.value = !showExchangeRateHistory.value
  if (showExchangeRateHistory.value) loadExchangeRatesHistory()
}

// Billing
const billingLoading = ref(false)
const billingError = ref('')

async function startCheckout() {
  if (!firmStore.activeFirm) return
  billingLoading.value = true
  billingError.value = ''
  const res = await api.post<{ checkout_url: string }>(
    `/api/v1/firms/${firmStore.activeFirm.id}/billing/checkout`,
    {}
  )
  billingLoading.value = false
  if (res.ok && res.data?.checkout_url) {
    window.location.href = res.data.checkout_url
  } else {
    billingError.value =
      ((res.data as unknown) as Record<string, string> | null)?.detail ??
      t('settings.failedToStartCheckout')
  }
}

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
interface WebhookDelivery {
  id: string
  event: string
  status_code: number | null
  success: boolean
  error: string
  delivered_at: string
  duration_ms: number
}
const webhooks = ref<WebhookEndpoint[]>([])
const webhooksLoading = ref(false)
const newWebhookUrl = ref('')
const newWebhookEvents = ref('')
const newWebhookCreating = ref(false)
const webhookDeliveries = ref<Record<string, WebhookDelivery[]>>({})
const webhookDeliveriesLoading = ref<Record<string, boolean>>({})
const webhookDeliveriesOpen = ref<Record<string, boolean>>({})
const pendingRevokeToken = ref<APIToken | null>(null)
const pendingDeleteWebhook = ref<WebhookEndpoint | null>(null)

async function toggleWebhookDeliveries(wh: WebhookEndpoint) {
  const id = wh.id
  if (webhookDeliveriesOpen.value[id]) {
    webhookDeliveriesOpen.value[id] = false
    return
  }
  webhookDeliveriesOpen.value[id] = true
  if (webhookDeliveries.value[id]) return
  if (!firmStore.activeFirm) return
  webhookDeliveriesLoading.value[id] = true
  const res = await api.get<WebhookDelivery[]>(
    `/api/v1/firms/${firmStore.activeFirm.id}/webhooks/${id}/deliveries`
  )
  webhookDeliveriesLoading.value[id] = false
  if (res.ok && Array.isArray(res.data)) {
    webhookDeliveries.value[id] = res.data
  } else {
    webhookDeliveries.value[id] = []
  }
}

// iCal feed
const icalUrl = ref('')
const icalLoading = ref(false)
const icalCopied = ref(false)

async function loadIcalUrl() {
  if (!firmStore.activeFirm) return
  icalLoading.value = true
  const res = await api.get<{ token: string; url: string }>('/api/v1/integrations/ical/token')
  icalLoading.value = false
  if (res.ok && res.data?.url) {
    icalUrl.value = `${window.location.origin}${res.data.url}`
  } else {
    toast.error(t('settings.failedToGenerateCalendar'))
  }
}

function copyIcalUrl() {
  if (!icalUrl.value) return
  navigator.clipboard.writeText(icalUrl.value).then(() => {
    icalCopied.value = true
    setTimeout(() => { icalCopied.value = false }, 2000)
  })
}

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
        ? t('settings.weeklyDigestEnabled')
        : t('settings.weeklyDigestDisabled'),
    )
  } else {
    toast.error(t('settings.failedToUpdateDigest'))
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
    ruleError.value = t('settings.operandRequired')
    return
  }
  ruleError.value = ''
  ruleLoading.value = true
  let operand: unknown = newRuleOperand.value
  // coerce numeric operands
  if (newRuleField.value === 'value_gte' || newRuleField.value === 'last_activity_days_lte') {
    const n = parseFloat(String(operand))
    if (isNaN(n)) { ruleError.value = t('settings.operandMustBeNumber'); ruleLoading.value = false; return }
    operand = n
  }
  const result = await leadScoringStore.createRule({
    field: newRuleField.value,
    operand,
    score_delta: newRuleScoreDelta.value,
  })
  ruleLoading.value = false
  if (result) {
    toast.success(t('settings.scoringRuleAdded'))
    newRuleOperand.value = ''
    newRuleScoreDelta.value = 10
  } else {
    ruleError.value = t('settings.failedToAddRule')
  }
}

async function removeScoringRule(id: string) {
  await leadScoringStore.deleteRule(id)
  toast.success(t('settings.ruleDeleted'))
}

onMounted(() => {
  if (authStore.user) {
    profileFirstName.value = authStore.user.first_name
    profileLastName.value = authStore.user.last_name
    profileTimezone.value = authStore.user.timezone
    profileNumberLocale.value = authStore.user.number_locale || ''
  }
  // Always re-fetch the firm so subscription_tier/active reflects the latest server state
  firmStore.fetchFirms().then(() => {
    if (firmStore.activeFirm) {
      workspaceName.value = firmStore.activeFirm.name
      loadTokens()
      loadWebhooks()
      loadDigestPreference()
      leadScoringStore.fetchRules()
      loadCustomFields()
      if (firmStore.isPro) loadExchangeRates()
    }
  })
  // Seed the workspace name from the cached store value immediately so the input is not blank
  if (firmStore.activeFirm) {
    workspaceName.value = firmStore.activeFirm.name
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
    toast.success(t('settings.tokenCreated'))
  } else {
    toast.error(t('settings.failedToCreateToken'))
  }
}

async function revokeToken(token: APIToken) {
  if (!firmStore.activeFirm) return
  pendingRevokeToken.value = token
}

async function executeRevokeToken() {
  const token = pendingRevokeToken.value
  pendingRevokeToken.value = null
  if (!token || !firmStore.activeFirm) return
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/tokens/${token.id}`)
  if (res.ok || res.status === 204) {
    tokens.value = tokens.value.map((t) =>
      t.id === token.id ? { ...t, is_active: false, revoked_at: new Date().toISOString() } : t
    )
    toast.success(t('settings.tokenRevoked'))
  } else {
    toast.error(t('settings.failedToRevokeToken'))
  }
}

function copyToken() {
  if (!createdTokenValue.value) return
  navigator.clipboard.writeText(createdTokenValue.value).then(() => {
    toast.success(t('settings.tokenCopied'))
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
    toast.success(t('settings.webhookCreated'))
  } else {
    toast.error(t('settings.failedToCreateWebhook'))
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
    toast.success(res.data.is_active ? t('settings.webhookEnabled') : t('settings.webhookDisabled'))
  } else {
    toast.error(t('settings.failedToUpdateWebhook'))
  }
}

async function deleteWebhook(wh: WebhookEndpoint) {
  if (!firmStore.activeFirm) return
  pendingDeleteWebhook.value = wh
}

async function executeDeleteWebhook() {
  const wh = pendingDeleteWebhook.value
  pendingDeleteWebhook.value = null
  if (!wh || !firmStore.activeFirm) return
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks/${wh.id}`)
  if (res.ok || res.status === 204) {
    webhooks.value = webhooks.value.filter((w) => w.id !== wh.id)
    toast.success(t('settings.webhookDeleted'))
  } else {
    toast.error(t('settings.failedToDeleteWebhook'))
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
    number_locale: profileNumberLocale.value,
  })
  profileLoading.value = false
  if (res.ok && res.data) {
    authStore.user = res.data as typeof authStore.user
    profileSuccess.value = true
    toast.success(t('settings.profileUpdated'))
    setTimeout(() => { profileSuccess.value = false }, 3000)
  } else {
    profileError.value = ((res.data as unknown) as Record<string, string> | null)?.detail ?? t('settings.failedToUpdateProfile')
  }
}

function exportExchangeRatesCsv(includeHistory = true) {
  if (!firmStore.activeFirm) return
  const url = `/api/v1/firms/${firmStore.activeFirm.id}/exchange-rates/export.csv?include_history=${includeHistory}`
  const a = document.createElement('a')
  a.href = url
  a.download = `exchange_rates_${firmStore.activeFirm.slug}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
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
    toast.success(t('settings.avatarUpdated'))
  } else {
    toast.error(t('settings.failedToUploadAvatar'))
  }
}

async function saveWorkspaceName() {
  if (!firmStore.activeFirm) return
  if (!workspaceName.value.trim()) { workspaceError.value = t('settings.workspaceNameRequired'); return }
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
    toast.success(t('settings.workspaceRenamed'))
    setTimeout(() => { workspaceSuccess.value = false }, 3000)
  } else {
    workspaceError.value = ((res.data as unknown) as Record<string, string> | null)?.detail ?? t('settings.failedToRenameWorkspace')
  }
}

async function deleteWorkspace() {
  if (!firmStore.activeFirm) return
  if (confirmDeleteText.value !== firmStore.activeFirm.name) {
    toast.error(t('settings.workspaceNameMismatch'))
    return
  }
  dangerLoading.value = true
  const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}`)
  dangerLoading.value = false
  if (res.ok || res.status === 204) {
    firmStore.firms = firmStore.firms.filter((f) => f.id !== firmStore.activeFirm!.id)
    firmStore.activeFirm = firmStore.firms[0] ?? null
    localStorage.removeItem('firmId')
    toast.success(t('settings.workspaceDeleted'))
    if (!firmStore.activeFirm) {
      await router.push('/app/onboarding')
    }
  } else {
    toast.error(((res.data as unknown) as Record<string, string> | null)?.detail ?? t('settings.failedToDeleteWorkspace'))
  }
}

// ---------------------------------------------------------------------------
// Phase 8: Custom Fields management
// ---------------------------------------------------------------------------
import { useTasksStore, type TaskCustomFieldOut } from '@/stores/tasks'

const tasksStore = useTasksStore()
const customFieldsList = ref<TaskCustomFieldOut[]>([])
const customFieldsLoading = ref(false)

const showNewCFModal = ref(false)
const newCFName = ref('')
const newCFType = ref('text')
const newCFOptions = ref('')
const newCFRequired = ref(false)
const newCFSaving = ref(false)
const newCFError = ref('')

const editingCF = ref<TaskCustomFieldOut | null>(null)
const confirmDeleteCFId = ref<string | null>(null)
const confirmDeleteCFName = ref<string | null>(null)
const editCFName = ref('')
const editCFType = ref('text')
const editCFOptions = ref('')
const editCFRequired = ref(false)
const editCFSaving = ref(false)

async function loadCustomFields() {
  customFieldsLoading.value = true
  const result = await tasksStore.fetchCustomFields()
  if (result.ok) customFieldsList.value = result.data ?? []
  customFieldsLoading.value = false
}

async function saveNewCF() {
  if (!newCFName.value.trim()) { newCFError.value = t('tasks.cfSettings_nameRequired'); return }
  newCFSaving.value = true
  newCFError.value = ''
  const options = newCFType.value === 'dropdown'
    ? newCFOptions.value.split('\n').map((s) => s.trim()).filter(Boolean)
    : []
  const result = await tasksStore.createCustomField({
    name: newCFName.value.trim(),
    field_type: newCFType.value,
    options,
    is_required: newCFRequired.value,
    position: customFieldsList.value.length,
  })
  newCFSaving.value = false
  if (result.ok) {
    showNewCFModal.value = false
    newCFName.value = ''
    newCFType.value = 'text'
    newCFOptions.value = ''
    newCFRequired.value = false
    await loadCustomFields()
  } else {
    newCFError.value = result.error ?? t('tasks.cfSettings_createFailed')
  }
}

function openEditCF(cf: TaskCustomFieldOut) {
  editingCF.value = cf
  editCFName.value = cf.name
  editCFType.value = cf.field_type
  editCFOptions.value = (cf.options ?? []).join('\n')
  editCFRequired.value = cf.is_required
}

async function saveEditCF() {
  if (!editingCF.value) return
  editCFSaving.value = true
  const options = editCFType.value === 'dropdown'
    ? editCFOptions.value.split('\n').map((s) => s.trim()).filter(Boolean)
    : []
  const result = await tasksStore.updateCustomField(editingCF.value.id, {
    name: editCFName.value.trim(),
    field_type: editCFType.value,
    options,
    is_required: editCFRequired.value,
  })
  editCFSaving.value = false
  if (result.ok) {
    editingCF.value = null
    await loadCustomFields()
  }
}

async function doDeleteCF(id: string) {
  await tasksStore.deleteCustomField(id)
  await loadCustomFields()
}

function deleteCF(cf: TaskCustomFieldOut) {
  confirmDeleteCFId.value = cf.id
  confirmDeleteCFName.value = cf.name
}

const cfFieldTypes = computed(() => [
  { value: 'text', label: t('tasks.cfTypeText') },
  { value: 'number', label: t('tasks.cfTypeNumber') },
  { value: 'date', label: t('tasks.cfTypeDate') },
  { value: 'dropdown', label: t('tasks.cfTypeDropdown') },
  { value: 'checkbox', label: t('tasks.cfTypeCheckbox') },
  { value: 'url', label: t('tasks.cfTypeUrl') },
])

const CF_TYPE_LABELS = computed<Record<string, string>>(() => ({
  text: t('tasks.cfTypeText'),
  number: t('tasks.cfTypeNumber'),
  date: t('tasks.cfTypeDate'),
  dropdown: t('tasks.cfTypeDropdown'),
  checkbox: t('tasks.cfTypeCheckbox'),
  url: t('tasks.cfTypeUrl'),
}))

// ---------------------------------------------------------------------------
// (Fakturoid credentials are managed via the generic Plugins settings panel)
// ---------------------------------------------------------------------------
</script>

<template>
  <div class="p-6 space-y-5">

    <!-- Tab switcher -->
    <div class="flex gap-1 bg-gray-100 rounded-2xl p-1 w-fit">
      <button
        :class="activeTab === 'user' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-xl text-sm font-medium transition-all"
        @click="activeTab = 'user'"
      >{{ t('settings.tabUser') }}</button>
      <button
        :class="activeTab === 'workspace' ? 'bg-white shadow text-gray-900' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-xl text-sm font-medium transition-all"
        @click="activeTab = 'workspace'"
      >{{ t('settings.tabWorkspace') }}</button>
    </div>

    <!-- ==================== USER TAB ==================== -->
    <div v-show="activeTab === 'user'">

    <!-- Profile -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">{{ t('settings.profileSection') }}</h2>

      <!-- Avatar -->
      <div class="flex items-center gap-4 mb-5">
        <div class="relative w-16 h-16 rounded-2xl bg-red-100 flex items-center justify-center overflow-hidden flex-shrink-0">
          <img v-if="avatarPreview" :src="avatarPreview" alt="Avatar preview" class="w-full h-full object-cover" />
          <span v-else class="text-red-600 text-2xl font-semibold">{{ authStore.user?.first_name?.[0]?.toUpperCase() ?? '?' }}</span>
        </div>
        <div>
          <label class="cursor-pointer text-sm text-red-600 hover:text-red-700 font-medium">
            {{ t('settings.changeAvatar') }}
            <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarChange" />
          </label>
          <button
            v-if="avatarPreview"
            :disabled="avatarLoading"
            class="ml-3 text-sm text-gray-600 border border-gray-200 rounded-lg px-3 py-1 hover:bg-gray-50 disabled:opacity-50"
            @click="uploadAvatar"
          >{{ avatarLoading ? t('settings.uploading') : t('settings.upload') }}</button>
          <p class="text-xs text-gray-400 mt-1">{{ t('settings.avatarFormat') }}</p>
        </div>
      </div>

      <div v-if="profileError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ profileError }}</div>
      <div v-if="profileSuccess" class="mb-3 rounded-xl bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">{{ t('settings.profileUpdatedSuccess') }}</div>

      <form class="space-y-3" @submit.prevent="saveProfile">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('settings.firstName') }}</label>
            <input v-model="profileFirstName" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('settings.lastName') }}</label>
            <input v-model="profileLastName" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('settings.email') }}</label>
          <input :value="authStore.user?.email" type="email" disabled class="w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('settings.timezone') }}</label>
          <input v-model="profileTimezone" type="text" class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" placeholder="Europe/Prague" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">{{ t('profile.numberLocale') }}</label>
          <select
            v-model="profileNumberLocale"
            class="w-full rounded-xl border border-gray-300 bg-white text-gray-900 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option value="">{{ t('profile.numberLocaleDefault') }}</option>
            <option v-for="loc in NUMBER_LOCALES" :key="loc.value" :value="loc.value">{{ loc.label }}</option>
          </select>
          <p class="text-xs text-gray-400 mt-1">{{ t('profile.numberLocaleHelp') }}</p>
        </div>
        <button type="submit" :disabled="profileLoading" class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60">
          {{ profileLoading ? t('settings.saving') : t('settings.saveProfile') }}
        </button>
      </form>
    </div>

    <!-- Language -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4">
      <div>
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('settings.languageSection') }}</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ t('settings.languageDesc') }}</p>
      </div>
      <div class="flex gap-3">
        <button
          v-for="lang in [{ code: 'en', label: '🇬🇧 English' }, { code: 'cs', label: '🇨🇿 Čeština' }, { code: 'de', label: '🇩🇪 Deutsch' }, { code: 'pl', label: '🇵🇱 Polski' }]"
          :key="lang.code"
          :class="currentLocale === lang.code ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'"
          class="px-4 py-2 rounded-xl text-sm font-medium transition-colors"
          @click="changeLocale(lang.code)"
        >{{ lang.label }}</button>
      </div>
    </div>

    <!-- Notifications -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">{{ t('settings.notificationsSection') }}</h2>
      <p class="text-xs text-gray-500 mb-4">{{ t('settings.notificationsDesc') }}</p>
      <div class="flex items-center justify-between py-3 border-b border-gray-50">
        <div>
          <div class="text-sm font-medium text-gray-800">{{ t('settings.weeklyDigestTitle') }}</div>
          <div class="text-xs text-gray-400 mt-0.5">{{ t('settings.weeklyDigestSubtitle') }}</div>
        </div>
        <button
          :disabled="digestLoading"
          :class="digestEnabled ? 'bg-green-600' : 'bg-gray-200'"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-60 flex-shrink-0"
          role="switch"
          :aria-checked="digestEnabled"
          :aria-label="t('settings.weeklyDigestTitle')"
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
          <div class="text-sm font-medium text-gray-800">{{ t('settings.browserPushTitle') }}</div>
          <div class="text-xs text-gray-400 mt-0.5">
            {{ t('settings.browserPushSubtitle') }}
          </div>
          <div v-if="!pushSupported" class="text-xs text-amber-600 mt-0.5">
            {{ t('settings.browserPushNotSupported') }}
          </div>
        </div>
        <button
          v-if="pushSupported"
          :disabled="pushLoading"
          :class="pushSubscribed ? 'bg-green-600' : 'bg-gray-200'"
          class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-60 flex-shrink-0"
          role="switch"
          :aria-checked="pushSubscribed"
          :aria-label="t('settings.browserPushTitle')"
          @click="pushSubscribed ? unsubscribePush() : subscribePush()"
        >
          <span
            :class="pushSubscribed ? 'translate-x-6' : 'translate-x-1'"
            class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
          />
        </button>
      </div>
    </div>

    <!-- Calendar Feed (iCal) -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">{{ t('settings.calendarFeedSection') }}</h2>
      <p class="text-xs text-gray-500 mb-4">{{ t('settings.calendarFeedDesc') }}</p>
      <div v-if="!icalUrl">
        <button
          :disabled="icalLoading"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
          @click="loadIcalUrl"
        >{{ icalLoading ? t('settings.generating') : t('settings.generateFeedUrl') }}</button>
      </div>
      <div v-else class="space-y-2">
        <div class="flex items-center gap-2">
          <input
            :value="icalUrl"
            readonly
            class="flex-1 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-xs font-mono text-gray-600 select-all cursor-text focus:outline-none"
            @click="($event.target as HTMLInputElement).select()"
          />
          <button
            class="px-3 py-2 text-sm font-medium rounded-xl border flex-shrink-0 transition-colors"
            :class="icalCopied ? 'bg-green-600 text-white border-green-600' : 'border-gray-200 text-gray-700 hover:bg-gray-50'"
            @click="copyIcalUrl"
          >{{ icalCopied ? t('settings.copied') : t('settings.copyBtn') }}</button>
        </div>
        <p class="text-xs text-gray-400">{{ t('settings.calendarFeedReadOnly') }}</p>
      </div>
    </div>

    </div>
    <!-- ==================== WORKSPACE TAB ==================== -->
    <div v-show="activeTab === 'workspace'">

    <!-- Workspace -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">{{ t('settings.workspaceSection') }}</h2>
      <div class="text-xs text-gray-500 mb-1">{{ t('settings.slugLabel') }} <span class="font-mono">{{ firmStore.activeFirm?.slug }}</span></div>
      <div class="text-xs text-gray-500 mb-3">{{ t('settings.subscriptionLabel') }} <span class="capitalize">{{ firmStore.activeFirm?.subscription_tier }}</span></div>

      <div v-if="workspaceError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ workspaceError }}</div>
      <div v-if="workspaceSuccess" class="mb-3 rounded-xl bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700">{{ t('settings.workspaceRenamedMsg') }}</div>

      <form class="flex gap-2" @submit.prevent="saveWorkspaceName">
        <input
          v-model="workspaceName"
          type="text"
          class="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          :placeholder="t('settings.workspaceNamePlaceholder')"
        />
        <button type="submit" :disabled="workspaceLoading" class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60">
          {{ workspaceLoading ? t('settings.saving') : t('settings.renameBtn') }}
        </button>
      </form>
    </div>

    <!-- Currency & Formatting -->
    <div v-if="isPro" class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">{{ t('currencySettings.title') }}</h2>
      <div class="space-y-4 max-w-md">
        <!-- Default currency -->
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('currencySettings.defaultCurrency') }}</label>
          <CurrencySelect :model-value="currencyDefaultCurrency" @update:model-value="onDefaultCurrencyChange" />
        </div>

        <!-- Number locale -->
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-1">{{ t('currencySettings.numberLocale') }}</label>
          <select
            v-model="currencyNumberLocale"
            class="w-full rounded-xl border border-gray-300 bg-white text-gray-900 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          >
            <option v-for="loc in NUMBER_LOCALES" :key="loc.value" :value="loc.value">{{ loc.label }}</option>
          </select>
        </div>

        <!-- Preview -->
        <p class="text-xs text-gray-500">
          {{ t('currencySettings.preview', { example: currencyPreview }) }}
        </p>

        <!-- Exchange rate mode -->
        <div>
          <label class="block text-xs font-medium text-gray-600 mb-2">{{ t('currencySettings.exchangeRateMode') }}</label>
          <div class="flex flex-col gap-2">
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input type="radio" v-model="currencyExchangeRateMode" value="auto" class="accent-red-600" />
              {{ t('currencySettings.modeAuto') }}
            </label>
            <label class="flex items-center gap-2 text-sm cursor-pointer">
              <input type="radio" v-model="currencyExchangeRateMode" value="manual" class="accent-red-600" />
              {{ t('currencySettings.modeManual') }}
            </label>
          </div>
        </div>

        <!-- Warning note -->
        <p class="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2">
          {{ t('currencySettings.warningChangeNote') }}
        </p>

        <!-- Error / success feedback -->
        <p v-if="currencyError" class="text-xs text-red-600">{{ currencyError }}</p>
        <p v-if="currencySuccess" class="text-xs text-green-600">{{ t('currencySettings.saved') }}</p>

        <button
          :disabled="currencyLoading"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
          @click="saveCurrencySettings"
        >
          {{ currencyLoading ? t('currencySettings.saving') : t('currencySettings.save') }}
        </button>
      </div>
    </div>

    <!-- Exchange Rate Management (Pro only) -->
    <div v-if="isPro" class="bg-white rounded-2xl border border-gray-100 p-5">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-sm font-semibold text-gray-900">{{ t('exchangeRates.title') }}</h2>
        <button
          class="text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg px-3 py-1 hover:bg-gray-50"
          @click="exportExchangeRatesCsv(true)"
        >
          {{ t('exchangeRates.exportCsv') }}
        </button>
      </div>

      <!-- Active rates table -->
      <div class="overflow-x-auto mb-4">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-xs text-gray-500 border-b border-gray-100">
              <th class="text-left py-2 pr-4">{{ t('exchangeRates.fromCurrency') }}</th>
              <th class="text-left py-2 pr-4">{{ t('exchangeRates.toCurrency') }}</th>
              <th class="text-right py-2 pr-4">{{ t('exchangeRates.rate') }}</th>
              <th class="text-left py-2 pr-4">{{ t('exchangeRates.validFrom') }}</th>
              <th class="text-left py-2 pr-4">{{ t('exchangeRates.source') }}</th>
              <th class="text-left py-2 pr-4">{{ t('exchangeRates.note') }}</th>
              <th class="text-right py-2"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="exchangeRatesLoading">
              <td colspan="7" class="py-4 text-center text-gray-400 text-xs">{{ t('exchangeRates.loading') }}</td>
            </tr>
            <tr v-else-if="exchangeRates.length === 0">
              <td colspan="7" class="py-4 text-center text-gray-400 text-xs">{{ t('exchangeRates.noRates') }}</td>
            </tr>
            <tr v-for="rate in exchangeRates" :key="rate.id" class="border-b border-gray-50 last:border-0">
              <td class="py-2 pr-4 font-mono font-medium text-gray-900">{{ rate.from_currency }}</td>
              <td class="py-2 pr-4 font-mono text-gray-500">{{ rate.to_currency }}</td>
              <td class="py-2 pr-4 text-right font-mono">{{ Number(rate.rate).toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 6 }) }}</td>
              <td class="py-2 pr-4 text-gray-500">{{ rate.valid_from }}</td>
              <td class="py-2 pr-4">
                <span
                  class="inline-block px-1.5 py-0.5 rounded text-xs"
                  :class="rate.source === 'manual' ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'"
                >{{ rate.source }}</span>
              </td>
              <td class="py-2 pr-4 text-gray-500 max-w-xs truncate">
                <span v-if="editingNoteId !== rate.id">{{ rate.note || '—' }}</span>
                <input
                  v-else
                  v-model="editingNoteValue"
                  class="w-full rounded border border-gray-300 px-2 py-0.5 text-xs"
                  @keyup.enter="saveEditNote(rate.id)"
                  @keyup.escape="editingNoteId = null"
                />
              </td>
              <td class="py-2 text-right whitespace-nowrap">
                <template v-if="rate.source === 'manual'">
                  <button
                    v-if="editingNoteId !== rate.id"
                    class="text-xs text-gray-400 hover:text-gray-700 mr-2"
                    @click="editingNoteId = rate.id; editingNoteValue = rate.note"
                  >{{ t('exchangeRates.editNote') }}</button>
                  <button
                    v-else
                    class="text-xs text-blue-600 hover:text-blue-800 mr-2"
                    @click="saveEditNote(rate.id)"
                  >{{ t('exchangeRates.save') }}</button>
                  <button
                    class="text-xs text-red-500 hover:text-red-700"
                    @click="deleteExchangeRate(rate.id)"
                  >{{ t('exchangeRates.delete') }}</button>
                </template>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- History toggle -->
      <button
        class="text-xs text-gray-500 hover:text-gray-700 mb-4 underline"
        @click="toggleExchangeRateHistory"
      >
        {{ showExchangeRateHistory ? t('exchangeRates.hideHistory') : t('exchangeRates.showHistory') }}
      </button>

      <div v-if="showExchangeRateHistory" class="overflow-x-auto mb-4">
        <table class="w-full text-xs text-gray-500">
          <thead>
            <tr class="border-b border-gray-100">
              <th class="text-left py-1.5 pr-3">{{ t('exchangeRates.fromCurrency') }}</th>
              <th class="text-right py-1.5 pr-3">{{ t('exchangeRates.rate') }}</th>
              <th class="text-left py-1.5 pr-3">{{ t('exchangeRates.validFrom') }}</th>
              <th class="text-left py-1.5 pr-3">{{ t('exchangeRates.validTo') }}</th>
              <th class="text-left py-1.5 pr-3">{{ t('exchangeRates.source') }}</th>
              <th class="text-left py-1.5">{{ t('exchangeRates.createdBy') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="exchangeRatesHistoryLoading">
              <td colspan="6" class="py-3 text-center">{{ t('exchangeRates.loading') }}</td>
            </tr>
            <tr v-for="rate in exchangeRatesHistory" :key="rate.id" class="border-b border-gray-50 last:border-0">
              <td class="py-1.5 pr-3 font-mono">{{ rate.from_currency }}</td>
              <td class="py-1.5 pr-3 text-right font-mono">{{ Number(rate.rate).toFixed(4) }}</td>
              <td class="py-1.5 pr-3">{{ rate.valid_from }}</td>
              <td class="py-1.5 pr-3">{{ rate.valid_to || '—' }}</td>
              <td class="py-1.5 pr-3">{{ rate.source }}</td>
              <td class="py-1.5">{{ rate.created_by_email || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Add new rate form -->
      <div class="border-t border-gray-100 pt-4">
        <h3 class="text-xs font-semibold text-gray-700 mb-3">{{ t('exchangeRates.addRate') }}</h3>
        <div class="flex flex-wrap gap-3 items-end">
          <div>
            <label class="block text-xs text-gray-500 mb-1">{{ t('exchangeRates.fromCurrency') }}</label>
            <CurrencySelect v-model="newRateFromCurrency" class="w-36" />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">{{ t('exchangeRates.toCurrency') }}</label>
            <input
              :value="firmStore.activeFirm?.default_currency"
              disabled
              class="w-20 rounded-xl border border-gray-200 bg-gray-50 text-gray-500 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">{{ t('exchangeRates.rate') }}</label>
            <input
              v-model="newRateValue"
              type="number"
              step="0.0001"
              min="0.0001"
              placeholder="1.0000"
              class="w-32 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">{{ t('exchangeRates.validFrom') }}</label>
            <input
              v-model="newRateValidFrom"
              type="date"
              class="rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>
          <div class="flex-1 min-w-40">
            <label class="block text-xs text-gray-500 mb-1">{{ t('exchangeRates.note') }}</label>
            <input
              v-model="newRateNote"
              type="text"
              :placeholder="t('exchangeRates.notePlaceholder')"
              maxlength="255"
              class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>
          <button
            :disabled="newRateLoading || !newRateFromCurrency || !newRateValue"
            class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
            @click="saveNewRate"
          >
            {{ newRateLoading ? t('exchangeRates.saving') : t('exchangeRates.saveRate') }}
          </button>
        </div>
        <p v-if="newRateError" class="text-xs text-red-600 mt-2">{{ newRateError }}</p>
        <p v-if="newRateSuccess" class="text-xs text-green-600 mt-2">{{ t('exchangeRates.rateSaved') }}</p>
      </div>
    </div>

    <!-- Danger zone -->
    <div class="bg-white rounded-2xl border border-red-200 p-5">
      <h2 class="text-sm font-semibold text-red-600 mb-4">{{ t('settings.dangerZoneSection') }}</h2>

      <button
        v-if="!confirmDeleteWorkspace"
        class="px-4 py-2 border border-red-300 text-red-600 rounded-xl text-sm hover:bg-red-50"
        @click="confirmDeleteWorkspace = true"
      >{{ t('settings.deleteWorkspaceBtn') }}</button>

      <div v-else class="space-y-3">
        <p class="text-sm text-gray-700">
          {{ t('settings.deleteWorkspaceConfirm').replace('{name}', firmStore.activeFirm?.name ?? '') }}
        </p>
        <input
          v-model="confirmDeleteText"
          type="text"
          :placeholder="firmStore.activeFirm?.name"
          class="w-full rounded-xl border border-red-300 px-3 py-2 text-sm focus:outline-none focus:border-red-500"
        />
        <div class="flex gap-2">
          <button class="flex-1 rounded-xl border border-gray-200 py-2 text-sm" @click="confirmDeleteWorkspace = false; confirmDeleteText = ''">{{ t('common.cancel') }}</button>
          <button
            :disabled="dangerLoading || confirmDeleteText !== firmStore.activeFirm?.name"
            class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            @click="deleteWorkspace"
          >{{ dangerLoading ? t('settings.deleting') : t('settings.deleteWorkspace') }}</button>
        </div>
      </div>
    </div>

    <!-- Billing -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-4">{{ t('settings.billingSection') }}</h2>

      <!-- Current plan badge -->
      <div class="flex items-center gap-3 mb-4">
        <div
          :class="isPro ? 'bg-amber-50 border-amber-200 text-amber-700' : 'bg-gray-50 border-gray-200 text-gray-600'"
          class="inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold"
        >
          <span v-if="isPro" class="flex items-center gap-1"><StarIcon class="w-4 h-4 text-yellow-400" /> {{ t('settings.proLabelBadge') }}</span>
          <span v-else>{{ t('settings.freeLabelBadge') }}</span>
        </div>
        <span v-if="isPro && firmStore.activeFirm?.subscription_active" class="text-xs text-green-600 font-medium">{{ t('settings.activeLabel') }}</span>
        <span v-else-if="isPro && !firmStore.activeFirm?.subscription_active" class="text-xs text-red-500 font-medium">{{ t('settings.inactiveLabel') }}</span>
      </div>

      <!-- Pro features list for free tier -->
      <ul v-if="!isPro" class="space-y-1 mb-5 text-xs text-gray-500">
        <li class="flex items-center gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> {{ t('settings.proFeatureBranding') }}</li>
        <li class="flex items-center gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> {{ t('settings.proFeatureWhiteLabel') }}</li>
        <li class="flex items-center gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> {{ t('settings.proFeatureProposals') }}</li>
        <li class="flex items-center gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> {{ t('settings.proFeatureAutomations') }}</li>
        <li class="flex items-center gap-2"><CheckIcon class="w-4 h-4 text-green-500 flex-shrink-0" /> {{ t('settings.proFeatureSupport') }}</li>
      </ul>

      <!-- Already Pro message -->
      <p v-if="isPro" class="text-sm text-gray-600 mb-4">{{ t('settings.proProText') }}</p>

      <!-- Error -->
      <div v-if="billingError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ billingError }}</div>

      <!-- Upgrade button (only for free tier) -->
      <button
        v-if="!isPro"
        :disabled="billingLoading"
        class="px-5 py-2.5 bg-amber-500 text-white rounded-xl text-sm font-semibold hover:bg-amber-600 disabled:opacity-60 transition-colors"
        @click="startCheckout"
      >
        {{ billingLoading ? t('settings.redirecting') : t('settings.upgradeToPro') }}
      </button>
    </div>

    <!-- API Tokens -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">{{ t('settings.apiTokensSection') }}</h2>
      <p class="text-xs text-gray-500 mb-4">{{ t('settings.apiTokensDesc') }}</p>

      <!-- Created token banner -->
      <div v-if="createdTokenValue" class="mb-4 rounded-xl bg-green-50 border border-green-200 p-4">
        <p class="text-xs font-semibold text-green-800 mb-2">{{ t('settings.tokenCreatedBanner') }}</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 text-xs font-mono bg-white border border-green-200 rounded-lg px-3 py-2 break-all select-all">{{ createdTokenValue }}</code>
          <button
            class="px-3 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 flex-shrink-0"
            @click="copyToken"
          >{{ t('settings.copyBtn') }}</button>
        </div>
        <button class="mt-2 text-xs text-green-700 underline" @click="createdTokenValue = null">{{ t('common.dismiss') }}</button>
      </div>

      <!-- Create form -->
      <form class="flex gap-2 mb-4" @submit.prevent="createToken">
        <input
          v-model="newTokenName"
          type="text"
          :placeholder="t('settings.tokenNamePlaceholder')"
          class="flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <button
          type="submit"
          :disabled="newTokenCreating || !newTokenName.trim()"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
        >{{ newTokenCreating ? t('settings.tokenCreating') : t('settings.createBtn') }}</button>
      </form>

      <!-- Token list -->
      <div v-if="tokensLoading" class="text-sm text-gray-400">{{ t('common.loading') }}</div>
      <div v-else-if="tokens.length === 0" class="text-sm text-gray-400">{{ t('settings.noTokens') }}</div>
      <ul v-else class="divide-y divide-gray-100">
        <li v-for="token in tokens" :key="token.id" class="flex items-center justify-between py-3 gap-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-gray-800">{{ token.name }}</span>
              <span
                :class="token.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                class="text-xs px-2 py-0.5 rounded-full"
              >{{ token.is_active ? t('settings.tokenActiveLabel') : t('settings.tokenRevokedLabel2') }}</span>
            </div>
            <p class="text-xs text-gray-400 font-mono mt-0.5">{{ token.prefix }}…</p>
            <p class="text-xs text-gray-400 mt-0.5">
              {{ t('settings.colCreated') }} {{ new Date(token.created_at).toLocaleDateString() }}
              <template v-if="token.last_used_at"> · {{ t('settings.colLastUsed') }} {{ new Date(token.last_used_at).toLocaleDateString() }}</template>
            </p>
          </div>
          <button
            v-if="token.is_active"
            class="flex-shrink-0 text-xs text-red-600 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-50"
            @click="revokeToken(token)"
          >{{ t('settings.revokeBtn') }}</button>
        </li>
      </ul>
    </div>

    <!-- Outbound Webhooks -->
    <div class="bg-white rounded-2xl border border-gray-100 p-5">
      <h2 class="text-sm font-semibold text-gray-900 mb-1">{{ t('settings.webhooksSection') }}</h2>
      <p class="text-xs text-gray-500 mb-4">{{ t('settings.webhooksDesc') }}</p>

      <!-- Create form -->
      <form class="space-y-2 mb-4" @submit.prevent="createWebhook">
        <input
          v-model="newWebhookUrl"
          type="url"
          :placeholder="t('settings.webhookUrlPlaceholder')"
          class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <input
          v-model="newWebhookEvents"
          type="text"
          :placeholder="t('settings.webhookEventsPlaceholder')"
          class="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <button
          type="submit"
          :disabled="newWebhookCreating || !newWebhookUrl.trim()"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
        >{{ newWebhookCreating ? t('settings.adding') : t('settings.addEndpointBtn') }}</button>
      </form>

      <!-- Webhook list -->
      <div v-if="webhooksLoading" class="text-sm text-gray-400">{{ t('common.loading') }}</div>
      <div v-else-if="webhooks.length === 0" class="text-sm text-gray-400">{{ t('settings.noWebhooks') }}</div>
      <ul v-else class="divide-y divide-gray-100">
        <li v-for="wh in webhooks" :key="wh.id" class="py-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm font-mono text-gray-800 break-all">{{ wh.url }}</p>
              <p class="text-xs text-gray-400 mt-0.5">
                {{ t('settings.colEvents') }}: <span class="font-medium">{{ wh.events.length ? wh.events.join(', ') : t('streamlineFilter.all') }}</span>
              </p>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                class="text-xs text-gray-500 border border-gray-200 rounded-lg px-2 py-1 hover:bg-gray-50"
                @click="toggleWebhookDeliveries(wh)"
              >{{ webhookDeliveriesOpen[wh.id] ? t('settings.hideLog') : t('settings.viewLog') }}</button>
              <button
                :class="wh.is_active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'"
                class="text-xs px-2 py-1 rounded-lg"
                @click="toggleWebhook(wh)"
              >{{ wh.is_active ? t('settings.webhookActiveLabel') : t('settings.webhookDisabledLabel2') }}</button>
              <button
                class="text-xs text-red-600 border border-red-200 rounded-lg px-2 py-1 hover:bg-red-50"
                @click="deleteWebhook(wh)"
              >{{ t('common.delete') }}</button>
            </div>
          </div>
          <!-- Delivery log -->
          <div v-if="webhookDeliveriesOpen[wh.id]" class="mt-3 rounded-xl border border-gray-100 bg-gray-50 overflow-hidden">
            <div v-if="webhookDeliveriesLoading[wh.id]" class="px-3 py-2 text-xs text-gray-400">{{ t('common.loading') }}</div>
            <div v-else-if="!webhookDeliveries[wh.id]?.length" class="px-3 py-2 text-xs text-gray-400">{{ t('settings.noDeliveries') }}</div>
            <table v-else class="w-full text-xs">
              <thead>
                <tr class="border-b border-gray-200 text-gray-500">
                  <th class="px-3 py-2 text-left font-medium">{{ t('settings.colEvent') }}</th>
                  <th class="px-3 py-2 text-left font-medium">{{ t('settings.colStatus') }}</th>
                  <th class="px-3 py-2 text-left font-medium">{{ t('settings.colDuration') }}</th>
                  <th class="px-3 py-2 text-left font-medium">{{ t('settings.colDelivered') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100">
                <tr v-for="d in webhookDeliveries[wh.id]" :key="d.id">
                  <td class="px-3 py-2 font-mono text-gray-700">{{ d.event }}</td>
                  <td class="px-3 py-2">
                    <span
                      :class="d.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                      class="px-1.5 py-0.5 rounded-md font-medium"
                    >{{ d.status_code ?? (d.success ? 'OK' : 'ERR') }}</span>
                  </td>
                  <td class="px-3 py-2 text-gray-500">{{ d.duration_ms }}ms</td>
                  <td class="px-3 py-2 text-gray-400">{{ new Date(d.delivered_at).toLocaleString() }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </li>
      </ul>
    </div>

    <!-- Branding (Pro) -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4">
      <div>
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('settings.brandingSection') }}</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ t('settings.brandingDesc') }}</p>
      </div>

      <div v-if="!isPro" class="rounded-xl bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 px-4 py-3 text-sm text-purple-700 dark:text-purple-300">
        {{ t('settings.upgradeToBranding') }}
      </div>

      <template v-else>
        <!-- Logo upload -->
        <div class="space-y-2">
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('settings.logoLabel') }}</label>
          <div class="flex items-center gap-4">
            <img
              v-if="brandLogoPreview || firmStore.activeFirm?.logo_url"
              :src="brandLogoPreview || firmStore.activeFirm?.logo_url || undefined"
              alt="Logo preview"
              class="h-12 w-auto rounded-lg border border-gray-200"
            />
            <div v-else class="h-12 w-24 rounded-lg bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 flex items-center justify-center text-xs text-gray-400">{{ t('settings.noLogoLabel') }}</div>
            <input ref="brandLogoInput" type="file" accept="image/*" class="hidden" @change="onBrandLogoChange" />
            <button class="px-3 py-1.5 border border-gray-200 dark:border-gray-600 text-sm rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700" @click="brandLogoInput?.click()">{{ t('settings.uploadLogo2') }}</button>
          </div>
        </div>
        <!-- Colour picker -->
        <div class="space-y-2">
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300">{{ t('settings.brandColourLabel') }}</label>
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
        >{{ brandSaving ? t('settings.saving') : t('settings.saveBrandingBtn') }}</button>
        <p v-if="brandError" class="text-xs text-red-600">{{ brandError }}</p>
        <p v-if="brandSuccess" class="text-xs text-green-600">{{ t('settings.brandingSavedMsg') }}</p>
      </template>
    </div>

    <!-- ===== LEAD SCORING ===== -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
      <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('settings.leadScoringRules') }}</h2>
      <p class="text-xs text-gray-500 dark:text-gray-400 mb-5">{{ t('settings.leadScoringDesc2') }}</p>

      <!-- Existing rules -->
      <div v-if="leadScoringStore.loading" class="animate-pulse space-y-2 mb-4">
        <div v-for="i in 2" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>
      <div v-else-if="leadScoringStore.rules.length === 0" class="text-sm text-gray-400 dark:text-gray-500 mb-4">{{ t('settings.noRulesYet') }}</div>
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
            @click="removeScoringRule(rule.id)">
          <TrashIcon class="w-4 h-4" /></button>
        </li>
      </ul>

      <!-- Add new rule -->
      <div class="border-t border-gray-100 dark:border-gray-700 pt-4">
        <h3 class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-3">{{ t('settings.addRuleSection') }}</h3>
        <div v-if="ruleError" class="mb-2 text-xs text-red-600 dark:text-red-400" role="alert">{{ ruleError }}</div>
        <div class="flex flex-wrap gap-2 items-end">
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('settings.fieldLabel') }}</label>
            <select v-model="newRuleField" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400">
              <option v-for="f in SCORING_FIELDS" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('settings.valueLabel') }}</label>
            <input
              v-model="newRuleOperand"
              type="text"
              placeholder="e.g. won, web, 5000…"
              class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 w-36 focus:outline-none focus:border-red-400"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('settings.scoreDelta') }}</label>
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
            {{ ruleLoading ? t('settings.addingRuleBtn') : t('settings.addRuleBtnLabel') }}
          </button>
        </div>
      </div>
    </div>


    <!-- ====================================================== -->
    <!-- Custom Fields                                           -->
    <!-- ====================================================== -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">🔧 {{ t('tasks.cfSettings_title') }}</h2>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ t('tasks.cfSettings_subtitle') }}</p>
        </div>
        <button
          class="px-3 py-1.5 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700"
          @click="showNewCFModal = true"
        >{{ t('tasks.cfSettings_addBtn') }}</button>
      </div>

      <!-- Loading skeleton -->
      <div v-if="customFieldsLoading" class="animate-pulse space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>

      <!-- Empty state -->
      <div v-else-if="customFieldsList.length === 0" class="text-center py-8 text-gray-400 dark:text-gray-500 text-sm">
        {{ t('tasks.cfSettings_empty') }}
      </div>

      <!-- Field list -->
      <div v-else class="space-y-2">
        <div
          v-for="cf in customFieldsList"
          :key="cf.id"
          class="flex items-center justify-between gap-3 px-4 py-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-sm text-gray-900 dark:text-gray-100">{{ cf.name }}</span>
              <span v-if="cf.is_required" class="text-xs text-red-500">*</span>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              {{ CF_TYPE_LABELS[cf.field_type] ?? cf.field_type }}
              <template v-if="cf.field_type === 'dropdown' && cf.options.length">
                · {{ cf.options.slice(0, 3).join(', ') }}<span v-if="cf.options.length > 3">…</span>
              </template>
            </p>
          </div>
          <div class="flex items-center gap-1.5">
            <button
              class="px-2.5 py-1 rounded-lg text-xs border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
              @click="openEditCF(cf)"
            >{{ t('tasks.cfSettings_editBtn') }}</button>
            <button
              class="p-1.5 rounded-lg text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
              @click="deleteCF(cf)">
            <TrashIcon class="w-4 h-4" /></button>
          </div>
        </div>
      </div>

      <!-- New CF Modal -->
      <Teleport to="body">
        <div v-if="showNewCFModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="showNewCFModal = false">
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.cfSettings_newTitle') }}</h3>
            <div v-if="newCFError" class="text-sm text-red-600 bg-red-50 dark:bg-red-900/30 rounded-xl px-3 py-2">{{ newCFError }}</div>
            <div>
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.cfSettings_fieldName') }}</label>
              <input v-model="newCFName" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400" :placeholder="t('tasks.cfSettings_fieldNamePlaceholder')" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.cfSettings_fieldType') }}</label>
              <select v-model="newCFType" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400">
                <option v-for="item in cfFieldTypes" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </div>
            <div v-if="newCFType === 'dropdown'">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.cfSettings_options') }} <span class="text-gray-400">{{ t('tasks.cfSettings_optionsHint') }}</span></label>
              <textarea v-model="newCFOptions" rows="4" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none" :placeholder="t('tasks.cfSettings_optionsPlaceholder')" />
            </div>
            <label class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input type="checkbox" v-model="newCFRequired" class="rounded" />
              {{ t('tasks.cfSettings_required') }}
            </label>
            <div class="flex gap-3 justify-end pt-2">
              <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showNewCFModal = false">{{ t('tasks.cfSettings_cancel') }}</button>
              <button :disabled="newCFSaving" class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50" @click="saveNewCF">{{ newCFSaving ? '…' : t('tasks.cfSettings_save') }}</button>
            </div>
          </div>
        </div>
      </Teleport>

      <!-- Edit CF Modal -->
      <Teleport to="body">
        <div v-if="editingCF" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="editingCF = null">
          <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('tasks.cfSettings_editTitle') }}</h3>
            <div>
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.cfSettings_fieldName') }}</label>
              <input v-model="editCFName" type="text" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.cfSettings_fieldType') }}</label>
              <select v-model="editCFType" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400">
                <option v-for="item in cfFieldTypes" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </div>
            <div v-if="editCFType === 'dropdown'">
              <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">{{ t('tasks.cfSettings_options') }}</label>
              <textarea v-model="editCFOptions" rows="4" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none" />
            </div>
            <label class="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input type="checkbox" v-model="editCFRequired" class="rounded" />
              {{ t('tasks.cfSettings_required') }}
            </label>
            <div class="flex gap-3 justify-end pt-2">
              <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="editingCF = null">{{ t('tasks.cfSettings_cancel') }}</button>
              <button :disabled="editCFSaving" class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50" @click="saveEditCF">{{ editCFSaving ? '…' : t('tasks.cfSettings_save') }}</button>
            </div>
          </div>
        </div>
      </Teleport>
    </div>

    </div>
    <!-- ==================== END WORKSPACE TAB ==================== -->

  </div>

  <ConfirmDeleteModal
    :open="!!confirmDeleteCFId"
    :message="t('tasks.cfSettings_deleteConfirm').replace('{name}', confirmDeleteCFName ?? '')"
    @confirm="doDeleteCF(confirmDeleteCFId!); confirmDeleteCFId = null; confirmDeleteCFName = null"
    @cancel="confirmDeleteCFId = null; confirmDeleteCFName = null"
  />

  <ConfirmDeleteModal
    :open="!!pendingRevokeToken"
    :title="t('settings.confirmRevokeToken').replace('{name}', pendingRevokeToken?.name ?? '')"
    :confirm-label="t('settings.revokeBtn')"
    @confirm="executeRevokeToken"
    @cancel="pendingRevokeToken = null"
  />

  <ConfirmDeleteModal
    :open="!!pendingDeleteWebhook"
    :message="t('settings.confirmDeleteWebhook').replace('{url}', pendingDeleteWebhook?.url ?? '')"
    @confirm="executeDeleteWebhook"
    @cancel="pendingDeleteWebhook = null"
  />
</template>

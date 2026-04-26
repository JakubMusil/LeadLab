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
  </div>
</template>

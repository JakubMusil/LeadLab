<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const firmStore = useFirmStore()
const toast = useToast()
const router = useRouter()

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
  </div>
</template>

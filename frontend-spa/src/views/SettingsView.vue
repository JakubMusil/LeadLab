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

onMounted(() => {
  if (authStore.user) {
    profileFirstName.value = authStore.user.first_name
    profileLastName.value = authStore.user.last_name
    profileTimezone.value = authStore.user.timezone
  }
  if (firmStore.activeFirm) {
    workspaceName.value = firmStore.activeFirm.name
  }
})

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
  </div>
</template>

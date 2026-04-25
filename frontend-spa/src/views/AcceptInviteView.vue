<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'

interface InvitationOut {
  email: string
  firm_name?: string
  role?: string
}

const route = useRoute()
const router = useRouter()

const token = route.params.token as string

const state = ref<'loading' | 'form' | 'error' | 'success'>('loading')
const invitation = ref<InvitationOut | null>(null)
const errorMsg = ref('')
const formError = ref('')
const isLoading = ref(false)

const firstName = ref('')
const lastName = ref('')
const password = ref('')

onMounted(async () => {
  const res = await api.get<InvitationOut>(`/api/v1/invitations/${token}`)
  if (res.ok) {
    invitation.value = res.data
    state.value = 'form'
  } else {
    errorMsg.value = 'This invitation link is invalid or has expired.'
    state.value = 'error'
  }
})

async function handleSubmit() {
  formError.value = ''
  if (password.value.length < 8) {
    formError.value = 'Password must be at least 8 characters.'
    return
  }
  isLoading.value = true
  const res = await api.post(`/api/v1/invitations/${token}/accept`, {
    password: password.value,
    first_name: firstName.value,
    last_name: lastName.value,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  })
  isLoading.value = false
  if (res.ok) {
    state.value = 'success'
    setTimeout(() => router.push('/app/login'), 2500)
  } else {
    const errData = res.data as unknown as Record<string, unknown>
    formError.value = (errData?.detail as string) ?? 'Failed to accept invitation.'
  }
}
</script>

<template>
  <div class="min-h-screen flex flex-col justify-center items-center bg-gray-50 p-8">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <span class="text-3xl font-bold text-red-600">LeadLab</span>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <!-- Loading -->
        <div v-if="state === 'loading'" class="animate-pulse space-y-3">
          <div class="h-6 bg-gray-200 rounded w-3/4" />
          <div class="h-4 bg-gray-200 rounded w-1/2" />
          <div class="h-10 bg-gray-200 rounded mt-6" />
          <div class="h-10 bg-gray-200 rounded" />
        </div>

        <!-- Error -->
        <div v-else-if="state === 'error'" class="text-center">
          <div class="text-4xl mb-4">⚠️</div>
          <h2 class="text-xl font-semibold text-gray-900 mb-2">Invalid invitation</h2>
          <p class="text-gray-500 text-sm mb-6">{{ errorMsg }}</p>
          <RouterLink to="/app/login" class="text-red-600 font-medium text-sm hover:text-red-700">
            Back to sign in
          </RouterLink>
        </div>

        <!-- Success -->
        <div v-else-if="state === 'success'" class="text-center">
          <div class="text-4xl mb-4">🎉</div>
          <h2 class="text-xl font-semibold text-gray-900 mb-2">You're in!</h2>
          <p class="text-gray-500 text-sm">Redirecting to sign in…</p>
        </div>

        <!-- Form -->
        <div v-else>
          <h1 class="text-2xl font-semibold text-gray-900 mb-1">Accept invitation</h1>
          <p v-if="invitation?.firm_name" class="text-gray-500 mb-1 text-sm">
            You've been invited to join <strong>{{ invitation.firm_name }}</strong>.
          </p>
          <p v-if="invitation?.email" class="text-gray-400 text-xs mb-6">{{ invitation.email }}</p>

          <div v-if="formError" class="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {{ formError }}
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">First name</label>
                <input
                  v-model="firstName"
                  type="text"
                  required
                  class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                  placeholder="Jane"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Last name</label>
                <input
                  v-model="lastName"
                  type="text"
                  required
                  class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                  placeholder="Smith"
                />
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                v-model="password"
                type="password"
                required
                autocomplete="new-password"
                class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                placeholder="Min. 8 characters"
              />
            </div>

            <button
              type="submit"
              :disabled="isLoading"
              class="w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <svg v-if="isLoading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              {{ isLoading ? 'Joining…' : 'Join workspace' }}
            </button>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

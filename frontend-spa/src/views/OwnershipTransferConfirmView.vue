<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { useI18n } from '@/composables/useI18n'
import { CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/vue/24/outline'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const firmId = route.params.firmId as string
const token = route.params.token as string

const state = ref<'loading' | 'confirm' | 'confirming' | 'success' | 'error'>('loading')
const errorMsg = ref('')

interface TransferPreview {
  id: string
  from_user_email: string
  to_user_email: string
  expires_at: string
  is_pending: boolean
}

const transfer = ref<TransferPreview | null>(null)

onMounted(async () => {
  if (!authStore.user) {
    // Redirect to login, then back here
    router.push({ path: '/app/login', query: { next: route.fullPath } })
    return
  }
  const res = await api.get<TransferPreview>(`/api/v1/firms/${firmId}/transfer-ownership`)
  if (res.ok && res.data && res.data.is_pending) {
    transfer.value = res.data
    state.value = 'confirm'
  } else {
    errorMsg.value = t('settings.transferOwnershipLinkInvalid')
    state.value = 'error'
  }
})

async function confirm() {
  state.value = 'confirming'
  const res = await api.post(`/api/v1/firms/${firmId}/transfer-ownership/${token}/confirm`, {})
  if (res.ok) {
    state.value = 'success'
    setTimeout(() => router.push('/app/dashboard'), 3000)
  } else {
    errorMsg.value = ((res.data as unknown) as { detail?: string })?.detail ?? t('settings.transferOwnershipError')
    state.value = 'error'
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-sm border border-gray-100 p-8">

      <!-- Loading -->
      <div v-if="state === 'loading'" class="text-center text-gray-500 text-sm">
        {{ t('common.loading') }}
      </div>

      <!-- Confirm -->
      <div v-else-if="state === 'confirm' || state === 'confirming'" class="space-y-5">
        <div class="flex items-center gap-3">
          <span class="inline-flex items-center justify-center w-10 h-10 rounded-full bg-amber-100">
            <ExclamationTriangleIcon class="w-5 h-5 text-amber-600" />
          </span>
          <h1 class="text-lg font-semibold text-gray-900">{{ t('settings.transferOwnershipConfirmTitle') }}</h1>
        </div>

        <p class="text-sm text-gray-600">
          {{ t('settings.transferOwnershipConfirmDesc', { from: transfer?.from_user_email, firm: firmId }) }}
        </p>

        <div class="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800 space-y-1">
          <p><span class="font-medium">{{ t('settings.transferOwnershipFrom') }}:</span> {{ transfer?.from_user_email }}</p>
          <p><span class="font-medium">{{ t('settings.transferOwnershipTo') }}:</span> {{ transfer?.to_user_email }}</p>
          <p class="text-xs text-amber-600 mt-1">{{ t('settings.transferOwnershipExpires', { date: transfer ? new Date(transfer.expires_at).toLocaleString() : '' }) }}</p>
        </div>

        <p class="text-xs text-gray-500">{{ t('settings.transferOwnershipConfirmWarning') }}</p>

        <div class="flex gap-3">
          <button
            class="flex-1 rounded-xl border border-gray-200 py-2.5 text-sm text-gray-600 hover:bg-gray-50"
            @click="router.push('/app/dashboard')"
          >{{ t('common.cancel') }}</button>
          <button
            :disabled="state === 'confirming'"
            class="flex-1 bg-amber-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-amber-700 disabled:opacity-50"
            @click="confirm"
          >{{ state === 'confirming' ? '…' : t('settings.transferOwnershipAcceptBtn') }}</button>
        </div>
      </div>

      <!-- Success -->
      <div v-else-if="state === 'success'" class="text-center space-y-4">
        <CheckCircleIcon class="w-12 h-12 text-green-500 mx-auto" />
        <h2 class="text-lg font-semibold text-gray-900">{{ t('settings.transferOwnershipSuccessTitle') }}</h2>
        <p class="text-sm text-gray-500">{{ t('settings.transferOwnershipSuccessDesc') }}</p>
      </div>

      <!-- Error -->
      <div v-else-if="state === 'error'" class="text-center space-y-4">
        <ExclamationTriangleIcon class="w-12 h-12 text-red-500 mx-auto" />
        <h2 class="text-lg font-semibold text-gray-900">{{ t('settings.transferOwnershipErrorTitle') }}</h2>
        <p class="text-sm text-gray-500">{{ errorMsg }}</p>
        <button class="px-4 py-2 bg-gray-100 text-gray-700 rounded-xl text-sm hover:bg-gray-200" @click="router.push('/app/dashboard')">
          {{ t('settings.transferOwnershipGoToDashboard') }}
        </button>
      </div>

    </div>
  </div>
</template>

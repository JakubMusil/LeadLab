<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const newPassword = ref('')
const confirmPassword = ref('')
const errorMsg = ref('')
const successMsg = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  errorMsg.value = ''

  if (newPassword.value.length < 8) {
    errorMsg.value = t('resetPassword.passwordTooShort')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    errorMsg.value = t('resetPassword.passwordMismatch')
    return
  }

  isLoading.value = true
  const res = await api.post('/api/v1/users/password-reset/confirm', {
    uid: route.params.uidb64,
    token: route.params.token,
    new_password: newPassword.value,
  })
  isLoading.value = false

  if (res.ok) {
    successMsg.value = t('resetPassword.successMessage')
    setTimeout(() => router.push('/app/login'), 2000)
  } else {
    errorMsg.value = extractErrorMessage(res.data, t('resetPassword.invalidToken'))
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
        <h1 class="text-2xl font-semibold text-gray-900 mb-2">{{ t('resetPassword.title') }}</h1>
        <p class="text-gray-500 mb-6 text-sm">{{ t('resetPassword.subtitle') }}</p>

        <div v-if="successMsg" class="mb-4 rounded-xl bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
          {{ successMsg }}
        </div>

        <div v-if="errorMsg" class="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <form v-if="!successMsg" @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label for="newPassword" class="block text-sm font-medium text-gray-700 mb-1">{{ t('resetPassword.password') }}</label>
            <input
              id="newPassword"
              v-model="newPassword"
              type="password"
              required
              autocomplete="new-password"
              class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
              placeholder="Min. 8 characters"
            />
          </div>

          <div>
            <label for="confirmPassword" class="block text-sm font-medium text-gray-700 mb-1">{{ t('resetPassword.confirm') }}</label>
            <input
              id="confirmPassword"
              v-model="confirmPassword"
              type="password"
              required
              autocomplete="new-password"
              class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
              placeholder="Repeat password"
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
            {{ isLoading ? t('resetPassword.submitting') : t('resetPassword.submit') }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

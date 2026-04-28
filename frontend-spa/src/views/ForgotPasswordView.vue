<script setup lang="ts">
import { ref } from 'vue'
import { api } from '@/api'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
const email = ref('')
const isLoading = ref(false)
const submitted = ref(false)

async function handleSubmit() {
  isLoading.value = true
  await api.post('/api/v1/users/password-reset/request', { email: email.value })
  isLoading.value = false
  submitted.value = true
}
</script>

<template>
  <div class="min-h-screen flex flex-col justify-center items-center bg-gray-50 p-8">
    <div class="w-full max-w-md">
      <div class="text-center mb-8">
        <span class="text-3xl font-bold text-red-600">LeadLab</span>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h1 class="text-2xl font-semibold text-gray-900 mb-2">{{ t('forgotPassword.title') }}</h1>
        <p class="text-gray-500 mb-6 text-sm">{{ t('forgotPassword.subtitle') }}</p>

        <div
          v-if="submitted"
          class="rounded-xl bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700 mb-4"
        >
          <p class="font-medium mb-1">{{ t('forgotPassword.successTitle') }}</p>
          {{ t('forgotPassword.successMessage') }}
        </div>

        <form v-if="!submitted" @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label for="email" class="block text-sm font-medium text-gray-700 mb-1">{{ t('forgotPassword.email') }}</label>
            <input
              id="email"
              v-model="email"
              type="email"
              required
              autocomplete="email"
              class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
              placeholder="you@example.com"
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
            {{ isLoading ? t('forgotPassword.sending') : t('forgotPassword.send') }}
          </button>
        </form>
      </div>

      <p class="text-center mt-6 text-sm text-gray-600">
        <RouterLink to="/app/login" class="text-red-600 font-medium hover:text-red-700">← {{ t('forgotPassword.backToLogin') }}</RouterLink>
      </p>
    </div>
  </div>
</template>

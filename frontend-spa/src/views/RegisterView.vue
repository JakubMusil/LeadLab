<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const firstName = ref('')
const lastName = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const errorMsg = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  errorMsg.value = ''

  if (password.value.length < 8) {
    errorMsg.value = t('register.passwordTooShort')
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMsg.value = t('register.passwordMismatch')
    return
  }

  isLoading.value = true
  const result = await authStore.register(email.value, password.value, firstName.value, lastName.value)
  isLoading.value = false

  if (result.ok) {
    await router.push('/app/onboarding')
  } else {
    errorMsg.value = result.error ?? t('register.registrationFailed')
  }
}
</script>

<template>
  <div class="min-h-screen flex">
    <!-- Left branding panel -->
    <div class="hidden lg:flex lg:w-1/2 bg-red-600 flex-col justify-center items-center p-12 text-white">
      <div class="max-w-md text-center">
        <div class="text-5xl font-bold mb-4">LeadLab</div>
        <p class="text-xl text-red-100">{{ t('register.brandingTagline') }}</p>
        <p class="mt-4 text-red-200 text-sm">{{ t('register.brandingDescription') }}</p>
      </div>
    </div>

    <!-- Right form panel -->
    <div class="flex-1 flex flex-col justify-center items-center p-8 bg-gray-50">
      <div class="w-full max-w-md">
        <div class="lg:hidden text-center mb-8">
          <span class="text-3xl font-bold text-red-600">LeadLab</span>
        </div>

        <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
          <h1 class="text-2xl font-semibold text-gray-900 mb-2">{{ t('register.title') }}</h1>
          <p class="text-gray-500 mb-6 text-sm">{{ t('register.subtitle') }}</p>

          <div v-if="errorMsg" class="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {{ errorMsg }}
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label for="firstName" class="block text-sm font-medium text-gray-700 mb-1">{{ t('register.firstName') }}</label>
                <input
                  id="firstName"
                  v-model="firstName"
                  type="text"
                  required
                  class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                  placeholder="Jane"
                />
              </div>
              <div>
                <label for="lastName" class="block text-sm font-medium text-gray-700 mb-1">{{ t('register.lastName') }}</label>
                <input
                  id="lastName"
                  v-model="lastName"
                  type="text"
                  required
                  class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                  placeholder="Smith"
                />
              </div>
            </div>

            <div>
              <label for="email" class="block text-sm font-medium text-gray-700 mb-1">{{ t('register.email') }}</label>
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

            <div>
              <label for="password" class="block text-sm font-medium text-gray-700 mb-1">{{ t('register.password') }}</label>
              <input
                id="password"
                v-model="password"
                type="password"
                required
                autocomplete="new-password"
                class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                placeholder="Min. 8 characters"
              />
            </div>

            <div>
              <label for="confirmPassword" class="block text-sm font-medium text-gray-700 mb-1">{{ t('register.confirmPassword') }}</label>
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
              {{ isLoading ? t('register.creating') : t('register.createAccount') }}
            </button>
          </form>
        </div>

        <p class="text-center mt-6 text-sm text-gray-600">
          {{ t('register.alreadyHaveAccount') }}
          <RouterLink to="/app/login" class="text-red-600 font-medium hover:text-red-700">{{ t('register.signIn') }}</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const password = ref('')
const errorMsg = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  errorMsg.value = ''
  isLoading.value = true
  const result = await authStore.login(email.value, password.value)
  isLoading.value = false
  if (result.ok) {
    await router.push('/app/dashboard')
  } else {
    errorMsg.value = result.error ?? 'Login failed.'
  }
}
</script>

<template>
  <div class="min-h-screen flex">
    <!-- Left branding panel -->
    <div class="hidden lg:flex lg:w-1/2 bg-red-600 flex-col justify-center items-center p-12 text-white">
      <div class="max-w-md text-center">
        <div class="text-5xl font-bold mb-4">LeadLab</div>
        <p class="text-xl text-red-100">Your CRM for modern sales teams.</p>
        <p class="mt-4 text-red-200 text-sm">Manage leads, track deals, grow your business.</p>
      </div>
    </div>

    <!-- Right form panel -->
    <div class="flex-1 flex flex-col justify-center items-center p-8 bg-gray-50 dark:bg-gray-900">
      <div class="w-full max-w-md">
        <div class="lg:hidden text-center mb-8">
          <span class="text-3xl font-bold text-red-600">LeadLab</span>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-8">
          <h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Welcome back</h1>
          <p class="text-gray-500 dark:text-gray-400 mb-6 text-sm">Sign in to your account</p>

          <div v-if="errorMsg" class="mb-4 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400" role="alert">
            {{ errorMsg }}
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-4">
            <div>
              <label for="email" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
              <input
                id="email"
                v-model="email"
                type="email"
                required
                autocomplete="email"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label for="password" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
              <input
                id="password"
                v-model="password"
                type="password"
                required
                autocomplete="current-password"
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                placeholder="••••••••"
              />
            </div>

            <div class="flex justify-end">
              <RouterLink to="/app/forgot-password" class="text-sm text-red-600 hover:text-red-700">
                Forgot password?
              </RouterLink>
            </div>

            <button
              type="submit"
              :disabled="isLoading"
              class="w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <svg v-if="isLoading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              {{ isLoading ? 'Signing in…' : 'Sign in' }}
            </button>
          </form>
        </div>

        <p class="text-center mt-6 text-sm text-gray-600 dark:text-gray-400">
          Don't have an account?
          <RouterLink to="/app/register" class="text-red-600 font-medium hover:text-red-700">Sign up</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

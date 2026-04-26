<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Button as UiButton, Input as UiInput } from '@/components/ui'

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
            <UiInput
              id="email"
              v-model="email"
              type="email"
              label="Email"
              placeholder="you@example.com"
              autocomplete="email"
              required
            />

            <UiInput
              id="password"
              v-model="password"
              type="password"
              label="Password"
              placeholder="••••••••"
              autocomplete="current-password"
              required
            />

            <div class="flex justify-end">
              <RouterLink to="/app/forgot-password" class="text-sm text-red-600 hover:text-red-700">
                Forgot password?
              </RouterLink>
            </div>

            <UiButton type="submit" :loading="isLoading" :disabled="isLoading" class="w-full">
              {{ isLoading ? 'Signing in…' : 'Sign in' }}
            </UiButton>
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

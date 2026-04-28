<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()
</script>

<template>
  <div class="min-h-screen flex flex-col items-center justify-center bg-gray-50 dark:bg-gray-900 px-6 text-center">
    <div class="mb-6">
      <svg class="w-24 h-24 mx-auto text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </div>
    <h1 class="text-6xl font-bold text-gray-200 dark:text-gray-700 mb-2">404</h1>
    <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">{{ t('notFound.title') }}</h2>
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-8 max-w-sm">
      {{ t('notFound.message') }}
    </p>
    <RouterLink
      to="/app/dashboard"
      class="px-6 py-2.5 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
    >
      {{ t('notFound.backToDashboard') }}
    </RouterLink>
  </div>
</template>

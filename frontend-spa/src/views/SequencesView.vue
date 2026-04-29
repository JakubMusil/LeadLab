<script setup lang="ts">
import { useI18n } from '@/composables/useI18n'
const { t } = useI18n()
</script>

<template>
  <div class="p-6 flex flex-col items-center justify-center py-24 text-center">
    <div class="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center mb-4">
      <span class="text-3xl" aria-hidden="true">📧</span>
    </div>
    <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">{{ t('sequences.title') }}</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400 max-w-sm mb-6">
      {{ t('sequences.description') }}
    </p>
    <div class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 text-sm font-medium">
      <span aria-hidden="true">🚧</span>
      {{ t('sequences.comingSoon') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useI18n } from '@/composables/useI18n'

const error = ref<Error | null>(null)

const { t } = useI18n()

const props = defineProps<{ retry?: () => void }>()

onErrorCaptured((err) => {
  error.value = err instanceof Error ? err : new Error(String(err))
  return false
})

function handleRetry() {
  error.value = null
  props.retry?.()
}
</script>

<template>
  <div v-if="error" class="flex flex-col items-center justify-center py-24 px-6 text-center">
    <div class="w-16 h-16 rounded-2xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
      <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
      </svg>
    </div>
    <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{{ t('errorBoundary.title') }}</h2>
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-1 max-w-sm">{{ error.message }}</p>
    <p class="text-xs text-gray-400 dark:text-gray-500 mb-6 max-w-sm">{{ t('errorBoundary.message') }}</p>
    <button
      class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
      @click="handleRetry"
    >
      {{ t('errorBoundary.retry') }}
    </button>
  </div>
  <slot v-else />
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{
  description?: string
}>()

const router = useRouter()

function goToUpgrade() {
  router.push('/app/settings#billing')
}
</script>

<template>
  <div class="flex flex-col items-center justify-center py-24 px-6 text-center">
    <div class="w-16 h-16 rounded-full bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center mb-4">
      <span class="text-3xl" aria-hidden="true">🔒</span>
    </div>
    <h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Pro feature</h2>
    <p class="text-sm text-gray-500 dark:text-gray-400 max-w-sm mb-6">
      {{ description ?? 'This feature requires a Pro subscription.' }}
    </p>
    <button
      class="px-5 py-2.5 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
      @click="goToUpgrade"
    >
      Upgrade to Pro
    </button>
  </div>
</template>

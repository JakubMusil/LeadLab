<script setup lang="ts">
import { useToast } from '@/composables/useToast'
const { toasts } = useToast()
</script>

<template>
  <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="flex items-start gap-3 rounded-xl px-4 py-3 shadow-lg text-sm font-medium"
        :class="{
          'bg-green-600 dark:bg-green-700 text-white': toast.type === 'success',
          'bg-red-600 dark:bg-red-700 text-white': toast.type === 'error',
          'bg-gray-800 dark:bg-gray-700 text-white': toast.type === 'info',
        }"
        role="alert"
        aria-live="assertive"
      >
        <span v-if="toast.type === 'success'">✓</span>
        <span v-else-if="toast.type === 'error'">✕</span>
        <span v-else>ℹ</span>
        <span>{{ toast.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
@media (prefers-reduced-motion: reduce) {
  .toast-enter-active,
  .toast-leave-active {
    transition: none;
  }
}
</style>

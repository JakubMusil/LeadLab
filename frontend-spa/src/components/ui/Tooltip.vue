<script setup lang="ts">
import { ref } from 'vue'

withDefaults(
  defineProps<{
    content: string
    placement?: 'top' | 'bottom' | 'left' | 'right'
  }>(),
  { placement: 'top' },
)

const visible = ref(false)
</script>

<template>
  <div
    class="relative inline-flex"
    @mouseenter="visible = true"
    @mouseleave="visible = false"
    @focusin="visible = true"
    @focusout="visible = false"
  >
    <slot />
    <Transition name="tooltip">
      <div
        v-if="visible"
        role="tooltip"
        class="absolute z-50 whitespace-nowrap bg-gray-900 dark:bg-gray-700 text-white text-xs px-2 py-1 rounded-lg pointer-events-none"
        :class="[
          placement === 'top' && 'bottom-full left-1/2 -translate-x-1/2 mb-1',
          placement === 'bottom' && 'top-full left-1/2 -translate-x-1/2 mt-1',
          placement === 'left' && 'right-full top-1/2 -translate-y-1/2 mr-1',
          placement === 'right' && 'left-full top-1/2 -translate-y-1/2 ml-1',
        ]"
      >
        {{ content }}
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.tooltip-enter-active,
.tooltip-leave-active {
  transition: opacity 0.15s ease;
}
.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
}
@media (prefers-reduced-motion: reduce) {
  .tooltip-enter-active,
  .tooltip-leave-active {
    transition: none;
  }
}
</style>

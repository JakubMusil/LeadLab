<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'gray' | 'blue' | 'green' | 'yellow' | 'red' | 'orange'
    size?: 'sm' | 'md'
  }>(),
  {
    variant: 'gray',
    size: 'sm',
  },
)
</script>

<template>
  <span
    class="inline-flex items-center font-medium rounded-full"
    :class="[
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
      variant === 'gray' && 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
      variant === 'blue' && 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      variant === 'green' && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
      variant === 'yellow' &&
        'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-500',
      variant === 'red' && 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
      variant === 'orange' &&
        'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    ]"
    ><slot
  /></span>
</template>

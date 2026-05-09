<script setup lang="ts">
defineOptions({ inheritAttrs: false })

withDefaults(
  defineProps<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    size?: 'sm' | 'md' | 'lg'
    disabled?: boolean
    loading?: boolean
    type?: 'button' | 'submit' | 'reset'
  }>(),
  {
    variant: 'primary',
    size: 'md',
    type: 'button' as const,
  },
)

defineEmits<{ click: [e: MouseEvent] }>()
</script>

<template>
  <button
    v-bind="$attrs"
    :type="type"
    :disabled="disabled || loading"
    class="inline-flex items-center justify-center gap-2 font-semibold rounded-lg transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed"
    :class="[
      variant === 'primary' &&
        'bg-accent-500 text-white shadow-md hover:bg-accent-600 hover:-translate-y-0.5 hover:shadow-lg active:translate-y-0 active:shadow-sm focus:ring-accent-500',
      variant === 'secondary' &&
        'bg-transparent border-2 border-brand-600 text-brand-600 hover:bg-brand-50 hover:-translate-y-0.5 active:translate-y-0 focus:ring-brand-500 dark:bg-transparent dark:border-brand-500 dark:text-brand-300 dark:hover:bg-brand-900/30',
      variant === 'ghost' &&
        'text-gray-600 hover:bg-brand-50 hover:text-brand-700 dark:text-gray-300 dark:hover:bg-gray-700 focus:ring-brand-500',
      variant === 'danger' &&
        'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800 focus:ring-red-500',
      size === 'sm' && 'px-3 py-1.5 text-xs',
      size === 'md' && 'px-4 py-2 text-sm',
      size === 'lg' && 'px-5 py-2.5 text-base',
    ]"
    @click="$emit('click', $event)"
  >
    <svg
      v-if="loading"
      class="animate-spin h-4 w-4 flex-shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
    </svg>
    <slot />
  </button>
</template>

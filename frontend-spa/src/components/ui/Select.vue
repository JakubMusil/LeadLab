<script setup lang="ts">
defineOptions({ inheritAttrs: false })

withDefaults(
  defineProps<{
    modelValue?: string
    options: { value: string; label: string }[]
    label?: string
    placeholder?: string
    error?: string
    disabled?: boolean
  }>(),
  {},
)

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="w-full">
    <label v-if="label" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
      {{ label }}
    </label>
    <select
      v-bind="$attrs"
      :value="modelValue"
      :disabled="disabled"
      class="w-full rounded-xl border bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-4 py-2.5 text-sm focus:outline-none transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
      :class="
        error
          ? 'border-red-300 dark:border-red-700 focus:border-red-500 focus:ring-1 focus:ring-red-500'
          : 'border-gray-300 dark:border-gray-600 focus:border-brand-500 focus:ring-1 focus:ring-brand-500'
      "
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>
    <p v-if="error" class="mt-1 text-xs text-red-500 dark:text-red-400">{{ error }}</p>
  </div>
</template>

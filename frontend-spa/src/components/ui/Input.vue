<script setup lang="ts">
defineOptions({ inheritAttrs: false })

withDefaults(
  defineProps<{
    modelValue?: string
    type?: string
    placeholder?: string
    label?: string
    error?: string
    disabled?: boolean
    id?: string
    required?: boolean
    autocomplete?: string
  }>(),
  {
    type: 'text',
  },
)

defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="w-full">
    <label
      v-if="label"
      :for="id"
      class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
    >
      {{ label }}<span v-if="required" class="text-red-500 ml-0.5">*</span>
    </label>
    <input
      v-bind="$attrs"
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :required="required"
      :autocomplete="autocomplete"
      class="w-full rounded-xl border bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 px-4 py-2.5 text-sm focus:outline-none transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
      :class="
        error
          ? 'border-red-300 dark:border-red-700 focus:border-red-500 focus:ring-1 focus:ring-red-500'
          : 'border-gray-300 dark:border-gray-600 focus:border-red-500 focus:ring-1 focus:ring-red-500'
      "
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="mt-1 text-xs text-red-500 dark:text-red-400">{{ error }}</p>
  </div>
</template>

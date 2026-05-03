<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMoney } from '@/composables/useMoney'

const props = defineProps<{
  modelValue: string
  disabled?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const { currencies } = useMoney()

const query = ref('')
const isOpen = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const selectedLabel = computed(() => {
  const found = currencies.value.find((c) => c.code === props.modelValue)
  return found ? found.label : props.modelValue
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return currencies.value
  return currencies.value.filter(
    (c) => c.code.toLowerCase().includes(q) || c.label.toLowerCase().includes(q)
  )
})

function open() {
  if (props.disabled) return
  isOpen.value = true
  query.value = ''
}

function close() {
  isOpen.value = false
  query.value = ''
}

function select(code: string) {
  emit('update:modelValue', code)
  close()
}

function onBlur(e: FocusEvent) {
  // Delay close to allow click on option to register
  setTimeout(() => {
    if (!inputRef.value?.closest('.currency-select-wrapper')?.contains(document.activeElement)) {
      close()
    }
  }, 150)
}

watch(
  () => props.modelValue,
  () => {
    query.value = ''
  }
)
</script>

<template>
  <div class="currency-select-wrapper relative">
    <!-- Trigger button -->
    <button
      v-if="!isOpen"
      type="button"
      :disabled="disabled"
      class="w-full text-left rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 disabled:opacity-60 disabled:cursor-not-allowed truncate"
      @click="open"
    >
      {{ selectedLabel || placeholder || modelValue }}
    </button>

    <!-- Search input (shown when open) -->
    <input
      v-if="isOpen"
      ref="inputRef"
      v-model="query"
      type="text"
      autofocus
      class="w-full rounded-xl border border-red-400 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none"
      @blur="onBlur"
    />

    <!-- Dropdown -->
    <ul
      v-if="isOpen"
      class="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-lg"
    >
      <li
        v-for="opt in filtered"
        :key="opt.code"
        class="px-3 py-2 text-sm cursor-pointer hover:bg-red-50 dark:hover:bg-gray-700 text-gray-900 dark:text-gray-100"
        :class="{ 'bg-red-50 dark:bg-gray-700 font-medium': opt.code === modelValue }"
        @mousedown.prevent="select(opt.code)"
      >
        {{ opt.label }}
      </li>
      <li v-if="filtered.length === 0" class="px-3 py-2 text-sm text-gray-400">—</li>
    </ul>
  </div>
</template>

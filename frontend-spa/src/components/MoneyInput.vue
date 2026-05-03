<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMoney } from '@/composables/useMoney'

const props = defineProps<{
  modelValue: number | null
  currency?: string
  min?: number
  max?: number
  placeholder?: string
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: number | null): void
}>()

const { firmLocale, firmCurrency, formatAmountPlain, parseMoney } = useMoney()

const isFocused = ref(false)
const rawInput = ref('')

const effectiveCurrency = computed(() => props.currency ?? firmCurrency.value)

// Display value: formatted when blurred, plain numeric string when focused
const displayValue = computed(() => {
  if (isFocused.value) return rawInput.value
  if (props.modelValue == null || props.modelValue === 0 && rawInput.value === '') return ''
  return formatAmountPlain(props.modelValue)
})

// Currency symbol position (prefix vs. suffix)
const symbolPrefix = computed(() => {
  try {
    const parts = new Intl.NumberFormat(firmLocale.value, {
      style: 'currency',
      currency: effectiveCurrency.value,
    }).formatToParts(1)
    const currencyIdx = parts.findIndex((p) => p.type === 'currency')
    const integerIdx = parts.findIndex((p) => p.type === 'integer')
    return currencyIdx < integerIdx
  } catch {
    return false
  }
})

const currencySymbol = computed(() => {
  try {
    const parts = new Intl.NumberFormat(firmLocale.value, {
      style: 'currency',
      currency: effectiveCurrency.value,
    }).formatToParts(1)
    return parts.find((p) => p.type === 'currency')?.value ?? effectiveCurrency.value
  } catch {
    return effectiveCurrency.value
  }
})

function onFocus() {
  isFocused.value = true
  // Show plain number string for editing
  rawInput.value = props.modelValue != null ? String(props.modelValue) : ''
}

function onBlur() {
  isFocused.value = false
  const parsed = parseMoney(rawInput.value)
  const value = isNaN(parsed) ? null : parsed
  emit('update:modelValue', value)
}

function onInput(e: Event) {
  rawInput.value = (e.target as HTMLInputElement).value
  const parsed = parseMoney(rawInput.value)
  if (!isNaN(parsed)) {
    emit('update:modelValue', parsed)
  }
}

// Sync external value changes when not focused
watch(
  () => props.modelValue,
  (val) => {
    if (!isFocused.value) {
      rawInput.value = val != null ? String(val) : ''
    }
  }
)
</script>

<template>
  <div class="money-input-wrapper flex items-center w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 focus-within:border-red-400 overflow-hidden">
    <!-- Currency symbol prefix -->
    <span
      v-if="symbolPrefix"
      class="px-2 text-sm text-gray-500 dark:text-gray-400 select-none shrink-0"
    >
      {{ currencySymbol }}
    </span>

    <input
      :value="displayValue"
      :placeholder="placeholder ?? '0'"
      :disabled="disabled"
      type="text"
      inputmode="decimal"
      class="flex-1 min-w-0 bg-transparent text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
      @focus="onFocus"
      @blur="onBlur"
      @input="onInput"
    />

    <!-- Currency symbol suffix -->
    <span
      v-if="!symbolPrefix"
      class="px-2 text-sm text-gray-500 dark:text-gray-400 select-none shrink-0"
    >
      {{ currencySymbol }}
    </span>
  </div>
</template>

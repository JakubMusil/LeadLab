<script setup lang="ts">
import { computed } from 'vue'
import { setLocale, useI18n } from '@/composables/useI18n'

withDefaults(
  defineProps<{
    variant?: 'nav' | 'footer'
  }>(),
  {
    variant: 'nav',
  },
)

const { t, locale } = useI18n()

const languages = ['en', 'cs', 'de', 'pl'] as const

const ariaLabel = computed(() => t('marketing.languageSwitcher.label'))

function isActive(code: string) {
  return locale.value === code
}

function onSelect(code: string) {
  if (code === locale.value) return
  setLocale(code)
}
</script>

<template>
  <div
    role="group"
    :aria-label="ariaLabel"
    :class="
      variant === 'nav'
        ? 'inline-flex items-center gap-1 rounded-xl border border-gray-200 bg-white p-0.5'
        : 'inline-flex items-center gap-0.5 rounded-lg bg-gray-100 p-0.5'
    "
  >
    <button
      v-for="code in languages"
      :key="code"
      type="button"
      :aria-pressed="isActive(code)"
      :aria-label="t(`marketing.languageSwitcher.languages.${code}`)"
      class="text-xs font-semibold rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
      :class="[
        variant === 'nav' ? 'px-2.5 py-1' : 'px-2 py-0.5',
        isActive(code)
          ? variant === 'nav'
            ? 'bg-brand-600 text-white'
            : 'bg-white text-gray-900 shadow-sm'
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
      ]"
      @click="onSelect(code)"
    >
      {{ t(`marketing.languageSwitcher.languages.${code}`) }}
    </button>
  </div>
</template>

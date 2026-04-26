<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name?: string
    src?: string
    size?: 'xs' | 'sm' | 'md' | 'lg'
  }>(),
  { size: 'md' },
)

const initials = computed(() => {
  if (!props.name) return '?'
  const words = props.name.trim().split(/\s+/)
  return ((words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')).toUpperCase() || '?'
})
</script>

<template>
  <span
    class="inline-flex items-center justify-center rounded-full bg-red-600 text-white font-medium flex-shrink-0 overflow-hidden"
    :class="[
      size === 'xs' && 'w-6 h-6 text-xs',
      size === 'sm' && 'w-8 h-8 text-sm',
      size === 'md' && 'w-10 h-10 text-sm',
      size === 'lg' && 'w-12 h-12 text-base',
    ]"
    :title="name"
  >
    <img v-if="src" :src="src" :alt="name" class="w-full h-full object-cover" />
    <span v-else aria-hidden="true">{{ initials }}</span>
  </span>
</template>

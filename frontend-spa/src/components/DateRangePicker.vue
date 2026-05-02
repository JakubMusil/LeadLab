<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'

interface Props {
  modelValueFrom?: string
  modelValueTo?: string
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  modelValueFrom: '',
  modelValueTo: '',
  label: 'Date range',
})

const emit = defineEmits<{
  'update:modelValueFrom': [value: string]
  'update:modelValueTo': [value: string]
}>()

const localFrom = ref(props.modelValueFrom)
const localTo = ref(props.modelValueTo)

watch(
  () => props.modelValueFrom,
  (v) => { localFrom.value = v },
)
watch(
  () => props.modelValueTo,
  (v) => { localTo.value = v },
)

function onFromChange(e: Event) {
  localFrom.value = (e.target as HTMLInputElement).value
  emit('update:modelValueFrom', localFrom.value)
}

function onToChange(e: Event) {
  localTo.value = (e.target as HTMLInputElement).value
  emit('update:modelValueTo', localTo.value)
}

function clear() {
  localFrom.value = ''
  localTo.value = ''
  emit('update:modelValueFrom', '')
  emit('update:modelValueTo', '')
}

const hasValue = computed(() => localFrom.value || localTo.value)
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <span class="text-xs font-medium text-gray-500 dark:text-gray-400">{{ label }}</span>
    <div class="flex items-center gap-1">
      <input
        type="date"
        :value="localFrom"
        @change="onFromChange"
        class="text-xs border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-red-400"
        aria-label="From date"
      />
      <span class="text-xs text-gray-400">–</span>
      <input
        type="date"
        :value="localTo"
        @change="onToChange"
        class="text-xs border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-2 focus:ring-red-400"
        aria-label="To date"
      />
    </div>
    <button
      v-if="hasValue"
      @click="clear"
      class="text-xs text-gray-400 hover:text-red-500 transition-colors"
      aria-label="Clear date range"
      title="Clear"
    >
      <XMarkIcon class="w-4 h-4" />
    </button>
  </div>
</template>

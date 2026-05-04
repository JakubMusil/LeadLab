<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/api'
import { useI18n } from '@/composables/useI18n'
import type { TimerContext } from '@/stores/timer'

const { t } = useI18n()

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  (e: 'confirm', ctx: TimerContext, description: string, billable: boolean): void
  (e: 'close'): void
}>()

type EntityType = 'record' | 'customer' | 'task' | null

interface SearchResult {
  id: string
  label: string
}

const entityType = ref<EntityType>(null)
const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const selectedEntity = ref<SearchResult | null>(null)
const description = ref('')
const isBillable = ref(true)
const searching = ref(false)

watch(searchQuery, async (q) => {
  if (!q || !entityType.value) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    let url = ''
    if (entityType.value === 'record') {
      url = `/api/v1/crm/records?search=${encodeURIComponent(q)}&page_size=10`
    } else if (entityType.value === 'customer') {
      url = `/api/v1/crm/customers?search=${encodeURIComponent(q)}&page_size=10`
    } else if (entityType.value === 'task') {
      url = `/api/v1/crm/tasks?search=${encodeURIComponent(q)}&page_size=10`
    }
    if (!url) return
    const res = await api.get<{ results?: unknown[]; items?: unknown[] } | unknown[]>(url)
    if (res.ok) {
      const items = Array.isArray(res.data)
        ? res.data
        : (res.data as { results?: unknown[]; items?: unknown[] }).results
          ?? (res.data as { results?: unknown[]; items?: unknown[] }).items
          ?? []
      searchResults.value = (items as Record<string, string>[]).map((item) => ({
        id: item.id as string,
        label: (item.title ?? item.first_name
          ? `${item.first_name ?? ''} ${item.last_name ?? ''}`.trim()
          : item.email ?? item.id) as string,
      }))
    }
  } finally {
    searching.value = false
  }
})

watch(() => props.open, (v) => {
  if (!v) return
  // Reset on open
  entityType.value = null
  searchQuery.value = ''
  searchResults.value = []
  selectedEntity.value = null
  description.value = ''
  isBillable.value = true
})

function selectEntity(item: SearchResult) {
  selectedEntity.value = item
  searchResults.value = []
  searchQuery.value = item.label
}

function confirm() {
  const ctx: TimerContext = {
    entityType: entityType.value,
    entityId: selectedEntity.value?.id ?? null,
    entityLabel: selectedEntity.value?.label ?? null,
  }
  emit('confirm', ctx, description.value, isBillable.value)
}

function close() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      @click.self="close"
      role="dialog"
      aria-modal="true"
      :aria-label="t('timerModal.title')"
    >
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-6 w-full max-w-md mx-4">
        <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('timerModal.title') }}</h2>

        <!-- Entity type selector -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('timerModal.linkTo') }}</label>
          <div class="flex gap-2 flex-wrap">
            <button
              v-for="opt in [
                { value: null, label: t('timerModal.none') },
                { value: 'record', label: t('timerModal.opportunity') },
                { value: 'customer', label: t('timerModal.contact') },
                { value: 'task', label: t('timerModal.taskEntity') },
              ]"
              :key="String(opt.value)"
              class="px-3 py-1 rounded-full text-sm border transition-colors"
              :class="entityType === opt.value
                ? 'bg-red-600 text-white border-red-600'
                : 'border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-red-400'"
              @click="entityType = opt.value as EntityType; selectedEntity = null; searchQuery = ''"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <!-- Search for entity -->
        <div v-if="entityType" class="mb-4 relative">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            {{ t('timerModal.searchLabel', { type: entityType }) }}
          </label>
          <input
            v-model="searchQuery"
            type="text"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            :placeholder="t('timerModal.searchPlaceholder', { type: entityType })"
          />
          <div
            v-if="searchResults.length"
            class="absolute z-10 w-full mt-1 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-48 overflow-y-auto"
          >
            <button
              v-for="item in searchResults"
              :key="item.id"
              class="w-full text-left px-3 py-2 text-sm text-gray-900 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-600"
              @click="selectEntity(item)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>

        <!-- Description -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('timerModal.description') }}</label>
          <input
            v-model="description"
            type="text"
            class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500"
            :placeholder="t('timerModal.descriptionPlaceholder')"
          />
        </div>

        <!-- Billable toggle -->
        <div class="mb-6 flex items-center gap-3">
          <button
            type="button"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none"
            :class="isBillable ? 'bg-red-600' : 'bg-gray-300 dark:bg-gray-600'"
            @click="isBillable = !isBillable"
            role="switch"
            :aria-checked="isBillable"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
              :class="isBillable ? 'translate-x-4' : 'translate-x-0.5'"
            />
          </button>
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('timerModal.billable') }}</span>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 justify-end">
          <button
            class="px-4 py-2 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
            @click="close"
          >
            {{ t('timerModal.cancel') }}
          </button>
          <button
            class="px-4 py-2 rounded-xl text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
            @click="confirm"
          >
            {{ t('timerModal.start') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

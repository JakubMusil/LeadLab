<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { BoltIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { api } from '@/api'

interface FocusNextRecord {
  id: string
  title: string
  company_name: string | null
  contact_person_name: string | null
  value_canonical: number | null
  status: string
  stage_name: string | null
  category_name: string | null
  assigned_to_name: string | null
  days_since_activity: number
  score: number | null
}

interface FocusNextResponse {
  record: FocusNextRecord | null
}

const { t } = useI18n()
const { formatAmount } = useMoney()
const router = useRouter()

const STALE_THRESHOLD_DAYS = 14
const loading = ref(false)
const record = ref<FocusNextRecord | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await api.get<FocusNextResponse>('/api/v1/crm/dashboard/focus-next')
    if (res.ok) record.value = res.data.record
  } finally {
    loading.value = false
  }
}

defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header -->
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2 mb-4">
      <BoltIcon class="w-4 h-4 text-amber-500" aria-hidden="true" />
      {{ t('dashboard.focusNextTitle') }}
    </h3>

    <!-- Skeleton -->
    <div v-if="loading && !record" class="animate-pulse">
      <div class="h-32 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading && !record" class="text-center py-8">
      <div class="text-3xl mb-2">🎯</div>
      <p class="text-sm text-gray-400 dark:text-gray-500">{{ t('dashboard.focusNextEmpty') }}</p>
    </div>

    <!-- Record card -->
    <div v-else-if="record" class="space-y-3">
      <div>
        <RouterLink
          :to="`/app/records/${record.id}`"
          class="text-base font-bold text-gray-900 dark:text-gray-100 hover:text-red-600 dark:hover:text-red-400 block truncate"
        >
          {{ record.title }}
        </RouterLink>
        <p v-if="record.company_name || record.contact_person_name" class="text-xs text-gray-400 mt-0.5 truncate">
          {{ [record.company_name, record.contact_person_name].filter(Boolean).join(' · ') }}
        </p>
      </div>

      <!-- Breadcrumb -->
      <div v-if="record.stage_name || record.category_name" class="flex items-center gap-1 text-xs text-gray-400">
        <span v-if="record.stage_name">{{ record.stage_name }}</span>
        <span v-if="record.stage_name && record.category_name" class="text-gray-300 dark:text-gray-600">›</span>
        <span v-if="record.category_name">{{ record.category_name }}</span>
      </div>

      <!-- Badges row -->
      <div class="flex items-center gap-2 flex-wrap">
        <span
          class="inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-semibold"
          :class="record.days_since_activity >= STALE_THRESHOLD_DAYS
            ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'"
        >
          {{ t('dashboard.focusNextDaysStale', { n: record.days_since_activity }) }}
        </span>
        <span
          v-if="record.score !== null"
          class="inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-semibold bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
        >
          ★ {{ record.score }}
        </span>
        <span v-if="record.value_canonical" class="text-xs text-gray-500 dark:text-gray-400 font-medium">
          {{ formatAmount(record.value_canonical) }}
        </span>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center gap-2 pt-1">
        <button
          type="button"
          class="flex-1 px-3 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-xs font-medium hover:opacity-90 transition-opacity"
          @click="router.push(`/app/records/${record.id}`)"
        >
          {{ t('dashboard.focusNextOpen') }}
        </button>
        <button
          type="button"
          class="flex-1 px-3 py-1.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-xl text-xs font-medium hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          @click="load()"
        >
          {{ t('dashboard.focusNextSkip') }}
        </button>
      </div>
    </div>
  </div>
</template>

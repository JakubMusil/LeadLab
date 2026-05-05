<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { ExclamationTriangleIcon, ArrowRightIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { getStatusMeta } from '@/stores/records'
import { api } from '@/api'

interface StaleRecordItem {
  id: string
  title: string
  category_id: string | null
  category_name: string | null
  stage_id: string | null
  stage_name: string | null
  status: string
  value_canonical: number | null
  assigned_to_id: string | null
  assigned_to_name: string | null
  last_activity_at: string | null
  days_since_activity: number
}

interface StaleRecordsData {
  threshold_days: number
  items: StaleRecordItem[]
}

const { t } = useI18n()
const { formatAmount } = useMoney()

const data = ref<StaleRecordsData | null>(null)
const loading = ref(false)

const THRESHOLD_DAYS = 14

async function load() {
  loading.value = true
  try {
    const res = await api.get<StaleRecordsData>(
      `/api/v1/crm/dashboard/stale-records?days=${THRESHOLD_DAYS}&limit=10`,
    )
    if (res.ok) data.value = res.data
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
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <ExclamationTriangleIcon class="w-4 h-4 text-amber-500" aria-hidden="true" />
        {{ t('dashboard.staleRecords') }}
        <span class="text-xs font-normal text-gray-400">({{ t('dashboard.staleRecordsDays', { n: THRESHOLD_DAYS }) }})</span>
      </h3>
      <RouterLink
        to="/app/records"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600"
      >
        {{ t('dashboard.viewAll') }}
      </RouterLink>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="space-y-2 animate-pulse">
      <div v-for="i in 5" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="data && data.items.length === 0" class="text-center py-8">
      <p class="text-sm text-gray-400 dark:text-gray-500">{{ t('dashboard.staleRecordsEmpty') }}</p>
    </div>

    <!-- List -->
    <ul v-else-if="data" class="divide-y divide-gray-50 dark:divide-gray-700">
      <li
        v-for="record in data.items"
        :key="record.id"
        class="-mx-2 px-2 py-2.5 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div class="flex items-start gap-3">
          <!-- Stale badge -->
          <span
            class="flex-shrink-0 mt-0.5 inline-flex items-center rounded-lg px-2 py-0.5 text-xs font-semibold"
            :class="record.days_since_activity >= 30
              ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
              : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'"
          >
            {{ record.days_since_activity }}d
          </span>

          <!-- Record info -->
          <div class="flex-1 min-w-0">
            <RouterLink
              :to="`/app/records/${record.id}`"
              class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 dark:hover:text-red-400 truncate block"
            >
              {{ record.title }}
            </RouterLink>
            <div class="flex items-center gap-1.5 flex-wrap mt-0.5">
              <span v-if="record.category_name" class="text-xs text-gray-400">{{ record.category_name }}</span>
              <span v-if="record.category_name && record.stage_name" class="text-gray-300 dark:text-gray-600">›</span>
              <span v-if="record.stage_name" class="text-xs text-gray-500 dark:text-gray-400">{{ record.stage_name }}</span>
              <span
                v-else-if="!record.stage_name"
                class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium"
                :class="getStatusMeta(record.status).color"
              >
                {{ record.status }}
              </span>
            </div>
          </div>

          <!-- Value + navigate -->
          <div class="flex-shrink-0 text-right">
            <div v-if="record.value_canonical" class="text-xs font-medium text-gray-700 dark:text-gray-300">
              {{ formatAmount(record.value_canonical) }}
            </div>
            <RouterLink
              :to="`/app/records/${record.id}`"
              class="inline-flex items-center gap-0.5 text-xs text-gray-400 hover:text-red-600 transition-colors mt-0.5"
              :aria-label="record.title"
            >
              <ArrowRightIcon class="w-3 h-3" aria-hidden="true" />
            </RouterLink>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

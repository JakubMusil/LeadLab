<script setup lang="ts">
import { computed } from 'vue'
import { useMoney } from '@/composables/useMoney'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'

interface StatsData {
  total_records: number
  total_customers: number
  pipeline_value: number
  pipeline_value_canonical?: number
  won_value: number
  won_value_canonical?: number
  canonical_currency?: string
  conversion_rate: number
  total_tasks_pending: number
  total_tasks_overdue: number
  avg_cycle_days?: number
  mixed_currencies?: boolean
}

const props = defineProps<{ stats: StatsData }>()

const { t } = useI18n()
const { formatAmount } = useMoney()
const firmStore = useFirmStore()

const pipelineDisplay = computed(() =>
  props.stats.pipeline_value_canonical != null
    ? formatAmount(props.stats.pipeline_value_canonical)
    : formatAmount(props.stats.pipeline_value),
)

const wonDisplay = computed(() =>
  props.stats.won_value_canonical != null
    ? formatAmount(props.stats.won_value_canonical)
    : formatAmount(props.stats.won_value),
)
</script>

<template>
  <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
    <!-- Total records -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.totalRecords') }}</div>
      <div class="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ stats.total_records }}</div>
      <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('dashboard.conversion', { rate: (stats.conversion_rate * 100).toFixed(1) }) }}</div>
    </div>

    <!-- Customers -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.customers') }}</div>
      <div class="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ stats.total_customers }}</div>
      <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('dashboard.inAddressBook') }}</div>
    </div>

    <!-- Pipeline value -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.pipeline') }}</div>
      <div class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ pipelineDisplay }}</div>
      <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('dashboard.won', { value: wonDisplay }) }}</div>
      <div v-if="stats.mixed_currencies" class="text-xs text-amber-600 mt-1">
        {{ t('currencySettings.warningMixedCurrencies', { currency: firmStore.activeFirm?.default_currency }) }}
      </div>
    </div>

    <!-- Open tasks -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.openTasks') }}</div>
      <div class="text-3xl font-bold mt-1" :class="stats.total_tasks_overdue > 0 ? 'text-red-600' : 'text-gray-900 dark:text-gray-100'">
        {{ stats.total_tasks_pending }}
      </div>
      <div class="text-xs mt-1" :class="stats.total_tasks_overdue > 0 ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'">
        {{ t('dashboard.overdue', { count: stats.total_tasks_overdue }) }}
      </div>
    </div>
  </div>
</template>

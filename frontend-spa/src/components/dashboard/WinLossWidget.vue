<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { TrophyIcon } from '@heroicons/vue/24/outline'

interface StatsData {
  records_by_status: Record<string, number>
  conversion_rate: number
  avg_cycle_days?: number
  won_value_canonical?: number
  won_value: number
  canonical_currency?: string
}

const props = defineProps<{ stats: StatsData }>()

const { t } = useI18n()
const { formatAmount } = useMoney()

const wonCount = computed(() => props.stats.records_by_status?.won ?? 0)
const lostCount = computed(() => props.stats.records_by_status?.lost ?? 0)
const canceledCount = computed(() => props.stats.records_by_status?.canceled ?? 0)
const totalClosed = computed(() => wonCount.value + lostCount.value + canceledCount.value)
const winRate = computed(() =>
  totalClosed.value > 0 ? (wonCount.value / totalClosed.value) * 100 : props.stats.conversion_rate * 100,
)

// SVG gauge arc: radius=40, circumference ≈ 251.3
const RADIUS = 40
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const gaugeOffset = computed(() => CIRCUMFERENCE * (1 - winRate.value / 100))

const wonValue = computed(() =>
  props.stats.won_value_canonical != null
    ? formatAmount(props.stats.won_value_canonical)
    : formatAmount(props.stats.won_value),
)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header -->
    <div class="flex items-center gap-2 mb-4">
      <TrophyIcon class="w-4 h-4 text-amber-500" aria-hidden="true" />
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
        {{ t('dashboard.winLoss') }}
      </h3>
    </div>

    <!-- Empty state: no closed records -->
    <div
      v-if="totalClosed === 0"
      class="text-center py-8 text-sm text-gray-400"
    >
      {{ t('dashboard.winLossEmpty') }}
    </div>

    <!-- Content -->
    <template v-else>
      <div class="flex items-center gap-6">
        <!-- SVG Gauge -->
        <div class="relative flex-shrink-0">
          <svg width="100" height="60" viewBox="0 0 100 60" aria-hidden="true">
            <!-- Background arc -->
            <path
              d="M10,50 A40,40 0 0,1 90,50"
              fill="none"
              stroke="currentColor"
              class="text-gray-100 dark:text-gray-700"
              stroke-width="8"
              stroke-linecap="round"
            />
            <!-- Value arc -->
            <circle
              cx="50"
              cy="50"
              r="40"
              fill="none"
              stroke="#22c55e"
              stroke-width="8"
              stroke-linecap="round"
              :stroke-dasharray="`${CIRCUMFERENCE}`"
              :stroke-dashoffset="`${gaugeOffset}`"
              transform="rotate(-180 50 50)"
              style="clip-path: inset(-10px -10px 50% -10px)"
            />
          </svg>
          <!-- Percentage label -->
          <div class="absolute inset-0 flex items-end justify-center pb-0">
            <span class="text-xl font-bold text-green-600 dark:text-green-400">
              {{ winRate.toFixed(0) }}%
            </span>
          </div>
        </div>

        <!-- Stats list -->
        <div class="flex-1 space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="text-gray-500 dark:text-gray-400">{{ t('dashboard.wlWon') }}</span>
            <span class="font-semibold text-green-600 dark:text-green-400">{{ wonCount }}</span>
          </div>
          <div class="flex items-center justify-between text-xs">
            <span class="text-gray-500 dark:text-gray-400">{{ t('dashboard.wlLost') }}</span>
            <span class="font-semibold text-red-500">{{ lostCount }}</span>
          </div>
          <div v-if="canceledCount > 0" class="flex items-center justify-between text-xs">
            <span class="text-gray-500 dark:text-gray-400">{{ t('dashboard.wlCanceled') }}</span>
            <span class="font-semibold text-gray-500">{{ canceledCount }}</span>
          </div>
          <div class="flex items-center justify-between text-xs border-t border-gray-100 dark:border-gray-700 pt-1 mt-1">
            <span class="text-gray-500 dark:text-gray-400">{{ t('dashboard.wlValue') }}</span>
            <span class="font-semibold text-gray-800 dark:text-gray-200">{{ wonValue }}</span>
          </div>
          <div v-if="stats.avg_cycle_days != null" class="flex items-center justify-between text-xs">
            <span class="text-gray-500 dark:text-gray-400">{{ t('dashboard.avgCycleDays') }}</span>
            <span class="font-semibold text-gray-700 dark:text-gray-300">
              {{ t('dashboard.cycleDays', { n: Math.round(stats.avg_cycle_days) }) }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { useChartTheme } from '@/composables/useChartTheme'
import { useDashboardWidget } from '@/composables/useDashboardWidget'
import { api } from '@/api'

ChartJS.register(LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler)

type TrendMetric = 'created' | 'won' | 'lost' | 'value_won' | 'value_pipeline' | 'activities'
type TrendRange = '30d' | '90d'

interface TrendPoint {
  date: string
  value: number
}

interface TrendData {
  metric: TrendMetric
  range: string
  points: TrendPoint[]
}

const { t } = useI18n()
const { formatAmount } = useMoney()
const { tickColor, gridColor } = useChartTheme()
const { range: configRange, categoryId, updateConfig } = useDashboardWidget('pipeline_trend')

const data = ref<TrendData | null>(null)
const loading = ref(false)
const selectedMetric = ref<TrendMetric>('created')

// Local range: constrained to 30d/90d (trend widget only supports these)
// Falls back to configRange when it's one of those values; otherwise defaults to 30d
const selectedRange = computed<TrendRange>(() => {
  const r = configRange.value
  return r === '90d' ? '90d' : '30d'
})

// Allow the local 30d/90d toggle to write back to per-widget config
function setLocalRange(r: TrendRange) {
  updateConfig({ range: r })
}

const isValueMetric = computed(() =>
  selectedMetric.value === 'value_won' || selectedMetric.value === 'value_pipeline',
)

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('metric', selectedMetric.value)
    params.set('range', selectedRange.value)
    if (categoryId.value) params.set('category_id', categoryId.value)
    const res = await api.get<TrendData>(`/api/v1/crm/dashboard/trend?${params.toString()}`)
    if (res.ok) data.value = res.data
  } finally {
    loading.value = false
  }
}

watch([selectedMetric, selectedRange, categoryId], () => load())

const METRIC_COLORS: Record<TrendMetric, string> = {
  created: '#6366f1',
  won: '#22c55e',
  lost: '#ef4444',
  value_won: '#22c55e',
  value_pipeline: '#6366f1',
  activities: '#f59e0b',
}

const chartData = computed(() => {
  const points = data.value?.points ?? []
  const color = METRIC_COLORS[selectedMetric.value] ?? '#6366f1'
  return {
    labels: points.map((p) => {
      const d = new Date(p.date)
      return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    }),
    datasets: [
      {
        data: points.map((p) => p.value),
        borderColor: color,
        backgroundColor: color + '22',
        fill: true,
        tension: 0.35,
        pointRadius: points.length > 30 ? 0 : 3,
        borderWidth: 2,
      },
    ],
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        label: (ctx: any) => {
          const val = (ctx.parsed?.y ?? 0) as number
          if (isValueMetric.value) return ` ${formatAmount(val)}`
          return ` ${val}`
        },
      },
    },
  },
  scales: {
    x: {
      ticks: {
        maxTicksLimit: 8,
        color: tickColor.value,
        font: { size: 10 },
      },
      grid: { color: gridColor.value },
    },
    y: {
      ticks: {
        color: tickColor.value,
        precision: 0,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        callback: (value: any) =>
          isValueMetric.value ? formatAmount(Number(value)) : String(value),
      },
      grid: { color: gridColor.value },
    },
  },
}))

const METRIC_OPTIONS: { value: TrendMetric; labelKey: string }[] = [
  { value: 'created', labelKey: 'dashboard.trendMetricCreated' },
  { value: 'won', labelKey: 'dashboard.trendMetricWon' },
  { value: 'value_pipeline', labelKey: 'dashboard.trendMetricValue' },
  { value: 'activities', labelKey: 'dashboard.trendMetricActivities' },
]

defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header with metric + range selectors -->
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 shrink-0">
        {{ t('dashboard.pipelineTrend') }}
      </h3>
      <div class="flex items-center gap-2 flex-wrap">
        <select
          v-model="selectedMetric"
          :aria-label="t('dashboard.trendSelectMetric')"
          class="text-xs rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-2 py-1 focus:outline-none focus:border-red-400"
        >
          <option v-for="opt in METRIC_OPTIONS" :key="opt.value" :value="opt.value">
            {{ t(opt.labelKey) }}
          </option>
        </select>
        <div class="flex rounded-xl border border-gray-200 dark:border-gray-600 overflow-hidden text-xs">
          <button
            v-for="r in (['30d', '90d'] as TrendRange[])"
            :key="r"
            type="button"
            class="px-2.5 py-1 transition-colors"
            :class="selectedRange === r
              ? 'bg-[color:var(--brand-color)] text-white'
              : 'bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600'"
            @click="setLocalRange(r)"
          >
            {{ r === '30d' ? t('dashboard.trendRange30d') : t('dashboard.trendRange90d') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="animate-pulse">
      <div class="h-48 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="data && data.points.length === 0"
      class="text-center py-8 text-sm text-gray-400"
    >
      {{ t('dashboard.pipelineTrendEmpty') }}
    </div>

    <!-- Chart -->
    <template v-else-if="data && data.points.length > 0">
      <div style="height: 220px; position: relative">
        <Line :data="chartData" :options="chartOptions" />
      </div>
    </template>
  </div>
</template>

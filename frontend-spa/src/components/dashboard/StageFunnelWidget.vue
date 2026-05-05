<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { useChartTheme } from '@/composables/useChartTheme'
import { usePipelineStore } from '@/stores/pipeline'
import { api } from '@/api'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

interface StageFunnelStage {
  stage_id: string
  name: string
  color: string
  is_terminal: boolean
  is_won: boolean
  order: number
  count: number
  value_canonical: number
  conversion_to_next: number | null
}

interface StageFunnelData {
  category_id: string | null
  category_name: string | null
  canonical_currency: string | null
  stages: StageFunnelStage[]
}

const { t } = useI18n()
const { formatAmount } = useMoney()
const { tickColor, gridColor } = useChartTheme()
const pipelineStore = usePipelineStore()

const data = ref<StageFunnelData | null>(null)
const loading = ref(false)
const selectedCategoryId = ref<string | null>(null)

const activeCategories = computed(() => pipelineStore.categories.filter((c) => c.is_active))

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (selectedCategoryId.value) params.set('category_id', selectedCategoryId.value)
    const qs = params.toString()
    const url = `/api/v1/crm/dashboard/stage-funnel${qs ? '?' + qs : ''}`
    const res = await api.get<StageFunnelData>(url)
    if (res.ok) {
      data.value = res.data
      // Sync selected to what the backend resolved (e.g. first category when no param given)
      if (!selectedCategoryId.value && res.data.category_id) {
        selectedCategoryId.value = res.data.category_id
      }
    }
  } finally {
    loading.value = false
  }
}

watch(selectedCategoryId, () => load())

// Non-terminal stages for the funnel bars
const funnelStages = computed(() => (data.value?.stages ?? []).filter((s) => !s.is_terminal))
// Terminal stages separate (won/lost)
const terminalStages = computed(() => (data.value?.stages ?? []).filter((s) => s.is_terminal))

const chartData = computed(() => {
  const stages = funnelStages.value
  return {
    labels: stages.map((s) => s.name),
    datasets: [
      {
        data: stages.map((s) => s.count),
        backgroundColor: stages.map((s) => s.color || '#ef4444'),
        borderRadius: 4,
        maxBarThickness: 40,
      },
    ],
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: 'y' as const,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        afterLabel: (ctx: { dataIndex: number }) => {
          const stage = funnelStages.value[ctx.dataIndex]
          if (!stage) return ''
          const val = formatAmount(stage.value_canonical)
          const conv = stage.conversion_to_next != null
            ? ` | ${(stage.conversion_to_next * 100).toFixed(0)}% →`
            : ''
          return `${val}${conv}`
        },
      },
    },
  },
  scales: {
    x: { ticks: { precision: 0, color: tickColor.value }, grid: { color: gridColor.value } },
    y: { ticks: { font: { size: 11 }, color: tickColor.value }, grid: { display: false } },
  },
}))

defineExpose({ load })
onMounted(async () => {
  if (pipelineStore.categories.length === 0) {
    await pipelineStore.fetchCategories()
  }
  await load()
})
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header with category selector -->
    <div class="flex items-center justify-between mb-4 gap-3">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 shrink-0">
        {{ t('dashboard.stageFunnel') }}
        <span v-if="data?.category_name" class="text-gray-400 font-normal">— {{ data.category_name }}</span>
      </h3>
      <select
        v-if="activeCategories.length > 1"
        v-model="selectedCategoryId"
        :aria-label="t('dashboard.funnelSelectCategory')"
        class="text-xs rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 px-2 py-1 focus:outline-none focus:border-red-400"
      >
        <option v-for="cat in activeCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
      </select>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="animate-pulse space-y-2">
      <div v-for="i in 4" :key="i" class="h-8 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- No categories configured -->
    <div v-else-if="data && data.stages.length === 0" class="text-center py-6 text-sm text-gray-400">
      {{ t('dashboard.stageFunnelEmpty') }}
    </div>

    <!-- Funnel chart -->
    <template v-else-if="data && funnelStages.length > 0">
      <div style="height: 200px; position: relative">
        <Bar :data="chartData" :options="chartOptions" />
      </div>

      <!-- Terminal stages summary (won / lost) -->
      <div v-if="terminalStages.length > 0" class="mt-3 flex flex-wrap gap-2">
        <div
          v-for="stage in terminalStages"
          :key="stage.stage_id"
          class="flex items-center gap-1.5 text-xs rounded-xl px-2.5 py-1"
          :style="stage.color ? `background: ${stage.color}22; color: ${stage.color}` : 'background: #f3f4f6'"
        >
          <span class="font-semibold">{{ stage.name }}</span>
          <span>{{ stage.count }}</span>
          <span class="text-xs opacity-70">{{ formatAmount(stage.value_canonical) }}</span>
        </div>
      </div>

      <!-- Value totals per stage (tooltip already shows, but provide accessible text) -->
      <div class="mt-2 grid grid-cols-2 gap-1 sm:hidden">
        <div
          v-for="stage in funnelStages"
          :key="stage.stage_id"
          class="text-xs text-gray-500 dark:text-gray-400 truncate"
        >
          <span class="font-medium text-gray-700 dark:text-gray-300">{{ stage.name }}</span>
          {{ t('dashboard.funnelRecords', { n: stage.count }) }} · {{ formatAmount(stage.value_canonical) }}
        </div>
      </div>
    </template>
  </div>
</template>

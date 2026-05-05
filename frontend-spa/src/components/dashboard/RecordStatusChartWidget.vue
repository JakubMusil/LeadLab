<script setup lang="ts">
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { useI18n } from '@/composables/useI18n'
import { useChartTheme } from '@/composables/useChartTheme'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

const STATUS_COLORS: Record<string, string> = {
  new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
  negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
}

const props = defineProps<{
  recordsByStatus: Record<string, number>
}>()

const { t } = useI18n()
const { tickColor, gridColor } = useChartTheme()

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  new: t('leads.statusNew'),
  contacted: t('leads.statusContacted'),
  proposal: t('leads.statusProposal'),
  negotiation: t('leads.statusNegotiation'),
  won: t('leads.statusWon'),
  lost: t('leads.statusLost'),
  canceled: t('leads.statusCanceled'),
}))

const chartData = computed(() => {
  const entries = Object.entries(props.recordsByStatus)
  return {
    labels: entries.map(([k]) => STATUS_LABELS.value[k] ?? k),
    datasets: [
      {
        data: entries.map(([, v]) => v),
        backgroundColor: entries.map(([k]) => STATUS_COLORS[k] ?? '#6b7280'),
        borderRadius: 4,
        maxBarThickness: 40,
      },
    ],
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { mode: 'index' as const } },
  scales: {
    x: { ticks: { font: { size: 11 }, color: tickColor.value }, grid: { color: gridColor.value } },
    y: { ticks: { precision: 0, color: tickColor.value }, grid: { color: gridColor.value } },
  },
}))
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.recordStatusChart') }}</h3>
    <div style="height: 220px; position: relative">
      <Bar :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

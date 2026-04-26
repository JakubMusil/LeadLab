<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { api } from '@/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import type { ComposeOption } from 'echarts/core'
import type { BarSeriesOption } from 'echarts/charts'
import type { GridComponentOption, TooltipComponentOption } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

type EChartsOption = ComposeOption<BarSeriesOption | GridComponentOption | TooltipComponentOption>

interface ActivityItem {
  id: string
  lead_id: string
  lead_title?: string
  type: string
  content_text: string
  created_at: string
}

interface StatsData {
  total_leads: number
  leads_by_status: Record<string, number>
  total_customers: number
  total_tasks_pending: number
  total_tasks_overdue: number
  pipeline_value: number
  won_value: number
  conversion_rate: number
  recent_activities: ActivityItem[]
}

const firmStore = useFirmStore()
const stats = ref<StatsData | null>(null)
const loading = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const STATUS_LABELS: Record<string, string> = {
  new: 'New', contacted: 'Contacted', proposal: 'Proposal',
  negotiation: 'Negotiation', won: 'Won', lost: 'Lost', canceled: 'Canceled',
}
const STATUS_COLORS: Record<string, string> = {
  new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
  negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
}

const chartOption = computed<EChartsOption>(() => {
  if (!stats.value) return {}
  const entries = Object.entries(stats.value.leads_by_status)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 8, top: 8, bottom: 0, containLabel: true },
    xAxis: {
      type: 'category',
      data: entries.map(([k]) => STATUS_LABELS[k] ?? k),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: entries.map(([k, v]) => ({ value: v, itemStyle: { color: STATUS_COLORS[k] ?? '#6b7280' } })),
      barMaxWidth: 40,
    }],
  }
})

const activityIcons: Record<string, string> = {
  comment: '💬', email_out: '📧', email_in: '📥', call: '📞',
  meeting: '🤝', status_change: '🔄', file_upload: '📎',
  task_assigned: '📋', task_completed: '✅',
}

function activityIcon(type: string) {
  return activityIcons[type] ?? '📌'
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtCurrency(val: number) {
  return new Intl.NumberFormat(undefined, { style: 'decimal', maximumFractionDigits: 0 }).format(val)
}

async function loadStats() {
  if (!firmStore.activeFirm) return
  loading.value = true
  try {
    const res = await api.get<StatsData>('/api/v1/crm/stats')
    if (res.ok) stats.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadStats()
  refreshTimer = setInterval(loadStats, 60_000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

const showSetupBanner = computed(() => {
  if (!firmStore.activeFirm) return false
  return !localStorage.getItem('onboarding_complete_' + firmStore.activeFirm.id)
})
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto space-y-6">
    <!-- Setup banner -->
    <div v-if="showSetupBanner" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-5 flex items-center justify-between gap-4">
      <div>
        <div class="text-sm font-semibold text-red-900 dark:text-red-100">Complete your setup</div>
        <div class="text-xs text-red-700 dark:text-red-300 mt-0.5">You're almost ready! Complete the onboarding steps to get the most out of LeadLab.</div>
      </div>
      <RouterLink to="/app/onboarding" class="flex-shrink-0 px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors">
        Continue setup
      </RouterLink>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && !stats" class="animate-pulse space-y-4">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="h-24 bg-gray-200 dark:bg-gray-700 rounded-2xl" />
      </div>
      <div class="grid lg:grid-cols-3 gap-4">
        <div class="lg:col-span-2 h-64 bg-gray-200 dark:bg-gray-700 rounded-2xl" />
        <div class="h-64 bg-gray-200 dark:bg-gray-700 rounded-2xl" />
      </div>
    </div>

    <template v-else-if="stats">
      <!-- Stat cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total Leads</div>
          <div class="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ stats.total_leads }}</div>
          <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ (stats.conversion_rate * 100).toFixed(1) }}% conversion</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Customers</div>
          <div class="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ stats.total_customers }}</div>
          <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">in address book</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Pipeline</div>
          <div class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ fmtCurrency(stats.pipeline_value) }}</div>
          <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">Won: {{ fmtCurrency(stats.won_value) }}</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Open Tasks</div>
          <div class="text-3xl font-bold mt-1" :class="stats.total_tasks_overdue > 0 ? 'text-red-600' : 'text-gray-900 dark:text-gray-100'">
            {{ stats.total_tasks_pending }}
          </div>
          <div class="text-xs mt-1" :class="stats.total_tasks_overdue > 0 ? 'text-red-500' : 'text-gray-400 dark:text-gray-500'">
            {{ stats.total_tasks_overdue }} overdue
          </div>
        </div>
      </div>

      <!-- Chart + Recent activity -->
      <div class="grid lg:grid-cols-3 gap-4">
        <!-- Pipeline bar chart -->
        <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Pipeline by Status</h3>
          <VChart :option="chartOption" style="height: 220px" autoresize />
        </div>

        <!-- Recent activities -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Recent Activity</h3>
          <div v-if="stats.recent_activities.length === 0" class="text-sm text-gray-400 text-center py-8">
            No recent activity
          </div>
          <ul class="space-y-3 overflow-y-auto max-h-56">
            <li v-for="act in stats.recent_activities" :key="act.id" class="flex items-start gap-2.5">
              <span class="text-base mt-0.5 flex-shrink-0" aria-hidden="true">{{ activityIcon(act.type) }}</span>
              <div class="min-w-0">
                <p class="text-xs text-gray-700 dark:text-gray-300 truncate">
                  <RouterLink v-if="act.lead_id" :to="`/app/leads/${act.lead_id}`" class="font-medium hover:text-red-600">
                    {{ (act as ActivityItem & { lead_title?: string }).lead_title ?? 'Lead' }}
                  </RouterLink>
                  <span v-if="act.content_text"> — {{ act.content_text }}</span>
                </p>
                <p class="text-xs text-gray-400 dark:text-gray-500">{{ formatTime(act.created_at) }}</p>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <!-- Status breakdown -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Status Breakdown</h3>
        <div class="flex flex-wrap gap-3">
          <RouterLink
            v-for="[status, count] in Object.entries(stats.leads_by_status)"
            :key="status"
            :to="`/app/leads?status=${status}`"
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
          >
            <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: STATUS_COLORS[status] ?? '#6b7280' }" />
            <span class="text-sm text-gray-700 dark:text-gray-300">{{ STATUS_LABELS[status] ?? status }}</span>
            <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ count }}</span>
          </RouterLink>
        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400">Failed to load dashboard data.</div>
  </div>
</template>

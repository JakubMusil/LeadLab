<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useFirmStore } from '@/stores/firm'
import { api } from '@/api'
import DateRangePicker from '@/components/DateRangePicker.vue'
import UpgradePrompt from '@/components/UpgradePrompt.vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, FunnelChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
} from 'echarts/components'
import type { ComposeOption } from 'echarts/core'
import type { BarSeriesOption, LineSeriesOption, FunnelSeriesOption } from 'echarts/charts'
import type {
  GridComponentOption,
  TooltipComponentOption,
  LegendComponentOption,
} from 'echarts/components'

use([CanvasRenderer, BarChart, LineChart, FunnelChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

type EChartsOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | FunnelSeriesOption
  | GridComponentOption
  | TooltipComponentOption
  | LegendComponentOption
>

const firmStore = useFirmStore()
const { isPro } = storeToRefs(firmStore)
const loading = ref(false)

// -- Pipeline Velocity --
interface VelocityRow { status: string; avg_hours: number; sample_count: number }
const velocity = ref<VelocityRow[]>([])

// -- Won / Lost by Source --
interface WonLostRow { source: string; won: number; lost: number }
const wonLost = ref<WonLostRow[]>([])
const dateFrom = ref('')
const dateTo = ref('')

// -- Team Performance --
interface TeamRow {
  user_id: string
  email: string
  full_name: string
  leads_owned: number
  tasks_completed: number
  activities_logged: number
}
const team = ref<TeamRow[]>([])
type SortKey = 'full_name' | 'leads_owned' | 'tasks_completed' | 'activities_logged'
const sortKey = ref<SortKey>('leads_owned')
const sortDir = ref<'asc' | 'desc'>('desc')

// -- Trends --
interface WeeklyRow { week_start: string; created: number; closed: number }
interface TrendsData { weekly: WeeklyRow[]; conversion_rate_30d: number }
const trends = ref<TrendsData | null>(null)

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

async function loadVelocity() {
  const res = await api.get<VelocityRow[]>('/api/v1/crm/reports/pipeline-velocity')
  if (res.ok && Array.isArray(res.data)) velocity.value = res.data
}

async function loadWonLost() {
  const params = new URLSearchParams()
  if (dateFrom.value) params.set('date_from', new Date(dateFrom.value).toISOString())
  if (dateTo.value) params.set('date_to', new Date(dateTo.value + 'T23:59:59').toISOString())
  const url = `/api/v1/crm/reports/won-lost-by-source${params.toString() ? '?' + params.toString() : ''}`
  const res = await api.get<WonLostRow[]>(url)
  if (res.ok && Array.isArray(res.data)) wonLost.value = res.data
}

async function loadTeam() {
  const res = await api.get<TeamRow[]>('/api/v1/crm/reports/team-performance')
  if (res.ok && Array.isArray(res.data)) team.value = res.data
}

async function loadTrends() {
  const res = await api.get<TrendsData>('/api/v1/crm/reports/trends')
  if (res.ok && res.data) trends.value = res.data
}

// -- Proposal Analytics --
interface ProposalAnalytics {
  total: number
  draft: number
  sent: number
  viewed: number
  accepted: number
  rejected: number
  expired: number
  acceptance_rate: number
  rejection_rate: number
  avg_time_to_open_hours: number | null
  template_stats: Array<{ template_id: string; name: string }>
}
const proposalAnalytics = ref<ProposalAnalytics | null>(null)

async function loadProposalAnalytics() {
  const res = await api.get<ProposalAnalytics>('/api/v1/crm/reports/proposal-analytics')
  if (res.ok && res.data) proposalAnalytics.value = res.data
}

async function loadAll() {
  if (!firmStore.activeFirm) return
  loading.value = true
  try {
    await Promise.all([loadVelocity(), loadWonLost(), loadTeam(), loadTrends(), loadProposalAnalytics()])
  } finally {
    loading.value = false
  }
}

watch([dateFrom, dateTo], () => loadWonLost())

onMounted(loadAll)

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

function toggleSort(key: SortKey) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

const sortedTeam = computed(() => {
  return [...team.value].sort((a, b) => {
    const av = a[sortKey.value]
    const bv = b[sortKey.value]
    if (typeof av === 'string' && typeof bv === 'string') {
      return sortDir.value === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    return sortDir.value === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
  })
})

function sortIcon(key: SortKey) {
  if (sortKey.value !== key) return '↕'
  return sortDir.value === 'asc' ? '↑' : '↓'
}

// ---------------------------------------------------------------------------
// Chart options
// ---------------------------------------------------------------------------

const STATUS_ORDER = ['new', 'contacted', 'proposal', 'negotiation', 'won', 'lost', 'canceled']
const STATUS_LABELS: Record<string, string> = {
  new: 'New', contacted: 'Contacted', proposal: 'Proposal',
  negotiation: 'Negotiation', won: 'Won', lost: 'Lost', canceled: 'Canceled',
}
const STATUS_COLORS: Record<string, string> = {
  new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
  negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
}

const velocityChartOption = computed<EChartsOption>(() => {
  const sorted = [...velocity.value].sort(
    (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status),
  )
  const maxHours = Math.max(...sorted.map((r) => r.avg_hours), 1)
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p: unknown) => {
        const { name, value } = p as { name: string; value: number }
        return `${STATUS_LABELS[name] ?? name}: ${Number(value).toFixed(1)} h avg (${sorted.find((r) => r.status === name)?.sample_count ?? 0} transitions)`
      },
    },
    series: [
      {
        type: 'funnel',
        sort: 'none',
        left: '5%',
        width: '90%',
        min: 0,
        max: maxHours,
        minSize: '10%',
        maxSize: '100%',
        gap: 4,
        label: {
          show: true,
          formatter: (p: unknown) => {
            const { name, value } = p as { name: string; value: number }
            return `${STATUS_LABELS[name] ?? name}: ${Number(value).toFixed(1)} h`
          },
        },
        data: sorted.map((r) => ({
          name: r.status,
          value: r.avg_hours,
          itemStyle: { color: STATUS_COLORS[r.status] ?? '#6b7280' },
        })),
      },
    ],
  }
})

const SOURCE_LABELS: Record<string, string> = {
  web: 'Web', email: 'Email', referral: 'Referral',
  cold_call: 'Cold Call', social: 'Social', other: 'Other',
}

const wonLostChartOption = computed<EChartsOption>(() => {
  const sources = wonLost.value.map((r) => SOURCE_LABELS[r.source] ?? r.source)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { left: 8, right: 8, top: 8, bottom: 32, containLabel: true },
    xAxis: { type: 'category', data: sources, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: 'Won',
        type: 'bar',
        stack: 'total',
        data: wonLost.value.map((r) => r.won),
        itemStyle: { color: '#22c55e' },
        barMaxWidth: 48,
      },
      {
        name: 'Lost',
        type: 'bar',
        stack: 'total',
        data: wonLost.value.map((r) => r.lost),
        itemStyle: { color: '#ef4444' },
        barMaxWidth: 48,
      },
    ],
  }
})

const trendsChartOption = computed<EChartsOption>(() => {
  if (!trends.value) return {}
  const weeks = trends.value.weekly.map((r) => {
    const d = new Date(r.week_start)
    return `${d.getMonth() + 1}/${d.getDate()}`
  })
  return {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    grid: { left: 8, right: 8, top: 8, bottom: 32, containLabel: true },
    xAxis: { type: 'category', data: weeks, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      {
        name: 'Created',
        type: 'line',
        data: trends.value.weekly.map((r) => r.created),
        itemStyle: { color: '#3b82f6' },
        smooth: true,
      },
      {
        name: 'Closed',
        type: 'line',
        data: trends.value.weekly.map((r) => r.closed),
        itemStyle: { color: '#9ca3af' },
        smooth: true,
      },
    ],
  }
})
</script>

<template>
  <UpgradePrompt
    v-if="!isPro"
    description="Advanced analytics are available on the Pro plan."
  />
  <div v-else class="p-6 max-w-7xl mx-auto space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">Analytics &amp; Reporting</h1>
      <button
        @click="loadAll"
        class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
        :disabled="loading"
        aria-label="Refresh analytics"
      >
        {{ loading ? 'Loading…' : '↻ Refresh' }}
      </button>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && velocity.length === 0" class="animate-pulse grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div v-for="i in 4" :key="i" class="h-64 bg-gray-200 dark:bg-gray-700 rounded-2xl" />
    </div>

    <template v-else>
      <!-- Row 1: Pipeline velocity + Won/Lost by source -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Pipeline velocity funnel -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">Pipeline Velocity</h2>
          <p class="text-xs text-gray-400 dark:text-gray-500 mb-4">Avg. hours a lead spends in each status</p>
          <div v-if="velocity.length === 0" class="flex items-center justify-center h-48 text-sm text-gray-400">
            No status history data yet
          </div>
          <VChart v-else :option="velocityChartOption" style="height: 260px" autoresize />
        </div>

        <!-- Won / Lost by source stacked bar -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="flex flex-wrap items-start justify-between gap-2 mb-4">
            <div>
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Won / Lost by Source</h2>
              <p class="text-xs text-gray-400 dark:text-gray-500">Filterable by date range</p>
            </div>
            <DateRangePicker
              v-model:model-value-from="dateFrom"
              v-model:model-value-to="dateTo"
              label=""
            />
          </div>
          <div v-if="wonLost.length === 0" class="flex items-center justify-center h-48 text-sm text-gray-400">
            No closed leads yet
          </div>
          <VChart v-else :option="wonLostChartOption" style="height: 220px" autoresize />
        </div>
      </div>

      <!-- Row 2: Trends -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <div class="flex flex-wrap items-start justify-between gap-2 mb-4">
          <div>
            <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Lead Trends — last 12 weeks</h2>
            <p class="text-xs text-gray-400 dark:text-gray-500">Created vs. closed (won + lost) per week</p>
          </div>
          <div
            v-if="trends"
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
          >
            <span class="text-xs font-medium">30-day conversion rate:</span>
            <span class="text-sm font-bold">{{ trends.conversion_rate_30d.toFixed(1) }}%</span>
          </div>
        </div>
        <div v-if="!trends || trends.weekly.length === 0" class="flex items-center justify-center h-48 text-sm text-gray-400">
          No trend data yet
        </div>
        <VChart v-else :option="trendsChartOption" style="height: 240px" autoresize />
      </div>

      <!-- Row 3: Team performance -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Team Performance</h2>

        <div v-if="team.length === 0" class="text-sm text-gray-400 text-center py-8">
          No team members found
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm" role="grid" aria-label="Team performance table">
            <thead>
              <tr class="border-b border-gray-100 dark:border-gray-700">
                <th
                  class="text-left py-2 pr-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('full_name')"
                  scope="col"
                  :aria-sort="sortKey === 'full_name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  Member <span aria-hidden="true">{{ sortIcon('full_name') }}</span>
                </th>
                <th
                  class="text-right py-2 px-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('leads_owned')"
                  scope="col"
                  :aria-sort="sortKey === 'leads_owned' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  Leads <span aria-hidden="true">{{ sortIcon('leads_owned') }}</span>
                </th>
                <th
                  class="text-right py-2 px-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('tasks_completed')"
                  scope="col"
                  :aria-sort="sortKey === 'tasks_completed' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  Tasks Done <span aria-hidden="true">{{ sortIcon('tasks_completed') }}</span>
                </th>
                <th
                  class="text-right py-2 pl-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('activities_logged')"
                  scope="col"
                  :aria-sort="sortKey === 'activities_logged' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  Activities <span aria-hidden="true">{{ sortIcon('activities_logged') }}</span>
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50 dark:divide-gray-700/50">
              <tr
                v-for="row in sortedTeam"
                :key="row.user_id"
                class="hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
              >
                <td class="py-3 pr-4">
                  <div class="font-medium text-gray-900 dark:text-gray-100 truncate max-w-[180px]">
                    {{ row.full_name || row.email }}
                  </div>
                  <div class="text-xs text-gray-400 dark:text-gray-500 truncate max-w-[180px]">{{ row.email }}</div>
                </td>
                <td class="py-3 px-4 text-right font-medium text-gray-700 dark:text-gray-300">
                  {{ row.leads_owned }}
                </td>
                <td class="py-3 px-4 text-right font-medium text-gray-700 dark:text-gray-300">
                  {{ row.tasks_completed }}
                </td>
                <td class="py-3 pl-4 text-right font-medium text-gray-700 dark:text-gray-300">
                  {{ row.activities_logged }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Row 4: Proposal Analytics -->
      <div v-if="proposalAnalytics" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Proposal Analytics</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
          <div class="text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
            <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ proposalAnalytics.total }}</div>
            <div class="text-xs text-gray-500 mt-1">Total</div>
          </div>
          <div class="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-xl">
            <div class="text-2xl font-bold text-green-700 dark:text-green-400">{{ proposalAnalytics.accepted }}</div>
            <div class="text-xs text-gray-500 mt-1">Accepted ({{ proposalAnalytics.acceptance_rate }}%)</div>
          </div>
          <div class="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
            <div class="text-2xl font-bold text-red-700 dark:text-red-400">{{ proposalAnalytics.rejected }}</div>
            <div class="text-xs text-gray-500 mt-1">Rejected ({{ proposalAnalytics.rejection_rate }}%)</div>
          </div>
          <div class="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
            <div class="text-2xl font-bold text-blue-700 dark:text-blue-400">
              {{ proposalAnalytics.avg_time_to_open_hours != null ? proposalAnalytics.avg_time_to_open_hours.toFixed(1) + 'h' : '—' }}
            </div>
            <div class="text-xs text-gray-500 mt-1">Avg. Time to Open</div>
          </div>
        </div>
        <div class="flex flex-wrap gap-3">
          <span class="px-2.5 py-1 rounded-lg text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">Draft: {{ proposalAnalytics.draft }}</span>
          <span class="px-2.5 py-1 rounded-lg text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">Sent: {{ proposalAnalytics.sent }}</span>
          <span class="px-2.5 py-1 rounded-lg text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400">Viewed: {{ proposalAnalytics.viewed }}</span>
          <span class="px-2.5 py-1 rounded-lg text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400">Expired: {{ proposalAnalytics.expired }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

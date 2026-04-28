<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import DateRangePicker from '@/components/DateRangePicker.vue'
import UpgradePrompt from '@/components/UpgradePrompt.vue'
import { Bar, Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  BarElement,
  LineElement,
  PointElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend, Filler)

const firmStore = useFirmStore()
const { isPro } = storeToRefs(firmStore)
const { t } = useI18n()
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

// -- Phase 4.5 Realization Metrics --
interface RealizationStatusRow { status: string; count: number; avg_days: number }
interface RealizationTrendRow { week_start: string; created: number; completed: number }
interface RealizationMetrics {
  by_status: RealizationStatusRow[]
  trend: RealizationTrendRow[]
  total: number
  completed_total: number
}
const realizationMetrics = ref<RealizationMetrics | null>(null)

async function loadRealizationMetrics() {
  const res = await api.get<RealizationMetrics>('/api/v1/crm/reports/realization-metrics')
  if (res.ok && res.data) realizationMetrics.value = res.data
}

// -- Phase 4.5 SLA Compliance --
interface SlaCompliance {
  total: number
  green: number
  yellow: number
  red: number
  no_expiry: number
}
const slaCompliance = ref<SlaCompliance | null>(null)

async function loadSlaCompliance() {
  const res = await api.get<SlaCompliance>('/api/v1/crm/reports/sla-compliance')
  if (res.ok && res.data) slaCompliance.value = res.data
}

// -- Phase 4.5 Profitability --
interface ProfitabilityRow {
  entity_id: string
  entity_type: string
  entity_title: string
  total_minutes: number
  total_expenses: number
  total_revenues: number
  profit_loss: number
}
interface Profitability {
  rows: ProfitabilityRow[]
  totals: ProfitabilityRow
}
const profitability = ref<Profitability | null>(null)

async function loadProfitability() {
  const params = new URLSearchParams()
  if (dateFrom.value) params.set('date_from', dateFrom.value)
  if (dateTo.value) params.set('date_to', dateTo.value)
  const url = `/api/v1/crm/reports/profitability${params.toString() ? '?' + params.toString() : ''}`
  const res = await api.get<Profitability>(url)
  if (res.ok && res.data) profitability.value = res.data
}

async function loadAll() {
  if (!firmStore.activeFirm) return
  loading.value = true
  try {
    await Promise.all([
      loadVelocity(), loadWonLost(), loadTeam(), loadTrends(), loadProposalAnalytics(),
      loadRealizationMetrics(), loadSlaCompliance(), loadProfitability(),
    ])
  } finally {
    loading.value = false
  }
}

watch([dateFrom, dateTo], () => { loadWonLost(); loadProfitability() })

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

const velocityChartData = computed(() => {
  const sorted = [...velocity.value].sort(
    (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status),
  )
  return {
    labels: sorted.map((r) => STATUS_LABELS[r.status] ?? r.status),
    datasets: [
      {
        label: t('analytics.avgHoursInStatus'),
        data: sorted.map((r) => r.avg_hours),
        backgroundColor: sorted.map((r) => STATUS_COLORS[r.status] ?? '#6b7280'),
        borderRadius: 4,
        maxBarThickness: 48,
      },
    ],
  }
})

const velocityChartOptions = computed(() => ({
  indexAxis: 'y' as const,
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: { raw: unknown; dataIndex: number }) => {
          const sorted = [...velocity.value].sort(
            (a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status),
          )
          const row = sorted[ctx.dataIndex]
          return ` ${Number(ctx.raw).toFixed(1)} h avg (${row?.sample_count ?? 0} transitions)`
        },
      },
    },
  },
  scales: { x: { ticks: { precision: 1 } }, y: { ticks: { font: { size: 11 } } } },
}))

const SOURCE_LABELS: Record<string, string> = {
  web: 'Web', email: 'Email', referral: 'Referral',
  cold_call: 'Cold Call', social: 'Social', other: 'Other',
}

const wonLostChartData = computed(() => ({
  labels: wonLost.value.map((r) => SOURCE_LABELS[r.source] ?? r.source),
  datasets: [
    {
      label: t('analytics.won'),
      data: wonLost.value.map((r) => r.won),
      backgroundColor: '#22c55e',
      borderRadius: 4,
      maxBarThickness: 48,
    },
    {
      label: t('analytics.lost'),
      data: wonLost.value.map((r) => r.lost),
      backgroundColor: '#ef4444',
      borderRadius: 4,
      maxBarThickness: 48,
    },
  ],
}))

const wonLostChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' as const, labels: { font: { size: 11 } } } },
  scales: { x: { stacked: true, ticks: { font: { size: 11 } } }, y: { stacked: true, ticks: { precision: 0 } } },
}

const trendsChartData = computed(() => {
  if (!trends.value) return { labels: [], datasets: [] }
  return {
    labels: trends.value.weekly.map((r) => {
      const d = new Date(r.week_start)
      return `${d.getMonth() + 1}/${d.getDate()}`
    }),
    datasets: [
      {
        label: t('analytics.created'),
        data: trends.value.weekly.map((r) => r.created),
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.1)',
        tension: 0.3,
        fill: true,
      },
      {
        label: t('analytics.closed'),
        data: trends.value.weekly.map((r) => r.closed),
        borderColor: '#9ca3af',
        backgroundColor: 'rgba(156,163,175,0.1)',
        tension: 0.3,
        fill: true,
      },
    ],
  }
})

const trendsChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' as const, labels: { font: { size: 11 } } } },
  scales: { x: { ticks: { font: { size: 11 } } }, y: { ticks: { precision: 0 } } },
}
</script>

<template>
  <UpgradePrompt
    v-if="!isPro"
    :description="t('analytics.proDescription')"
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
        {{ loading ? t('analytics.loading') : t('analytics.refresh') }}
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
          <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('analytics.pipelineVelocity') }}</h2>
          <p class="text-xs text-gray-400 dark:text-gray-500 mb-4">{{ t('analytics.pipelineVelocityDesc') }}</p>
          <div v-if="velocity.length === 0" class="flex items-center justify-center h-48 text-sm text-gray-400">
            {{ t('analytics.noStatusHistory') }}
          </div>
          <div v-else style="height: 260px; position: relative">
            <Bar :data="velocityChartData" :options="velocityChartOptions" />
          </div>
        </div>

        <!-- Won / Lost by source stacked bar -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="flex flex-wrap items-start justify-between gap-2 mb-4">
            <div>
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('analytics.wonLostBySource') }}</h2>
              <p class="text-xs text-gray-400 dark:text-gray-500">{{ t('analytics.wonLostBySourceDesc') }}</p>
            </div>
            <DateRangePicker
              v-model:model-value-from="dateFrom"
              v-model:model-value-to="dateTo"
              label=""
            />
          </div>
          <div v-if="wonLost.length === 0" class="flex items-center justify-center h-48 text-sm text-gray-400">
            {{ t('analytics.noClosedLeads') }}
          </div>
          <div v-else style="height: 220px; position: relative">
            <Bar :data="wonLostChartData" :options="wonLostChartOptions" />
          </div>
        </div>
      </div>

      <!-- Row 2: Trends -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <div class="flex flex-wrap items-start justify-between gap-2 mb-4">
          <div>
            <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('analytics.leadTrends') }}</h2>
            <p class="text-xs text-gray-400 dark:text-gray-500">{{ t('analytics.leadTrendsDesc') }}</p>
          </div>
          <div
            v-if="trends"
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
          >
            <span class="text-xs font-medium">{{ t('analytics.conversionRate') }}</span>
            <span class="text-sm font-bold">{{ trends.conversion_rate_30d.toFixed(1) }}%</span>
          </div>
        </div>
        <div v-if="!trends || trends.weekly.length === 0" class="flex items-center justify-center h-48 text-sm text-gray-400">
          {{ t('analytics.noTrendData') }}
        </div>
        <div v-else style="height: 240px; position: relative">
          <Line :data="trendsChartData" :options="trendsChartOptions" />
        </div>
      </div>

      <!-- Row 3: Team performance -->
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('analytics.teamPerformance') }}</h2>

        <div v-if="team.length === 0" class="text-sm text-gray-400 text-center py-8">
          {{ t('analytics.noTeamMembers') }}
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
                  {{ t('analytics.colMember') }} <span aria-hidden="true">{{ sortIcon('full_name') }}</span>
                </th>
                <th
                  class="text-right py-2 px-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('leads_owned')"
                  scope="col"
                  :aria-sort="sortKey === 'leads_owned' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  {{ t('analytics.colLeads') }} <span aria-hidden="true">{{ sortIcon('leads_owned') }}</span>
                </th>
                <th
                  class="text-right py-2 px-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('tasks_completed')"
                  scope="col"
                  :aria-sort="sortKey === 'tasks_completed' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  {{ t('analytics.colTasksDone') }} <span aria-hidden="true">{{ sortIcon('tasks_completed') }}</span>
                </th>
                <th
                  class="text-right py-2 pl-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200"
                  @click="toggleSort('activities_logged')"
                  scope="col"
                  :aria-sort="sortKey === 'activities_logged' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'"
                >
                  {{ t('analytics.colActivities') }} <span aria-hidden="true">{{ sortIcon('activities_logged') }}</span>
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
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('analytics.proposalAnalytics') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
          <div class="text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl">
            <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ proposalAnalytics.total }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.total') }}</div>
          </div>
          <div class="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-xl">
            <div class="text-2xl font-bold text-green-700 dark:text-green-400">{{ proposalAnalytics.accepted }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.accepted', { rate: proposalAnalytics.acceptance_rate }) }}</div>
          </div>
          <div class="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl">
            <div class="text-2xl font-bold text-red-700 dark:text-red-400">{{ proposalAnalytics.rejected }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.rejected', { rate: proposalAnalytics.rejection_rate }) }}</div>
          </div>
          <div class="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
            <div class="text-2xl font-bold text-blue-700 dark:text-blue-400">
              {{ proposalAnalytics.avg_time_to_open_hours != null ? proposalAnalytics.avg_time_to_open_hours.toFixed(1) + 'h' : '—' }}
            </div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.avgTimeToOpen') }}</div>
          </div>
        </div>
        <div class="flex flex-wrap gap-3">
          <span class="px-2.5 py-1 rounded-lg text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{{ t('analytics.draft') }}: {{ proposalAnalytics.draft }}</span>
          <span class="px-2.5 py-1 rounded-lg text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400">{{ t('analytics.sent') }}: {{ proposalAnalytics.sent }}</span>
          <span class="px-2.5 py-1 rounded-lg text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400">{{ t('analytics.viewed') }}: {{ proposalAnalytics.viewed }}</span>
          <span class="px-2.5 py-1 rounded-lg text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400">{{ t('analytics.expired') }}: {{ proposalAnalytics.expired }}</span>
        </div>
      </div>
    </template>

    <!-- Row 5: Realization Metrics (Phase 4.5) -->
    <template v-if="!loading && realizationMetrics">
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('analytics.realizationStatusOverview') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div v-for="row in realizationMetrics.by_status" :key="row.status" class="text-center">
            <div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ row.count }}</div>
            <div class="text-xs font-medium text-gray-500 mt-0.5">{{ row.status }}</div>
            <div class="text-xs text-gray-400">{{ t('analytics.avgDays', { days: row.avg_days }) }}</div>
          </div>
        </div>
        <div class="mt-4 flex gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span>{{ t('analytics.totalCount', { count: realizationMetrics.total }) }}</span>
          <span>{{ t('analytics.completedCount', { count: realizationMetrics.completed_total }) }}</span>
        </div>
      </div>
    </template>

    <!-- Row 6: SLA Compliance (Phase 4.5) -->
    <template v-if="!loading && slaCompliance">
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('analytics.slaCompliance') }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div class="text-center">
            <div class="text-2xl font-bold text-green-600 dark:text-green-400">{{ slaCompliance.green }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.slaOk') }}</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{{ slaCompliance.yellow }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.slaSoon') }}</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-red-600 dark:text-red-400">{{ slaCompliance.red }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.slaExpired') }}</div>
          </div>
          <div class="text-center">
            <div class="text-2xl font-bold text-gray-400 dark:text-gray-500">{{ slaCompliance.no_expiry }}</div>
            <div class="text-xs text-gray-500 mt-1">{{ t('analytics.slaNoExpiry') }}</div>
          </div>
        </div>
        <div class="mt-3 text-xs text-gray-400 dark:text-gray-500">{{ t('analytics.slaOnlyOpen', { total: slaCompliance.total }) }}</div>
      </div>
    </template>

    <!-- Row 7: Profitability (Phase 4.5) -->
    <template v-if="!loading && profitability">
      <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('analytics.profitability') }}</h2>
        <div class="overflow-x-auto">
          <table class="w-full text-xs text-left">
            <thead>
              <tr class="border-b border-gray-100 dark:border-gray-700">
                <th class="pb-2 text-gray-500 font-medium">{{ t('analytics.colRealization') }}</th>
                <th class="pb-2 text-right text-gray-500 font-medium">{{ t('analytics.colTime') }}</th>
                <th class="pb-2 text-right text-gray-500 font-medium">{{ t('analytics.colCost') }}</th>
                <th class="pb-2 text-right text-gray-500 font-medium">{{ t('analytics.colRevenue') }}</th>
                <th class="pb-2 text-right text-gray-500 font-medium">{{ t('analytics.colProfitLoss') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in profitability.rows" :key="row.entity_id" class="border-b border-gray-50 dark:border-gray-700/50">
                <td class="py-1.5 text-gray-800 dark:text-gray-200">{{ row.entity_title }}</td>
                <td class="py-1.5 text-right text-gray-600 dark:text-gray-400">{{ Math.round(row.total_minutes / 60 * 10) / 10 }}</td>
                <td class="py-1.5 text-right text-gray-600 dark:text-gray-400">{{ row.total_expenses.toLocaleString() }}</td>
                <td class="py-1.5 text-right text-gray-600 dark:text-gray-400">{{ row.total_revenues.toLocaleString() }}</td>
                <td class="py-1.5 text-right font-semibold" :class="row.profit_loss >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                  {{ row.profit_loss >= 0 ? '+' : '' }}{{ row.profit_loss.toLocaleString() }}
                </td>
              </tr>
              <!-- Totals row -->
              <tr class="border-t-2 border-gray-200 dark:border-gray-600 font-semibold">
                <td class="pt-2 text-gray-900 dark:text-gray-100">{{ t('analytics.colTotal') }}</td>
                <td class="pt-2 text-right text-gray-800 dark:text-gray-200">{{ Math.round(profitability.totals.total_minutes / 60 * 10) / 10 }}</td>
                <td class="pt-2 text-right text-gray-800 dark:text-gray-200">{{ profitability.totals.total_expenses.toLocaleString() }}</td>
                <td class="pt-2 text-right text-gray-800 dark:text-gray-200">{{ profitability.totals.total_revenues.toLocaleString() }}</td>
                <td class="pt-2 text-right" :class="profitability.totals.profit_loss >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                  {{ profitability.totals.profit_loss >= 0 ? '+' : '' }}{{ profitability.totals.profit_loss.toLocaleString() }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { api } from '@/api'
import { Bar } from 'vue-chartjs'
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { VueDraggable } from 'vue-draggable-plus'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

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

interface WidgetConfig {
  id: string
  visible: boolean
  order: number
}

type WidgetId = 'stat_cards' | 'pipeline_chart' | 'recent_activity' | 'status_breakdown'

const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: 'stat_cards', visible: true, order: 0 },
  { id: 'pipeline_chart', visible: true, order: 1 },
  { id: 'recent_activity', visible: true, order: 2 },
  { id: 'status_breakdown', visible: true, order: 3 },
]

const WIDGET_LABELS: Record<WidgetId, string> = {
  stat_cards: 'Stat Cards',
  pipeline_chart: 'Pipeline Chart',
  recent_activity: 'Recent Activity',
  status_breakdown: 'Status Breakdown',
}

const firmStore = useFirmStore()
const stats = ref<StatsData | null>(null)
const loading = ref(false)
const widgets = ref<WidgetConfig[]>([...DEFAULT_WIDGETS])
const showLayoutEditor = ref(false)
const savingLayout = ref(false)
let refreshTimer: ReturnType<typeof setInterval> | null = null

const STATUS_LABELS: Record<string, string> = {
  new: 'New', contacted: 'Contacted', proposal: 'Proposal',
  negotiation: 'Negotiation', won: 'Won', lost: 'Lost', canceled: 'Canceled',
}
const STATUS_COLORS: Record<string, string> = {
  new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
  negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
}

const chartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] }
  const entries = Object.entries(stats.value.leads_by_status)
  return {
    labels: entries.map(([k]) => STATUS_LABELS[k] ?? k),
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

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { mode: 'index' as const } },
  scales: {
    x: { ticks: { font: { size: 11 } } },
    y: { ticks: { precision: 0 } },
  },
}

const visibleWidgets = computed(() =>
  widgets.value
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order),
)

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

async function loadLayout() {
  const res = await api.get<{ layout: WidgetConfig[] }>('/api/v1/crm/dashboard-layout')
  if (res.ok && res.data.layout && res.data.layout.length > 0) {
    // Merge saved layout with defaults (handle new widgets added after save)
    const saved = res.data.layout
    const savedIds = new Set(saved.map((w) => w.id))
    const merged = [
      ...saved,
      ...DEFAULT_WIDGETS.filter((d) => !savedIds.has(d.id)),
    ]
    widgets.value = merged
  }
}

async function saveLayout() {
  savingLayout.value = true
  try {
    // Update order from current array position
    const layout = widgets.value.map((w, i) => ({ ...w, order: i }))
    widgets.value = layout
    await api.put('/api/v1/crm/dashboard-layout', { layout })
  } finally {
    savingLayout.value = false
    showLayoutEditor.value = false
  }
}

function onDragEnd() {
  // Re-index order after drag
  widgets.value = widgets.value.map((w, i) => ({ ...w, order: i }))
  saveLayout()
}

function toggleWidget(id: string) {
  const w = widgets.value.find((w) => w.id === id)
  if (w) w.visible = !w.visible
}

onMounted(async () => {
  await loadLayout()
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

    <!-- Dashboard header with layout button -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h2>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        @click="showLayoutEditor = !showLayoutEditor"
        :aria-expanded="showLayoutEditor"
      >
        <span aria-hidden="true">⊞</span>
        Customise layout
      </button>
    </div>

    <!-- Layout editor -->
    <div v-if="showLayoutEditor" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Widget Layout</h3>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-400">Drag to reorder · toggle to show/hide</span>
          <button
            class="px-3 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            :disabled="savingLayout"
            @click="saveLayout"
          >
            {{ savingLayout ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
      <VueDraggable v-model="widgets" handle=".drag-handle" class="space-y-2" @end="onDragEnd">
        <div
          v-for="widget in widgets"
          :key="widget.id"
          class="flex items-center gap-3 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 cursor-default"
        >
          <span class="drag-handle cursor-grab text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" title="Drag to reorder" aria-hidden="true">⠿</span>
          <span class="flex-1 text-sm text-gray-700 dark:text-gray-300">{{ WIDGET_LABELS[widget.id as WidgetId] ?? widget.id }}</span>
          <button
            type="button"
            class="relative inline-flex h-5 w-9 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[color:var(--brand-color)] focus:ring-offset-2"
            :class="widget.visible ? 'bg-[color:var(--brand-color)]' : 'bg-gray-300 dark:bg-gray-600'"
            :aria-label="`${widget.visible ? 'Hide' : 'Show'} ${WIDGET_LABELS[widget.id as WidgetId] ?? widget.id}`"
            :aria-checked="widget.visible"
            role="switch"
            @click="toggleWidget(widget.id)"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform mt-0.5"
              :class="widget.visible ? 'translate-x-4' : 'translate-x-0.5'"
            />
          </button>
        </div>
      </VueDraggable>
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
      <template v-for="widget in visibleWidgets" :key="widget.id">

        <!-- Stat cards -->
        <div v-if="widget.id === 'stat_cards'" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
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

        <!-- Pipeline chart + Recent activity -->
        <div v-else-if="widget.id === 'pipeline_chart' || widget.id === 'recent_activity'" class="grid lg:grid-cols-3 gap-4">
          <template v-if="visibleWidgets.some((w) => w.id === 'pipeline_chart') && visibleWidgets.some((w) => w.id === 'recent_activity') && widget.id === 'pipeline_chart'">
            <!-- Pipeline bar chart -->
            <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Pipeline by Status</h3>
              <div style="height: 220px; position: relative">
                <Bar :data="chartData" :options="chartOptions" />
              </div>
            </div>

            <!-- Recent activities (rendered alongside chart) -->
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
          </template>

          <!-- Chart only (no recent activity) -->
          <template v-else-if="widget.id === 'pipeline_chart' && !visibleWidgets.some((w) => w.id === 'recent_activity')">
            <div class="lg:col-span-3 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Pipeline by Status</h3>
              <div style="height: 220px; position: relative">
                <Bar :data="chartData" :options="chartOptions" />
              </div>
            </div>
          </template>

          <!-- Recent activity only (no chart) -->
          <template v-else-if="widget.id === 'recent_activity' && !visibleWidgets.some((w) => w.id === 'pipeline_chart')">
            <div class="lg:col-span-3 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">Recent Activity</h3>
              <div v-if="stats.recent_activities.length === 0" class="text-sm text-gray-400 text-center py-8">
                No recent activity
              </div>
              <ul class="space-y-3">
                <li v-for="act in stats.recent_activities" :key="act.id" class="flex items-start gap-2.5">
                  <span class="text-base mt-0.5 flex-shrink-0" aria-hidden="true">{{ activityIcon(act.type) }}</span>
                  <div class="min-w-0">
                    <p class="text-xs text-gray-700 dark:text-gray-300 truncate">
                      <RouterLink v-if="act.lead_id" :to="`/app/leads/${act.lead_id}`" class="font-medium hover:text-red-600">
                        {{ act.lead_title ?? 'Lead' }}
                      </RouterLink>
                      <span v-if="act.content_text"> — {{ act.content_text }}</span>
                    </p>
                    <p class="text-xs text-gray-400 dark:text-gray-500">{{ formatTime(act.created_at) }}</p>
                  </div>
                </li>
              </ul>
            </div>
          </template>
        </div>

        <!-- Status breakdown -->
        <div v-else-if="widget.id === 'status_breakdown'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
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
    </template>

    <div v-else class="text-center py-12 text-gray-400">Failed to load dashboard data.</div>
  </div>
</template>

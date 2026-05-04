<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { useRecordsStore, RECORD_STATUSES, getStatusMeta, type RecordOut } from '@/stores/records'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'
import { Bar } from 'vue-chartjs'
import { useMoney } from '@/composables/useMoney'
import { useChartTheme } from '@/composables/useChartTheme'
import {
  Chart as ChartJS,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
} from 'chart.js'
import { VueDraggable } from 'vue-draggable-plus'
import { useI18n } from '@/composables/useI18n'
import { RouterLink, useRouter } from 'vue-router'
import type { Component } from 'vue'
import {
  ChatBubbleLeftIcon,
  EnvelopeIcon,
  InboxArrowDownIcon,
  PhoneIcon,
  UsersIcon,
  ArrowsRightLeftIcon,
  PaperClipIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  MapPinIcon,
  XMarkIcon,
  Squares2X2Icon,
  PlusIcon,
  StarIcon,
} from '@heroicons/vue/24/outline'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

const { t } = useI18n()

interface ActivityItem {
  id: string
  record_id: string
  record_title?: string
  type: string
  content_text: string
  created_at: string
}

interface StatsData {
  total_records: number
  records_by_status: Record<string, number>
  total_customers: number
  total_tasks_pending: number
  total_tasks_overdue: number
  pipeline_value: number
  won_value: number
  conversion_rate: number
  recent_activities: ActivityItem[]
  mixed_currencies?: boolean
}

interface WidgetConfig {
  id: string
  visible: boolean
  order: number
}

type WidgetId = 'stat_cards' | 'pipeline_chart' | 'recent_activity' | 'status_breakdown' | 'my_top_leads' | 'quick_create_lead'

const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: 'stat_cards', visible: true, order: 0 },
  { id: 'quick_create_lead', visible: true, order: 1 },
  { id: 'pipeline_chart', visible: true, order: 2 },
  { id: 'recent_activity', visible: true, order: 3 },
  { id: 'my_top_leads', visible: true, order: 4 },
  { id: 'status_breakdown', visible: true, order: 5 },
]

const WIDGET_LABELS = computed<Record<WidgetId, string>>(() => ({
  stat_cards: t('dashboard.statCards'),
  pipeline_chart: t('dashboard.pipelineByStatus'),
  recent_activity: t('dashboard.recentActivity'),
  status_breakdown: t('dashboard.statusBreakdown'),
  my_top_leads: t('dashboard.myTopLeads'),
  quick_create_lead: t('dashboard.quickCreateLead'),
}))

const firmStore = useFirmStore()
const authStore = useAuthStore()
const recordsStore = useRecordsStore()
const toast = useToast()
const router = useRouter()
const { formatAmount } = useMoney()
const { tickColor, gridColor } = useChartTheme()
const stats = ref<StatsData | null>(null)
const loading = ref(false)
const widgets = ref<WidgetConfig[]>([...DEFAULT_WIDGETS])
const showLayoutEditor = ref(false)
const savingLayout = ref(false)

// "My top records" widget state
const myTopRecords = ref<RecordOut[]>([])
const myTopRecordsLoading = ref(false)

// "Quick create record" widget state
const qcTitle = ref('')
const qcStatus = ref('new')
const qcValue = ref('')
const qcSubmitting = ref(false)
const qcError = ref('')

let refreshTimer: ReturnType<typeof setInterval> | null = null

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  new: t('leads.statusNew'), contacted: t('leads.statusContacted'),
  proposal: t('leads.statusProposal'), negotiation: t('leads.statusNegotiation'),
  won: t('leads.statusWon'), lost: t('leads.statusLost'), canceled: t('leads.statusCanceled'),
}))

const STATUS_COLORS: Record<string, string> = {
  new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
  negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
}

const chartData = computed(() => {
  if (!stats.value) return { labels: [], datasets: [] }
  const entries = Object.entries(stats.value.records_by_status)
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

const visibleWidgets = computed(() =>
  widgets.value
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order),
)

const activityIcons: Record<string, Component> = {
  comment: ChatBubbleLeftIcon,
  email_out: EnvelopeIcon,
  email_in: InboxArrowDownIcon,
  call: PhoneIcon,
  meeting: UsersIcon,
  status_change: ArrowsRightLeftIcon,
  file_upload: PaperClipIcon,
  task_assigned: ClipboardDocumentListIcon,
  task_completed: CheckCircleIcon,
}

function activityIcon(type: string): Component {
  return activityIcons[type] ?? MapPinIcon
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtCurrency(val: number) {
  return formatAmount(val)
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

async function loadMyTopLeads() {
  if (!firmStore.activeFirm || !authStore.user) return
  myTopRecordsLoading.value = true
  try {
    const params = new URLSearchParams()
    params.set('assigned_to', String(authStore.user.id))
    params.set('page', '1')
    params.set('page_size', '50')
    const res = await api.get<RecordOut[]>(`/api/v1/crm/records?${params}`)
    if (res.ok) {
      // Exclude closed statuses (won/lost/canceled) — focus on active records.
      const active = res.data.filter((l) => !['won', 'lost', 'canceled'].includes(l.status))
      const sorted = active
        .slice()
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, 5)
      myTopRecords.value = sorted
    }
  } finally {
    myTopRecordsLoading.value = false
  }
}

async function submitQuickCreate() {
  const title = qcTitle.value.trim()
  if (!title) {
    qcError.value = t('dashboard.qcTitleRequired')
    return
  }
  qcSubmitting.value = true
  qcError.value = ''
  try {
    const valueNum = qcValue.value ? parseFloat(qcValue.value) : null
    const res = await recordsStore.createRecord({
      title,
      status: qcStatus.value,
      value: valueNum != null && !isNaN(valueNum) ? valueNum : null,
    })
    if (res.ok) {
      toast.success(t('dashboard.qcCreated'))
      qcTitle.value = ''
      qcStatus.value = 'new'
      qcValue.value = ''
      // Refresh widgets that depend on record data
      loadStats()
      loadMyTopLeads()
    } else {
      qcError.value = res.error ?? t('dashboard.qcFailed')
    }
  } finally {
    qcSubmitting.value = false
  }
}

function openRecordDetail(id: string) {
  router.push(`/app/records/${id}`)
}

function statusLabelFor(status: string): string {
  return STATUS_LABELS.value[status] ?? getStatusMeta(status).label
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
  loadMyTopLeads()
  refreshTimer = setInterval(loadStats, 60_000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

const dismissSetupBanner = ref(false)

const showSetupBanner = computed(() => {
  if (dismissSetupBanner.value) return false
  if (!firmStore.activeFirm) return false
  return !localStorage.getItem('onboarding_complete_' + firmStore.activeFirm.id)
})

function hideSetupBanner() {
  dismissSetupBanner.value = true
  if (firmStore.activeFirm) {
    localStorage.setItem('onboarding_complete_' + firmStore.activeFirm.id, '1')
  }
}
</script>

<template>
  <div class="p-6 space-y-6">
    <!-- Setup banner -->
    <div v-if="showSetupBanner" class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-5 flex items-center justify-between gap-4 relative">
      <div>
        <div class="text-sm font-semibold text-red-900 dark:text-red-100">{{ t('dashboard.completeSetup') }}</div>
        <div class="text-xs text-red-700 dark:text-red-300 mt-0.5">{{ t('dashboard.setupBannerText') }}</div>
      </div>
      <div class="flex items-center gap-3 flex-shrink-0">
        <RouterLink to="/app/onboarding" class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors">
          {{ t('dashboard.continueSetup') }}
        </RouterLink>
        <button
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors text-sm px-2 py-1"
          @click="hideSetupBanner"
          aria-label="Dismiss banner"
        ><XMarkIcon class="w-4 h-4" /></button>
      </div>
    </div>

    <!-- Dashboard header with layout button -->
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h2>
      <button
        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        @click="showLayoutEditor = !showLayoutEditor"
        :aria-expanded="showLayoutEditor"
      >
        <Squares2X2Icon class="w-4 h-4" aria-hidden="true" />
        {{ t('dashboard.customiseLayout') }}
      </button>
    </div>

    <!-- Layout editor -->
    <div v-if="showLayoutEditor" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('dashboard.widgetLayout') }}</h3>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-400">{{ t('dashboard.dragToReorder') }}</span>
          <button
            class="px-3 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            :disabled="savingLayout"
            @click="saveLayout"
          >
            {{ savingLayout ? t('dashboard.saving') : t('dashboard.save') }}
          </button>
        </div>
      </div>
      <VueDraggable v-model="widgets" handle=".drag-handle" class="space-y-2" @end="onDragEnd">
        <div
          v-for="widget in widgets"
          :key="widget.id"
          class="flex items-center gap-3 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 cursor-default"
        >
          <span class="drag-handle cursor-grab text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" :title="t('dashboard.dragToReorder')" aria-hidden="true">⠿</span>
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
            <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.totalLeads') }}</div>
            <div class="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ stats.total_records }}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('dashboard.conversion', { rate: (stats.conversion_rate * 100).toFixed(1) }) }}</div>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
            <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.customers') }}</div>
            <div class="text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ stats.total_customers }}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('dashboard.inAddressBook') }}</div>
          </div>
          <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
            <div class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('dashboard.pipeline') }}</div>
            <div class="text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1">{{ fmtCurrency(stats.pipeline_value) }}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500 mt-1">{{ t('dashboard.won', { value: fmtCurrency(stats.won_value) }) }}</div>
            <div v-if="stats.mixed_currencies" class="text-xs text-amber-600 mt-1">{{ t('currencySettings.warningMixedCurrencies', { currency: firmStore.activeFirm?.default_currency }) }}</div>
          </div>
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

        <!-- Pipeline chart + Recent activity -->
        <div v-else-if="widget.id === 'pipeline_chart' || widget.id === 'recent_activity'" class="grid lg:grid-cols-3 gap-4">
          <template v-if="visibleWidgets.some((w) => w.id === 'pipeline_chart') && visibleWidgets.some((w) => w.id === 'recent_activity') && widget.id === 'pipeline_chart'">
            <!-- Pipeline bar chart -->
            <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.pipelineByStatus') }}</h3>
              <div style="height: 220px; position: relative">
                <Bar :data="chartData" :options="chartOptions" />
              </div>
            </div>

            <!-- Recent activities (rendered alongside chart) -->
            <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.recentActivity') }}</h3>
              <div v-if="stats.recent_activities.length === 0" class="text-sm text-gray-400 text-center py-8">
                {{ t('dashboard.noRecentActivity') }}
              </div>
              <ul class="space-y-3 overflow-y-auto max-h-56">
                <li v-for="act in stats.recent_activities" :key="act.id" class="flex items-start gap-2.5">
                  <component :is="activityIcon(act.type)" class="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true" />
                  <div class="min-w-0">
                    <p class="text-xs text-gray-700 dark:text-gray-300 truncate">
                      <RouterLink v-if="act.record_id" :to="`/app/records/${act.record_id}`" class="font-medium hover:text-red-600">
                        {{ (act as ActivityItem & { record_title?: string }).record_title ?? 'Record' }}
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
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.pipelineByStatus') }}</h3>
              <div style="height: 220px; position: relative">
                <Bar :data="chartData" :options="chartOptions" />
              </div>
            </div>
          </template>

          <!-- Recent activity only (no chart) -->
          <template v-else-if="widget.id === 'recent_activity' && !visibleWidgets.some((w) => w.id === 'pipeline_chart')">
            <div class="lg:col-span-3 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.recentActivity') }}</h3>
              <div v-if="stats.recent_activities.length === 0" class="text-sm text-gray-400 text-center py-8">
                {{ t('dashboard.noRecentActivity') }}
              </div>
              <ul class="space-y-3">
                <li v-for="act in stats.recent_activities" :key="act.id" class="flex items-start gap-2.5">
                  <component :is="activityIcon(act.type)" class="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true" />
                  <div class="min-w-0">
                    <p class="text-xs text-gray-700 dark:text-gray-300 truncate">
                      <RouterLink v-if="act.record_id" :to="`/app/records/${act.record_id}`" class="font-medium hover:text-red-600">
                        {{ act.record_title ?? 'Record' }}
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

        <!-- Quick create record -->
        <div v-else-if="widget.id === 'quick_create_lead'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <PlusIcon class="w-4 h-4 text-red-600" aria-hidden="true" />
              {{ t('dashboard.quickCreateLead') }}
            </h3>
          </div>
          <form class="grid grid-cols-1 md:grid-cols-12 gap-2" @submit.prevent="submitQuickCreate">
            <input
              v-model="qcTitle"
              type="text"
              :placeholder="t('dashboard.qcTitlePlaceholder')"
              :aria-label="t('dashboard.qcTitlePlaceholder')"
              class="md:col-span-5 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
            />
            <select
              v-model="qcStatus"
              :aria-label="t('dashboard.qcStatusLabel')"
              class="md:col-span-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
            >
              <option v-for="s in RECORD_STATUSES" :key="s.value" :value="s.value">{{ statusLabelFor(s.value) }}</option>
            </select>
            <input
              v-model="qcValue"
              type="number"
              min="0"
              step="any"
              :placeholder="t('dashboard.qcValuePlaceholder')"
              :aria-label="t('dashboard.qcValuePlaceholder')"
              class="md:col-span-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
            />
            <button
              type="submit"
              :disabled="qcSubmitting || !qcTitle.trim()"
              class="md:col-span-2 bg-red-600 hover:bg-red-700 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ qcSubmitting ? t('common.saving') : t('dashboard.qcCreate') }}
            </button>
          </form>
          <p v-if="qcError" class="mt-2 text-xs text-red-600 dark:text-red-400">{{ qcError }}</p>
        </div>

        <!-- My top records -->
        <div v-else-if="widget.id === 'my_top_leads'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <StarIcon class="w-4 h-4 text-yellow-500" aria-hidden="true" />
              {{ t('dashboard.myTopLeads') }}
            </h3>
            <RouterLink to="/app/records" class="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600">{{ t('dashboard.viewAll') }}</RouterLink>
          </div>
          <div v-if="myTopLeadsLoading && myTopLeads.length === 0" class="space-y-2 animate-pulse">
            <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
          </div>
          <div v-else-if="myTopLeads.length === 0" class="text-sm text-gray-400 text-center py-6">
            {{ t('dashboard.myTopLeadsEmpty') }}
          </div>
          <ul v-else class="divide-y divide-gray-50 dark:divide-gray-700">
            <li
              v-for="record in myTopRecords"
              :key="record.id"
              class="flex items-center gap-3 py-2.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 -mx-2 px-2 rounded-lg transition-colors"
              @click="openRecordDetail(record.id)"
            >
              <span
                class="flex-shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-semibold"
                :class="(record.score ?? 0) >= 75 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
                  : (record.score ?? 0) >= 50 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'"
                :title="t('dashboard.scoreTitle', { score: record.score ?? 0 })"
              >
                {{ record.score ?? 0 }}
              </span>
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ record.title }}</div>
                <div class="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {{ record.company_name || record.contact_person_name || '—' }}
                </div>
              </div>
              <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium flex-shrink-0" :class="getStatusMeta(record.status).color">
                {{ statusLabelFor(record.status) }}
              </span>
            </li>
          </ul>
        </div>

        <!-- Status breakdown -->
        <div v-else-if="widget.id === 'status_breakdown'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.statusBreakdown') }}</h3>
          <div class="flex flex-wrap gap-3">
            <RouterLink
              v-for="[status, count] in Object.entries(stats.records_by_status)"
              :key="status"
              :to="`/app/records?status=${status}`"
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

    <div v-else class="text-center py-12 text-gray-400">{{ t('dashboard.failedToLoad') }}</div>
  </div>
</template>

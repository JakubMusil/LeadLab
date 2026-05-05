<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePipelineStore } from '@/stores/pipeline'
import { useDashboardLayoutStore, type WidgetConfig, type DashboardRange } from '@/stores/dashboard'
import { api } from '@/api'
import { VueDraggable } from 'vue-draggable-plus'
import { useI18n } from '@/composables/useI18n'
import {
  Squares2X2Icon,
} from '@heroicons/vue/24/outline'

// Widget components
import StatCardsWidget from '@/components/dashboard/StatCardsWidget.vue'
import PipelineChartWidget from '@/components/dashboard/PipelineChartWidget.vue'
import RecentActivityWidget from '@/components/dashboard/RecentActivityWidget.vue'
import QuickCreateRecordWidget from '@/components/dashboard/QuickCreateRecordWidget.vue'
import MyTopRecordsWidget from '@/components/dashboard/MyTopRecordsWidget.vue'
import StatusBreakdownWidget from '@/components/dashboard/StatusBreakdownWidget.vue'
import CategoryOverviewWidget from '@/components/dashboard/CategoryOverviewWidget.vue'
import StageFunnelWidget from '@/components/dashboard/StageFunnelWidget.vue'
import RecordStatusChartWidget from '@/components/dashboard/RecordStatusChartWidget.vue'
import MyDayWidget from '@/components/dashboard/MyDayWidget.vue'
import StaleRecordsWidget from '@/components/dashboard/StaleRecordsWidget.vue'
import UpcomingCheckpointsWidget from '@/components/dashboard/UpcomingCheckpointsWidget.vue'
import PipelineTrendWidget from '@/components/dashboard/PipelineTrendWidget.vue'
import WinLossWidget from '@/components/dashboard/WinLossWidget.vue'
import ActivityHeatmapWidget from '@/components/dashboard/ActivityHeatmapWidget.vue'
import TeamLeaderboardWidget from '@/components/dashboard/TeamLeaderboardWidget.vue'
import DashboardTour from '@/components/dashboard/DashboardTour.vue'
import WidgetConfigDialog from '@/components/dashboard/WidgetConfigDialog.vue'
import SetupProgressWidget from '@/components/dashboard/SetupProgressWidget.vue'
import { widgetHasConfig } from '@/stores/dashboard'
import { Cog6ToothIcon } from '@heroicons/vue/24/outline'

const { t } = useI18n()
const firmStore = useFirmStore()
const pipelineStore = usePipelineStore()
const layoutStore = useDashboardLayoutStore()

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

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
  pipeline_value_canonical?: number
  won_value: number
  won_value_canonical?: number
  canonical_currency?: string
  conversion_rate: number
  avg_cycle_days?: number
  recent_activities: ActivityItem[]
  mixed_currencies?: boolean
}

const stats = ref<StatsData | null>(null)
const loading = ref(false)
const showLayoutEditor = ref(false)
const configuringWidgetId = ref<string | null>(null)

// Ref to MyTopRecordsWidget to call load() after quick-create
const myTopRecordsRef = ref<InstanceType<typeof MyTopRecordsWidget> | null>(null)

let refreshTimer: ReturnType<typeof setInterval> | null = null
let rangeDebounceTimer: ReturnType<typeof setTimeout> | null = null

// ---------------------------------------------------------------------------
// Widget label map for layout editor
// ---------------------------------------------------------------------------

type WidgetId = 'stat_cards' | 'pipeline_chart' | 'recent_activity' | 'status_breakdown' | 'my_top_records' | 'quick_create_record' | 'category_overview' | 'stage_funnel' | 'record_status_chart' | 'my_day' | 'stale_records' | 'upcoming_checkpoints' | 'pipeline_trend' | 'win_loss' | 'activity_heatmap' | 'team_leaderboard' | 'setup_progress'

const WIDGET_LABELS = computed<Record<WidgetId, string>>(() => ({
  stat_cards: t('dashboard.statCards'),
  pipeline_chart: t('dashboard.pipelineByStatus'),
  recent_activity: t('dashboard.recentActivity'),
  status_breakdown: t('dashboard.statusBreakdown'),
  my_top_records: t('dashboard.myTopRecords'),
  quick_create_record: t('dashboard.quickCreateRecord'),
  category_overview: t('dashboard.categoryOverview'),
  stage_funnel: t('dashboard.stageFunnel'),
  record_status_chart: t('dashboard.recordStatusChart'),
  my_day: t('dashboard.myDay'),
  stale_records: t('dashboard.staleRecords'),
  upcoming_checkpoints: t('dashboard.upcomingCheckpoints'),
  pipeline_trend: t('dashboard.pipelineTrend'),
  win_loss: t('dashboard.winLoss'),
  activity_heatmap: t('dashboard.activityHeatmap'),
  team_leaderboard: t('dashboard.teamLeaderboard'),
  setup_progress: t('dashboard.setupProgress'),
}))

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadStats() {
  if (!firmStore.activeFirm) return
  loading.value = true
  try {
    const params = new URLSearchParams({ range: layoutStore.globalRange })
    const res = await api.get<StatsData>(`/api/v1/crm/stats?${params.toString()}`)
    if (res.ok) stats.value = res.data
  } finally {
    loading.value = false
  }
}

function onRecordCreated() {
  loadStats()
  myTopRecordsRef.value?.load()
}

// ---------------------------------------------------------------------------
// Range picker options
// ---------------------------------------------------------------------------

const RANGE_OPTIONS = computed(() => [
  { value: '7d' as DashboardRange, label: t('dashboard.range7d') },
  { value: '30d' as DashboardRange, label: t('dashboard.range30d') },
  { value: '90d' as DashboardRange, label: t('dashboard.range90d') },
  { value: 'qtd' as DashboardRange, label: t('dashboard.rangeQtd') },
  { value: 'ytd' as DashboardRange, label: t('dashboard.rangeYtd') },
  { value: 'all' as DashboardRange, label: t('dashboard.rangeAll') },
])

const COL_SPAN_CLASSES: Record<number, string> = {
  1: 'md:col-span-1',
  2: 'md:col-span-2',
  3: 'md:col-span-3',
  4: 'md:col-span-4',
  5: 'md:col-span-5',
  6: 'md:col-span-6',
  7: 'md:col-span-7',
  8: 'md:col-span-8',
  9: 'md:col-span-9',
  10: 'md:col-span-10',
  11: 'md:col-span-11',
  12: 'md:col-span-12',
}

// ---------------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------------

const visibleWidgets = computed(() => layoutStore.visibleWidgets)

function effectiveColSpan(widget: WidgetConfig): number {
  const PAIRED = new Set(['pipeline_chart', 'recent_activity'])
  if (PAIRED.has(widget.id)) {
    const bothVisible = visibleWidgets.value.some(w => w.id === 'pipeline_chart') &&
                        visibleWidgets.value.some(w => w.id === 'recent_activity')
    if (!bothVisible) return 12
  }
  return widget.colSpan ?? 12
}

function colSpanClass(widget: WidgetConfig): string {
  return COL_SPAN_CLASSES[effectiveColSpan(widget)] ?? 'md:col-span-12'
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

onMounted(async () => {
  await layoutStore.loadLayout()
  await loadStats()
  if (pipelineStore.categories.length === 0) {
    pipelineStore.fetchCategories()
  }
  refreshTimer = setInterval(loadStats, 60_000)
})

watch(() => layoutStore.globalRange, () => {
  // Debounce: avoid multiple rapid API calls if user clicks quickly through ranges
  if (rangeDebounceTimer) clearTimeout(rangeDebounceTimer)
  rangeDebounceTimer = setTimeout(() => loadStats(), 300)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (rangeDebounceTimer) clearTimeout(rangeDebounceTimer)
})
</script>

<template>
  <div class="p-6 space-y-6">
    <DashboardTour />

    <!-- Dashboard header with layout button -->
    <div class="flex flex-wrap items-center justify-between gap-y-2">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Dashboard</h2>
      <div class="flex flex-wrap items-center gap-2 gap-y-2">
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          @click="showLayoutEditor = !showLayoutEditor"
          :aria-expanded="showLayoutEditor"
        >
          <Squares2X2Icon class="w-4 h-4" aria-hidden="true" />
          {{ t('dashboard.customiseLayout') }}
        </button>
        <div class="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1">
          <button
            v-for="r in RANGE_OPTIONS"
            :key="r.value"
            type="button"
            class="px-2.5 py-1 text-xs font-medium rounded-lg transition-colors"
            :class="layoutStore.globalRange === r.value ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
            @click="layoutStore.setGlobalRange(r.value)"
          >
            {{ r.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Layout editor -->
    <div v-if="showLayoutEditor" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('dashboard.widgetLayout') }}</h3>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-400">{{ t('dashboard.dragToReorder') }}</span>
          <button
            class="px-3 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            :disabled="layoutStore.savingLayout"
            @click="layoutStore.saveLayout()"
          >
            {{ layoutStore.savingLayout ? t('dashboard.saving') : t('dashboard.save') }}
          </button>
        </div>
      </div>
      <VueDraggable v-model="layoutStore.widgets" handle=".drag-handle" class="space-y-2" @end="layoutStore.onDragEnd()">
        <div
          v-for="widget in layoutStore.widgets"
          :key="widget.id"
          class="flex items-center gap-3 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 cursor-default"
        >
          <span class="drag-handle cursor-grab text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" :title="t('dashboard.dragToReorder')" aria-hidden="true">⠿</span>
          <span class="flex-1 text-sm text-gray-700 dark:text-gray-300">{{ WIDGET_LABELS[widget.id as WidgetId] ?? widget.id }}</span>
          <button
            v-if="widgetHasConfig(widget.id)"
            type="button"
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors p-1 rounded"
            :aria-label="`${t('dashboard.cfgConfigure')} ${WIDGET_LABELS[widget.id as WidgetId] ?? widget.id}`"
            :title="t('dashboard.cfgConfigure')"
            @click="configuringWidgetId = widget.id"
          >
            <Cog6ToothIcon class="w-4 h-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            class="relative inline-flex h-5 w-9 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[color:var(--brand-color)] focus:ring-offset-2"
            :class="widget.visible ? 'bg-[color:var(--brand-color)]' : 'bg-gray-300 dark:bg-gray-600'"
            :aria-label="`${widget.visible ? 'Hide' : 'Show'} ${WIDGET_LABELS[widget.id as WidgetId] ?? widget.id}`"
            :aria-checked="widget.visible"
            role="switch"
            @click="layoutStore.toggleWidget(widget.id)"
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
      <div class="grid grid-cols-12 gap-4">
        <div
          v-for="widget in visibleWidgets"
          :key="widget.id"
          class="col-span-12"
          :class="colSpanClass(widget)"
        >
          <StatCardsWidget
            v-if="widget.id === 'stat_cards'"
            :stats="stats"
          />

          <PipelineChartWidget
            v-else-if="widget.id === 'pipeline_chart'"
            :records-by-status="stats.records_by_status"
          />

          <RecentActivityWidget
            v-else-if="widget.id === 'recent_activity'"
            :activities="stats.recent_activities"
          />

          <QuickCreateRecordWidget
            v-else-if="widget.id === 'quick_create_record'"
            @created="onRecordCreated"
          />

          <MyTopRecordsWidget
            v-else-if="widget.id === 'my_top_records'"
            ref="myTopRecordsRef"
          />

          <StatusBreakdownWidget
            v-else-if="widget.id === 'status_breakdown'"
            :records-by-status="stats.records_by_status"
          />

          <CategoryOverviewWidget
            v-else-if="widget.id === 'category_overview'"
          />

          <StageFunnelWidget
            v-else-if="widget.id === 'stage_funnel'"
          />

          <RecordStatusChartWidget
            v-else-if="widget.id === 'record_status_chart'"
            :records-by-status="stats.records_by_status"
          />

          <MyDayWidget
            v-else-if="widget.id === 'my_day'"
          />

          <StaleRecordsWidget
            v-else-if="widget.id === 'stale_records'"
          />

          <UpcomingCheckpointsWidget
            v-else-if="widget.id === 'upcoming_checkpoints'"
          />

          <PipelineTrendWidget
            v-else-if="widget.id === 'pipeline_trend'"
          />

          <WinLossWidget
            v-else-if="widget.id === 'win_loss'"
            :stats="stats"
          />

          <ActivityHeatmapWidget
            v-else-if="widget.id === 'activity_heatmap'"
          />

          <TeamLeaderboardWidget
            v-else-if="widget.id === 'team_leaderboard'"
          />

          <SetupProgressWidget
            v-else-if="widget.id === 'setup_progress'"
          />
        </div>
      </div>
    </template>

    <div v-else class="text-center py-12 text-gray-400">{{ t('dashboard.failedToLoad') }}</div>

    <WidgetConfigDialog
      :widget-id="configuringWidgetId"
      :widget-label="configuringWidgetId ? WIDGET_LABELS[configuringWidgetId as WidgetId] : ''"
      @close="configuringWidgetId = null"
    />
  </div>
</template>

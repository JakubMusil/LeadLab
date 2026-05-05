<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePipelineStore } from '@/stores/pipeline'
import { useDashboardLayoutStore, type WidgetConfig } from '@/stores/dashboard'
import { api } from '@/api'
import { VueDraggable } from 'vue-draggable-plus'
import { useI18n } from '@/composables/useI18n'
import { RouterLink } from 'vue-router'
import {
  Squares2X2Icon,
  XMarkIcon,
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

// Ref to MyTopRecordsWidget to call load() after quick-create
const myTopRecordsRef = ref<InstanceType<typeof MyTopRecordsWidget> | null>(null)

let refreshTimer: ReturnType<typeof setInterval> | null = null

// ---------------------------------------------------------------------------
// Widget label map for layout editor
// ---------------------------------------------------------------------------

type WidgetId = 'stat_cards' | 'pipeline_chart' | 'recent_activity' | 'status_breakdown' | 'my_top_records' | 'quick_create_record' | 'category_overview' | 'stage_funnel' | 'record_status_chart' | 'my_day' | 'stale_records' | 'upcoming_checkpoints'

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
}))

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

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

function onRecordCreated() {
  loadStats()
  myTopRecordsRef.value?.load()
}

// ---------------------------------------------------------------------------
// Layout helpers
// ---------------------------------------------------------------------------

const visibleWidgets = computed(() => layoutStore.visibleWidgets)

function bothChartAndActivity(widget: WidgetConfig) {
  return (
    visibleWidgets.value.some((w) => w.id === 'pipeline_chart') &&
    visibleWidgets.value.some((w) => w.id === 'recent_activity') &&
    widget.id === 'pipeline_chart'
  )
}

// ---------------------------------------------------------------------------
// Setup banner
// ---------------------------------------------------------------------------

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

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
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
      <template v-for="widget in visibleWidgets" :key="widget.id">

        <!-- Stat cards -->
        <StatCardsWidget
          v-if="widget.id === 'stat_cards'"
          :stats="stats"
        />

        <!-- Pipeline chart + Recent activity (rendered as a pair when both visible) -->
        <div
          v-else-if="widget.id === 'pipeline_chart' || widget.id === 'recent_activity'"
          class="grid lg:grid-cols-3 gap-4"
        >
          <!-- Both visible: chart 2/3, activity 1/3 -->
          <template v-if="bothChartAndActivity(widget)">
            <div class="lg:col-span-2">
              <PipelineChartWidget :records-by-status="stats.records_by_status" />
            </div>
            <div>
              <RecentActivityWidget :activities="stats.recent_activities" />
            </div>
          </template>

          <!-- Chart only -->
          <template v-else-if="widget.id === 'pipeline_chart' && !visibleWidgets.some((w) => w.id === 'recent_activity')">
            <div class="lg:col-span-3">
              <PipelineChartWidget :records-by-status="stats.records_by_status" />
            </div>
          </template>

          <!-- Recent activity only -->
          <template v-else-if="widget.id === 'recent_activity' && !visibleWidgets.some((w) => w.id === 'pipeline_chart')">
            <div class="lg:col-span-3">
              <RecentActivityWidget :activities="stats.recent_activities" />
            </div>
          </template>
        </div>

        <!-- Quick create record -->
        <QuickCreateRecordWidget
          v-else-if="widget.id === 'quick_create_record'"
          @created="onRecordCreated"
        />

        <!-- My top records -->
        <MyTopRecordsWidget
          v-else-if="widget.id === 'my_top_records'"
          ref="myTopRecordsRef"
        />

        <!-- Status breakdown -->
        <StatusBreakdownWidget
          v-else-if="widget.id === 'status_breakdown'"
          :records-by-status="stats.records_by_status"
        />

        <!-- Category overview -->
        <CategoryOverviewWidget
          v-else-if="widget.id === 'category_overview'"
        />

        <!-- Stage funnel -->
        <StageFunnelWidget
          v-else-if="widget.id === 'stage_funnel'"
        />

        <!-- Record status chart (legacy optional) -->
        <RecordStatusChartWidget
          v-else-if="widget.id === 'record_status_chart'"
          :records-by-status="stats.records_by_status"
        />

        <!-- My day (tasks + checkpoints feed) -->
        <MyDayWidget
          v-else-if="widget.id === 'my_day'"
        />

        <!-- Stale records -->
        <StaleRecordsWidget
          v-else-if="widget.id === 'stale_records'"
        />

        <!-- Upcoming checkpoints -->
        <UpcomingCheckpointsWidget
          v-else-if="widget.id === 'upcoming_checkpoints'"
        />

      </template>
    </template>

    <div v-else class="text-center py-12 text-gray-400">{{ t('dashboard.failedToLoad') }}</div>
  </div>
</template>

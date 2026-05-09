import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DashboardRange = '7d' | '30d' | '90d' | 'qtd' | 'ytd' | 'all'
export type DashboardScope = 'mine' | 'firm'
export type DashboardAudience = 'all' | 'admin'

export interface WidgetSize {
  w: number
  h: number
}

export type WidgetSortOption = 'score' | 'value' | 'stale'

export interface WidgetConfigOptions {
  category_id?: string | null
  scope?: DashboardScope
  range?: DashboardRange
  sort?: WidgetSortOption
  limit?: number
  days?: number
}

// ---------------------------------------------------------------------------
// Per-widget config schema
//
// Drives the WidgetConfigDialog form: each entry lists the config fields a
// widget exposes to the user. Widgets that don't appear in this map have no
// configurable options and their gear icon stays hidden.
// ---------------------------------------------------------------------------

export type WidgetConfigFieldType = 'range' | 'scope' | 'category' | 'sort' | 'number'

export interface WidgetConfigField {
  key: keyof WidgetConfigOptions
  type: WidgetConfigFieldType
  /** Translation key under `dashboard.cfg*` for the field's label */
  labelKey: string
  /** For 'number' type: clamp range */
  min?: number
  max?: number
  /** For 'sort' type: allowed values */
  sortOptions?: WidgetSortOption[]
}

export const WIDGET_CONFIG_SCHEMA: Record<string, WidgetConfigField[] | undefined> = {
  my_top_records: [
    { key: 'sort', type: 'sort', labelKey: 'cfgSort', sortOptions: ['score', 'value', 'stale'] },
    { key: 'limit', type: 'number', labelKey: 'cfgLimit', min: 3, max: 20 },
  ],
  stale_records: [
    { key: 'days', type: 'number', labelKey: 'cfgDaysThreshold', min: 1, max: 90 },
    { key: 'limit', type: 'number', labelKey: 'cfgLimit', min: 3, max: 20 },
  ],
  upcoming_checkpoints: [
    { key: 'scope', type: 'scope', labelKey: 'cfgScope' },
    { key: 'days', type: 'number', labelKey: 'cfgDaysAhead', min: 1, max: 60 },
  ],
  category_overview: [
    { key: 'range', type: 'range', labelKey: 'cfgTimeRange' },
    { key: 'scope', type: 'scope', labelKey: 'cfgScope' },
  ],
  stage_funnel: [
    { key: 'category_id', type: 'category', labelKey: 'cfgCategory' },
    { key: 'range', type: 'range', labelKey: 'cfgTimeRange' },
  ],
  pipeline_trend: [
    { key: 'category_id', type: 'category', labelKey: 'cfgCategory' },
    { key: 'range', type: 'range', labelKey: 'cfgTimeRange' },
  ],
}

export function widgetHasConfig(id: string): boolean {
  const fields = WIDGET_CONFIG_SCHEMA[id]
  return Array.isArray(fields) && fields.length > 0
}

export interface WidgetConfig {
  id: string
  visible: boolean
  order: number
  colSpan?: number
  size?: WidgetSize
  config?: WidgetConfigOptions
  audience?: DashboardAudience
}

// ---------------------------------------------------------------------------
// Default layout
// ---------------------------------------------------------------------------

export const DEFAULT_WIDGETS: WidgetConfig[] = [
  // Row 1: My day (full width — most important)
  { id: 'my_day', colSpan: 12, visible: true, order: 0, audience: 'all' },
  // Row 2: Focus next + daily goals
  { id: 'focus_next', colSpan: 6, visible: true, order: 1, audience: 'all' },
  { id: 'daily_goals', colSpan: 6, visible: true, order: 2, audience: 'all' },
  // Row 3: Quick create + upcoming checkpoints
  { id: 'quick_create_record', colSpan: 6, visible: true, order: 3, audience: 'all' },
  { id: 'upcoming_checkpoints', colSpan: 6, visible: true, order: 4, audience: 'all' },
  // Row 4: My top records (full width)
  { id: 'my_top_records', colSpan: 12, visible: true, order: 5, audience: 'all' },
  // Row 5: Stale records + recent wins
  { id: 'stale_records', colSpan: 6, visible: true, order: 6, audience: 'all' },
  { id: 'recent_wins', colSpan: 6, visible: true, order: 7, audience: 'all' },
  // Row 6: Activity heatmap + team leaderboard
  { id: 'activity_heatmap', colSpan: 6, visible: true, order: 8, audience: 'all' },
  { id: 'team_leaderboard', colSpan: 6, visible: true, order: 9, audience: 'admin' },
  // Row 7: Setup progress (full width, admin)
  { id: 'setup_progress', colSpan: 12, visible: true, order: 10, audience: 'admin' },
  // --- Hidden by default: analytics / stat widgets ---
  { id: 'stat_cards', colSpan: 12, visible: false, order: 11, audience: 'all' },
  { id: 'pipeline_chart', colSpan: 8, visible: false, order: 12, audience: 'all' },
  { id: 'recent_activity', colSpan: 4, visible: false, order: 13, audience: 'all' },
  { id: 'status_breakdown', colSpan: 12, visible: false, order: 14, audience: 'all' },
  { id: 'category_overview', colSpan: 12, visible: false, order: 15, audience: 'all' },
  { id: 'stage_funnel', colSpan: 8, visible: false, order: 16, audience: 'all' },
  { id: 'record_status_chart', colSpan: 12, visible: false, order: 17, audience: 'all' },
  { id: 'pipeline_trend', colSpan: 6, visible: false, order: 18, audience: 'all' },
  { id: 'win_loss', colSpan: 4, visible: false, order: 19, audience: 'all' },
]

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useDashboardLayoutStore = defineStore('dashboardLayout', () => {
  const widgets = ref<WidgetConfig[]>([...DEFAULT_WIDGETS])
  const savingLayout = ref(false)
  const globalRange = ref<DashboardRange>('30d')

  const visibleWidgets = computed(() =>
    widgets.value
      .filter((w) => w.visible)
      .sort((a, b) => a.order - b.order),
  )

  function getWidgetEntry(id: string): WidgetConfig | undefined {
    return widgets.value.find((w) => w.id === id)
  }

  function getWidgetConfigOptions(id: string): WidgetConfigOptions {
    return getWidgetEntry(id)?.config ?? {}
  }

  function updateWidgetConfigOptions(id: string, updates: Partial<WidgetConfigOptions>) {
    const entry = getWidgetEntry(id)
    if (entry) {
      entry.config = { ...entry.config, ...updates }
    }
  }

  function toggleWidget(id: string) {
    const w = getWidgetEntry(id)
    if (w) w.visible = !w.visible
  }

  function reindex() {
    widgets.value = widgets.value.map((w, i) => ({ ...w, order: i }))
  }

  async function loadLayout(): Promise<void> {
    const res = await api.get<{ layout: WidgetConfig[]; globalRange?: string }>('/api/v1/crm/dashboard-layout')
    if (res.ok && res.data.layout && res.data.layout.length > 0) {
      const saved = res.data.layout
      const savedIds = new Set(saved.map((w) => w.id))
      // Merge saved layout with defaults (handle new widgets added after save)
      const merged = [
        ...saved,
        ...DEFAULT_WIDGETS.filter((d) => !savedIds.has(d.id)),
      ]
      widgets.value = merged
      if (res.data.globalRange) globalRange.value = res.data.globalRange as DashboardRange
    }
  }

  async function saveLayout(): Promise<void> {
    savingLayout.value = true
    try {
      reindex()
      await api.put('/api/v1/crm/dashboard-layout', { layout: widgets.value, globalRange: globalRange.value })
    } finally {
      savingLayout.value = false
    }
  }

  function setGlobalRange(r: DashboardRange) {
    globalRange.value = r
    // Fire-and-forget: persist the new range immediately so it survives page reload
    saveLayout().catch(() => undefined)
  }

  function onDragEnd() {
    reindex()
    // Fire-and-forget: save errors are non-critical (layout restores on next load)
    saveLayout().catch(() => undefined)
  }

  return {
    widgets,
    visibleWidgets,
    savingLayout,
    globalRange,
    setGlobalRange,
    getWidgetEntry,
    getWidgetConfigOptions,
    updateWidgetConfigOptions,
    toggleWidget,
    reindex,
    loadLayout,
    saveLayout,
    onDragEnd,
  }
})

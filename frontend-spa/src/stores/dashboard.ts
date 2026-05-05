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

export interface WidgetConfigOptions {
  category_id?: string | null
  scope?: DashboardScope
  range?: DashboardRange
  sort?: 'score' | 'value' | 'stale'
  limit?: number
}

export interface WidgetConfig {
  id: string
  visible: boolean
  order: number
  size?: WidgetSize
  config?: WidgetConfigOptions
  audience?: DashboardAudience
}

// ---------------------------------------------------------------------------
// Default layout
// ---------------------------------------------------------------------------

export const DEFAULT_WIDGETS: WidgetConfig[] = [
  { id: 'stat_cards', visible: true, order: 0, audience: 'all' },
  { id: 'quick_create_record', visible: true, order: 1, audience: 'all' },
  { id: 'category_overview', visible: true, order: 2, audience: 'all' },
  { id: 'stage_funnel', visible: true, order: 3, audience: 'all' },
  { id: 'my_day', visible: true, order: 4, audience: 'all' },
  { id: 'upcoming_checkpoints', visible: true, order: 5, audience: 'all' },
  { id: 'pipeline_chart', visible: true, order: 6, audience: 'all' },
  { id: 'recent_activity', visible: true, order: 7, audience: 'all' },
  { id: 'my_top_records', visible: true, order: 8, audience: 'all' },
  { id: 'stale_records', visible: true, order: 9, audience: 'all' },
  { id: 'status_breakdown', visible: true, order: 10, audience: 'all' },
  { id: 'record_status_chart', visible: false, order: 11, audience: 'all' },
]

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useDashboardLayoutStore = defineStore('dashboardLayout', () => {
  const widgets = ref<WidgetConfig[]>([...DEFAULT_WIDGETS])
  const savingLayout = ref(false)

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
      entry.config = { ...(entry.config ?? {}), ...updates }
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
    const res = await api.get<{ layout: WidgetConfig[] }>('/api/v1/crm/dashboard-layout')
    if (res.ok && res.data.layout && res.data.layout.length > 0) {
      const saved = res.data.layout
      const savedIds = new Set(saved.map((w) => w.id))
      // Merge saved layout with defaults (handle new widgets added after save)
      const merged = [
        ...saved,
        ...DEFAULT_WIDGETS.filter((d) => !savedIds.has(d.id)),
      ]
      widgets.value = merged
    }
  }

  async function saveLayout(): Promise<void> {
    savingLayout.value = true
    try {
      reindex()
      await api.put('/api/v1/crm/dashboard-layout', { layout: widgets.value })
    } finally {
      savingLayout.value = false
    }
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

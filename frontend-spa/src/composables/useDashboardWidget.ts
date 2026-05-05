import { computed } from 'vue'
import { useDashboardLayoutStore, type WidgetConfigOptions, type DashboardRange, type DashboardScope } from '@/stores/dashboard'

/**
 * Per-widget composable that provides reactive access to the widget's config
 * (category_id, scope, range, sort, limit) stored inside the dashboard layout.
 *
 * Usage inside a widget component:
 *   const { range, categoryId, scope, updateConfig } = useDashboardWidget('my_top_records')
 */
export function useDashboardWidget(id: string) {
  const layoutStore = useDashboardLayoutStore()

  const config = computed<WidgetConfigOptions>(() => layoutStore.getWidgetConfigOptions(id))

  const range = computed<DashboardRange>(() => config.value.range ?? '30d')
  const categoryId = computed<string | null>(() => config.value.category_id ?? null)
  const scope = computed<DashboardScope>(() => config.value.scope ?? 'mine')
  const sort = computed(() => config.value.sort ?? 'score')
  const limit = computed<number>(() => config.value.limit ?? 5)

  function updateConfig(updates: Partial<WidgetConfigOptions>) {
    layoutStore.updateWidgetConfigOptions(id, updates)
  }

  return {
    config,
    range,
    categoryId,
    scope,
    sort,
    limit,
    updateConfig,
  }
}

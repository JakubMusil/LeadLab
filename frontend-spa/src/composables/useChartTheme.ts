import { computed } from 'vue'
import { useTheme } from '@/composables/useTheme'

/**
 * Returns reactive chart color tokens that adapt to the current dark/light theme.
 * Color values are read from the CSS custom properties defined in main.css so
 * there is a single source of truth: --chart-tick-color, --chart-grid-color,
 * and --chart-legend-color.
 */
export function useChartTheme() {
  const { isDark } = useTheme()

  function cssVar(name: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  }

  // Re-derive on every isDark change so the chart re-renders with updated colors.
  const tickColor = computed(() => { isDark.value; return cssVar('--chart-tick-color') })
  const gridColor = computed(() => { isDark.value; return cssVar('--chart-grid-color') })
  const legendColor = computed(() => { isDark.value; return cssVar('--chart-legend-color') })

  return { tickColor, gridColor, legendColor }
}

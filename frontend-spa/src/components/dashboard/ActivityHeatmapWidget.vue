<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

interface TrendPoint {
  date: string
  value: number
}

interface TrendData {
  metric: string
  range: string
  points: TrendPoint[]
}

const { t } = useI18n()

const data = ref<TrendData | null>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await api.get<TrendData>(
      '/api/v1/crm/dashboard/trend?metric=activities&range=90d',
    )
    if (res.ok) data.value = res.data
  } finally {
    loading.value = false
  }
}

// Build a 13-week × 7-day grid ending today
const WEEKS = 13
const DAYS = 7

const grid = computed(() => {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  // Start from the Sunday (or Monday) WEEKS*7 days ago
  const startDate = new Date(today)
  startDate.setDate(today.getDate() - WEEKS * DAYS + 1)

  // Map date string → value
  const map = new Map<string, number>()
  for (const p of data.value?.points ?? []) {
    map.set(p.date, p.value)
  }

  const maxVal = Math.max(1, ...Array.from(map.values()))

  const weeks: { date: Date; value: number; intensity: number }[][] = []
  let current = new Date(startDate)
  for (let w = 0; w < WEEKS; w++) {
    const week: { date: Date; value: number; intensity: number }[] = []
    for (let d = 0; d < DAYS; d++) {
      const dateStr = current.toISOString().slice(0, 10)
      const value = map.get(dateStr) ?? 0
      const intensity = value === 0 ? 0 : Math.ceil((value / maxVal) * 4)
      week.push({ date: new Date(current), value, intensity })
      current.setDate(current.getDate() + 1)
    }
    weeks.push(week)
  }
  return weeks
})

const DAY_LABELS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

// Intensity → Tailwind color class
function cellClass(intensity: number): string {
  switch (intensity) {
    case 0: return 'bg-gray-100 dark:bg-gray-700'
    case 1: return 'bg-amber-100 dark:bg-amber-900/40'
    case 2: return 'bg-amber-300 dark:bg-amber-700'
    case 3: return 'bg-amber-500 dark:bg-amber-500'
    case 4: return 'bg-amber-600 dark:bg-amber-400'
    default: return 'bg-gray-100 dark:bg-gray-700'
  }
}

function cellTitle(cell: { date: Date; value: number }): string {
  return `${cell.date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}: ${cell.value}`
}

defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header -->
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
      {{ t('dashboard.activityHeatmap') }}
    </h3>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="animate-pulse">
      <div class="h-28 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="data && data.points.every((p) => p.value === 0)"
      class="text-center py-6 text-sm text-gray-400"
    >
      {{ t('dashboard.activityHeatmapEmpty') }}
    </div>

    <!-- Heatmap grid -->
    <template v-else-if="data">
      <div class="overflow-x-auto">
        <div class="flex gap-0.5 min-w-0">
          <!-- Day-of-week labels -->
          <div class="flex flex-col gap-0.5 mr-1">
            <div
              v-for="(label, di) in DAY_LABELS"
              :key="di"
              class="h-3 w-4 text-[9px] text-gray-400 dark:text-gray-500 flex items-center"
            >
              {{ di % 2 === 1 ? label : '' }}
            </div>
          </div>
          <!-- Week columns -->
          <div
            v-for="(week, wi) in grid"
            :key="wi"
            class="flex flex-col gap-0.5"
          >
            <div
              v-for="(cell, di) in week"
              :key="di"
              class="w-3 h-3 rounded-sm transition-colors"
              :class="cellClass(cell.intensity)"
              :title="cellTitle(cell)"
              role="img"
              :aria-label="cellTitle(cell)"
            />
          </div>
        </div>
      </div>
      <!-- Legend -->
      <div class="flex items-center gap-1 mt-2 text-[10px] text-gray-400">
        <span>{{ t('dashboard.heatmapLess') }}</span>
        <div v-for="i in 5" :key="i" class="w-3 h-3 rounded-sm" :class="cellClass(i - 1)" />
        <span>{{ t('dashboard.heatmapMore') }}</span>
      </div>
    </template>
  </div>
</template>

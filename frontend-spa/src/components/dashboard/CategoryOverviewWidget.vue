<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { useDashboardWidget } from '@/composables/useDashboardWidget'
import { api } from '@/api'

interface CategoryOverviewItem {
  category_id: string
  name: string
  icon: string
  color: string
  records_total: number
  records_open: number
  records_won: number
  value_open_canonical: number
  value_won_canonical: number
  win_rate: number
  sparkline: number[]
}

interface CategoryOverviewData {
  canonical_currency: string | null
  items: CategoryOverviewItem[]
  uncategorized: CategoryOverviewItem | null
}

const { t } = useI18n()
const { formatAmount } = useMoney()
const router = useRouter()
const { range, scope } = useDashboardWidget('category_overview')

const data = ref<CategoryOverviewData | null>(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('range', range.value)
    if (scope.value === 'mine') params.set('owner_id', 'me')
    const res = await api.get<CategoryOverviewData>(`/api/v1/crm/dashboard/category-overview?${params.toString()}`)
    if (res.ok) data.value = res.data
  } finally {
    loading.value = false
  }
}

/** Build an SVG polyline path string from sparkline data (30 points). */
function sparklinePath(points: number[]): string {
  if (!points || points.length === 0) return ''
  const max = Math.max(...points, 1)
  const w = 100
  const h = 28
  const coords = points.map((v, i) => {
    const x = (i / (points.length - 1)) * w
    const y = h - (v / max) * h
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  return coords.join(' ')
}

function openCategory(categoryId: string) {
  router.push({ path: '/app/records', query: { category: categoryId } })
}

watch([range, scope], () => load())
defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
      {{ t('dashboard.categoryOverview') }}
    </h3>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 animate-pulse">
      <div v-for="i in 3" :key="i" class="h-28 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="data && data.items.length === 0 && !data.uncategorized" class="text-center py-8 space-y-3">
      <p class="text-sm text-gray-400">{{ t('dashboard.categoryOverviewEmpty') }}</p>
      <button
        class="px-4 py-2 bg-red-600 text-white rounded-xl text-xs font-medium hover:bg-red-700 transition-colors"
        @click="router.push('/app/settings?tab=pipeline')"
      >
        {{ t('dashboard.setupPipeline') }}
      </button>
    </div>

    <!-- Category grid -->
    <div v-else-if="data" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <div
        v-for="item in data.items"
        :key="item.category_id"
        class="relative rounded-xl border border-gray-100 dark:border-gray-700 p-4 cursor-pointer hover:shadow-md transition-shadow overflow-hidden"
        :style="item.color ? { borderLeft: `3px solid ${item.color}` } : {}"
        @click="openCategory(item.category_id)"
        role="button"
        :aria-label="item.name"
      >
        <!-- Category name -->
        <div class="flex items-center gap-2 mb-2">
          <span
            v-if="item.color"
            class="inline-block w-2 h-2 rounded-full flex-shrink-0"
            :style="{ backgroundColor: item.color }"
            aria-hidden="true"
          />
          <span class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">{{ item.name }}</span>
        </div>

        <!-- KPIs row -->
        <div class="flex items-end justify-between gap-2">
          <div>
            <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ item.records_open }}</div>
            <div class="text-xs text-gray-500 dark:text-gray-400">{{ t('dashboard.catRecordsOpen', { n: item.records_won }) }}</div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ t('dashboard.catValueOpen', { value: formatAmount(item.value_open_canonical) }) }}</div>
            <div class="text-xs mt-1 font-medium" :class="item.win_rate >= 0.5 ? 'text-green-600 dark:text-green-400' : 'text-gray-500 dark:text-gray-400'">
              {{ t('dashboard.catWinRate', { pct: (item.win_rate * 100).toFixed(0) }) }}
            </div>
          </div>

          <!-- Sparkline -->
          <svg
            viewBox="0 0 100 28"
            class="w-20 h-7 flex-shrink-0 opacity-70"
            aria-hidden="true"
            preserveAspectRatio="none"
          >
            <polyline
              :points="sparklinePath(item.sparkline)"
              fill="none"
              :stroke="item.color || '#ef4444'"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
      </div>

      <!-- Uncategorized bucket -->
      <div
        v-if="data.uncategorized"
        class="relative rounded-xl border border-dashed border-gray-200 dark:border-gray-600 p-4 cursor-pointer hover:shadow-md transition-shadow overflow-hidden"
        @click="openCategory('')"
        role="button"
        :aria-label="t('dashboard.uncategorized')"
      >
        <div class="text-sm font-semibold text-gray-500 dark:text-gray-400 mb-2">{{ t('dashboard.uncategorized') }}</div>
        <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ data.uncategorized.records_open }}</div>
        <div class="text-xs text-gray-500 dark:text-gray-400">{{ t('dashboard.catRecordsOpen', { n: data.uncategorized.records_won }) }}</div>
      </div>
    </div>
  </div>
</template>

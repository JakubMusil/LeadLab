<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { TrophyIcon } from '@heroicons/vue/24/solid'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { api } from '@/api'

interface RecentWinItem {
  id: string
  title: string
  value_canonical: number | null
  won_at: string
  assigned_to_name: string | null
}

interface RecentWinsResponse {
  items: RecentWinItem[]
  canonical_currency: string
}

const { t } = useI18n()
const { formatAmount } = useMoney()

const data = ref<RecentWinsResponse | null>(null)
const loading = ref(false)

function relativeDate(wonAt: string): string {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const won = new Date(wonAt)
  won.setHours(0, 0, 0, 0)
  const diffMs = today.getTime() - won.getTime()
  const diffDays = Math.round(diffMs / 86_400_000)
  if (diffDays === 0) return t('dashboard.recentWinsToday')
  if (diffDays === 1) return t('dashboard.recentWinsYesterday')
  return t('dashboard.recentWinsDaysAgo', { n: diffDays })
}

const WINS_DAYS = 30

async function load() {
  loading.value = true
  try {
    const res = await api.get<RecentWinsResponse>(`/api/v1/crm/dashboard/recent-wins?days=${WINS_DAYS}`)
    if (res.ok) data.value = res.data
  } finally {
    loading.value = false
  }
}

defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header -->
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2 mb-4">
      <TrophyIcon class="w-4 h-4 text-amber-500" aria-hidden="true" />
      {{ t('dashboard.recentWinsTitle') }}
    </h3>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="space-y-2 animate-pulse">
      <div v-for="i in 3" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="data && data.items.length === 0" class="text-center py-8">
      <p class="text-sm text-gray-400 dark:text-gray-500">{{ t('dashboard.recentWinsEmpty') }}</p>
    </div>

    <!-- List -->
    <ul v-else-if="data" class="divide-y divide-gray-50 dark:divide-gray-700">
      <li
        v-for="item in data.items"
        :key="item.id"
        class="-mx-2 px-2 py-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div class="flex items-center gap-3">
          <!-- Icon -->
          <span class="flex-shrink-0 text-base" aria-hidden="true">🎉</span>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <RouterLink
              :to="`/app/records/${item.id}`"
              class="text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 dark:hover:text-red-400 truncate block"
            >
              {{ item.title }}
            </RouterLink>
            <p v-if="item.assigned_to_name" class="text-xs text-gray-400 truncate">
              {{ item.assigned_to_name }}
            </p>
          </div>

          <!-- Right: value + date -->
          <div class="flex-shrink-0 text-right">
            <div v-if="item.value_canonical" class="text-xs font-bold text-green-600 dark:text-green-400">
              {{ formatAmount(item.value_canonical) }}
            </div>
            <div class="text-[11px] text-gray-400 mt-0.5">{{ relativeDate(item.won_at) }}</div>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

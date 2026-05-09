<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { LockClosedIcon } from '@heroicons/vue/24/outline'
import { api } from '@/api'

interface LeaderboardEntry {
  user_id: string
  display_name: string
  won_count: number
  won_value_canonical: number
  activities_count: number
  records_open: number
}

interface LeaderboardData {
  canonical_currency: string
  range: string
  entries: LeaderboardEntry[]
}

const { t } = useI18n()
const { formatAmount } = useMoney()

const data = ref<LeaderboardData | null>(null)
const loading = ref(false)
const forbidden = ref(false)

async function load() {
  loading.value = true
  forbidden.value = false
  try {
    const res = await api.get<LeaderboardData>('/api/v1/crm/dashboard/team-leaderboard')
    if (res.ok) {
      data.value = res.data
    } else if (res.status === 403) {
      forbidden.value = true
    }
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
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">
      {{ t('dashboard.teamLeaderboard') }}
    </h3>

    <!-- Skeleton -->
    <div v-if="loading && !data && !forbidden" class="space-y-2 animate-pulse">
      <div v-for="i in 4" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Access denied -->
    <div
      v-else-if="forbidden"
      class="flex flex-col items-center justify-center py-8 text-center gap-2 text-gray-400"
    >
      <LockClosedIcon class="w-6 h-6" aria-hidden="true" />
      <p class="text-sm">{{ t('dashboard.teamLeaderboardForbidden') }}</p>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="data && data.entries.length === 0"
      class="text-center py-8 text-sm text-gray-400"
    >
      {{ t('dashboard.teamLeaderboardEmpty') }}
    </div>

    <!-- Table -->
    <template v-else-if="data && data.entries.length > 0">
      <div class="overflow-x-auto -mx-1">
        <table class="w-full text-xs min-w-[340px]">
          <thead>
            <tr class="text-gray-400 dark:text-gray-500 border-b border-gray-100 dark:border-gray-700">
              <th class="text-left py-1 px-1 font-medium">#</th>
              <th class="text-left py-1 px-1 font-medium">{{ t('dashboard.lbUser') }}</th>
              <th class="text-right py-1 px-1 font-medium">{{ t('dashboard.lbWon') }}</th>
              <th class="text-right py-1 px-1 font-medium hidden sm:table-cell">{{ t('dashboard.lbValue') }}</th>
              <th class="text-right py-1 px-1 font-medium hidden sm:table-cell">{{ t('dashboard.lbActivities') }}</th>
              <th class="text-right py-1 px-1 font-medium">{{ t('dashboard.lbOpen') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(entry, idx) in data.entries"
              :key="entry.user_id"
              class="border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors"
            >
              <td class="py-2 px-1 font-medium text-gray-500 dark:text-gray-400">
                <span v-if="idx === 0" class="text-lg" title="1">🥇</span>
                <span v-else-if="idx === 1" class="text-lg" title="2">🥈</span>
                <span v-else-if="idx === 2" class="text-lg" title="3">🥉</span>
                <span v-else class="text-gray-400">{{ idx + 1 }}</span>
              </td>
              <td class="py-2 px-1 font-medium text-gray-800 dark:text-gray-100 truncate max-w-[120px]">
                {{ entry.display_name }}
              </td>
              <td class="py-2 px-1 text-right font-semibold text-green-600 dark:text-green-400">
                {{ entry.won_count }}
              </td>
              <td class="py-2 px-1 text-right text-gray-600 dark:text-gray-300 hidden sm:table-cell">
                {{ formatAmount(entry.won_value_canonical) }}
              </td>
              <td class="py-2 px-1 text-right text-gray-500 dark:text-gray-400 hidden sm:table-cell">
                {{ entry.activities_count }}
              </td>
              <td class="py-2 px-1 text-right text-gray-500 dark:text-gray-400">
                {{ entry.records_open }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { FireIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

interface MyGoalsResponse {
  activities_today: number
  target_activities: number
  streak_days: number
  best_day_count: number
  best_day_date: string | null
}

const { t } = useI18n()

const data = ref<MyGoalsResponse | null>(null)
const loading = ref(false)

const CIRCLE_RADIUS = 36
const CIRCUMFERENCE = 2 * Math.PI * CIRCLE_RADIUS // ≈ 226.2

const progress = computed(() => {
  if (!data.value || data.value.target_activities === 0) return 0
  return Math.min(1, data.value.activities_today / data.value.target_activities)
})

const dashoffset = computed(() => CIRCUMFERENCE * (1 - progress.value))

const ringColor = computed(() => {
  const p = progress.value
  if (p >= 1) return '#22c55e'   // green-500
  if (p >= 0.5) return '#f59e0b' // amber-500
  return '#d1d5db'               // gray-300
})

const achieved = computed(() =>
  !!data.value && data.value.activities_today >= data.value.target_activities,
)

async function load() {
  loading.value = true
  try {
    const res = await api.get<MyGoalsResponse>('/api/v1/crm/dashboard/my-goals')
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
      <FireIcon class="w-4 h-4 text-orange-500" aria-hidden="true" />
      {{ t('dashboard.dailyGoalsTitle') }}
    </h3>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="animate-pulse flex flex-col items-center gap-3">
      <div class="w-24 h-24 bg-gray-100 dark:bg-gray-700 rounded-full" />
      <div class="h-4 w-32 bg-gray-100 dark:bg-gray-700 rounded" />
      <div class="h-4 w-28 bg-gray-100 dark:bg-gray-700 rounded" />
    </div>

    <!-- Content -->
    <div v-else-if="data" class="flex flex-col items-center gap-4">
      <!-- Circle progress -->
      <div class="relative">
        <!-- SVG uses CIRCLE_RADIUS for the progress ring -->
        <svg width="88" height="88" viewBox="0 0 88 88" aria-hidden="true">
          <!-- Track -->
          <circle
            cx="44"
            cy="44"
            :r="CIRCLE_RADIUS"
            fill="none"
            stroke="#e5e7eb"
            stroke-width="8"
            class="dark:stroke-gray-700"
          />
          <!-- Progress -->
          <circle
            cx="44"
            cy="44"
            :r="CIRCLE_RADIUS"
            fill="none"
            :stroke="ringColor"
            stroke-width="8"
            stroke-linecap="round"
            :stroke-dasharray="CIRCUMFERENCE"
            :stroke-dashoffset="dashoffset"
            transform="rotate(-90 44 44)"
            style="transition: stroke-dashoffset 0.5s ease, stroke 0.3s ease"
          />
        </svg>
        <!-- Center text -->
        <div class="absolute inset-0 flex items-center justify-center">
          <span class="text-sm font-bold text-gray-900 dark:text-gray-100">
            {{ data.activities_today }}&thinsp;/&thinsp;{{ data.target_activities }}
          </span>
        </div>
      </div>

      <!-- Achieved badge -->
      <span
        v-if="achieved"
        class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300"
      >
        {{ t('dashboard.dailyGoalsAchieved') }}
      </span>

      <!-- Stats row -->
      <div class="flex items-center gap-6 text-sm text-gray-600 dark:text-gray-300">
        <div class="flex items-center gap-1">
          <span aria-hidden="true">🔥</span>
          <span class="font-semibold text-gray-900 dark:text-gray-100">{{ data.streak_days }}</span>
          <span class="text-xs text-gray-400">{{ t('dashboard.dailyGoalsStreak') }}</span>
        </div>
        <div class="flex items-center gap-1">
          <span aria-hidden="true">🏆</span>
          <span class="font-semibold text-gray-900 dark:text-gray-100">{{ data.best_day_count }}</span>
          <span class="text-xs text-gray-400">{{ t('dashboard.dailyGoalsBest') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

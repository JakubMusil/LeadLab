<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { FlagIcon, CheckCircleIcon as CheckCircleOutlineIcon } from '@heroicons/vue/24/outline'
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/vue/24/solid'
import { useI18n } from '@/composables/useI18n'
import { useDashboardWidget } from '@/composables/useDashboardWidget'
import { api } from '@/api'

interface CheckpointItem {
  id: string
  name: string
  date: string | null
  is_completed: boolean
  record_id: string
  record_title: string
  category_name: string | null
  assigned_to_name: string | null
  days_until: number | null
}

interface CheckpointsData {
  items: CheckpointItem[]
}

const { t } = useI18n()
const { scope, days } = useDashboardWidget('upcoming_checkpoints')

const data = ref<CheckpointsData | null>(null)
const loading = ref(false)
const completing = ref<Set<string>>(new Set())

const DEFAULT_UPCOMING_DAYS = 14

const upcomingDays = computed(() => days.value ?? DEFAULT_UPCOMING_DAYS)

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      upcoming_days: String(upcomingDays.value),
      scope: scope.value,
    })
    const res = await api.get<CheckpointsData>(
      `/api/v1/crm/dashboard/checkpoints?${params}`,
    )
    if (res.ok) data.value = res.data
  } finally {
    loading.value = false
  }
}

async function completeCheckpoint(item: CheckpointItem) {
  if (completing.value.has(item.id)) return
  completing.value = new Set([...completing.value, item.id])
  try {
    const res = await api.patch(
      `/api/v1/crm/records/${item.record_id}/checkpoints/${item.id}`,
      { is_completed: true },
    )
    if (res.ok && data.value) {
      data.value = { items: data.value.items.filter((i) => i.id !== item.id) }
    }
  } finally {
    const next = new Set(completing.value)
    next.delete(item.id)
    completing.value = next
  }
}

function dayLabel(item: CheckpointItem): string {
  if (item.days_until == null) return ''
  if (item.days_until < 0) return t('dashboard.cpOverdue', { n: Math.abs(item.days_until) })
  if (item.days_until === 0) return t('dashboard.cpToday')
  if (item.days_until === 1) return t('dashboard.cpTomorrow')
  return t('dashboard.cpInDays', { n: item.days_until })
}

function dayClass(item: CheckpointItem): string {
  if (item.days_until == null) return 'text-gray-400'
  if (item.days_until < 0) return 'text-red-600 dark:text-red-400'
  if (item.days_until === 0) return 'text-orange-600 dark:text-orange-400'
  if (item.days_until <= 3) return 'text-amber-600 dark:text-amber-400'
  return 'text-gray-500 dark:text-gray-400'
}

const overdueCount = computed(
  () => data.value?.items.filter((i) => i.days_until != null && i.days_until < 0).length ?? 0,
)

defineExpose({ load })
onMounted(load)
watch([scope, upcomingDays], load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <FlagIcon class="w-4 h-4 text-purple-500" aria-hidden="true" />
        {{ t('dashboard.upcomingCheckpoints') }}
        <span
          v-if="overdueCount > 0"
          class="text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 rounded-full px-2 py-0.5"
        >
          {{ overdueCount }} {{ t('dashboard.cpOverdueLabel') }}
        </span>
      </h3>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="space-y-2 animate-pulse">
      <div v-for="i in 4" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="data && data.items.length === 0" class="flex flex-col items-center py-8 text-center gap-2">
      <CheckCircleSolidIcon class="w-8 h-8 text-green-400" aria-hidden="true" />
      <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('dashboard.upcomingCheckpointsEmpty') }}</p>
    </div>

    <!-- List -->
    <ul v-else-if="data" class="divide-y divide-gray-50 dark:divide-gray-700">
      <li
        v-for="item in data.items"
        :key="item.id"
        class="flex items-center gap-2.5 -mx-2 px-2 py-2.5 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors group"
      >
        <!-- Complete button -->
        <button
          type="button"
          class="flex-shrink-0 w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-600 text-transparent hover:border-green-500 hover:text-green-500 transition-colors flex items-center justify-center disabled:opacity-50"
          :disabled="completing.has(item.id)"
          :aria-label="t('dashboard.cpComplete')"
          @click="completeCheckpoint(item)"
        >
          <CheckCircleOutlineIcon class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
        </button>

        <!-- Info -->
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ item.name }}</div>
          <div class="text-xs text-gray-400 truncate">
            <RouterLink
              :to="`/app/records/${item.record_id}`"
              class="hover:text-red-600 hover:underline"
              @click.stop
            >
              {{ item.record_title }}
            </RouterLink>
            <span v-if="item.category_name" class="ml-1 text-gray-300 dark:text-gray-600">·</span>
            <span v-if="item.category_name" class="ml-1">{{ item.category_name }}</span>
          </div>
        </div>

        <!-- Due date label -->
        <span
          class="flex-shrink-0 text-xs font-medium whitespace-nowrap"
          :class="dayClass(item)"
        >
          {{ dayLabel(item) }}
        </span>
      </li>
    </ul>
  </div>
</template>

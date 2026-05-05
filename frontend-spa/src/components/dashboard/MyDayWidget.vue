<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { CheckCircleIcon, ClockIcon, CalendarDaysIcon, ExclamationCircleIcon } from '@heroicons/vue/24/outline'
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/vue/24/solid'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

interface MyDayItem {
  id: string
  kind: 'task' | 'checkpoint'
  title: string
  record_id: string | null
  record_title: string | null
  due_date: string | null
  priority: string | null
  is_completed: boolean
}

interface MyDayData {
  overdue: MyDayItem[]
  today: MyDayItem[]
  this_week: MyDayItem[]
}

const { t } = useI18n()

const data = ref<MyDayData | null>(null)
const loading = ref(false)
const completing = ref<Set<string>>(new Set())

async function load() {
  loading.value = true
  try {
    const res = await api.get<MyDayData>('/api/v1/crm/dashboard/my-day')
    if (res.ok) data.value = res.data
  } finally {
    loading.value = false
  }
}

async function completeItem(item: MyDayItem) {
  if (completing.value.has(item.id)) return
  completing.value = new Set([...completing.value, item.id])
  try {
    let ok = false
    if (item.kind === 'task') {
      const res = await api.post(`/api/v1/crm/tasks/${item.id}/complete`, {})
      ok = res.ok
    } else if (item.kind === 'checkpoint' && item.record_id) {
      const res = await api.patch(`/api/v1/crm/records/${item.record_id}/checkpoints/${item.id}`, {
        is_completed: true,
      })
      ok = res.ok
    }
    if (ok) {
      // Remove item from data optimistically
      if (data.value) {
        data.value = {
          overdue: data.value.overdue.filter((i) => i.id !== item.id),
          today: data.value.today.filter((i) => i.id !== item.id),
          this_week: data.value.this_week.filter((i) => i.id !== item.id),
        }
      }
    }
  } finally {
    const next = new Set(completing.value)
    next.delete(item.id)
    completing.value = next
  }
}

const totalCount = computed(() => {
  if (!data.value) return 0
  return data.value.overdue.length + data.value.today.length + data.value.this_week.length
})

const overdueCount = computed(() => data.value?.overdue.length ?? 0)

defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <CalendarDaysIcon class="w-4 h-4 text-blue-500" aria-hidden="true" />
        {{ t('dashboard.myDay') }}
        <span
          v-if="overdueCount > 0"
          class="inline-flex items-center gap-0.5 text-xs font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 rounded-full px-2 py-0.5"
        >
          <ExclamationCircleIcon class="w-3 h-3" aria-hidden="true" />
          {{ overdueCount }}
        </span>
      </h3>
      <RouterLink
        to="/app/tasks"
        class="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600"
      >
        {{ t('dashboard.viewAll') }}
      </RouterLink>
    </div>

    <!-- Skeleton -->
    <div v-if="loading && !data" class="space-y-2 animate-pulse">
      <div v-for="i in 4" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="data && totalCount === 0" class="flex flex-col items-center justify-center py-8 text-center gap-2">
      <CheckCircleSolidIcon class="w-8 h-8 text-green-400" aria-hidden="true" />
      <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('dashboard.myDayEmpty') }}</p>
    </div>

    <!-- Buckets -->
    <div v-else-if="data" class="space-y-4">

      <!-- Overdue -->
      <div v-if="data.overdue.length > 0">
        <div class="flex items-center gap-1.5 mb-2">
          <ExclamationCircleIcon class="w-3.5 h-3.5 text-red-500" aria-hidden="true" />
          <span class="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide">
            {{ t('dashboard.myDayOverdue') }}
          </span>
        </div>
        <ul class="space-y-1">
          <li
            v-for="item in data.overdue"
            :key="item.id"
            class="flex items-center gap-2.5 rounded-xl px-2 py-2 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors group"
          >
            <button
              type="button"
              class="flex-shrink-0 w-5 h-5 rounded-full border-2 border-red-400 text-transparent hover:border-red-600 hover:text-red-600 dark:hover:border-red-400 transition-colors flex items-center justify-center disabled:opacity-50"
              :disabled="completing.has(item.id)"
              :aria-label="t('dashboard.myDayComplete')"
              @click="completeItem(item)"
            >
              <CheckCircleIcon class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
            </button>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ item.title }}</div>
              <div v-if="item.record_title && item.record_id" class="text-xs text-gray-400 truncate">
                <RouterLink :to="`/app/records/${item.record_id}`" class="hover:text-red-600 hover:underline" @click.stop>
                  {{ item.record_title }}
                </RouterLink>
              </div>
            </div>
            <span class="flex-shrink-0 text-xs text-red-500 dark:text-red-400">
              <ClockIcon class="w-3.5 h-3.5 inline" aria-hidden="true" />
            </span>
          </li>
        </ul>
      </div>

      <!-- Today -->
      <div v-if="data.today.length > 0">
        <div class="flex items-center gap-1.5 mb-2">
          <ClockIcon class="w-3.5 h-3.5 text-orange-500" aria-hidden="true" />
          <span class="text-xs font-semibold text-orange-600 dark:text-orange-400 uppercase tracking-wide">
            {{ t('dashboard.myDayToday') }}
          </span>
        </div>
        <ul class="space-y-1">
          <li
            v-for="item in data.today"
            :key="item.id"
            class="flex items-center gap-2.5 rounded-xl px-2 py-2 hover:bg-orange-50 dark:hover:bg-orange-900/20 transition-colors group"
          >
            <button
              type="button"
              class="flex-shrink-0 w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-600 text-transparent hover:border-green-500 hover:text-green-500 transition-colors flex items-center justify-center disabled:opacity-50"
              :disabled="completing.has(item.id)"
              :aria-label="t('dashboard.myDayComplete')"
              @click="completeItem(item)"
            >
              <CheckCircleIcon class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
            </button>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ item.title }}</div>
              <div v-if="item.record_title && item.record_id" class="text-xs text-gray-400 truncate">
                <RouterLink :to="`/app/records/${item.record_id}`" class="hover:text-red-600 hover:underline" @click.stop>
                  {{ item.record_title }}
                </RouterLink>
              </div>
            </div>
          </li>
        </ul>
      </div>

      <!-- This week -->
      <div v-if="data.this_week.length > 0">
        <div class="flex items-center gap-1.5 mb-2">
          <CalendarDaysIcon class="w-3.5 h-3.5 text-blue-500" aria-hidden="true" />
          <span class="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">
            {{ t('dashboard.myDayThisWeek') }}
          </span>
        </div>
        <ul class="space-y-1">
          <li
            v-for="item in data.this_week"
            :key="item.id"
            class="flex items-center gap-2.5 rounded-xl px-2 py-2 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors group"
          >
            <button
              type="button"
              class="flex-shrink-0 w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-600 text-transparent hover:border-green-500 hover:text-green-500 transition-colors flex items-center justify-center disabled:opacity-50"
              :disabled="completing.has(item.id)"
              :aria-label="t('dashboard.myDayComplete')"
              @click="completeItem(item)"
            >
              <CheckCircleIcon class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
            </button>
            <div class="flex-1 min-w-0">
              <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ item.title }}</div>
              <div v-if="item.record_title && item.record_id" class="text-xs text-gray-400 truncate">
                <RouterLink :to="`/app/records/${item.record_id}`" class="hover:text-red-600 hover:underline" @click.stop>
                  {{ item.record_title }}
                </RouterLink>
              </div>
            </div>
            <span v-if="item.due_date" class="flex-shrink-0 text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
              {{ new Date(item.due_date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }) }}
            </span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

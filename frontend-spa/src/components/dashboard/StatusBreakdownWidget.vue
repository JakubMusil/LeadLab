<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from '@/composables/useI18n'

const STATUS_COLORS: Record<string, string> = {
  new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
  negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
}

const props = defineProps<{
  recordsByStatus: Record<string, number>
}>()

const { t } = useI18n()

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  new: t('leads.statusNew'),
  contacted: t('leads.statusContacted'),
  proposal: t('leads.statusProposal'),
  negotiation: t('leads.statusNegotiation'),
  won: t('leads.statusWon'),
  lost: t('leads.statusLost'),
  canceled: t('leads.statusCanceled'),
}))
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.statusBreakdown') }}</h3>
    <div class="flex flex-wrap gap-3">
      <RouterLink
        v-for="[status, count] in Object.entries(recordsByStatus)"
        :key="status"
        :to="`/app/records?status=${status}`"
        class="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors"
      >
        <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: STATUS_COLORS[status] ?? '#6b7280' }" />
        <span class="text-sm text-gray-700 dark:text-gray-300">{{ STATUS_LABELS[status] ?? status }}</span>
        <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ count }}</span>
      </RouterLink>
    </div>
  </div>
</template>

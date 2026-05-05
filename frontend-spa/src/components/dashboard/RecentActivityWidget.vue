<script setup lang="ts">
import type { Component } from 'vue'
import { RouterLink } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import {
  ChatBubbleLeftIcon,
  EnvelopeIcon,
  InboxArrowDownIcon,
  PhoneIcon,
  UsersIcon,
  ArrowsRightLeftIcon,
  PaperClipIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  MapPinIcon,
} from '@heroicons/vue/24/outline'

interface ActivityItem {
  id: string
  record_id: string
  record_title?: string
  type: string
  content_text: string
  created_at: string
}

const props = defineProps<{ activities: ActivityItem[] }>()

const { t } = useI18n()

const activityIcons: Record<string, Component> = {
  comment: ChatBubbleLeftIcon,
  email_out: EnvelopeIcon,
  email_in: InboxArrowDownIcon,
  call: PhoneIcon,
  meeting: UsersIcon,
  status_change: ArrowsRightLeftIcon,
  file_upload: PaperClipIcon,
  task_assigned: ClipboardDocumentListIcon,
  task_completed: CheckCircleIcon,
}

function activityIcon(type: string): Component {
  return activityIcons[type] ?? MapPinIcon
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4">{{ t('dashboard.recentActivity') }}</h3>
    <div v-if="activities.length === 0" class="text-sm text-gray-400 text-center py-8">
      {{ t('dashboard.noRecentActivity') }}
    </div>
    <ul class="space-y-3 overflow-y-auto max-h-56">
      <li v-for="act in activities" :key="act.id" class="flex items-start gap-2.5">
        <component :is="activityIcon(act.type)" class="w-4 h-4 mt-0.5 flex-shrink-0 text-gray-400 dark:text-gray-500" aria-hidden="true" />
        <div class="min-w-0">
          <p class="text-xs text-gray-700 dark:text-gray-300 truncate">
            <RouterLink v-if="act.record_id" :to="`/app/records/${act.record_id}`" class="font-medium hover:text-red-600">
              {{ act.record_title ?? 'Record' }}
            </RouterLink>
            <span v-if="act.content_text"> — {{ act.content_text }}</span>
          </p>
          <p class="text-xs text-gray-400 dark:text-gray-500">{{ formatTime(act.created_at) }}</p>
        </div>
      </li>
    </ul>
  </div>
</template>

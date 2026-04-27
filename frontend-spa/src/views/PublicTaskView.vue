<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'

const route = useRoute()
const token = route.params.token as string

interface PublicTask {
  id: string
  title: string
  description_html: string
  priority: string
  status: string
  tags: string[]
  due_date: string | null
  due_date_end: string | null
  is_completed: boolean
  created_at: string
  assigned_to_name: string | null
  firm_name: string
  checklist: { text: string; is_checked: boolean }[]
}

const task = ref<PublicTask | null>(null)
const loading = ref(true)
const error = ref('')

const STATUS_LABELS: Record<string, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  blocked: 'Blocked',
  done: 'Done',
  cancelled: 'Cancelled',
}

const PRIORITY_LABELS: Record<string, string> = {
  none: '—',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
}

function formatDate(ds: string | null) {
  if (!ds) return '—'
  return new Date(ds).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

onMounted(async () => {
  const res = await api.get<PublicTask>(`/api/v1/crm/public/tasks/${token}`)
  loading.value = false
  if (res.ok) {
    task.value = res.data
  } else {
    error.value = 'Task not found or link has expired.'
  }
})
</script>

<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
    <div class="max-w-2xl mx-auto">
      <!-- Loading -->
      <div v-if="loading" class="animate-pulse space-y-4 mt-12">
        <div class="h-8 bg-gray-200 dark:bg-gray-700 rounded-xl w-2/3 mx-auto" />
        <div class="h-4 bg-gray-100 dark:bg-gray-800 rounded-xl w-1/2 mx-auto" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-16 text-gray-500 dark:text-gray-400">
        <div class="text-4xl mb-4">🔒</div>
        <h1 class="text-xl font-bold mb-2 text-gray-900 dark:text-gray-100">Link not found</h1>
        <p class="text-sm">{{ error }}</p>
      </div>

      <!-- Task -->
      <template v-else-if="task">
        <!-- Header -->
        <div class="text-center mb-6">
          <p class="text-sm text-gray-400 mb-1">{{ task.firm_name }}</p>
          <h1
            class="text-2xl font-bold text-gray-900 dark:text-gray-100"
            :class="task.is_completed ? 'line-through text-gray-400' : ''"
          >
            {{ task.title }}
          </h1>
          <div class="flex items-center justify-center gap-2 mt-2 flex-wrap">
            <span class="px-2 py-0.5 rounded-full text-xs font-medium" :class="{
              'bg-gray-100 text-gray-600': task.status === 'todo',
              'bg-blue-100 text-blue-700': task.status === 'in_progress',
              'bg-red-100 text-red-700': task.status === 'blocked',
              'bg-green-100 text-green-700': task.status === 'done',
              'bg-gray-200 text-gray-500': task.status === 'cancelled',
            }">{{ STATUS_LABELS[task.status] ?? task.status }}</span>
            <span v-if="task.priority !== 'none'" class="text-xs text-gray-500">⚠ {{ PRIORITY_LABELS[task.priority] }}</span>
          </div>
        </div>

        <!-- Card -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6 space-y-5">
          <!-- Meta -->
          <div class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm text-gray-500 dark:text-gray-400">
            <div v-if="task.assigned_to_name">
              <span class="font-medium text-gray-700 dark:text-gray-300">Assignee</span>
              <p>{{ task.assigned_to_name }}</p>
            </div>
            <div v-if="task.due_date">
              <span class="font-medium text-gray-700 dark:text-gray-300">Due date</span>
              <p>{{ formatDate(task.due_date) }}<template v-if="task.due_date_end"> – {{ formatDate(task.due_date_end) }}</template></p>
            </div>
            <div v-if="(task.tags ?? []).length">
              <span class="font-medium text-gray-700 dark:text-gray-300">Tags</span>
              <div class="flex flex-wrap gap-1 mt-0.5">
                <span v-for="tag in task.tags" :key="tag" class="px-1.5 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-xs">🏷 {{ tag }}</span>
              </div>
            </div>
          </div>

          <!-- Description -->
          <div v-if="task.description_html">
            <h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Description</h2>
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="prose prose-sm dark:prose-invert max-w-none" v-html="task.description_html" />
          </div>

          <!-- Checklist -->
          <div v-if="task.checklist && task.checklist.length > 0">
            <h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Checklist</h2>
            <ul class="space-y-1.5">
              <li v-for="(item, idx) in task.checklist" :key="idx" class="flex items-center gap-2 text-sm">
                <span class="w-4 h-4 rounded border flex items-center justify-center flex-shrink-0"
                  :class="item.is_checked ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300'">
                  <span v-if="item.is_checked" class="text-xs">✓</span>
                </span>
                <span :class="item.is_checked ? 'line-through text-gray-400' : 'text-gray-700 dark:text-gray-300'">{{ item.text }}</span>
              </li>
            </ul>
          </div>
        </div>

        <p class="text-center text-xs text-gray-400 mt-4">Shared via LeadLab</p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'
import { ChevronLeftIcon, ChevronRightIcon, FunnelIcon } from '@heroicons/vue/24/outline'

const firmStore = useFirmStore()
const { t } = useI18n()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

interface AuditEntry {
  id: string
  action: string
  target_type: string
  target_id: string
  actor_email: string | null
  payload: Record<string, unknown>
  created_at: string
}

const entries = ref<AuditEntry[]>([])
const loading = ref(false)
const error = ref('')

// Filters
const filterAction = ref('')
const filterTargetType = ref('')

// Pagination
const page = ref(1)
const pageSize = 25
const hasMore = ref(false)

const ACTION_OPTIONS = [
  'role.created', 'role.updated', 'role.deleted',
  'membership.created', 'membership.updated', 'membership.deleted',
  'category_grant.created', 'category_grant.deleted',
  'record_grant.created', 'record_grant.deleted',
]

const TARGET_TYPE_OPTIONS = ['role', 'membership', 'category_grant', 'record_grant']

async function fetchAuditLog() {
  if (!firmId.value) return
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize + 1), // fetch one extra to detect hasMore
    })
    if (filterAction.value) params.set('action', filterAction.value)
    if (filterTargetType.value) params.set('target_type', filterTargetType.value)

    const res = await fetch(`/api/v1/firms/${firmId.value}/audit-log?${params}`, {
      credentials: 'include',
    })
    if (!res.ok) {
      error.value = `HTTP ${res.status}`
      return
    }
    const data: AuditEntry[] = await res.json()
    hasMore.value = data.length > pageSize
    entries.value = data.slice(0, pageSize)
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  fetchAuditLog()
}

function prevPage() {
  if (page.value > 1) {
    page.value--
    fetchAuditLog()
  }
}

function nextPage() {
  if (hasMore.value) {
    page.value++
    fetchAuditLog()
  }
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

onMounted(() => {
  fetchAuditLog()
})

watch(firmId, () => {
  page.value = 1
  fetchAuditLog()
})
</script>

<template>
  <div class="space-y-4">
    <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('permissions.auditLog') }}</h2>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 items-end">
      <div>
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
          <FunnelIcon class="inline-block w-3.5 h-3.5 mr-0.5" />{{ t('permissions.auditAction') }}
        </label>
        <select
          v-model="filterAction"
          class="rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
          @change="applyFilters"
        >
          <option value="">— {{ t('permissions.auditAction') }} —</option>
          <option v-for="a in ACTION_OPTIONS" :key="a" :value="a">{{ a }}</option>
        </select>
      </div>
      <div>
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.auditTarget') }}</label>
        <select
          v-model="filterTargetType"
          class="rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
          @change="applyFilters"
        >
          <option value="">— {{ t('permissions.auditTarget') }} —</option>
          <option v-for="tt in TARGET_TYPE_OPTIONS" :key="tt" :value="tt">{{ tt }}</option>
        </select>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ error }}</div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 5" :key="i" class="h-10 bg-gray-100 dark:bg-gray-700 rounded-xl animate-pulse" />
    </div>

    <!-- Table -->
    <div v-else-if="entries.length > 0" class="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-700">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 dark:bg-gray-800">
          <tr>
            <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('permissions.auditActor') }}</th>
            <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('permissions.auditAction') }}</th>
            <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('permissions.auditTarget') }}</th>
            <th class="text-left px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400">{{ t('permissions.auditTime') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
          <tr
            v-for="entry in entries"
            :key="entry.id"
            class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
          >
            <td class="px-4 py-2 text-gray-900 dark:text-gray-100 font-medium truncate max-w-[180px]">
              {{ entry.actor_email ?? '—' }}
            </td>
            <td class="px-4 py-2">
              <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                {{ entry.action }}
              </span>
            </td>
            <td class="px-4 py-2 text-gray-600 dark:text-gray-400 text-xs font-mono">
              {{ entry.target_type }}: {{ entry.target_id.slice(0, 8) }}…
            </td>
            <td class="px-4 py-2 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
              {{ formatDate(entry.created_at) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Empty state -->
    <div v-else class="text-center py-12 text-gray-400 text-sm">
      {{ t('permissions.noAuditEntries') }}
    </div>

    <!-- Pagination -->
    <div v-if="entries.length > 0 || page > 1" class="flex items-center justify-between pt-1">
      <button
        :disabled="page <= 1"
        class="flex items-center gap-1 px-3 py-1.5 text-sm rounded-xl border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
        @click="prevPage"
      >
        <ChevronLeftIcon class="w-4 h-4" />
      </button>
      <span class="text-xs text-gray-500 dark:text-gray-400">{{ t('permissions.auditLog') }} – {{ t('permissions.auditTime') }} ↓</span>
      <button
        :disabled="!hasMore"
        class="flex items-center gap-1 px-3 py-1.5 text-sm rounded-xl border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed"
        @click="nextPage"
      >
        <ChevronRightIcon class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>

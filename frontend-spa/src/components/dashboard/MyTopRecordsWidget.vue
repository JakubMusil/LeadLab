<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { StarIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { getStatusMeta, type RecordOut } from '@/stores/records'
import { api } from '@/api'

const { t } = useI18n()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const router = useRouter()

const myTopRecords = ref<RecordOut[]>([])
const loading = ref(false)

const STATUS_LABELS = computed<Record<string, string>>(() => ({
  new: t('leads.statusNew'),
  contacted: t('leads.statusContacted'),
  proposal: t('leads.statusProposal'),
  negotiation: t('leads.statusNegotiation'),
  won: t('leads.statusWon'),
  lost: t('leads.statusLost'),
  canceled: t('leads.statusCanceled'),
}))

function statusLabelFor(status: string): string {
  return STATUS_LABELS.value[status] ?? getStatusMeta(status).label
}

async function load() {
  if (!firmStore.activeFirm || !authStore.user) return
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.set('assigned_to', String(authStore.user.id))
    params.set('page', '1')
    params.set('page_size', '50')
    const res = await api.get<RecordOut[]>(`/api/v1/crm/records?${params}`)
    if (res.ok) {
      const active = res.data.filter((l) => !['won', 'lost', 'canceled'].includes(l.status))
      myTopRecords.value = active
        .slice()
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, 5)
    }
  } finally {
    loading.value = false
  }
}

function openRecordDetail(id: string) {
  router.push(`/app/records/${id}`)
}

defineExpose({ load })
onMounted(load)
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <StarIcon class="w-4 h-4 text-yellow-500" aria-hidden="true" />
        {{ t('dashboard.myTopRecords') }}
      </h3>
      <RouterLink to="/app/records" class="text-xs text-gray-500 dark:text-gray-400 hover:text-red-600">{{ t('dashboard.viewAll') }}</RouterLink>
    </div>
    <div v-if="loading && myTopRecords.length === 0" class="space-y-2 animate-pulse">
      <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>
    <div v-else-if="myTopRecords.length === 0" class="text-sm text-gray-400 text-center py-6">
      {{ t('dashboard.myTopRecordsEmpty') }}
    </div>
    <ul v-else class="divide-y divide-gray-50 dark:divide-gray-700">
      <li
        v-for="record in myTopRecords"
        :key="record.id"
        class="flex items-center gap-3 py-2.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 -mx-2 px-2 rounded-lg transition-colors"
        @click="openRecordDetail(record.id)"
      >
        <span
          class="flex-shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-semibold"
          :class="(record.score ?? 0) >= 75 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
            : (record.score ?? 0) >= 50 ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'"
          :title="t('dashboard.scoreTitle', { score: record.score ?? 0 })"
        >
          {{ record.score ?? 0 }}
        </span>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ record.title }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400 truncate">
            {{ record.company_name || record.contact_person_name || '—' }}
          </div>
        </div>
        <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium flex-shrink-0" :class="getStatusMeta(record.status).color">
          {{ statusLabelFor(record.status) }}
        </span>
      </li>
    </ul>
  </div>
</template>

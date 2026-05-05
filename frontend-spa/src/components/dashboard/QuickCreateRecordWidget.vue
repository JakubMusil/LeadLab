<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { PlusIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import { useRecordsStore, RECORD_STATUSES, getStatusMeta, type RecordIn } from '@/stores/records'
import { usePipelineStore } from '@/stores/pipeline'

const emit = defineEmits<{ created: [] }>()

const { t } = useI18n()
const toast = useToast()
const recordsStore = useRecordsStore()
const pipelineStore = usePipelineStore()

// Form state
const qcTitle = ref('')
const qcStatus = ref('new')
const qcValue = ref('')
const qcCategoryId = ref('')
const qcStageId = ref('')
const qcSubmitting = ref(false)
const qcError = ref('')

// Active categories from pipeline store
const activeCategories = computed(() =>
  pipelineStore.categories.filter((c) => c.is_active),
)

// Stages for the selected category
const stagesForCategory = computed(() => {
  if (!qcCategoryId.value) return []
  return pipelineStore.getStagesForCategory(qcCategoryId.value).filter((s) => !s.is_terminal)
})

// Reset stage selection when category changes
watch(qcCategoryId, () => {
  qcStageId.value = ''
})

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

async function submitQuickCreate() {
  const title = qcTitle.value.trim()
  if (!title) {
    qcError.value = t('dashboard.qcTitleRequired')
    return
  }
  qcSubmitting.value = true
  qcError.value = ''
  try {
    const valueNum = qcValue.value ? parseFloat(qcValue.value) : null
    const payload: RecordIn = {
      title,
      status: qcStatus.value,
      value: valueNum != null && !isNaN(valueNum) ? valueNum : null,
      category_id: qcCategoryId.value || null,
      current_stage_id: qcStageId.value || null,
    }

    const res = await recordsStore.createRecord(payload)
    if (res.ok) {
      toast.success(t('dashboard.qcCreated'))
      qcTitle.value = ''
      qcStatus.value = 'new'
      qcValue.value = ''
      qcCategoryId.value = ''
      qcStageId.value = ''
      emit('created')
    } else {
      qcError.value = res.error ?? t('dashboard.qcFailed')
    }
  } finally {
    qcSubmitting.value = false
  }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <PlusIcon class="w-4 h-4 text-red-600" aria-hidden="true" />
        {{ t('dashboard.quickCreateRecord') }}
      </h3>
    </div>

    <form class="space-y-2" @submit.prevent="submitQuickCreate">
      <!-- Row 1: Title + Status + Value -->
      <div class="grid grid-cols-1 md:grid-cols-12 gap-2">
        <input
          v-model="qcTitle"
          type="text"
          :placeholder="t('dashboard.qcTitlePlaceholder')"
          :aria-label="t('dashboard.qcTitlePlaceholder')"
          class="md:col-span-5 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
        />
        <select
          v-model="qcStatus"
          :aria-label="t('dashboard.qcStatusLabel')"
          class="md:col-span-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
        >
          <option v-for="s in RECORD_STATUSES" :key="s.value" :value="s.value">{{ statusLabelFor(s.value) }}</option>
        </select>
        <input
          v-model="qcValue"
          type="number"
          min="0"
          step="any"
          :placeholder="t('dashboard.qcValuePlaceholder')"
          :aria-label="t('dashboard.qcValuePlaceholder')"
          class="md:col-span-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
        />
        <button
          type="submit"
          :disabled="qcSubmitting || !qcTitle.trim()"
          class="md:col-span-2 bg-red-600 hover:bg-red-700 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ qcSubmitting ? t('common.saving') : t('dashboard.qcCreate') }}
        </button>
      </div>

      <!-- Row 2: Category + Stage (shown only when pipeline has categories) -->
      <div v-if="activeCategories.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <select
          v-model="qcCategoryId"
          :aria-label="t('dashboard.qcCategoryLabel')"
          class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
        >
          <option value="">{{ t('dashboard.qcCategoryPlaceholder') }}</option>
          <option v-for="cat in activeCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
        <select
          v-model="qcStageId"
          :disabled="!qcCategoryId || stagesForCategory.length === 0"
          :aria-label="t('dashboard.qcStageLabel')"
          class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm px-3 py-2 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400 disabled:opacity-50"
        >
          <option value="">{{ t('dashboard.qcStagePlaceholder') }}</option>
          <option v-for="stage in stagesForCategory" :key="stage.id" :value="stage.id">{{ stage.label || stage.name }}</option>
        </select>
      </div>
    </form>

    <p v-if="qcError" class="mt-2 text-xs text-red-600 dark:text-red-400">{{ qcError }}</p>
  </div>
</template>

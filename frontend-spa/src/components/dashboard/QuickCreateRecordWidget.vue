<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { PhoneIcon, UserIcon, BuildingOfficeIcon, ArrowRightIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import { useRecordsStore, type RecordIn } from '@/stores/records'
import { useCustomersStore } from '@/stores/customers'
import { usePipelineStore } from '@/stores/pipeline'

const emit = defineEmits<{ created: [] }>()

const { t } = useI18n()
const toast = useToast()
const router = useRouter()
const recordsStore = useRecordsStore()
const customersStore = useCustomersStore()
const pipelineStore = usePipelineStore()

// ---------------------------------------------------------------------------
// Cold-call form state
// ---------------------------------------------------------------------------
// Scenario: the operator has only a phone number and is about to make her
// first cold call. The minimum required field is the phone number; everything
// else is optional. When the form is submitted we create a Customer (person)
// holding the phone number, a Record linked to that contact (source =
// "cold_call", status = "contacted") and immediately navigate to the new
// record's detail view so the operator can log the call right there.

const phone = ref('')
const contactName = ref('')
const companyName = ref('')
const categoryId = ref('')
const submitting = ref(false)
const errorMsg = ref('')

const activeCategories = computed(() =>
  pipelineStore.categories.filter((c) => c.is_active),
)

const showCategorySelect = computed(() => activeCategories.value.length > 1)

// Default category = first active (selected silently when only one exists)
const effectiveCategoryId = computed(() => {
  if (categoryId.value) return categoryId.value
  return activeCategories.value[0]?.id ?? ''
})

// Pick the first non-terminal stage of the category, ordered by `order`
function firstStageId(catId: string): string {
  if (!catId) return ''
  const stages = pipelineStore.getStagesForCategory(catId).filter((s) => !s.is_terminal)
  if (!stages.length) return ''
  // getStagesForCategory already returns sorted but be defensive
  return stages[0]?.id ?? ''
}

const phoneValid = computed(() => phone.value.replace(/[^0-9+]/g, '').length >= 6)
const canSubmit = computed(() => phoneValid.value && !submitting.value)

// Build a sensible record title from the provided data
function buildTitle(): string {
  const name = contactName.value.trim()
  const company = companyName.value.trim()
  const tel = phone.value.trim()
  if (name && company) return `${name} — ${company}`
  if (name) return name
  if (company) return company
  return t('dashboard.qcColdCallTitle', { phone: tel })
}

// Split contact name into first/last (best-effort)
function splitName(full: string): { first: string; last: string } {
  const trimmed = full.trim()
  if (!trimmed) return { first: '', last: '' }
  const parts = trimmed.split(/\s+/)
  if (parts.length === 1) return { first: parts[0] ?? '', last: '' }
  return { first: parts[0] ?? '', last: parts.slice(1).join(' ') }
}

async function submit() {
  errorMsg.value = ''
  if (!phoneValid.value) {
    errorMsg.value = t('dashboard.qcPhoneRequired')
    return
  }
  submitting.value = true
  try {
    // 1) Create a Customer (person) holding the phone number. If a contact
    //    name is missing we use the phone number as the first_name fallback
    //    so the customer is still searchable.
    const { first, last } = splitName(contactName.value)
    const customerRes = await customersStore.createCustomer({
      type: 'person',
      first_name: first || phone.value.trim(),
      last_name: last,
      phone: phone.value.trim(),
      company_name: companyName.value.trim() || undefined,
    })

    if (!customerRes.ok || !customerRes.data) {
      errorMsg.value = customerRes.error ?? t('dashboard.qcFailed')
      return
    }

    const catId = effectiveCategoryId.value
    const stageId = firstStageId(catId)

    // 2) Create the Record linked to the freshly created contact
    const payload: RecordIn = {
      title: buildTitle(),
      status: 'contacted',
      source: 'cold_call',
      contact_person_id: customerRes.data.id,
      category_id: catId || null,
      current_stage_id: stageId || null,
    }
    const recordRes = await recordsStore.createRecord(payload)
    if (!recordRes.ok || !recordRes.data) {
      errorMsg.value = recordRes.error ?? t('dashboard.qcFailed')
      return
    }

    toast.success(t('dashboard.qcCreated'))
    emit('created')

    // Reset form
    const newId = recordRes.data.id
    phone.value = ''
    contactName.value = ''
    companyName.value = ''
    categoryId.value = ''

    // 3) Open the new record so the operator can immediately log the call
    router.push({ path: `/app/records/${newId}` })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 h-full flex flex-col">
    <div class="flex items-start justify-between mb-1">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <PhoneIcon class="w-4 h-4 text-red-600" aria-hidden="true" />
        {{ t('dashboard.quickCreateRecord') }}
      </h3>
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-400 mb-4">
      {{ t('dashboard.qcColdCallHint') }}
    </p>

    <form class="space-y-3 flex-1 flex flex-col" @submit.prevent="submit">
      <!-- Phone (primary, required) -->
      <label class="block">
        <span class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
          {{ t('dashboard.qcPhoneLabel') }} <span class="text-red-600" aria-hidden="true">*</span>
        </span>
        <div class="relative">
          <PhoneIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" aria-hidden="true" />
          <input
            v-model="phone"
            type="tel"
            inputmode="tel"
            autocomplete="tel"
            :placeholder="t('dashboard.qcPhonePlaceholder')"
            :aria-label="t('dashboard.qcPhoneLabel')"
            required
            class="w-full pl-9 pr-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400 focus:ring-2 focus:ring-red-100 dark:focus:ring-red-900/40"
          />
        </div>
      </label>

      <!-- Contact name (optional) -->
      <label class="block">
        <span class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
          {{ t('dashboard.qcContactLabel') }}
          <span class="text-gray-400 font-normal">{{ t('dashboard.qcOptional') }}</span>
        </span>
        <div class="relative">
          <UserIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" aria-hidden="true" />
          <input
            v-model="contactName"
            type="text"
            autocomplete="name"
            :placeholder="t('dashboard.qcContactPlaceholder')"
            :aria-label="t('dashboard.qcContactLabel')"
            class="w-full pl-9 pr-3 py-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
          />
        </div>
      </label>

      <!-- Company (optional) -->
      <label class="block">
        <span class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
          {{ t('dashboard.qcCompanyLabel') }}
          <span class="text-gray-400 font-normal">{{ t('dashboard.qcOptional') }}</span>
        </span>
        <div class="relative">
          <BuildingOfficeIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" aria-hidden="true" />
          <input
            v-model="companyName"
            type="text"
            autocomplete="organization"
            :placeholder="t('dashboard.qcCompanyPlaceholder')"
            :aria-label="t('dashboard.qcCompanyLabel')"
            class="w-full pl-9 pr-3 py-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
          />
        </div>
      </label>

      <!-- Category (only when multiple) -->
      <label v-if="showCategorySelect" class="block">
        <span class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
          {{ t('dashboard.qcCategoryLabel') }}
        </span>
        <select
          v-model="categoryId"
          :aria-label="t('dashboard.qcCategoryLabel')"
          class="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-400"
        >
          <option value="">{{ activeCategories[0]?.name ?? '' }} ({{ t('dashboard.qcDefault') }})</option>
          <option v-for="cat in activeCategories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
        </select>
      </label>

      <!-- Submit -->
      <div class="mt-auto pt-1 space-y-2">
        <button
          type="submit"
          :disabled="!canSubmit"
          class="w-full flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ submitting ? t('common.saving') : t('dashboard.qcStartCall') }}
          <ArrowRightIcon v-if="!submitting" class="w-4 h-4" aria-hidden="true" />
        </button>
        <p v-if="errorMsg" class="text-xs text-red-600 dark:text-red-400" role="alert">{{ errorMsg }}</p>
      </div>
    </form>
  </div>
</template>

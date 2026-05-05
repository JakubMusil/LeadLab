<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useFirmStore } from '@/stores/firm'
import { usePipelineStore } from '@/stores/pipeline'
import { useI18n } from '@/composables/useI18n'
import {
  CheckCircleIcon,
  BuildingOfficeIcon,
  AdjustmentsHorizontalIcon,
  ArrowUpTrayIcon,
  XMarkIcon,
} from '@heroicons/vue/24/outline'
import { CheckCircleIcon as CheckCircleSolidIcon } from '@heroicons/vue/24/solid'

const { t } = useI18n()
const firmStore = useFirmStore()
const pipelineStore = usePipelineStore()

const dismissed = ref(false)

const localStorageKey = computed(() =>
  firmStore.activeFirm ? `onboarding_complete_${firmStore.activeFirm.id}` : '',
)

function dismiss() {
  dismissed.value = true
  if (localStorageKey.value) {
    localStorage.setItem(localStorageKey.value, '1')
  }
}

const hasFirmName = computed(() => !!firmStore.activeFirm?.name)
const hasPipeline = computed(() => pipelineStore.categories.filter((c) => c.is_active).length > 0)

// Checklist items
interface CheckItem {
  labelKey: string
  done: boolean
  href?: string
}

const checkItems = computed<CheckItem[]>(() => [
  {
    labelKey: 'setupStepFirm',
    done: hasFirmName.value,
    href: '/app/settings',
  },
  {
    labelKey: 'setupStepPipeline',
    done: hasPipeline.value,
    href: '/app/settings?tab=pipeline',
  },
])

const doneCount = computed(() => checkItems.value.filter((i) => i.done).length)
const totalCount = computed(() => checkItems.value.length)
const allDone = computed(() => doneCount.value === totalCount.value)

// Auto-hide when all steps are done and user has interacted
const showWidget = computed(() => {
  if (dismissed.value) return false
  if (localStorageKey.value && localStorage.getItem(localStorageKey.value)) return false
  return true
})

onMounted(() => {
  if (pipelineStore.categories.length === 0) {
    pipelineStore.fetchCategories()
  }
})
</script>

<template>
  <div
    v-if="showWidget"
    class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 relative"
  >
    <!-- Dismiss button -->
    <button
      type="button"
      class="absolute top-4 right-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
      :aria-label="t('dashboard.cfgClose')"
      @click="dismiss"
    >
      <XMarkIcon class="w-4 h-4" />
    </button>

    <!-- Header -->
    <div class="flex items-center gap-3 mb-4 pr-6">
      <div class="p-2 bg-red-50 dark:bg-red-900/20 rounded-xl">
        <CheckCircleIcon class="w-5 h-5 text-red-500" aria-hidden="true" />
      </div>
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {{ t('dashboard.setupProgress') }}
        </h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
          {{ t('dashboard.setupProgressDesc', { done: doneCount, total: totalCount }) }}
        </p>
      </div>
    </div>

    <!-- Progress bar -->
    <div class="w-full bg-gray-100 dark:bg-gray-700 rounded-full h-1.5 mb-4">
      <div
        class="h-1.5 rounded-full transition-all duration-500"
        :class="allDone ? 'bg-green-500' : 'bg-red-500'"
        :style="{ width: `${(doneCount / totalCount) * 100}%` }"
      />
    </div>

    <!-- Checklist -->
    <ul class="space-y-2 mb-4">
      <li
        v-for="item in checkItems"
        :key="item.labelKey"
        class="flex items-center gap-3"
      >
        <CheckCircleSolidIcon
          v-if="item.done"
          class="w-4 h-4 text-green-500 flex-shrink-0"
          aria-hidden="true"
        />
        <div
          v-else
          class="w-4 h-4 rounded-full border-2 border-gray-300 dark:border-gray-600 flex-shrink-0"
          aria-hidden="true"
        />
        <RouterLink
          v-if="item.href && !item.done"
          :to="item.href"
          class="text-xs text-[color:var(--brand-color)] hover:underline"
        >
          {{ t('dashboard.' + item.labelKey) }}
        </RouterLink>
        <span
          v-else
          class="text-xs"
          :class="item.done ? 'text-gray-400 dark:text-gray-500 line-through' : 'text-gray-700 dark:text-gray-300'"
        >
          {{ t('dashboard.' + item.labelKey) }}
        </span>
      </li>
    </ul>

    <!-- CTA -->
    <RouterLink
      v-if="!allDone"
      to="/app/onboarding"
      class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-xl text-xs font-medium hover:bg-red-700 transition-colors"
    >
      <ArrowUpTrayIcon class="w-3.5 h-3.5" aria-hidden="true" />
      {{ t('dashboard.continueSetup') }}
    </RouterLink>
    <p v-else class="text-xs text-green-600 dark:text-green-400 font-medium">
      {{ t('dashboard.setupAllDone') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

const TOUR_STORAGE_KEY = 'dashboard_tour_done_v1'
const visible = ref(false)
const step = ref(0)

const steps = computed(() => [
  { title: t('dashboard.tourWelcomeTitle'), body: t('dashboard.tourWelcomeBody') },
  { title: t('dashboard.tourKpiTitle'), body: t('dashboard.tourKpiBody') },
  { title: t('dashboard.tourFunnelTitle'), body: t('dashboard.tourFunnelBody') },
  { title: t('dashboard.tourMyDayTitle'), body: t('dashboard.tourMyDayBody') },
  { title: t('dashboard.tourAnalyticsTitle'), body: t('dashboard.tourAnalyticsBody') },
  { title: t('dashboard.tourCustomiseTitle'), body: t('dashboard.tourCustomiseBody') },
])

function next() {
  if (step.value < steps.value.length - 1) step.value++
  else dismiss()
}
function prev() {
  if (step.value > 0) step.value--
}
function dismiss() {
  visible.value = false
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, 'completed')
  } catch {
    // localStorage unavailable (e.g. private browsing) – ignore
  }
}

onMounted(() => {
  try {
    if (!localStorage.getItem(TOUR_STORAGE_KEY)) {
      visible.value = true
    }
  } catch {
    // localStorage unavailable – skip tour
  }
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 dark:bg-black/60 backdrop-blur-sm"
      @click.self="dismiss"
      role="dialog"
      aria-modal="true"
      :aria-label="t('dashboard.tourWelcomeTitle')"
    >
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl max-w-md w-full mx-4 p-6 space-y-4">
        <!-- Step indicator -->
        <div class="flex items-center gap-1.5 justify-center">
          <span
            v-for="i in steps.length"
            :key="i"
            class="inline-block h-1.5 rounded-full transition-all duration-300"
            :class="i - 1 === step ? 'w-6 bg-[color:var(--brand-color)]' : 'w-2 bg-gray-200 dark:bg-gray-700'"
          />
        </div>

        <!-- Content -->
        <div>
          <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">{{ steps[step].title }}</h2>
          <p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">{{ steps[step].body }}</p>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-between pt-2">
          <button
            type="button"
            class="text-sm text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
            @click="dismiss"
          >{{ t('dashboard.tourSkip') }}</button>

          <div class="flex items-center gap-2">
            <button
              v-if="step > 0"
              type="button"
              class="px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              @click="prev"
            >{{ t('dashboard.tourPrev') }}</button>
            <button
              type="button"
              class="px-4 py-1.5 text-sm font-medium bg-[color:var(--brand-color)] text-white rounded-xl hover:opacity-90 transition-opacity"
              @click="next"
            >{{ step === steps.length - 1 ? t('dashboard.tourDone') : t('dashboard.tourNext') }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

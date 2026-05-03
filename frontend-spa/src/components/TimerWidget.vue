<script setup lang="ts">
import { ref } from 'vue'
import { useTimerStore } from '@/stores/timer'
import { useI18n } from '@/composables/useI18n'
import TimerContextModal from '@/components/TimerContextModal.vue'
import type { TimerContext } from '@/stores/timer'

const props = withDefaults(defineProps<{ variant?: 'floating' | 'inline' }>(), {
  variant: 'floating',
})

const timerStore = useTimerStore()
const { t } = useI18n()
const modalOpen = ref(false)
const stopLoading = ref(false)
const toast = ref<string | null>(null)

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = null }, 3000)
}

function onStartClick() {
  if (timerStore.running) return
  modalOpen.value = true
}

function onConfirm(ctx: TimerContext, desc: string, billable: boolean) {
  modalOpen.value = false
  timerStore.start(ctx, desc, billable)
}

async function onStop() {
  stopLoading.value = true
  const result = await timerStore.stop()
  stopLoading.value = false
  if (result.ok) {
    showToast(t('timerWidget.saved'))
  } else {
    showToast(result.error ?? t('timerWidget.saveFailed'))
  }
}

function onReset() {
  timerStore.reset()
}
</script>

<template>
  <!-- ── Inline header variant ─────────────────────────────────────────── -->
  <template v-if="variant === 'inline'">
    <!-- Toast (teleported to body so it floats above everything) -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="toast"
          class="fixed bottom-6 right-6 z-50 bg-gray-900 text-white text-sm px-4 py-2 rounded-xl shadow-lg pointer-events-none"
        >
          {{ toast }}
        </div>
      </Transition>
    </Teleport>

    <!-- Running state: compact row -->
    <div
      v-if="timerStore.running"
      class="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800"
    >
      <!-- Pulsing dot -->
      <span class="relative flex h-2.5 w-2.5 flex-shrink-0">
        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" />
        <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-600" />
      </span>

      <span class="font-mono text-sm font-semibold text-red-700 dark:text-red-400 tabular-nums">
        {{ timerStore.displayTime }}
      </span>

      <span
        v-if="timerStore.context.entityLabel || timerStore.description"
        class="hidden lg:block text-xs text-red-500 dark:text-red-400 truncate max-w-32"
      >
        {{ timerStore.context.entityLabel || timerStore.description }}
      </span>

      <!-- Stop -->
      <button
        class="p-1 rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-60 transition-colors ml-1"
        :disabled="stopLoading"
        :title="t('timerWidget.stopAndSave')"
        :aria-label="t('timerWidget.stopTimer')"
        @click="onStop"
      >
        <svg v-if="!stopLoading" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
          <rect x="5" y="5" width="10" height="10" rx="1" />
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
        </svg>
      </button>

      <!-- Discard -->
      <button
        class="p-1 rounded-md text-red-400 hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors"
        :title="t('timerWidget.discard')"
        :aria-label="t('timerWidget.discardTimer')"
        @click="onReset"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <!-- Idle state: icon button -->
    <button
      v-else
      class="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-1.5"
      :aria-label="t('timerWidget.startTimer')"
      :title="t('timerWidget.trackTime')"
      @click="onStartClick"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </button>
  </template>

  <!-- ── Floating variant (legacy / bottom-right) ───────────────────────── -->
  <template v-else>
    <div
      class="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-2"
      aria-label="Sitewide timer"
    >
      <!-- Toast -->
      <Transition name="fade">
        <div
          v-if="toast"
          class="bg-gray-900 text-white text-sm px-4 py-2 rounded-xl shadow-lg pointer-events-none"
        >
          {{ toast }}
        </div>
      </Transition>

      <!-- Timer card (shown when running) -->
      <div
        v-if="timerStore.running"
        class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl px-4 py-3 flex items-center gap-3 min-w-[220px]"
      >
        <!-- Pulsing dot -->
        <span class="relative flex h-3 w-3 flex-shrink-0">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-500 opacity-75" />
          <span class="relative inline-flex rounded-full h-3 w-3 bg-red-600" />
        </span>

        <div class="flex-1 min-w-0">
          <div class="font-mono text-xl font-semibold text-gray-900 dark:text-gray-100 tabular-nums">
            {{ timerStore.displayTime }}
          </div>
          <div v-if="timerStore.context.entityLabel" class="text-xs text-gray-500 dark:text-gray-400 truncate">
            {{ timerStore.context.entityLabel }}
          </div>
          <div v-else-if="timerStore.description" class="text-xs text-gray-500 dark:text-gray-400 truncate">
            {{ timerStore.description }}
          </div>
        </div>

        <div class="flex gap-1">
          <!-- Stop -->
          <button
            class="p-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-60 transition-colors"
            :disabled="stopLoading"
            :title="t('timerWidget.stopAndSave')"
            @click="onStop"
            :aria-label="t('timerWidget.stopTimer')"
          >
            <svg v-if="!stopLoading" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <rect x="5" y="5" width="10" height="10" rx="1" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          </button>

          <!-- Discard -->
          <button
            class="p-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            :title="t('timerWidget.discard')"
            @click="onReset"
            :aria-label="t('timerWidget.discardTimer')"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Start button (shown when not running) -->
      <button
        v-else
        class="flex items-center gap-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl shadow-xl px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:border-red-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
        @click="onStartClick"
        :aria-label="t('timerWidget.startTimer')"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        </svg>
        {{ t('timerWidget.trackTime') }}
      </button>
    </div>
  </template>

  <!-- Context modal -->
  <TimerContextModal
    :open="modalOpen"
    @confirm="onConfirm"
    @close="modalOpen = false"
  />
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

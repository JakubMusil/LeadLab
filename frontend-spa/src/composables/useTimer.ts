/**
 * Phase 4.0 — useTimer composable
 *
 * Thin wrapper around the timer Pinia store that provides a clean API
 * for starting, stopping and resetting the sitewide timer from any component.
 */
import { storeToRefs } from 'pinia'
import { useTimerStore, type TimerContext } from '@/stores/timer'

export function useTimer() {
  const timerStore = useTimerStore()
  const { running, displayTime, context, description, isBillable, elapsedSeconds } = storeToRefs(timerStore)

  function startTimer(ctx: TimerContext = { entityType: null, entityId: null, entityLabel: null }, desc = '', billable = true) {
    timerStore.start(ctx, desc, billable)
  }

  async function stopTimer() {
    return timerStore.stop()
  }

  function resetTimer() {
    timerStore.reset()
  }

  return {
    // State (reactive refs)
    running,
    displayTime,
    context,
    description,
    isBillable,
    elapsedSeconds,
    // Actions
    startTimer,
    stopTimer,
    resetTimer,
  }
}

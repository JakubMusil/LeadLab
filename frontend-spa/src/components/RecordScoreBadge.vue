<script setup lang="ts">
/**
 * RecordScoreBadge — colour-coded 0–100 score badge for a pipeline record.
 *
 * Colour bands:
 *   0–29  red   (low)
 *   30–59 yellow (medium)
 *   60–79 blue   (good)
 *   80–100 green (high)
 */
const props = defineProps<{
  score: number | null | undefined
}>()

function badgeClass(score: number): string {
  if (score >= 80) return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300'
  if (score >= 60) return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
  if (score >= 30) return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300'
  return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'
}

function label(score: number): string {
  if (score >= 80) return 'High'
  if (score >= 60) return 'Good'
  if (score >= 30) return 'Medium'
  return 'Low'
}
</script>

<template>
  <span
    v-if="score != null"
    class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold"
    :class="badgeClass(score)"
    :title="`Record score: ${score}/100 (${label(score)})`"
    :aria-label="`Score ${score} out of 100`"
  >
    <span class="tabular-nums">{{ score }}</span>
  </span>
</template>

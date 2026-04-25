<script setup lang="ts">
defineProps<{ lines?: number; class?: string }>()
</script>

<template>
  <div class="animate-pulse space-y-3">
    <div v-for="i in lines ?? 3" :key="i" class="h-4 bg-gray-200 rounded w-full" />
  </div>
</template>

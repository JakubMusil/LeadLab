<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

withDefaults(
  defineProps<{
    items: { label: string; icon?: string; danger?: boolean; onClick: () => void }[]
    placement?: 'left' | 'right'
    openOnHover?: boolean
  }>(),
  { placement: 'right', openOnHover: false },
)

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

function handleClickOutside(e: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

function selectItem(item: { onClick: () => void }) {
  open.value = false
  item.onClick()
}
</script>

<template>
  <div
    ref="rootRef"
    class="relative inline-block"
    @mouseenter="openOnHover && (open = true)"
    @mouseleave="openOnHover && (open = false)"
  >
    <div @click.stop="open = !open">
      <slot />
    </div>
    <Transition name="dropdown">
      <div
        v-if="open"
        class="absolute z-40 mt-1 py-1 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg min-w-36"
        :class="placement === 'left' ? 'right-0' : 'left-0'"
        role="menu"
        @click.stop
      >
        <button
          v-for="item in items"
          :key="item.label"
          class="w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors"
          :class="
            item.danger
              ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
              : 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700'
          "
          role="menuitem"
          @click="selectItem(item)"
        >
          <span v-if="item.icon">{{ item.icon }}</span>
          {{ item.label }}
        </button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
@media (prefers-reduced-motion: reduce) {
  .dropdown-enter-active,
  .dropdown-leave-active {
    transition: none;
  }
}
</style>

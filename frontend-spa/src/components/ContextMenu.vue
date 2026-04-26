<script setup lang="ts">
/**
 * ContextMenu — right-click / long-press context menu.
 *
 * Usage:
 *   <ContextMenu :items="menuItems" @action="handleAction">
 *     <tr @contextmenu.prevent="openMenu">...</tr>
 *   </ContextMenu>
 *
 * Or trigger programmatically via the exposed `open(x, y)` method.
 */
import { ref, onMounted, onUnmounted } from 'vue'

export interface ContextMenuItem {
  id: string
  label: string
  icon?: string
  danger?: boolean
  disabled?: boolean
  divider?: boolean
}

defineProps<{
  items: ContextMenuItem[]
}>()

const emit = defineEmits<{
  action: [id: string]
}>()

const visible = ref(false)
const x = ref(0)
const y = ref(0)

function open(clientX: number, clientY: number) {
  x.value = clientX
  y.value = clientY
  visible.value = true
}

function close() {
  visible.value = false
}

function handleAction(id: string) {
  emit('action', id)
  close()
}

function onClickOutside() {
  if (visible.value) close()
}

function onScroll() {
  if (visible.value) close()
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
  document.addEventListener('scroll', onScroll, true)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close()
  })
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
  document.removeEventListener('scroll', onScroll, true)
})

defineExpose({ open, close })
</script>

<template>
  <slot />

  <Teleport to="body">
    <Transition
      enter-active-class="transition-all duration-100 ease-out"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-active-class="transition-all duration-75 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        class="fixed z-[200] min-w-[160px] bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 py-1 overflow-hidden"
        :style="{ top: `${y}px`, left: `${x}px` }"
        role="menu"
        aria-label="Context menu"
        @click.stop
      >
        <template v-for="item in items" :key="item.id">
          <div
            v-if="item.divider"
            class="h-px mx-2 my-1 bg-gray-200 dark:bg-gray-700"
            role="separator"
          />
          <button
            v-else
            type="button"
            class="w-full flex items-center gap-2.5 px-3 py-1.5 text-sm text-left transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            :class="item.danger
              ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
              : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'"
            :disabled="item.disabled"
            role="menuitem"
            @click="handleAction(item.id)"
          >
            <span v-if="item.icon" class="w-4 text-center flex-shrink-0">{{ item.icon }}</span>
            {{ item.label }}
          </button>
        </template>
      </div>
    </Transition>
  </Teleport>
</template>

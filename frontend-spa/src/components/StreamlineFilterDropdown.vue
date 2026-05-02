<script setup lang="ts">
/**
 * StreamlineFilterDropdown — single dropdown button that replaces the long
 * row of filter chips on the activity timeline.
 *
 * Behaviour:
 * - Lists every registered StreamlineTool grouped by `category`.
 * - Each item is a checkbox; checked = the type is currently visible.
 * - Header actions: "Important only" / "All" / "None" / "Reset to defaults".
 * - The component owns no persistence logic itself; it emits an `update:visible`
 *   event on every change with the new list (or `null` for "reset to defaults"),
 *   and the parent decides whether to persist (via the streamline preferences
 *   store) or apply the change session-only.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { ChevronDownIcon, FunnelIcon, CheckIcon } from '@heroicons/vue/24/outline'

export interface StreamlineToolItem {
  activity_type: string
  label: string
  category: string
  default_visibility: 'important' | 'secondary'
}

export interface ShortcutPreset {
  id: string
  name: string
  visible_activity_types: string[]
}

const props = defineProps<{
  /** All registered tools, used to build the dropdown sections. */
  tools: StreamlineToolItem[]
  /** Activity types currently visible. */
  modelValue: Set<string>
  /** Whether the user has customised the filter (drives "Reset" availability). */
  isCustomised: boolean
  shortcuts?: ShortcutPreset[]
}>()

const emit = defineEmits<{
  // Toggle a single type / replace the full set; pass `null` to reset to defaults.
  (e: 'update:visible', value: string[] | null): void
  (e: 'delete-shortcut', id: string): void
  (e: 'move-shortcut', payload: { fromIdx: number; toIdx: number }): void
}>()

const { t, te } = useI18n()

function toolLabel(tool: StreamlineToolItem): string {
  const camel = tool.activity_type.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
  const key = `leadDetail.type${camel.charAt(0).toUpperCase()}${camel.slice(1)}`
  if (te(key)) return t(key)

  if (tool.activity_type === 'call') return t('leadDetail.typeCall')
  if (tool.activity_type === 'task') return t('leadDetail.typeTask')
  if (tool.activity_type === 'meeting') return t('leadDetail.typeMeeting')
  if (tool.activity_type === 'comment') return t('leadDetail.typeComment')
  if (tool.activity_type === 'todo_items_added') return t('leadDetail.typeTodoItems')

  return tool.label
}

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

function toggleOpen() {
  open.value = !open.value
}

function onDocClick(ev: MouseEvent) {
  if (!rootRef.value) return
  if (!rootRef.value.contains(ev.target as Node)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('mousedown', onDocClick))
onUnmounted(() => document.removeEventListener('mousedown', onDocClick))

// Close dropdown on Escape for keyboard users.
function onKeydown(ev: KeyboardEvent) {
  if (ev.key === 'Escape') open.value = false
}

watch(open, (isOpen) => {
  if (isOpen) document.addEventListener('keydown', onKeydown)
  else document.removeEventListener('keydown', onKeydown)
})

// ---------------------------------------------------------------------------
// Grouping
// ---------------------------------------------------------------------------

const CATEGORY_ORDER: string[] = ['communication', 'task', 'planning', 'commerce', 'system', 'ai', 'meta']

const categoryLabel: Record<string, string> = {
  communication: 'streamlineFilter.categoryCommunication',
  task: 'streamlineFilter.categoryTask',
  planning: 'streamlineFilter.categoryPlanning',
  commerce: 'streamlineFilter.categoryCommerce',
  system: 'streamlineFilter.categorySystem',
  ai: 'streamlineFilter.categoryAi',
  meta: 'streamlineFilter.categoryMeta',
}

const groupedTools = computed(() => {
  const groups = new Map<string, StreamlineToolItem[]>()
  for (const tool of props.tools) {
    const cat = tool.category || 'meta'
    if (!groups.has(cat)) groups.set(cat, [])
    groups.get(cat)!.push(tool)
  }
  // Sort tools alphabetically by label within each category for predictable UX.
  for (const list of groups.values()) {
    list.sort((a, b) => a.label.localeCompare(b.label))
  }
  // Preserve a stable category order, putting unknown categories last.
  const ordered: { category: string; labelKey: string; items: StreamlineToolItem[] }[] = []
  for (const cat of CATEGORY_ORDER) {
    const items = groups.get(cat)
    if (items && items.length > 0) {
      ordered.push({ category: cat, labelKey: categoryLabel[cat] ?? cat, items })
      groups.delete(cat)
    }
  }
  for (const [cat, items] of groups) {
    ordered.push({ category: cat, labelKey: categoryLabel[cat] ?? cat, items })
  }
  return ordered
})

// ---------------------------------------------------------------------------
// Visibility helpers
// ---------------------------------------------------------------------------

function isVisible(activityType: string): boolean {
  return props.modelValue.has(activityType)
}

function toggle(activityType: string) {
  const next = new Set(props.modelValue)
  if (next.has(activityType)) next.delete(activityType)
  else next.add(activityType)
  emit('update:visible', Array.from(next))
}

function selectAll() {
  emit('update:visible', props.tools.map((t) => t.activity_type))
}

function selectNone() {
  emit('update:visible', [])
}

function selectImportantOnly() {
  emit(
    'update:visible',
    props.tools
      .filter((t) => t.default_visibility === 'important')
      .map((t) => t.activity_type),
  )
}

function resetToDefaults() {
  emit('update:visible', null)
}

// ---------------------------------------------------------------------------
// Button label
// ---------------------------------------------------------------------------

const totalCount = computed(() => props.tools.length)
const visibleCount = computed(() => {
  // Only count types that exist in the registry, so stale prefs don't inflate.
  let n = 0
  for (const tool of props.tools) {
    if (props.modelValue.has(tool.activity_type)) n++
  }
  return n
})
const hiddenCount = computed(() => totalCount.value - visibleCount.value)
</script>

<template>
  <div ref="rootRef" class="relative inline-block text-left">
    <button
      type="button"
      data-testid="streamline-filter-dropdown-button"
      class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
      :aria-expanded="open"
      aria-haspopup="true"
      @click="toggleOpen"
    >
      <FunnelIcon class="w-4 h-4" aria-hidden="true" />
      <span>{{ t('streamlineFilter.button') }}</span>
      <span
        v-if="hiddenCount > 0"
        class="ml-1 inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-[10px] font-semibold"
        data-testid="streamline-filter-hidden-count"
      >{{ hiddenCount }}</span>
      <ChevronDownIcon class="w-3.5 h-3.5" aria-hidden="true" />
    </button>

    <div
      v-if="open"
      class="absolute z-30 mt-1 w-80 max-h-[28rem] overflow-y-auto rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg p-2 text-sm"
      role="menu"
      data-testid="streamline-filter-dropdown-panel"
    >
      <!-- Quick actions -->
      <div class="flex flex-wrap gap-1 px-1 pb-2 border-b border-gray-100 dark:border-gray-700 mb-1">
        <button
          type="button"
          class="px-2 py-1 rounded text-[11px] font-medium bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200"
          data-testid="streamline-filter-action-important"
          @click="selectImportantOnly"
        >{{ t('streamlineFilter.importantOnly') }}</button>
        <button
          type="button"
          class="px-2 py-1 rounded text-[11px] font-medium bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200"
          data-testid="streamline-filter-action-all"
          @click="selectAll"
        >{{ t('streamlineFilter.all') }}</button>
        <button
          type="button"
          class="px-2 py-1 rounded text-[11px] font-medium bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200"
          data-testid="streamline-filter-action-none"
          @click="selectNone"
        >{{ t('streamlineFilter.none') }}</button>
        <button
          v-if="isCustomised"
          type="button"
          class="ml-auto px-2 py-1 rounded text-[11px] font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
          data-testid="streamline-filter-action-reset"
          @click="resetToDefaults"
        >{{ t('streamlineFilter.reset') }}</button>
      </div>

      <!-- Grouped checkboxes -->
      <div
        v-for="group in groupedTools"
        :key="group.category"
        class="py-1"
        :data-testid="'streamline-filter-group-' + group.category"
      >
        <div class="px-2 pt-1 pb-0.5 text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500">
          {{ t(group.labelKey) }}
        </div>
        <button
          v-for="tool in group.items"
          :key="tool.activity_type"
          type="button"
          class="w-full flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-700 text-left"
          :data-testid="'streamline-filter-item'"
          :data-activity-type="tool.activity_type"
          :data-active="isVisible(tool.activity_type) ? 'true' : 'false'"
          @click="toggle(tool.activity_type)"
        >
          <span
            class="flex items-center justify-center w-4 h-4 rounded border"
            :class="isVisible(tool.activity_type)
              ? 'bg-red-600 border-red-600 text-white'
              : 'border-gray-300 dark:border-gray-500'"
          >
            <CheckIcon v-if="isVisible(tool.activity_type)" class="w-3 h-3" aria-hidden="true" />
          </span>
          <span class="flex-1 text-gray-700 dark:text-gray-200">{{ toolLabel(tool) }}</span>
          <span
            v-if="tool.default_visibility === 'secondary'"
            class="text-[9px] uppercase tracking-wide text-gray-400 dark:text-gray-500"
            :title="t('streamlineFilter.secondaryHint')"
          >{{ t('streamlineFilter.secondaryBadge') }}</span>
        </button>
      </div>

      <!-- Shortcuts management -->
      <div v-if="shortcuts && shortcuts.length > 0" class="border-t border-gray-100 dark:border-gray-700 mt-2 pt-2 px-1">
        <div class="px-2 pb-1.5 text-[10px] uppercase tracking-wider font-semibold text-gray-400 dark:text-gray-500">
          Správa zkratek
        </div>
        <div class="space-y-1">
          <div
            v-for="(shortcut, idx) in shortcuts"
            :key="shortcut.id"
            class="flex items-center justify-between px-2 py-1 bg-gray-50 dark:bg-gray-700/50 rounded text-xs text-gray-700 dark:text-gray-300"
          >
            <span class="truncate max-w-[120px]">{{ shortcut.name }}</span>
            <div class="flex items-center gap-1.5 flex-shrink-0">
              <button
                v-if="idx > 0"
                type="button"
                class="p-0.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                title="Posunout nahoru"
                @click.stop="emit('move-shortcut', { fromIdx: idx, toIdx: idx - 1 })"
              >↑</button>
              <button
                v-if="idx < shortcuts.length - 1"
                type="button"
                class="p-0.5 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                title="Posunout dolů"
                @click.stop="emit('move-shortcut', { fromIdx: idx, toIdx: idx + 1 })"
              >↓</button>
              <button
                type="button"
                class="p-0.5 text-xs text-red-500 hover:text-red-700 transition-colors"
                title="Smazat"
                @click.stop="emit('delete-shortcut', shortcut.id)"
              >×</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

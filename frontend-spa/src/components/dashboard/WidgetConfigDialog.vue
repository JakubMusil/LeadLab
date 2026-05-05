<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { XMarkIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'
import {
  WIDGET_CONFIG_SCHEMA,
  type WidgetConfigField,
  type WidgetConfigOptions,
  type WidgetSortOption,
  type DashboardScope,
  type DashboardRange,
} from '@/stores/dashboard'
import { useDashboardLayoutStore } from '@/stores/dashboard'
import { usePipelineStore } from '@/stores/pipeline'

const props = defineProps<{
  /** Widget id; when null/empty, the dialog is hidden. */
  widgetId: string | null
  /** Human-readable widget label shown in the dialog title. */
  widgetLabel?: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useI18n()
const layoutStore = useDashboardLayoutStore()
const pipelineStore = usePipelineStore()

const activeCategories = computed(() => pipelineStore.categories.filter((c) => c.is_active))

const fields = computed<WidgetConfigField[]>(() => {
  if (!props.widgetId) return []
  return WIDGET_CONFIG_SCHEMA[props.widgetId] ?? []
})

const config = computed<WidgetConfigOptions>(() => {
  if (!props.widgetId) return {}
  return layoutStore.getWidgetConfigOptions(props.widgetId)
})

function setField<K extends keyof WidgetConfigOptions>(key: K, value: WidgetConfigOptions[K]) {
  if (!props.widgetId) return
  layoutStore.updateWidgetConfigOptions(props.widgetId, { [key]: value } as Partial<WidgetConfigOptions>)
}

function clearOverride(key: keyof WidgetConfigOptions) {
  setField(key, undefined as never)
}

function close() {
  // Persist changes when the dialog closes (fire-and-forget; non-critical).
  layoutStore.saveLayout().catch(() => undefined)
  emit('close')
}

// ESC key support – single global handler that only acts while a widgetId is
// set. Registering once on mount and removing on unmount avoids the listener
// leak from re-registering on every prop change.
function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.widgetId) close()
}
onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))

// --- field-specific options -------------------------------------------------

const RANGE_OPTIONS: { value: DashboardRange; labelKey: string }[] = [
  { value: '7d', labelKey: 'range7d' },
  { value: '30d', labelKey: 'range30d' },
  { value: '90d', labelKey: 'range90d' },
  { value: 'qtd', labelKey: 'rangeQtd' },
  { value: 'ytd', labelKey: 'rangeYtd' },
  { value: 'all', labelKey: 'rangeAll' },
]

const SCOPE_OPTIONS: { value: DashboardScope; labelKey: string }[] = [
  { value: 'mine', labelKey: 'cfgScopeMine' },
  { value: 'firm', labelKey: 'cfgScopeFirm' },
]

function sortLabel(opt: WidgetSortOption): string {
  if (opt === 'score') return t('dashboard.cfgSortScore')
  if (opt === 'value') return t('dashboard.cfgSortValue')
  return t('dashboard.cfgSortStale')
}

function clampNumber(field: WidgetConfigField, raw: string): number {
  const n = Number.parseInt(raw, 10)
  if (Number.isNaN(n)) return field.min ?? 1
  const min = field.min ?? Number.MIN_SAFE_INTEGER
  const max = field.max ?? Number.MAX_SAFE_INTEGER
  return Math.max(min, Math.min(max, n))
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="widgetId && fields.length > 0"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      :aria-label="t('dashboard.cfgDialogTitle')"
      @click.self="close"
    >
      <div class="w-full max-w-md bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-xl">
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <div>
            <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {{ t('dashboard.cfgDialogTitle') }}
            </h3>
            <p v-if="widgetLabel" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ widgetLabel }}</p>
          </div>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors p-1 rounded"
            :aria-label="t('dashboard.cfgClose')"
            @click="close"
          >
            <XMarkIcon class="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        <!-- Body -->
        <div class="p-5 space-y-4">
          <div v-for="field in fields" :key="field.key" class="space-y-1">
            <label class="text-xs font-medium text-gray-700 dark:text-gray-300 block">
              {{ t('dashboard.' + field.labelKey) }}
            </label>

            <!-- Range -->
            <div v-if="field.type === 'range'" class="flex flex-wrap gap-1">
              <button
                type="button"
                class="px-2.5 py-1 text-xs font-medium rounded-lg transition-colors border"
                :class="config.range == null ? 'bg-[color:var(--brand-color)] text-white border-transparent' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
                @click="clearOverride('range')"
              >
                {{ t('dashboard.cfgUseGlobal') }}
              </button>
              <button
                v-for="r in RANGE_OPTIONS"
                :key="r.value"
                type="button"
                class="px-2.5 py-1 text-xs font-medium rounded-lg transition-colors border"
                :class="config.range === r.value ? 'bg-[color:var(--brand-color)] text-white border-transparent' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
                @click="setField('range', r.value)"
              >
                {{ t('dashboard.' + r.labelKey) }}
              </button>
            </div>

            <!-- Scope -->
            <div v-else-if="field.type === 'scope'" class="flex gap-1">
              <button
                v-for="s in SCOPE_OPTIONS"
                :key="s.value"
                type="button"
                class="flex-1 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors border"
                :class="(config.scope ?? 'mine') === s.value ? 'bg-[color:var(--brand-color)] text-white border-transparent' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'"
                @click="setField('scope', s.value)"
              >
                {{ t('dashboard.' + s.labelKey) }}
              </button>
            </div>

            <!-- Sort -->
            <select
              v-else-if="field.type === 'sort'"
              :value="config.sort ?? (field.sortOptions?.[0] ?? 'score')"
              class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200"
              @change="setField('sort', ($event.target as HTMLSelectElement).value as WidgetSortOption)"
            >
              <option v-for="opt in (field.sortOptions ?? [])" :key="opt" :value="opt">
                {{ sortLabel(opt) }}
              </option>
            </select>

            <!-- Number -->
            <input
              v-else-if="field.type === 'number'"
              type="number"
              :value="config[field.key] ?? ''"
              :min="field.min"
              :max="field.max"
              :placeholder="t('dashboard.cfgUseDefault')"
              class="w-32 px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200"
              @change="setField(field.key, clampNumber(field, ($event.target as HTMLInputElement).value))"
            />

            <!-- Category -->
            <select
              v-else-if="field.type === 'category'"
              :value="config.category_id ?? ''"
              class="w-full px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-200"
              @change="setField('category_id', ($event.target as HTMLSelectElement).value || null)"
            >
              <option value="">{{ t('dashboard.cfgAllCategories') }}</option>
              <option
                v-for="cat in activeCategories"
                :key="cat.id"
                :value="cat.id"
              >
                {{ cat.name }}
              </option>
            </select>

            <p v-if="field.type === 'number' && (field.min != null || field.max != null)" class="text-[11px] text-gray-400">
              {{ t('dashboard.cfgRange', { min: field.min ?? 0, max: field.max ?? 0 }) }}
            </p>
          </div>

          <p class="text-[11px] text-gray-400 dark:text-gray-500 pt-2 border-t border-gray-100 dark:border-gray-700">
            {{ t('dashboard.cfgHint') }}
          </p>
        </div>

        <!-- Footer -->
        <div class="px-5 py-3 border-t border-gray-100 dark:border-gray-700 flex justify-end">
          <button
            type="button"
            class="px-3 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-xs font-medium hover:opacity-90 transition-opacity"
            @click="close"
          >
            {{ t('dashboard.cfgDone') }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

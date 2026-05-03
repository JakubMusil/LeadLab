import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import type { Ref } from 'vue'

export interface ColumnDef<ColId extends string = string> {
  id: ColId
  /** Key within the entity's i18n namespace, e.g. 'colStatus'. */
  labelKey: string
  defaultVisible: boolean
}

interface UseListViewOptions<SortF extends string, ColId extends string> {
  /**
   * localStorage key prefix, e.g. 'leadlab_leads'.
   * The current user ID is appended automatically.
   */
  storageKeyPrefix: string
  columns: ColumnDef<ColId>[]
  defaultSortField: SortF
  defaultSortDir?: 'asc' | 'desc'
}

/**
 * Composable that encapsulates sort state and column visibility for list/table views.
 * Persists column prefs to localStorage (keyed per user).
 * Automatically registers / removes a document click listener that closes the column picker.
 */
export function useListView<SortF extends string, ColId extends string>(
  opts: UseListViewOptions<SortF, ColId>,
  userId: Ref<string | undefined>,
) {
  // ── Sort ──────────────────────────────────────────────────────────────────

  const sortField = ref<SortF>(opts.defaultSortField) as Ref<SortF>
  const sortDir = ref<'asc' | 'desc'>(opts.defaultSortDir ?? 'desc')

  function setSort(field: SortF) {
    if (sortField.value === field) {
      sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortField.value = field
      sortDir.value = 'asc'
    }
  }

  function sortIcon(field: SortF): string {
    if (sortField.value !== field) return '↕'
    return sortDir.value === 'asc' ? '↑' : '↓'
  }

  // ── Column visibility ─────────────────────────────────────────────────────

  const defaultVisibleCols = opts.columns
    .filter((c) => c.defaultVisible)
    .map((c) => c.id) as ColId[]

  const visibleColumns = ref<ColId[]>([...defaultVisibleCols]) as Ref<ColId[]>
  const columnPickerOpen = ref(false)
  const validColIds = opts.columns.map((c) => c.id)

  // ── localStorage ──────────────────────────────────────────────────────────

  watch(
    userId,
    (uid) => {
      if (!uid) return
      try {
        const raw = localStorage.getItem(`${opts.storageKeyPrefix}_cols_u${uid}`)
        if (!raw) return
        const parsed = JSON.parse(raw) as string[]
        if (Array.isArray(parsed) && parsed.length > 0) {
          const valid = parsed.filter((c) => validColIds.includes(c as ColId)) as ColId[]
          if (valid.length > 0) visibleColumns.value = valid
        }
      } catch { /* ignore */ }
    },
    { immediate: true },
  )

  watch(
    visibleColumns,
    (cols) => {
      const uid = userId.value
      if (!uid) return
      try {
        localStorage.setItem(`${opts.storageKeyPrefix}_cols_u${uid}`, JSON.stringify(cols))
      } catch { /* ignore */ }
    },
    { deep: true },
  )

  // ── Column helpers ────────────────────────────────────────────────────────

  function isColVisible(id: ColId): boolean {
    return visibleColumns.value.includes(id)
  }

  function toggleColumn(id: ColId) {
    const idx = visibleColumns.value.indexOf(id)
    if (idx === -1) {
      visibleColumns.value = [...visibleColumns.value, id]
    } else {
      visibleColumns.value = visibleColumns.value.filter((c) => c !== id)
    }
  }

  function resetColumns() {
    visibleColumns.value = [...defaultVisibleCols]
  }

  // ── Column picker close-on-outside-click ──────────────────────────────────

  function closeColumnPicker() {
    columnPickerOpen.value = false
  }

  onMounted(() => document.addEventListener('click', closeColumnPicker))
  onBeforeUnmount(() => document.removeEventListener('click', closeColumnPicker))

  return {
    // sort
    sortField,
    sortDir,
    DEFAULT_SORT_FIELD: opts.defaultSortField,
    DEFAULT_SORT_DIR: (opts.defaultSortDir ?? 'desc') as 'asc' | 'desc',
    setSort,
    sortIcon,
    // columns
    columns: opts.columns,
    defaultVisibleCols,
    visibleColumns,
    columnPickerOpen,
    isColVisible,
    toggleColumn,
    resetColumns,
  }
}

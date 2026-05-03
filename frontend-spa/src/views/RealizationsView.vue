<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  useRealizationsStore,
  REALIZATION_STATUSES,
  getRealizationStatusMeta,
  type RealizationOut,
  type RealizationIn,
} from '@/stores/realizations'
import { useCustomersStore, type CustomerOut } from '@/stores/customers'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useListView, type ColumnDef } from '@/composables/useListView'
import {
  PencilSquareIcon, XMarkIcon, TrashIcon,
  Bars3Icon, Squares2X2Icon, ListBulletIcon, AdjustmentsHorizontalIcon,
} from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'
import Avatar from '@/components/ui/Avatar.vue'

const router = useRouter()
const store = useRealizationsStore()
const customersStore = useCustomersStore()
const authStore = useAuthStore()
const toast = useToast()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// View mode (kanban | table | list) with localStorage persistence
// ---------------------------------------------------------------------------
type ViewMode = 'table' | 'kanban' | 'list'
const VIEW_MODES = ['table', 'kanban', 'list'] as const
const viewModeIcons: Record<ViewMode, object> = {
  table: Bars3Icon,
  kanban: Squares2X2Icon,
  list: ListBulletIcon,
}

const viewMode = ref<ViewMode>('kanban')

watch(() => authStore.user?.id, (userId) => {
  if (!userId) return
  try {
    const stored = localStorage.getItem(`leadlab_realizations_displaymode_u${userId}`)
    if (stored === 'table' || stored === 'kanban' || stored === 'list') viewMode.value = stored
  } catch { /* ignore */ }
}, { immediate: true })

watch(viewMode, (mode) => {
  const userId = authStore.user?.id
  if (!userId) return
  try {
    localStorage.setItem(`leadlab_realizations_displaymode_u${userId}`, mode)
  } catch { /* ignore */ }
})

// ---------------------------------------------------------------------------
// Sort + Column visibility (via useListView composable)
// ---------------------------------------------------------------------------
type SortField = 'title' | 'status' | 'customer_name' | 'end_date' | 'created_at'
type ColumnId = 'status' | 'customer' | 'end_date' | 'assigned_to' | 'created_at'

const TABLE_COLUMNS: ColumnDef<ColumnId>[] = [
  { id: 'status', labelKey: 'colStatus', defaultVisible: true },
  { id: 'customer', labelKey: 'colCustomer', defaultVisible: true },
  { id: 'end_date', labelKey: 'colDeadline', defaultVisible: true },
  { id: 'assigned_to', labelKey: 'colAssignedTo', defaultVisible: false },
  { id: 'created_at', labelKey: 'colCreatedAt', defaultVisible: false },
]

const {
  sortField, sortDir, setSort, sortIcon,
  visibleColumns, columnPickerOpen, isColVisible, toggleColumn, resetColumns,
} = useListView<SortField, ColumnId>(
  { storageKeyPrefix: 'leadlab_realizations', columns: TABLE_COLUMNS, defaultSortField: 'created_at', defaultSortDir: 'desc' },
  computed(() => authStore.user?.id),
)

// ---------------------------------------------------------------------------
// Client-side filter + sort
// ---------------------------------------------------------------------------
const filterStatus = ref('')
const filterSearch = ref('')

const REALIZATION_STATUS_ORDER: Record<string, number> = {
  planned: 1, in_progress: 2, on_hold: 3, done: 4, cancelled: 5,
}

const filteredAndSortedRealizations = computed(() => {
  let items = store.realizations.filter((r) => {
    if (filterStatus.value && r.status !== filterStatus.value) return false
    if (filterSearch.value) {
      const q = filterSearch.value.toLowerCase()
      return (
        r.title.toLowerCase().includes(q) ||
        (r.customer_name ?? '').toLowerCase().includes(q)
      )
    }
    return true
  })
  return items.slice().sort((a, b) => {
    let cmp = 0
    if (sortField.value === 'created_at') {
      cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    } else if (sortField.value === 'status') {
      cmp = (REALIZATION_STATUS_ORDER[a.status] ?? 0) - (REALIZATION_STATUS_ORDER[b.status] ?? 0)
    } else if (sortField.value === 'end_date') {
      const ad = a.end_date ?? ''
      const bd = b.end_date ?? ''
      cmp = ad < bd ? -1 : ad > bd ? 1 : 0
    } else {
      const va = ((a as Record<string, unknown>)[sortField.value] ?? '') as string
      const vb = ((b as Record<string, unknown>)[sortField.value] ?? '') as string
      cmp = va.localeCompare(vb)
    }
    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

// Kanban uses all items (unfiltered by status, but respects search)
const reByStatus = computed(() => {
  const map: Record<string, RealizationOut[]> = {}
  for (const s of REALIZATION_STATUSES) map[s.value] = []
  const items = filterSearch.value
    ? store.realizations.filter((r) => {
        const q = filterSearch.value.toLowerCase()
        return r.title.toLowerCase().includes(q) || (r.customer_name ?? '').toLowerCase().includes(q)
      })
    : store.realizations
  for (const r of items) {
    const bucket = map[r.status] ?? map['planned']
    bucket?.push(r)
  }
  return map
})

// ---------------------------------------------------------------------------
// Modal / form state (unchanged)
// ---------------------------------------------------------------------------
const showModal = ref(false)
const editingRealization = ref<RealizationOut | null>(null)
const confirmDeleteId = ref<string | null>(null)

const formTitle = ref('')
const formStatus = ref('planned')
const formCustomerId = ref<string | null>(null)
const formCustomerQuery = ref('')
const customerSuggestions = ref<CustomerOut[]>([])
const showCustomerDropdown = ref(false)
const formLoading = ref(false)
const formError = ref('')

onMounted(async () => {
  await store.fetchRealizations()
  await customersStore.fetchCustomers()
})

function openCreate() {
  editingRealization.value = null
  formTitle.value = ''
  formStatus.value = 'planned'
  formCustomerId.value = null
  formCustomerQuery.value = ''
  formError.value = ''
  showModal.value = true
}

function openEdit(r: RealizationOut) {
  editingRealization.value = r
  formTitle.value = r.title
  formStatus.value = r.status
  formCustomerId.value = r.customer_id
  formCustomerQuery.value = r.customer_name ?? ''
  formError.value = ''
  showModal.value = true
}

async function submitForm() {
  if (!formTitle.value.trim()) {
    formError.value = t('realizations.titleRequired')
    return
  }
  formLoading.value = true
  formError.value = ''
  try {
    const payload: RealizationIn = {
      title: formTitle.value.trim(),
      status: formStatus.value,
      customer_id: formCustomerId.value || null,
    }
    if (editingRealization.value) {
      const updated = await store.updateRealization(editingRealization.value.id, payload)
      if (updated) {
        toast.success(t('realizations.updated'))
        showModal.value = false
      }
    } else {
      const created = await store.createRealization(payload)
      if (created) {
        toast.success(t('realizations.created'))
        showModal.value = false
      }
    }
  } finally {
    formLoading.value = false
  }
}

async function handleDelete(id: string) {
  const ok = await store.deleteRealization(id)
  if (ok) {
    toast.success(t('realizations.deleted'))
    confirmDeleteId.value = null
  }
}

function onCustomerInput() {
  const q = formCustomerQuery.value.trim().toLowerCase()
  if (!q) {
    customerSuggestions.value = []
    showCustomerDropdown.value = false
    return
  }
  customerSuggestions.value = customersStore.customers.filter((c) => {
    const name = `${c.first_name} ${c.last_name} ${c.company_name}`.toLowerCase()
    return name.includes(q)
  }).slice(0, 8)
  showCustomerDropdown.value = customerSuggestions.value.length > 0
}

function selectCustomer(c: CustomerOut) {
  formCustomerId.value = c.id
  formCustomerQuery.value = `${c.first_name} ${c.last_name}`.trim() || c.company_name
  showCustomerDropdown.value = false
}
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-5 flex-wrap">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100 flex-1">{{ t('realizations.title') }}</h2>

      <!-- View toggle -->
      <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1">
        <button
          v-for="mode in VIEW_MODES"
          :key="mode"
          class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors"
          :class="viewMode === mode
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
          @click="viewMode = mode"
        >
          <component :is="viewModeIcons[mode]" class="w-4 h-4 inline-block mr-1 align-text-bottom" />{{ t(`realizations.viewMode_${mode}`) }}
        </button>
      </div>

      <!-- Filters (table & list) -->
      <template v-if="viewMode !== 'kanban'">
        <select
          v-model="filterStatus"
          class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400"
        >
          <option value="">{{ t('realizations.filterAll') }}</option>
          <option v-for="s in REALIZATION_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
        <input
          v-model="filterSearch"
          type="search"
          :placeholder="t('realizations.filterSearch')"
          class="rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400 w-44"
        />
      </template>

      <button
        class="bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors"
        @click="openCreate"
      >+ {{ t('realizations.new') }}</button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="store.loading && store.realizations.length === 0" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
    </div>

    <!-- TABLE VIEW -->
    <template v-else-if="viewMode === 'table'">
      <div v-if="filteredAndSortedRealizations.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
        <div class="w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4">
          <svg class="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('realizations.none') }}</h3>
        <button
          v-if="!filterStatus && !filterSearch"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors mt-4"
          @click="openCreate"
        >{{ t('realizations.new') }}</button>
      </div>
      <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-100 dark:border-gray-700 text-left">
              <th class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('title')">{{ t('realizations.colTitle') }} <span class="opacity-60">{{ sortIcon('title') }}</span></th>
              <th v-if="isColVisible('status')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('status')">{{ t('realizations.colStatus') }} <span class="opacity-60">{{ sortIcon('status') }}</span></th>
              <th v-if="isColVisible('customer')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('customer_name')">{{ t('realizations.colCustomer') }} <span class="opacity-60">{{ sortIcon('customer_name') }}</span></th>
              <th v-if="isColVisible('end_date')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('end_date')">{{ t('realizations.colDeadline') }} <span class="opacity-60">{{ sortIcon('end_date') }}</span></th>
              <th v-if="isColVisible('assigned_to')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('realizations.colAssignedTo') }}</th>
              <th v-if="isColVisible('created_at')" class="px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none" @click="setSort('created_at')">{{ t('realizations.colCreatedAt') }} <span class="opacity-60">{{ sortIcon('created_at') }}</span></th>
              <!-- Column picker -->
              <th class="px-4 py-3 text-right">
                <div class="relative inline-block">
                  <button
                    type="button"
                    class="p-1 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    :title="t('realizations.colPicker')"
                    :aria-label="t('realizations.colPicker')"
                    @click.stop="columnPickerOpen = !columnPickerOpen"
                  >
                    <AdjustmentsHorizontalIcon class="w-4 h-4" />
                  </button>
                  <div
                    v-if="columnPickerOpen"
                    class="absolute right-0 top-8 z-20 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-2 min-w-44"
                    @click.stop
                  >
                    <div class="px-3 pb-1.5 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
                      <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">{{ t('realizations.colPicker') }}</span>
                      <button type="button" class="text-xs text-red-500 hover:text-red-700" @click="resetColumns">{{ t('realizations.resetColumns') }}</button>
                    </div>
                    <label
                      v-for="col in TABLE_COLUMNS"
                      :key="col.id"
                      class="flex items-center gap-2.5 px-3 py-1.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 text-sm text-gray-700 dark:text-gray-300"
                    >
                      <input
                        type="checkbox"
                        class="rounded border-gray-300 text-red-600 focus:ring-red-500"
                        :checked="isColVisible(col.id)"
                        @change="toggleColumn(col.id)"
                      />
                      {{ t(`realizations.${col.labelKey}`) }}
                    </label>
                  </div>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in filteredAndSortedRealizations"
              :key="r.id"
              class="border-b border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
              @click="router.push(`/app/realizations/${r.id}`)"
            >
              <td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100 max-w-xs">
                <span class="truncate block">{{ r.title }}</span>
              </td>
              <td v-if="isColVisible('status')" class="px-4 py-3">
                <span :class="getRealizationStatusMeta(r.status).color" class="px-2 py-0.5 rounded-lg text-xs font-medium">
                  {{ getRealizationStatusMeta(r.status).label }}
                </span>
              </td>
              <td v-if="isColVisible('customer')" class="px-4 py-3 text-gray-500 dark:text-gray-400">{{ r.customer_name ?? '—' }}</td>
              <td v-if="isColVisible('end_date')" class="px-4 py-3 text-gray-500 dark:text-gray-400">{{ r.end_date ?? '—' }}</td>
              <td v-if="isColVisible('assigned_to')" class="px-4 py-3">
                <Avatar v-if="r.assigned_to_name" size="xs" :name="r.assigned_to_name" :title="r.assigned_to_name" />
                <span v-else class="text-gray-300 dark:text-gray-600">—</span>
              </td>
              <td v-if="isColVisible('created_at')" class="px-4 py-3 text-gray-400 dark:text-gray-500 text-xs">{{ new Date(r.created_at).toLocaleDateString() }}</td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('realizations.edit')" @click.stop="openEdit(r)"><PencilSquareIcon class="w-4 h-4" /></button>
                  <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('realizations.deleteBtn')" @click.stop="confirmDeleteId = r.id"><TrashIcon class="w-4 h-4" /></button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- LIST VIEW -->
    <template v-else-if="viewMode === 'list'">
      <div v-if="filteredAndSortedRealizations.length === 0" class="flex flex-col items-center justify-center py-20 text-center">
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('realizations.none') }}</h3>
        <button
          v-if="!filterStatus && !filterSearch"
          class="px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors mt-4"
          @click="openCreate"
        >{{ t('realizations.new') }}</button>
      </div>
      <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700">
        <div
          v-for="r in filteredAndSortedRealizations"
          :key="r.id"
          class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group"
          @click="router.push(`/app/realizations/${r.id}`)"
        >
          <!-- Status dot -->
          <span class="w-2.5 h-2.5 rounded-full flex-shrink-0" :class="getRealizationStatusMeta(r.status).color.split(' ')[0]" :aria-label="getRealizationStatusMeta(r.status).label" />

          <!-- Title -->
          <span class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ r.title }}</span>

          <!-- Status badge -->
          <span class="hidden sm:inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium flex-shrink-0" :class="getRealizationStatusMeta(r.status).color">
            {{ getRealizationStatusMeta(r.status).label }}
          </span>

          <!-- Customer -->
          <span class="hidden md:block text-xs text-gray-400 dark:text-gray-500 flex-shrink-0 w-32 truncate">{{ r.customer_name ?? '' }}</span>

          <!-- Deadline -->
          <span class="hidden lg:block text-xs text-gray-400 dark:text-gray-500 flex-shrink-0 w-24 text-right">{{ r.end_date ?? '' }}</span>

          <!-- Assignee avatar -->
          <div class="hidden sm:flex items-center flex-shrink-0" @click.stop>
            <Avatar v-if="r.assigned_to_name" size="xs" :name="r.assigned_to_name" :title="r.assigned_to_name" />
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" @click.stop>
            <button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400" :aria-label="t('realizations.edit')" @click="openEdit(r)"><PencilSquareIcon class="w-4 h-4" /></button>
            <button class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500" :aria-label="t('realizations.deleteBtn')" @click="confirmDeleteId = r.id"><TrashIcon class="w-4 h-4" /></button>
          </div>
        </div>
      </div>
    </template>

    <!-- KANBAN VIEW -->
    <template v-else-if="viewMode === 'kanban'">
      <div class="flex gap-4 overflow-x-auto pb-4">
        <div
          v-for="col in REALIZATION_STATUSES"
          :key="col.value"
          class="flex-shrink-0 w-72 bg-gray-50 dark:bg-gray-800/50 rounded-2xl p-3 border border-gray-100 dark:border-gray-700"
        >
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm font-semibold text-gray-700 dark:text-gray-300">{{ col.label }}</span>
            <span class="text-xs text-gray-500 bg-gray-200 dark:bg-gray-700 rounded-full px-2 py-0.5">
              {{ reByStatus[col.value]?.length ?? 0 }}
            </span>
          </div>
          <div class="space-y-2 min-h-16">
            <div
              v-for="r in reByStatus[col.value]"
              :key="r.id"
              class="bg-white dark:bg-gray-700 rounded-xl border border-gray-100 dark:border-gray-600 p-3 shadow-sm hover:shadow transition-shadow cursor-pointer group"
              @click="router.push(`/app/realizations/${r.id}`)"
            >
              <div class="flex items-start justify-between gap-2">
                <p class="text-sm font-medium text-gray-900 dark:text-white leading-snug">{{ r.title }}</p>
                <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                  <button class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-600 text-gray-400" :aria-label="t('realizations.edit')" @click.stop="openEdit(r)"><PencilSquareIcon class="w-3.5 h-3.5" /></button>
                </div>
              </div>
              <div v-if="r.customer_name" class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ r.customer_name }}</div>
              <div class="flex items-center justify-between mt-2">
                <span v-if="r.end_date" class="text-xs text-gray-400">{{ r.end_date }}</span>
                <div class="ml-auto">
                  <Avatar v-if="r.assigned_to_name" size="xs" :name="r.assigned_to_name" :title="r.assigned_to_name" />
                </div>
              </div>
            </div>
            <div v-if="(reByStatus[col.value]?.length ?? 0) === 0" class="text-center text-xs text-gray-300 dark:text-gray-600 py-4">—</div>
          </div>
        </div>
      </div>
    </template>
  </div>

  <!-- Create/Edit Modal -->
  <Teleport to="body">
    <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="showModal = false">
      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6" role="dialog" aria-modal="true" :aria-label="editingRealization ? t('realizations.editTitle') : t('realizations.newTitle')">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {{ editingRealization ? t('realizations.editTitle') : t('realizations.newTitle') }}
        </h3>
        <div v-if="formError" class="mb-4 p-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-sm">{{ formError }}</div>
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.nameLabel') }}</label>
            <input
              v-model="formTitle"
              type="text"
              :placeholder="t('realizations.namePlaceholder')"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.statusLabel') }}</label>
            <select
              v-model="formStatus"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            >
              <option v-for="s in REALIZATION_STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
          <div class="relative">
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('realizations.customerLabel') }}</label>
            <input
              v-model="formCustomerQuery"
              @input="onCustomerInput"
              type="text"
              :placeholder="t('realizations.customerSearch')"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:border-red-400"
            />
            <div v-if="showCustomerDropdown" class="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-700 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg z-10 max-h-48 overflow-y-auto">
              <button
                v-for="c in customerSuggestions"
                :key="c.id"
                @mousedown.prevent="selectCustomer(c)"
                class="w-full text-left px-3 py-2 text-sm text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                {{ c.first_name }} {{ c.last_name }} {{ c.company_name ? `(${c.company_name})` : '' }}
              </button>
            </div>
          </div>
        </div>
        <div class="flex gap-3 pt-5">
          <button type="button" class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700" @click="showModal = false">{{ t('common.cancel') }}</button>
          <button
            type="button"
            :disabled="formLoading"
            class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60"
            @click="submitForm"
          >
            {{ formLoading ? t('common.saving') : (editingRealization ? t('common.save') : t('common.create')) }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <ConfirmDeleteModal
    :open="!!confirmDeleteId"
    :title="t('realizations.confirmDeleteTitle')"
    :message="t('common.irreversible')"
    @confirm="handleDelete(confirmDeleteId!)"
    @cancel="confirmDeleteId = null"
  />
</template>

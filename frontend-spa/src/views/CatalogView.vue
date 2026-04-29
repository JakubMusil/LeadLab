<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useFirmStore } from '@/stores/firm'
import RichTextEditor from '@/components/RichTextEditor.vue'
import DOMPurify from 'dompurify'

const toast = useToast()
const { t } = useI18n()
const firmStore = useFirmStore()

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CatalogItem {
  id: string
  description: string
  sku: string
  notes: string
  image_url: string
  quantity: string | number
  unit_price: string | number
  discount: string | number
  vat_rate: string | number
  position: number
  created_at?: string
  updated_at?: string
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const allItems = ref<CatalogItem[]>([])
const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const PAGE_SIZE = 50

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html)
}

function htmlToPlainText(html: string): string {
  return new DOMParser().parseFromString(html, 'text/html').body.textContent ?? ''
}

function parseCSVLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current.trim())
      current = ''
    } else {
      current += ch
    }
  }
  result.push(current.trim())
  return result
}

// New item form
const showAddForm = ref(false)
const addingItem = ref(false)
const newItem = ref({
  description: '',
  sku: '',
  notes: '',
  image_url: '',
  quantity: 1,
  unit_price: 0,
  discount: 0,
  vat_rate: 0,
})

// Edit
const editingId = ref<string | null>(null)
const editItem = ref<CatalogItem | null>(null)
const savingEdit = ref(false)
const showEditNotes = ref(false)

// Detail modal for view/edit
const detailItem = ref<CatalogItem | null>(null)

// Import
const importFileInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const filteredItems = computed(() => {
  const q = searchQuery.value.toLowerCase().trim()
  if (!q) return allItems.value
  return allItems.value.filter(
    (item) =>
      item.description.toLowerCase().includes(q) ||
      (item.sku ?? '').toLowerCase().includes(q) ||
      (item.notes ?? '').toLowerCase().includes(q),
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredItems.value.length / PAGE_SIZE)))

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredItems.value.slice(start, start + PAGE_SIZE)
})

// Reset page when search changes
function onSearchChange() {
  currentPage.value = 1
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

async function loadItems() {
  loading.value = true
  const res = await api.get<CatalogItem[]>('/api/v1/crm/firm-proposal-items')
  loading.value = false
  if (res.ok && Array.isArray(res.data)) allItems.value = res.data
}

async function createItem() {
  if (!newItem.value.description.trim()) {
    toast.error(t('catalog.descriptionRequired'))
    return
  }
  addingItem.value = true
  const res = await api.post<CatalogItem>('/api/v1/crm/firm-proposal-items', {
    description: newItem.value.description.trim(),
    sku: newItem.value.sku.trim(),
    notes: newItem.value.notes,
    image_url: newItem.value.image_url.trim(),
    quantity: newItem.value.quantity,
    unit_price: newItem.value.unit_price,
    discount: newItem.value.discount,
    vat_rate: newItem.value.vat_rate,
    position: allItems.value.length,
  })
  addingItem.value = false
  if (res.ok && res.data) {
    allItems.value.unshift(res.data)
    resetNewItem()
    showAddForm.value = false
    toast.success(t('catalog.itemAdded'))
  } else {
    toast.error(t('catalog.failedToCreate'))
  }
}

function resetNewItem() {
  newItem.value = { description: '', sku: '', notes: '', image_url: '', quantity: 1, unit_price: 0, discount: 0, vat_rate: 0 }
}

function startEdit(item: CatalogItem) {
  editingId.value = item.id
  editItem.value = { ...item }
  showEditNotes.value = false
}

function cancelEdit() {
  editingId.value = null
  editItem.value = null
}

async function saveEdit() {
  if (!editItem.value) return
  savingEdit.value = true
  const res = await api.put<CatalogItem>(`/api/v1/crm/firm-proposal-items/${editItem.value.id}`, {
    description: editItem.value.description,
    sku: editItem.value.sku ?? '',
    notes: editItem.value.notes ?? '',
    image_url: editItem.value.image_url ?? '',
    quantity: editItem.value.quantity,
    unit_price: editItem.value.unit_price,
    discount: editItem.value.discount,
    vat_rate: editItem.value.vat_rate,
    position: editItem.value.position,
  })
  savingEdit.value = false
  if (res.ok && res.data) {
    const idx = allItems.value.findIndex((i) => i.id === editItem.value!.id)
    if (idx !== -1) allItems.value[idx] = res.data
    cancelEdit()
    toast.success(t('catalog.itemUpdated'))
  } else {
    toast.error(t('catalog.failedToUpdate'))
  }
}

async function deleteItem(id: string) {
  if (!confirm(t('catalog.confirmDelete'))) return
  const res = await api.delete(`/api/v1/crm/firm-proposal-items/${id}`)
  if (res.ok || res.status === 204) {
    allItems.value = allItems.value.filter((i) => i.id !== id)
    toast.success(t('catalog.itemDeleted'))
  } else {
    toast.error(t('catalog.failedToDelete'))
  }
}

// ---------------------------------------------------------------------------
// CSV Export
// ---------------------------------------------------------------------------

function exportCSV() {
  const headers = ['SKU', 'Description', 'Unit Price', 'Quantity', 'Discount %', 'VAT %', 'Image URL', 'Notes']
  const rows = allItems.value.map((item) => [
    item.sku ?? '',
    item.description,
    item.unit_price,
    item.quantity,
    item.discount,
    item.vat_rate,
    item.image_url ?? '',
    htmlToPlainText(item.notes ?? '').replace(/\n/g, ' '), // convert HTML to plain text for CSV
  ])

  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `catalog-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  toast.success(t('catalog.exported', { count: allItems.value.length }))
}

// ---------------------------------------------------------------------------
// CSV Import
// ---------------------------------------------------------------------------

function triggerImport() {
  importFileInput.value?.click()
}

async function onImportFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  importing.value = true

  const text = await file.text()
  const lines = text.split(/\r?\n/).filter(Boolean)

  if (lines.length < 2) {
    toast.error(t('catalog.csvMustHaveHeader'))
    importing.value = false
    ;(event.target as HTMLInputElement).value = ''
    return
  }

  const headers = parseCSVLine(lines[0]!).map((h) => h.toLowerCase().replace(/\s+/g, '_'))
  const skuIdx = headers.findIndex((h) => h === 'sku')
  const descIdx = headers.findIndex((h) => h.includes('desc') || h === 'name')
  const priceIdx = headers.findIndex((h) => h.includes('price') || h.includes('unit'))
  const qtyIdx = headers.findIndex((h) => h.includes('qty') || h.includes('quantity'))
  const discIdx = headers.findIndex((h) => h.includes('discount'))
  const vatIdx = headers.findIndex((h) => h.includes('vat') || h.includes('tax'))
  const imageIdx = headers.findIndex((h) => h.includes('image') || h.includes('photo'))
  const notesIdx = headers.findIndex((h) => h.includes('notes') || h.includes('description_long'))

  if (descIdx === -1) {
    toast.error(t('catalog.csvMustHaveDesc'))
    importing.value = false
    ;(event.target as HTMLInputElement).value = ''
    return
  }

  let created = 0
  let failed = 0

  for (let i = 1; i < lines.length; i++) {
    const cols = parseCSVLine(lines[i]!)
    const description = cols[descIdx]?.trim()
    if (!description) continue

    const payload = {
      description,
      sku: skuIdx >= 0 ? (cols[skuIdx]?.trim() ?? '') : '',
      notes: notesIdx >= 0 ? (cols[notesIdx]?.trim() ?? '') : '',
      image_url: imageIdx >= 0 ? (cols[imageIdx]?.trim() ?? '') : '',
      unit_price: priceIdx >= 0 ? parseFloat(cols[priceIdx] ?? '0') || 0 : 0,
      quantity: qtyIdx >= 0 ? parseFloat(cols[qtyIdx] ?? '1') || 1 : 1,
      discount: discIdx >= 0 ? parseFloat(cols[discIdx] ?? '0') || 0 : 0,
      vat_rate: vatIdx >= 0 ? parseFloat(cols[vatIdx] ?? '0') || 0 : 0,
      position: allItems.value.length + created,
    }

    const res = await api.post<CatalogItem>('/api/v1/crm/firm-proposal-items', payload)
    if (res.ok && res.data) {
      allItems.value.push(res.data)
      created++
    } else {
      failed++
    }
  }

  importing.value = false
  ;(event.target as HTMLInputElement).value = ''

  if (created > 0) {
    toast.success(t('catalog.importedItems', { count: created }))
  } else {
    toast.error(t('catalog.noItemsImported'))
  }
}

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

function goToPage(p: number) {
  currentPage.value = Math.max(1, Math.min(p, totalPages.value))
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

onMounted(() => {
  firmStore.fetchFirms().then(() => {
    if (firmStore.activeFirm) loadItems()
  })
})
</script>

<template>
  <div class="p-6 space-y-5">
    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ t('catalog.title') }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{{ t('catalog.subtitle') }}</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <!-- Import -->
        <input
          ref="importFileInput"
          type="file"
          accept=".csv"
          class="hidden"
          @change="onImportFile"
        />
        <button
          :disabled="importing"
          class="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-60"
          @click="triggerImport"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10" />
          </svg>
          {{ importing ? t('catalog.importing') : t('catalog.importCsv') }}
        </button>
        <!-- Export -->
        <button
          :disabled="allItems.length === 0"
          class="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-60"
          @click="exportCSV"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          {{ t('catalog.exportCsv') }}
        </button>
        <!-- Add item -->
        <button
          class="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700"
          @click="showAddForm = !showAddForm"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          {{ t('catalog.addItem') }}
        </button>
      </div>
    </div>

    <!-- Add item form -->
    <div v-if="showAddForm" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4">
      <h2 class="text-sm font-semibold text-gray-800 dark:text-gray-200">{{ t('catalog.newItem') }}</h2>

      <!-- Row 1: description + SKU -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div class="sm:col-span-2">
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.descriptionLabel') }}</label>
          <input
            v-model="newItem.description"
            type="text"
            :placeholder="t('catalog.descriptionPlaceholder')"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.sku') }}</label>
          <input
            v-model="newItem.sku"
            type="text"
            placeholder="e.g. PROD-001"
            class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
        </div>
      </div>

      <!-- Row 2: numeric fields -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.unitPrice') }}</label>
          <input v-model.number="newItem.unit_price" type="number" min="0" step="0.01" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm text-right focus:outline-none focus:border-red-400" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.quantity') }}</label>
          <input v-model.number="newItem.quantity" type="number" min="0.001" step="0.001" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm text-right focus:outline-none focus:border-red-400" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.discountPct') }}</label>
          <input v-model.number="newItem.discount" type="number" min="0" max="100" step="0.01" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm text-right focus:outline-none focus:border-red-400" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.vatPct') }}</label>
          <input v-model.number="newItem.vat_rate" type="number" min="0" max="100" step="0.01" class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm text-right focus:outline-none focus:border-red-400" />
        </div>
      </div>

      <!-- Image URL -->
      <div>
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.imageUrl') }}</label>
        <div class="flex items-center gap-3">
          <input
            v-model="newItem.image_url"
            type="url"
            placeholder="https://example.com/product-image.jpg"
            class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
          />
          <img
            v-if="newItem.image_url"
            :src="newItem.image_url"
            alt="Preview"
            class="w-10 h-10 rounded-lg object-cover border border-gray-200 dark:border-gray-600 flex-shrink-0"
            @error="(e) => (e.target as HTMLImageElement).style.visibility = 'hidden'"
          />
        </div>
      </div>

      <!-- Rich text notes -->
      <div>
        <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.notes') }}</label>
        <RichTextEditor
          v-model="newItem.notes"
          placeholder="Add detailed description, features, specifications…"
        />
      </div>

      <div class="flex gap-2 pt-1">
        <button
          :disabled="addingItem || !newItem.description.trim()"
          class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          @click="createItem"
        >{{ addingItem ? t('catalog.addingItem') : t('catalog.addToCatalog') }}</button>
        <button
          class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"
          @click="showAddForm = false; resetNewItem()"
        >Cancel</button>
      </div>
    </div>

    <!-- Search bar -->
    <div class="relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        v-model="searchQuery"
        type="text"
  :placeholder="t('catalog.searchPlaceholder')"
        class="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:border-red-400"
        @input="onSearchChange"
      />
      <button
        v-if="searchQuery"
        class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
        @click="searchQuery = ''; onSearchChange()"
      >✕</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="animate-pulse space-y-2">
      <div v-for="i in 5" :key="i" class="h-12 bg-gray-100 dark:bg-gray-800 rounded-xl" />
    </div>

    <!-- Empty state -->
    <div v-else-if="allItems.length === 0" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-12 text-center">
      <p class="text-4xl mb-3">📦</p>
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('catalog.empty') }}</p>
      <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">Add products and services to quickly include them in proposals.</p>
      <div class="flex justify-center gap-3 mt-4">
        <button class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700" @click="showAddForm = true">+ Add first item</button>
        <button class="px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="triggerImport">Import CSV</button>
      </div>
    </div>

    <!-- No search results -->
    <div v-else-if="filteredItems.length === 0" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-10 text-center">
      <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('catalog.noMatch', { query: searchQuery }) }}</p>
      <button class="mt-2 text-xs text-red-600 hover:underline" @click="searchQuery = ''">Clear search</button>
    </div>

    <!-- Table -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
      <!-- Table header -->
      <div class="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
        <span class="text-xs text-gray-500 dark:text-gray-400">
          Showing {{ (currentPage - 1) * PAGE_SIZE + 1 }}–{{ Math.min(currentPage * PAGE_SIZE, filteredItems.length) }} of {{ filteredItems.length }}
          <template v-if="searchQuery"> (filtered from {{ allItems.length }})</template>
        </span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-gray-100 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
              <th class="text-left text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-20">{{ t('catalog.colImage') }}</th>
              <th class="text-left text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3">{{ t('catalog.colDescription') }}</th>
              <th class="text-left text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-28">{{ t('catalog.colSku') }}</th>
              <th class="text-right text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-24">Price</th>
              <th class="text-right text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-20">Qty</th>
              <th class="text-right text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-20">Disc. %</th>
              <th class="text-right text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-20">{{ t('catalog.colVat') }}</th>
              <th class="text-right text-xs font-medium text-gray-500 dark:text-gray-400 px-4 py-3 w-28">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50 dark:divide-gray-700/50">
            <template v-for="item in pagedItems" :key="item.id">
              <!-- View row -->
              <tr
                v-if="editingId !== item.id"
                class="hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors group"
              >
                <td class="px-4 py-3">
                  <div class="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 overflow-hidden flex items-center justify-center flex-shrink-0">
                    <img
                      v-if="item.image_url"
                      :src="item.image_url"
                      :alt="item.description"
                      class="w-full h-full object-cover"
                      @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
                    />
                    <span v-else class="text-gray-300 dark:text-gray-600 text-lg">📦</span>
                  </div>
                </td>
                <td class="px-4 py-3">
                  <div class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ item.description }}</div>
                  <div
                    v-if="item.notes"
                    class="text-xs text-gray-400 dark:text-gray-500 mt-0.5 line-clamp-1"
                    v-html="sanitizeHtml(item.notes)"
                  />
                </td>
                <td class="px-4 py-3">
                  <span v-if="item.sku" class="text-xs font-mono bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded px-1.5 py-0.5">{{ item.sku }}</span>
                  <span v-else class="text-xs text-gray-300 dark:text-gray-600">—</span>
                </td>
                <td class="px-4 py-3 text-right text-sm text-gray-700 dark:text-gray-300 font-medium">{{ Number(item.unit_price).toFixed(2) }}</td>
                <td class="px-4 py-3 text-right text-sm text-gray-500 dark:text-gray-400">{{ item.quantity }}</td>
                <td class="px-4 py-3 text-right text-sm text-gray-500 dark:text-gray-400">{{ item.discount }}%</td>
                <td class="px-4 py-3 text-right text-sm text-gray-500 dark:text-gray-400">{{ item.vat_rate }}%</td>
                <td class="px-4 py-3 text-right">
                  <div class="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      class="p-1.5 rounded-lg text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                      title="Edit"
                      @click="startEdit(item)"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      class="p-1.5 rounded-lg text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      title="Delete"
                      @click="deleteItem(item.id)"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>

              <!-- Edit row -->
              <tr v-else class="bg-blue-50 dark:bg-blue-900/10">
                <td class="px-4 py-3">
                  <div class="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-700 overflow-hidden flex items-center justify-center flex-shrink-0">
                    <img
                      v-if="editItem?.image_url"
                      :src="editItem.image_url"
                      alt="Preview"
                      class="w-full h-full object-cover"
                      @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
                    />
                    <span v-else class="text-gray-300 dark:text-gray-600 text-lg">📦</span>
                  </div>
                </td>
                <td class="px-2 py-2" colspan="2">
                  <input
                    v-if="editItem"
                    v-model="editItem.description"
                    type="text"
                    class="w-full rounded-lg border border-blue-300 dark:border-blue-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-sm focus:outline-none focus:border-blue-500 mb-1"
                    placeholder="Description *"
                  />
                  <input
                    v-if="editItem"
                    v-model="editItem.sku"
                    type="text"
                    class="w-40 rounded-lg border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1 text-xs focus:outline-none focus:border-blue-500"
                    placeholder="SKU"
                  />
                  <button
                    class="ml-2 text-xs text-blue-600 dark:text-blue-400 hover:underline"
                    @click="showEditNotes = !showEditNotes"
                  >{{ showEditNotes ? t('catalog.hideNotes') : t('catalog.editNotes') }}</button>
                </td>
                <td class="px-2 py-2">
                  <input
                    v-if="editItem"
                    v-model.number="editItem.unit_price"
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full rounded-lg border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-sm text-right focus:outline-none focus:border-blue-500"
                  />
                </td>
                <td class="px-2 py-2">
                  <input
                    v-if="editItem"
                    v-model.number="editItem.quantity"
                    type="number"
                    min="0.001"
                    step="0.001"
                    class="w-full rounded-lg border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-sm text-right focus:outline-none focus:border-blue-500"
                  />
                </td>
                <td class="px-2 py-2">
                  <input
                    v-if="editItem"
                    v-model.number="editItem.discount"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    class="w-full rounded-lg border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-sm text-right focus:outline-none focus:border-blue-500"
                  />
                </td>
                <td class="px-2 py-2">
                  <input
                    v-if="editItem"
                    v-model.number="editItem.vat_rate"
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    class="w-full rounded-lg border border-blue-200 dark:border-blue-700 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-sm text-right focus:outline-none focus:border-blue-500"
                  />
                </td>
                <td class="px-2 py-2">
                  <div class="flex items-center justify-end gap-1">
                    <button
                      :disabled="savingEdit"
                      class="p-1.5 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                      title="Save"
                      @click="saveEdit"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                    <button
                      class="p-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700"
                      title="Cancel"
                      @click="cancelEdit"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>

              <!-- Edit extended row: image url + notes -->
              <tr v-if="editingId === item.id && showEditNotes && editItem" class="bg-blue-50/50 dark:bg-blue-900/5 border-b border-blue-100 dark:border-blue-800">
                <td colspan="8" class="px-4 pb-3 space-y-3">
                  <div>
                    <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('catalog.imageUrl') }}</label>
                    <div class="flex items-center gap-3">
                      <input
                        v-model="editItem.image_url"
                        type="url"
                        placeholder="https://example.com/image.jpg"
                        class="flex-1 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
                      />
                      <img
                        v-if="editItem.image_url"
                        :src="editItem.image_url"
                        alt="Preview"
                        class="w-10 h-10 rounded-lg object-cover border border-gray-200 flex-shrink-0"
                        @error="(e) => (e.target as HTMLImageElement).style.visibility = 'hidden'"
                      />
                    </div>
                  </div>
                  <div>
                    <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Notes / description</label>
                    <RichTextEditor
                      v-model="editItem.notes"
                      placeholder="Detailed description, specifications…"
                    />
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-gray-700">
        <button
          :disabled="currentPage === 1"
          class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40"
          @click="goToPage(currentPage - 1)"
        >{{ t('catalog.prevPage') }}</button>
<span class="text-sm text-gray-500 dark:text-gray-400">{{ t('catalog.page', { current: currentPage, total: totalPages }) }}</span>
        <button
          :disabled="currentPage === totalPages"
          class="px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-40"
          @click="goToPage(currentPage + 1)"
        >{{ t('catalog.nextPage') }}</button>
      </div>
    </div>

    <!-- CSV format hint -->
    <div class="text-xs text-gray-400 dark:text-gray-500 bg-gray-50 dark:bg-gray-800/50 rounded-xl px-4 py-3">
      <strong>CSV import format:</strong> Headers: <code class="font-mono">SKU, Description, Unit Price, Quantity, Discount %, VAT %, Image URL, Notes</code>.
      The <em>Description</em> (or <em>Name</em>) column is required. All other columns are optional.
    </div>
  </div>
</template>

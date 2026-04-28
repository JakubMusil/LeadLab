<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const firmStore = useFirmStore()
const { t } = useI18n()

// Route support:
// 1) /app/opportunities/:id/proposals/:pid? — lead-scoped (legacy)
// 2) /app/proposals/:id                     — standalone
const leadId = computed(() => route.params.id as string | undefined)
const proposalId = computed(() => {
  // standalone route: /app/proposals/:id
  if (route.path.startsWith('/app/proposals/')) return route.params.id as string
  // legacy route: /app/opportunities/:id/proposals/:pid
  return route.params.pid as string | undefined
})
const isStandalone = computed(() => route.path.startsWith('/app/proposals/') || route.path === '/app/proposals')

// -----------------------------------------------------------------------
// Types
// -----------------------------------------------------------------------
interface ProposalItem {
  id: string
  proposal_id: string
  description: string
  quantity: number
  unit_price: number
  discount: number
  vat_rate: number
  position: number
  subtotal: number
  discount_amount: number
  after_discount: number
  tax: number
  total: number
  created_at: string
}

interface Proposal {
  id: string
  lead_id: string | null
  customer_id: string | null
  realization_id: string | null
  management_id: string | null
  firm_id: string
  title: string
  status: string
  expiry_date: string | null
  currency: string
  notes: string
  intro_text: string
  closing_text: string
  public_token: string
  token_expires_at: string | null
  view_count: number
  first_viewed_at: string | null
  sent_at: string | null
  total_value: number
  items: ProposalItem[]
  created_at: string
  updated_at: string
}

interface ProposalTemplate {
  id: string
  name: string
  intro_text: string
  closing_text: string
  items: Array<{ description: string; quantity: number; unit_price: number; discount: number; vat_rate: number; position: number }>
}

interface CatalogItem {
  id: string
  description: string
  quantity: number
  unit_price: number
  discount: number
  vat_rate: number
  position: number
}

// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
const proposals = ref<Proposal[]>([])
const currentProposal = ref<Proposal | null>(null)
const loading = ref(false)
const saving = ref(false)

// Editor state
const editTitle = ref('')
const editStatus = ref('draft')
const editExpiry = ref('')
const editCurrency = ref('CZK')
const editNotes = ref('')
const editIntro = ref('')
const editClosing = ref('')

// Items
const items = ref<ProposalItem[]>([])
const newItemDesc = ref('')
const newItemQty = ref(1)
const newItemPrice = ref(0)
const newItemDiscount = ref(0)
const newItemVat = ref(0)
const addingItem = ref(false)
const editingItemId = ref<string | null>(null)

// Templates
const templates = ref<ProposalTemplate[]>([])
const showApplyTemplate = ref(false)
const applyingTemplate = ref(false)

// Catalog
const catalogItems = ref<CatalogItem[]>([])
const showCatalog = ref(false)
const addingFromCatalog = ref(false)
const selectedCatalogIds = ref<string[]>([])

// Public link
const publicLinkCopied = ref(false)
const sendingProposal = ref(false)

// Preview panel
const showPreview = ref(false)

const CURRENCIES = ['CZK', 'EUR', 'USD', 'GBP', 'PLN']
const STATUSES = [
  { value: 'draft', label: 'Draft', color: 'bg-gray-100 text-gray-700' },
  { value: 'sent', label: 'Sent', color: 'bg-blue-100 text-blue-700' },
  { value: 'viewed', label: 'Viewed', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'accepted', label: 'Accepted', color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-700' },
  { value: 'expired', label: 'Expired', color: 'bg-orange-100 text-orange-700' },
]

function statusMeta(status: string) {
  return STATUSES.find((s) => s.value === status) ?? { value: status, label: status, color: 'bg-gray-100 text-gray-700' }
}

// -----------------------------------------------------------------------
// Computed totals for preview
// -----------------------------------------------------------------------
const previewSubtotal = computed(() =>
  items.value.reduce((acc, i) => acc + Number(i.subtotal), 0)
)
const previewDiscount = computed(() =>
  items.value.reduce((acc, i) => acc + Number(i.discount_amount), 0)
)
const previewTax = computed(() =>
  items.value.reduce((acc, i) => acc + Number(i.tax), 0)
)
const previewTotal = computed(() =>
  items.value.reduce((acc, i) => acc + Number(i.total), 0)
)

// -----------------------------------------------------------------------
// Load data
// -----------------------------------------------------------------------
async function loadProposals() {
  loading.value = true
  try {
    if (isStandalone.value) {
      // standalone: no proposal list sidebar in this view, nothing to load
    } else if (leadId.value) {
      const res = await api.get<Proposal[]>(`/api/v1/crm/opportunities/${leadId.value}/proposals`)
      if (res.ok) proposals.value = res.data
    }
  } finally {
    loading.value = false
  }
}

async function loadProposal(id: string) {
  loading.value = true
  try {
    const res = await api.get<Proposal>(`/api/v1/crm/proposals/${id}`)
    if (res.ok) {
      currentProposal.value = res.data
      populateForm(res.data)
      items.value = [...res.data.items].sort((a, b) => a.position - b.position)
    } else {
      toast.error('Failed to load proposal.')
    }
  } finally {
    loading.value = false
  }
}

async function loadTemplates() {
  const res = await api.get<ProposalTemplate[]>('/api/v1/crm/proposal-templates')
  if (res.ok) templates.value = res.data
}

async function loadCatalogItems() {
  const res = await api.get<CatalogItem[]>('/api/v1/crm/firm-proposal-items')
  if (res.ok) catalogItems.value = res.data
}

function populateForm(p: Proposal) {
  editTitle.value = p.title
  editStatus.value = p.status
  editExpiry.value = p.expiry_date ?? ''
  editCurrency.value = p.currency
  editNotes.value = p.notes
  editIntro.value = p.intro_text
  editClosing.value = p.closing_text
}

// -----------------------------------------------------------------------
// Create / Save
// -----------------------------------------------------------------------
async function createProposal() {
  saving.value = true
  let res
  if (leadId.value && !isStandalone.value) {
    res = await api.post<Proposal>(`/api/v1/crm/opportunities/${leadId.value}/proposals`, {
      title: editTitle.value || 'New Proposal',
      currency: editCurrency.value,
    })
  } else {
    res = await api.post<Proposal>('/api/v1/crm/proposals', {
      title: editTitle.value || 'New Proposal',
      currency: editCurrency.value,
    })
  }
  saving.value = false
  if (res.ok) {
    proposals.value.unshift(res.data)
    currentProposal.value = res.data
    populateForm(res.data)
    items.value = []
    if (isStandalone.value) {
      router.replace(`/app/proposals/${res.data.id}`)
    } else {
      router.replace(`/app/opportunities/${leadId.value}/proposals/${res.data.id}`)
    }
    toast.success('Proposal created.')
  } else {
    toast.error('Failed to create proposal.')
  }
}

async function saveProposal() {
  if (!currentProposal.value) return
  saving.value = true
  const res = await api.put<Proposal>(`/api/v1/crm/proposals/${currentProposal.value.id}`, {
    title: editTitle.value,
    status: editStatus.value,
    expiry_date: editExpiry.value || null,
    currency: editCurrency.value,
    notes: editNotes.value,
    intro_text: editIntro.value,
    closing_text: editClosing.value,
  })
  saving.value = false
  if (res.ok) {
    currentProposal.value = res.data
    const idx = proposals.value.findIndex((p) => p.id === res.data.id)
    if (idx !== -1) proposals.value[idx] = res.data
    toast.success('Proposal saved.')
  } else {
    toast.error('Failed to save proposal.')
  }
}

async function deleteProposal(id: string) {
  if (!confirm('Delete this proposal?')) return
  const res = await api.delete(`/api/v1/crm/proposals/${id}`)
  if (res.ok || res.status === 204) {
    proposals.value = proposals.value.filter((p) => p.id !== id)
    if (currentProposal.value?.id === id) {
      currentProposal.value = null
      if (isStandalone.value) {
        router.replace('/app/proposals')
      } else {
        router.replace(`/app/opportunities/${leadId.value}/proposals`)
      }
    }
    toast.success('Proposal deleted.')
  } else {
    toast.error('Failed to delete proposal.')
  }
}

function selectProposal(p: Proposal) {
  if (isStandalone.value) {
    router.push(`/app/proposals/${p.id}`)
  } else {
    router.push(`/app/opportunities/${leadId.value}/proposals/${p.id}`)
  }
}

// -----------------------------------------------------------------------
// Items
// -----------------------------------------------------------------------
async function addItem() {
  if (!currentProposal.value || !newItemDesc.value.trim()) return
  addingItem.value = true
  const res = await api.post<ProposalItem>(`/api/v1/crm/proposals/${currentProposal.value.id}/items`, {
    description: newItemDesc.value.trim(),
    quantity: newItemQty.value,
    unit_price: newItemPrice.value,
    discount: newItemDiscount.value,
    vat_rate: newItemVat.value,
    position: items.value.length,
  })
  addingItem.value = false
  if (res.ok) {
    items.value.push(res.data)
    newItemDesc.value = ''
    newItemQty.value = 1
    newItemPrice.value = 0
    newItemDiscount.value = 0
    newItemVat.value = 0
  } else {
    toast.error('Failed to add item.')
  }
}

async function updateItem(item: ProposalItem) {
  if (!currentProposal.value) return
  const res = await api.put<ProposalItem>(
    `/api/v1/crm/proposals/${currentProposal.value.id}/items/${item.id}`,
    {
      description: item.description,
      quantity: item.quantity,
      unit_price: item.unit_price,
      discount: item.discount,
      vat_rate: item.vat_rate,
      position: item.position,
    }
  )
  if (res.ok) {
    const idx = items.value.findIndex((i) => i.id === item.id)
    if (idx !== -1) items.value[idx] = res.data
    editingItemId.value = null
  } else {
    toast.error('Failed to update item.')
  }
}

async function deleteItem(itemId: string) {
  if (!currentProposal.value) return
  const res = await api.delete(
    `/api/v1/crm/proposals/${currentProposal.value.id}/items/${itemId}`
  )
  if (res.ok || res.status === 204) {
    items.value = items.value.filter((i) => i.id !== itemId)
  } else {
    toast.error('Failed to delete item.')
  }
}

// Drag-and-drop reorder
const dragIndex = ref<number | null>(null)

function onDragStart(index: number) {
  dragIndex.value = index
}

function onDragOver(e: DragEvent, index: number) {
  e.preventDefault()
  if (dragIndex.value === null || dragIndex.value === index) return
  const removed = items.value.splice(dragIndex.value, 1)
  const moved = removed[0]
  if (!moved) return
  items.value.splice(index, 0, moved)
  dragIndex.value = index
}

async function onDragEnd() {
  dragIndex.value = null
  if (!currentProposal.value) return
  // Persist new order
  const reordered = items.value.map((item, idx) => ({ id: item.id, position: idx }))
  const res = await api.post<ProposalItem[]>(
    `/api/v1/crm/proposals/${currentProposal.value.id}/items/reorder`,
    { items: reordered }
  )
  if (res.ok) {
    items.value = res.data
  }
}

// -----------------------------------------------------------------------
// Apply template
// -----------------------------------------------------------------------
async function applyTemplate(templateId: string) {
  if (!currentProposal.value) return
  applyingTemplate.value = true
  const res = await api.post<Proposal>(
    `/api/v1/crm/proposals/${currentProposal.value.id}/apply-template`,
    { template_id: templateId }
  )
  applyingTemplate.value = false
  if (res.ok) {
    currentProposal.value = res.data
    populateForm(res.data)
    items.value = [...res.data.items].sort((a, b) => a.position - b.position)
    showApplyTemplate.value = false
    toast.success('Template applied.')
  } else {
    toast.error('Failed to apply template.')
  }
}

// -----------------------------------------------------------------------
// Add from catalog
// -----------------------------------------------------------------------
async function addFromCatalog() {
  if (!currentProposal.value || selectedCatalogIds.value.length === 0) return
  addingFromCatalog.value = true
  const res = await api.post<ProposalItem[]>(
    `/api/v1/crm/proposals/${currentProposal.value.id}/items/from-catalog`,
    { item_ids: selectedCatalogIds.value }
  )
  addingFromCatalog.value = false
  if (res.ok) {
    items.value.push(...res.data)
    selectedCatalogIds.value = []
    showCatalog.value = false
    toast.success('Položky přidány z katalogu.')
  } else {
    toast.error('Nepodařilo se přidat položky z katalogu.')
  }
}

function toggleCatalogItem(id: string) {
  const idx = selectedCatalogIds.value.indexOf(id)
  if (idx === -1) selectedCatalogIds.value.push(id)
  else selectedCatalogIds.value.splice(idx, 1)
}

// -----------------------------------------------------------------------
// Proposal context label
// -----------------------------------------------------------------------
function contextLabel(p: Proposal): string {
  if (p.lead_id) return `Příležitost`
  if (p.customer_id) return `Kontakt`
  if (p.realization_id) return `Realizace`
  if (p.management_id) return `Správa`
  return '—'
}

// -----------------------------------------------------------------------
// Send & public link
// -----------------------------------------------------------------------
async function sendProposal() {
  if (!currentProposal.value) return
  if (!confirm('Mark this proposal as Sent and generate a public link?')) return
  sendingProposal.value = true
  const res = await api.post<Proposal>(`/api/v1/crm/proposals/${currentProposal.value.id}/send`)
  sendingProposal.value = false
  if (res.ok) {
    currentProposal.value = res.data
    editStatus.value = res.data.status
    const idx = proposals.value.findIndex((p) => p.id === res.data.id)
    if (idx !== -1) proposals.value[idx] = res.data
    toast.success('Proposal marked as Sent. Copy the public link to share it.')
  } else {
    toast.error('Failed to send proposal.')
  }
}

function publicLink(proposal: Proposal) {
  return `${window.location.origin}/proposals/public/${proposal.public_token}`
}

async function copyPublicLink() {
  if (!currentProposal.value) return
  await navigator.clipboard.writeText(publicLink(currentProposal.value))
  publicLinkCopied.value = true
  setTimeout(() => (publicLinkCopied.value = false), 2000)
}

function downloadPdf() {
  if (!currentProposal.value) return
  window.open(`/api/v1/crm/proposals/${currentProposal.value.id}/pdf`, '_blank')
}

// -----------------------------------------------------------------------
// Formatting helpers
// -----------------------------------------------------------------------
function fmt(n: number | string) {
  return Number(n).toFixed(2)
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString()
}

// -----------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------
onMounted(async () => {
  await loadProposals()
  await loadTemplates()
  await loadCatalogItems()
  const pid = proposalId.value
  if (pid) {
    await loadProposal(pid)
  } else if (!isStandalone.value && proposals.value.length > 0) {
    const first = proposals.value[0]
    if (first) {
      await loadProposal(first.id)
      router.replace(`/app/opportunities/${leadId.value}/proposals/${first.id}`)
    }
  } else {
    // Pre-populate create form
    editTitle.value = 'New Proposal'
    editCurrency.value = 'CZK'
  }
})

watch(
  () => route.params.pid,
  async (pid) => {
    if (pid && pid !== currentProposal.value?.id) {
      await loadProposal(pid as string)
    }
  }
)
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Back -->
    <RouterLink
      v-if="isStandalone"
      to="/app/proposals"
      class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4"
    >
      {{ t('proposals.backToProposals') }}
    </RouterLink>
    <RouterLink
      v-else
      :to="`/app/opportunities/${leadId}`"
      class="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4"
    >
      ← Back to Lead
    </RouterLink>

    <!-- Context badge for standalone proposals -->
    <div v-if="isStandalone && currentProposal" class="mb-4">
      <span class="inline-flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-2.5 py-1 rounded-full">
        <span>{{ t('proposals.linkedTo') }}:</span>
        <strong>{{ contextLabel(currentProposal) }}</strong>
      </span>
    </div>

    <div class="flex gap-6">
      <!-- ----------------------------------------------------------------
           LEFT SIDEBAR: proposal list (only for lead-scoped view)
      ---------------------------------------------------------------- -->
      <aside v-if="!isStandalone" class="w-64 flex-shrink-0">
        <div class="bg-white rounded-2xl border border-gray-100 p-3">
          <div class="flex items-center justify-between mb-2 px-1">
            <h2 class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Proposals</h2>
            <button
              class="text-xs px-2 py-1 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
              @click="createProposal"
            >+ New</button>
          </div>

          <div v-if="loading && proposals.length === 0" class="animate-pulse space-y-2 py-2">
            <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 rounded-xl" />
          </div>

          <div v-else-if="proposals.length === 0" class="py-6 text-center text-xs text-gray-400">
            No proposals yet.<br/>Click "+ New" to create one.
          </div>

          <div v-else class="space-y-1">
            <button
              v-for="p in proposals"
              :key="p.id"
              class="w-full text-left px-3 py-2.5 rounded-xl transition-colors"
              :class="currentProposal?.id === p.id
                ? 'bg-red-50 text-red-700'
                : 'hover:bg-gray-50 text-gray-700'"
              @click="selectProposal(p)"
            >
              <div class="text-sm font-medium truncate">{{ p.title }}</div>
              <div class="flex items-center gap-1.5 mt-0.5">
                <span
                  class="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium"
                  :class="statusMeta(p.status).color"
                >{{ statusMeta(p.status).label }}</span>
                <span class="text-[10px] text-gray-400">{{ fmt(p.total_value) }} {{ p.currency }}</span>
              </div>
            </button>
          </div>
        </div>
      </aside>

      <!-- ----------------------------------------------------------------
           MAIN EDITOR
      ---------------------------------------------------------------- -->
      <div class="flex-1 min-w-0 space-y-4">
        <!-- If no proposal selected, show create prompt -->
        <div v-if="!currentProposal && !loading" class="bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400">
          <p class="text-sm mb-3">Select a proposal from the sidebar or create a new one.</p>
          <button
            class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700"
            @click="createProposal"
          >+ Create Proposal</button>
        </div>

        <template v-else-if="currentProposal">
          <!-- Header bar -->
          <div class="bg-white rounded-2xl border border-gray-100 p-4 flex flex-wrap items-center gap-3">
            <div class="flex-1 min-w-0">
              <input
                v-model="editTitle"
                type="text"
                class="w-full text-lg font-semibold bg-transparent border-b border-transparent focus:border-gray-300 focus:outline-none text-gray-900 pb-0.5"
                placeholder="Proposal title…"
              />
            </div>

            <!-- Status -->
            <select
              v-model="editStatus"
              class="rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400"
            >
              <option v-for="s in STATUSES" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>

            <!-- Actions -->
            <button
              class="px-3 py-1.5 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              :disabled="saving"
              @click="saveProposal"
            >{{ saving ? 'Saving…' : 'Save' }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              :disabled="sendingProposal"
              @click="sendProposal"
            >{{ sendingProposal ? '…' : '📤 Send' }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              @click="downloadPdf"
            >⬇ PDF</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm hover:bg-gray-50"
              :class="publicLinkCopied ? 'text-green-600' : 'text-gray-600'"
              @click="copyPublicLink"
            >{{ publicLinkCopied ? '✓ Copied!' : '🔗 Copy Link' }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              @click="showPreview = !showPreview"
            >{{ showPreview ? 'Hide Preview' : 'Preview' }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50"
              @click="deleteProposal(currentProposal.id)"
            >Delete</button>
          </div>

          <!-- Two-panel layout: editor + live preview -->
          <div class="flex gap-4">
            <!-- Editor column -->
            <div class="flex-1 min-w-0 space-y-4">

              <!-- Meta fields -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Details</h3>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">Currency</label>
                    <select v-model="editCurrency" class="w-full rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400">
                      <option v-for="c in CURRENCIES" :key="c" :value="c">{{ c }}</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">Valid Until</label>
                    <input v-model="editExpiry" type="date" class="w-full rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400" />
                  </div>
                </div>

                <!-- View stats -->
                <div v-if="currentProposal.view_count > 0" class="mt-3 flex gap-4 text-xs text-gray-400">
                  <span>👁 {{ currentProposal.view_count }} view{{ currentProposal.view_count !== 1 ? 's' : '' }}</span>
                  <span v-if="currentProposal.first_viewed_at">First opened: {{ formatDate(currentProposal.first_viewed_at) }}</span>
                </div>
              </div>

              <!-- Intro text -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Introduction</h3>
                <textarea
                  v-model="editIntro"
                  rows="3"
                  class="w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none"
                  placeholder="Write an introduction for your proposal…"
                />
              </div>

              <!-- Line items -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <div class="flex items-center justify-between mb-3">
                  <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Line Items</h3>
                  <div class="flex items-center gap-2">
                    <button
                      class="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                      @click="showCatalog = !showCatalog; showApplyTemplate = false"
                    >{{ t('proposals.addFromCatalog') }}</button>
                    <button
                      class="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                      @click="showApplyTemplate = !showApplyTemplate; showCatalog = false"
                    >Apply Template</button>
                  </div>
                </div>

                <!-- Catalog panel -->
                <div v-if="showCatalog" class="mb-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                  <p class="text-xs text-gray-500 mb-2">{{ t('proposals.catalogItemsHint') }}</p>
                  <div v-if="catalogItems.length === 0" class="text-xs text-gray-400">
                    Katalog je prázdný. Přidejte položky v Nastavení → Katalog nabídek.
                  </div>
                  <div v-else class="space-y-1 mb-3">
                    <label
                      v-for="ci in catalogItems"
                      :key="ci.id"
                      class="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-white dark:hover:bg-gray-700 transition-colors"
                    >
                      <input
                        type="checkbox"
                        :value="ci.id"
                        :checked="selectedCatalogIds.includes(ci.id)"
                        class="rounded"
                        @change="toggleCatalogItem(ci.id)"
                      />
                      <span class="text-sm flex-1">{{ ci.description }}</span>
                      <span class="text-xs text-gray-400">{{ fmt(ci.unit_price) }} / {{ ci.quantity }}</span>
                    </label>
                  </div>
                  <button
                    v-if="catalogItems.length > 0"
                    class="px-3 py-1.5 rounded-xl bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50"
                    :disabled="addingFromCatalog || selectedCatalogIds.length === 0"
                    @click="addFromCatalog"
                  >
                    {{ addingFromCatalog ? 'Přidávám…' : 'Přidat vybrané' }}
                  </button>
                </div>

                <!-- Apply template panel -->
                <div v-if="showApplyTemplate" class="mb-3 p-3 bg-gray-50 rounded-xl">
                  <p class="text-xs text-gray-500 mb-2">Select a template to apply:</p>
                  <div v-if="templates.length === 0" class="text-xs text-gray-400">No templates yet. Create one in Settings → Proposal Templates.</div>
                  <div v-else class="space-y-1">
                    <button
                      v-for="tmpl in templates"
                      :key="tmpl.id"
                      class="w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-white border border-transparent hover:border-gray-200 transition-colors"
                      :disabled="applyingTemplate"
                      @click="applyTemplate(tmpl.id)"
                    >
                      <span class="font-medium">{{ tmpl.name }}</span>
                      <span class="text-xs text-gray-400 ml-2">({{ tmpl.items.length }} items)</span>
                    </button>
                  </div>
                </div>

                <!-- Items table -->
                <div v-if="items.length > 0" class="mb-3 overflow-x-auto">
                  <table class="w-full text-sm">
                    <thead>
                      <tr class="border-b border-gray-100">
                        <th class="text-left py-1.5 pr-2 text-xs font-medium text-gray-500 w-6"></th>
                        <th class="text-left py-1.5 pr-2 text-xs font-medium text-gray-500">Description</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16">Qty</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-24">Unit Price</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16">Disc %</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16">VAT %</th>
                        <th class="text-right py-1.5 pl-2 text-xs font-medium text-gray-500 w-24">Total</th>
                        <th class="w-8"></th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(item, index) in items"
                        :key="item.id"
                        draggable="true"
                        class="border-b border-gray-50 hover:bg-gray-50 cursor-grab"
                        @dragstart="onDragStart(index)"
                        @dragover="onDragOver($event, index)"
                        @dragend="onDragEnd"
                      >
                        <td class="py-1.5 pr-2 text-gray-300 cursor-grab select-none">⠿</td>
                        <template v-if="editingItemId === item.id">
                          <td class="py-1 pr-2">
                            <input v-model="item.description" type="text" class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:border-red-400" />
                          </td>
                          <td class="py-1 px-2">
                            <input v-model.number="item.quantity" type="number" min="0.001" step="0.001" class="w-16 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" />
                          </td>
                          <td class="py-1 px-2">
                            <input v-model.number="item.unit_price" type="number" min="0" step="0.01" class="w-24 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" />
                          </td>
                          <td class="py-1 px-2">
                            <input v-model.number="item.discount" type="number" min="0" max="100" step="0.01" class="w-16 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" />
                          </td>
                          <td class="py-1 px-2">
                            <input v-model.number="item.vat_rate" type="number" min="0" max="100" step="0.01" class="w-16 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" />
                          </td>
                          <td class="py-1 pl-2 text-right text-xs font-medium text-gray-700">
                            {{ fmt(item.total) }}
                          </td>
                          <td class="py-1 pl-1">
                            <button class="text-xs text-green-600 hover:text-green-700 px-1" @click="updateItem(item)" title="Save">✓</button>
                          </td>
                        </template>
                        <template v-else>
                          <td class="py-1.5 pr-2 text-sm text-gray-700">{{ item.description }}</td>
                          <td class="py-1.5 px-2 text-right text-xs text-gray-500">{{ item.quantity }}</td>
                          <td class="py-1.5 px-2 text-right text-xs text-gray-500">{{ fmt(item.unit_price) }}</td>
                          <td class="py-1.5 px-2 text-right text-xs text-gray-500">{{ item.discount }}%</td>
                          <td class="py-1.5 px-2 text-right text-xs text-gray-500">{{ item.vat_rate }}%</td>
                          <td class="py-1.5 pl-2 text-right text-xs font-medium text-gray-700">{{ fmt(item.total) }}</td>
                          <td class="py-1.5 pl-1 flex items-center gap-0.5">
                            <button class="text-xs text-gray-400 hover:text-blue-500 px-1" @click="editingItemId = item.id" title="Edit">✏</button>
                            <button class="text-xs text-gray-400 hover:text-red-500 px-1" @click="deleteItem(item.id)" title="Delete">🗑</button>
                          </td>
                        </template>
                      </tr>
                    </tbody>
                    <tfoot>
                      <tr>
                        <td colspan="6" class="py-2 text-right text-xs font-semibold text-gray-700 pr-2">Total:</td>
                        <td class="py-2 pl-2 text-right text-sm font-bold text-gray-900">{{ fmt(previewTotal) }} {{ editCurrency }}</td>
                        <td></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                <!-- Add item form -->
                <div class="border border-dashed border-gray-200 rounded-xl p-3">
                  <p class="text-xs text-gray-400 mb-2 font-medium">Add line item</p>
                  <div class="flex flex-wrap gap-2">
                    <input
                      v-model="newItemDesc"
                      type="text"
                      placeholder="Description *"
                      class="flex-1 min-w-40 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400"
                    />
                    <input v-model.number="newItemQty" type="number" min="0.001" step="0.001" placeholder="Qty" class="w-20 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" />
                    <input v-model.number="newItemPrice" type="number" min="0" step="0.01" placeholder="Unit price" class="w-28 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" />
                    <input v-model.number="newItemDiscount" type="number" min="0" max="100" step="0.01" placeholder="Disc%" class="w-20 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" />
                    <input v-model.number="newItemVat" type="number" min="0" max="100" step="0.01" placeholder="VAT%" class="w-20 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" />
                    <button
                      :disabled="addingItem || !newItemDesc.trim()"
                      class="px-4 py-1.5 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                      @click="addItem"
                    >{{ addingItem ? '…' : '+ Add' }}</button>
                  </div>
                </div>
              </div>

              <!-- Notes -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Notes</h3>
                <textarea
                  v-model="editNotes"
                  rows="2"
                  class="w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none"
                  placeholder="Internal notes (not shown to recipient)…"
                />
              </div>

              <!-- Closing text -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Closing Text</h3>
                <textarea
                  v-model="editClosing"
                  rows="3"
                  class="w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none"
                  placeholder="Write a closing message (e.g. terms, next steps)…"
                />
              </div>
            </div>

            <!-- Live Preview panel -->
            <div
              v-if="showPreview"
              class="w-96 flex-shrink-0"
            >
              <div class="bg-white rounded-2xl border border-gray-100 p-5 sticky top-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">Preview</h3>

                <div
                  class="border-b-4 pb-3 mb-4"
                  :style="{ borderColor: firmStore.activeFirm?.primary_color || '#dc2626' }"
                >
                  <div
                    class="text-base font-bold"
                    :style="{ color: firmStore.activeFirm?.primary_color || '#dc2626' }"
                  >{{ firmStore.activeFirm?.name }}</div>
                  <div class="text-lg font-semibold text-gray-900 mt-1">{{ editTitle || 'Proposal Title' }}</div>
                  <span
                    class="inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium"
                    :class="statusMeta(editStatus).color"
                  >{{ statusMeta(editStatus).label }}</span>
                </div>

                <div class="flex gap-4 text-xs text-gray-400 mb-4">
                  <span v-if="editExpiry">Valid until: {{ editExpiry }}</span>
                  <span>{{ editCurrency }}</span>
                </div>

                <div v-if="editIntro" class="text-xs text-gray-600 mb-4 leading-relaxed whitespace-pre-wrap">{{ editIntro }}</div>

                <table class="w-full text-xs mb-4" v-if="items.length > 0">
                  <thead>
                    <tr class="text-gray-500 border-b border-gray-100">
                      <th class="text-left pb-1">Item</th>
                      <th class="text-right pb-1">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="item in items" :key="item.id" class="border-b border-gray-50">
                      <td class="py-1 text-gray-700">{{ item.description }}</td>
                      <td class="py-1 text-right text-gray-700">{{ fmt(item.total) }}</td>
                    </tr>
                  </tbody>
                </table>

                <div class="border-t border-gray-100 pt-2 text-xs space-y-0.5">
                  <div class="flex justify-between text-gray-500"><span>Subtotal</span><span>{{ fmt(previewSubtotal) }}</span></div>
                  <div v-if="previewDiscount > 0" class="flex justify-between text-gray-500"><span>Discount</span><span>-{{ fmt(previewDiscount) }}</span></div>
                  <div v-if="previewTax > 0" class="flex justify-between text-gray-500"><span>Tax / VAT</span><span>{{ fmt(previewTax) }}</span></div>
                  <div class="flex justify-between font-bold text-sm text-gray-900 pt-1"><span>Total</span><span>{{ fmt(previewTotal) }} {{ editCurrency }}</span></div>
                </div>

                <div v-if="editClosing" class="mt-4 text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">{{ editClosing }}</div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

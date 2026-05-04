<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'
import { useMoney } from '@/composables/useMoney'
import { api } from '@/api'
import ActivityTimeline from '@/components/ActivityTimeline.vue'
import EntitySidebarActionPicker from '@/components/EntitySidebarActionPicker.vue'
import StreamlineCreateModal from '@/components/StreamlineCreateModal.vue'
import CurrencySelect from '@/components/CurrencySelect.vue'
import { CheckIcon, TrashIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const firmStore = useFirmStore()
const { t } = useI18n()
const { firmCurrency, formatAmountPlain } = useMoney()

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
const editCurrency = ref(firmCurrency.value)
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
const confirmDeleteProposalId = ref<string | null>(null)

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
const confirmSendOpen = ref(false)

// Preview panel
const showPreview = ref(false)

// ActivityTimeline ref — reload feed after sidebar quick-action submits.
const activityTimelineRef = ref<InstanceType<typeof ActivityTimeline> | null>(null)

// Streamline Create Modal state (opened from sidebar picker tool-selected event).
const activeModalTool = ref('')
const STATUSES = computed(() => [
  { value: 'draft', label: t('proposals.statusDraft'), color: 'bg-gray-100 text-gray-700' },
  { value: 'sent', label: t('proposals.statusSent'), color: 'bg-blue-100 text-blue-700' },
  { value: 'viewed', label: t('proposals.statusViewed'), color: 'bg-yellow-100 text-yellow-700' },
  { value: 'accepted', label: t('proposals.statusAccepted'), color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: t('proposals.statusRejected'), color: 'bg-red-100 text-red-700' },
  { value: 'expired', label: t('proposals.statusExpired'), color: 'bg-orange-100 text-orange-700' },
])

function statusMeta(status: string) {
  return STATUSES.value.find((s) => s.value === status) ?? { value: status, label: status, color: 'bg-gray-100 text-gray-700' }
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
      toast.error(t('builder.failedToLoad'))
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
      title: editTitle.value || t('builder.newProposal'),
      currency: editCurrency.value,
    })
  } else {
    res = await api.post<Proposal>('/api/v1/crm/proposals', {
      title: editTitle.value || t('builder.newProposal'),
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
    toast.success(t('builder.proposalCreated'))
  } else {
    toast.error(t('builder.failedToCreate'))
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
    toast.success(t('builder.proposalSaved'))
  } else {
    toast.error(t('builder.failedToSave'))
  }
}

async function doDeleteProposal(id: string) {
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
    toast.success(t('builder.proposalDeleted'))
  } else {
    toast.error(t('builder.failedToDelete'))
  }
}

function deleteProposal(id: string) {
  confirmDeleteProposalId.value = id
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
    toast.error(t('builder.failedToAddItem'))
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
    toast.error(t('builder.failedToUpdateItem'))
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
    toast.error(t('builder.failedToDeleteItem'))
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
    toast.success(t('builder.templateApplied'))
  } else {
    toast.error(t('builder.failedToApplyTemplate'))
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
    toast.success(t('builder.itemsFromCatalog'))
  } else {
    toast.error(t('builder.failedFromCatalog'))
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
  confirmSendOpen.value = true
}

async function executeSendProposal() {
  if (!currentProposal.value) return
  confirmSendOpen.value = false
  sendingProposal.value = true
  const res = await api.post<Proposal>(`/api/v1/crm/proposals/${currentProposal.value.id}/send`)
  sendingProposal.value = false
  if (res.ok) {
    currentProposal.value = res.data
    editStatus.value = res.data.status
    const idx = proposals.value.findIndex((p) => p.id === res.data.id)
    if (idx !== -1) proposals.value[idx] = res.data
    toast.success(t('builder.proposalSent'))
  } else {
    toast.error(t('builder.failedToSend'))
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
  return formatAmountPlain(n)
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
    editTitle.value = ''
    editCurrency.value = firmCurrency.value
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
  <div class="p-6">
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
          <p class="text-sm mb-3">{{ t('builder.selectOrCreate') }}</p>
          <button
            class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700"
            @click="createProposal"
          >+ {{ t('builder.createProposal') }}</button>
        </div>

        <template v-else-if="currentProposal">
          <!-- Header bar -->
          <div class="bg-white rounded-2xl border border-gray-100 p-4 flex flex-wrap items-center gap-3">
            <div class="flex-1 min-w-0">
              <input
                v-model="editTitle"
                type="text"
                class="w-full text-lg font-semibold bg-transparent border-b border-transparent focus:border-gray-300 focus:outline-none text-gray-900 pb-0.5"
:placeholder="t('builder.proposalTitlePlaceholder')"
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
            >{{ saving ? t('common.saving') : t('common.save') }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              :disabled="sendingProposal"
              @click="sendProposal"
            >{{ sendingProposal ? '…' : t('builder.send') }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              @click="downloadPdf"
            >⬇ PDF</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm hover:bg-gray-50"
              :class="publicLinkCopied ? 'text-green-600' : 'text-gray-600'"
              @click="copyPublicLink"
            >{{ publicLinkCopied ? t('common.copied') : t('builder.copyLink') }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              @click="showPreview = !showPreview"
            >{{ showPreview ? t('builder.hidePreview') : t('builder.preview') }}</button>

            <button
              class="px-3 py-1.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50"
              @click="deleteProposal(currentProposal.id)"
            >{{ t('common.delete') }}</button>
          </div>

          <!-- Two-panel layout: editor + live preview -->
          <div class="flex gap-4">
            <!-- Editor column -->
            <div class="flex-1 min-w-0 space-y-4">

              <!-- Meta fields -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{{ t('builder.details') }}</h3>
                <div class="grid grid-cols-2 gap-3">
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">{{ t('proposals.currency') }}</label>
                    <CurrencySelect v-model="editCurrency" />
                  </div>
                  <div>
                    <label class="block text-xs text-gray-500 mb-1">{{ t('builder.validUntil') }}</label>
                    <input v-model="editExpiry" type="date" class="w-full rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400" />
                  </div>
                </div>

                <!-- View stats -->
                <div v-if="currentProposal.view_count > 0" class="mt-3 flex gap-4 text-xs text-gray-400">
                  <span>👁 {{ t('builder.views', { count: currentProposal.view_count }) }}</span>
                  <span v-if="currentProposal.first_viewed_at">{{ t('builder.firstOpened') }}: {{ formatDate(currentProposal.first_viewed_at) }}</span>
                </div>
              </div>

              <!-- Intro text -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{{ t('builder.introduction') }}</h3>
                <textarea
                  v-model="editIntro"
                  rows="3"
                  class="w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none"
:placeholder="t('builder.introPlaceholder')"
                />
              </div>

              <!-- Line items -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <div class="flex items-center justify-between mb-3">
                  <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide">{{ t('builder.lineItems') }}</h3>
                  <div class="flex items-center gap-2">
                    <button
                      class="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                      @click="showCatalog = !showCatalog; showApplyTemplate = false"
                    >{{ t('proposals.addFromCatalog') }}</button>
                    <button
                      class="text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                      @click="showApplyTemplate = !showApplyTemplate; showCatalog = false"
                    >{{ t('builder.applyTemplate') }}</button>
                  </div>
                </div>

                <!-- Catalog panel -->
                <div v-if="showCatalog" class="mb-3 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl">
                  <p class="text-xs text-gray-500 mb-2">{{ t('proposals.catalogItemsHint') }}</p>
                  <div v-if="catalogItems.length === 0" class="text-xs text-gray-400">
                    {{ t('proposals.catalogEmpty') }} {{ t('proposals.catalogEmptyHint') }}
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
                    {{ addingFromCatalog ? t('proposals.adding') : t('proposals.addSelected') }}
                  </button>
                </div>

                <!-- Apply template panel -->
                <div v-if="showApplyTemplate" class="mb-3 p-3 bg-gray-50 rounded-xl">
                  <p class="text-xs text-gray-500 mb-2">{{ t('builder.selectTemplateHint') }}</p>
                  <div v-if="templates.length === 0" class="text-xs text-gray-400">{{ t('builder.noTemplates') }}</div>
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
                        <th class="text-left py-1.5 pr-2 text-xs font-medium text-gray-500">{{ t('catalog.colDescription') }}</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16">{{ t('builder.qty') }}</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-24">{{ t('catalog.unitPrice') }}</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16">{{ t('catalog.discountPct') }}</th>
                        <th class="text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16">{{ t('catalog.vatPct') }}</th>
                        <th class="text-right py-1.5 pl-2 text-xs font-medium text-gray-500 w-24">{{ t('builder.total') }}</th>
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
                            <button class="text-xs text-green-600 hover:text-green-700 px-1" @click="updateItem(item)" title="Save"><CheckIcon class="w-3.5 h-3.5" /></button>
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
                            <button class="text-xs text-gray-400 hover:text-red-500 px-1" @click="deleteItem(item.id)" title="Delete"><TrashIcon class="w-3.5 h-3.5" /></button>
                          </td>
                        </template>
                      </tr>
                    </tbody>
                    <tfoot>
                      <tr>
                        <td colspan="6" class="py-2 text-right text-xs font-semibold text-gray-700 pr-2">{{ t('builder.total') }}:</td>
                        <td class="py-2 pl-2 text-right text-sm font-bold text-gray-900">{{ fmt(previewTotal) }} {{ editCurrency }}</td>
                        <td></td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                <!-- Add item form -->
                <div class="border border-dashed border-gray-200 rounded-xl p-3">
                  <p class="text-xs text-gray-400 mb-2 font-medium">{{ t('builder.addLineItem') }}</p>
                  <div class="flex flex-wrap gap-2">
                    <input
                      v-model="newItemDesc"
                      type="text"
:placeholder="t('catalog.descriptionLabel')"
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
                    >{{ addingItem ? '…' : ('+ ' + t('common.adding')) }}</button>
                  </div>
                </div>
              </div>

              <!-- Notes -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{{ t('builder.notes') }}</h3>
                <textarea
                  v-model="editNotes"
                  rows="2"
                  class="w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none"
:placeholder="t('builder.notesPlaceholder')"
                />
              </div>

              <!-- Closing text -->
              <div class="bg-white rounded-2xl border border-gray-100 p-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{{ t('builder.closingText') }}</h3>
                <textarea
                  v-model="editClosing"
                  rows="3"
                  class="w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none"
:placeholder="t('builder.closingPlaceholder')"
                />
              </div>
            </div>

            <!-- Live Preview panel -->
            <div
              v-if="showPreview"
              class="w-96 flex-shrink-0"
            >
              <div class="bg-white rounded-2xl border border-gray-100 p-5 sticky top-4">
                <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">{{ t('builder.preview') }}</h3>

                <div
                  class="border-b-4 pb-3 mb-4"
                  :style="{ borderColor: firmStore.activeFirm?.primary_color || '#dc2626' }"
                >
                  <div
                    class="text-base font-bold"
                    :style="{ color: firmStore.activeFirm?.primary_color || '#dc2626' }"
                  >{{ firmStore.activeFirm?.name }}</div>
                  <div class="text-lg font-semibold text-gray-900 mt-1">{{ editTitle || t('builder.proposalTitle') }}</div>
                  <span
                    class="inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium"
                    :class="statusMeta(editStatus).color"
                  >{{ statusMeta(editStatus).label }}</span>
                </div>

                <div class="flex gap-4 text-xs text-gray-400 mb-4">
                  <span v-if="editExpiry">{{ t('builder.validUntil') }}: {{ editExpiry }}</span>
                  <span>{{ editCurrency }}</span>
                </div>

                <div v-if="editIntro" class="text-xs text-gray-600 mb-4 leading-relaxed whitespace-pre-wrap">{{ editIntro }}</div>

                <table class="w-full text-xs mb-4" v-if="items.length > 0">
                  <thead>
                    <tr class="text-gray-500 border-b border-gray-100">
                      <th class="text-left pb-1">{{ t('builder.item') }}</th>
                      <th class="text-right pb-1">{{ t('builder.total') }}</th>
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
                  <div class="flex justify-between text-gray-500"><span>{{ t('builder.subtotal') }}</span><span>{{ fmt(previewSubtotal) }}</span></div>
                  <div v-if="previewDiscount > 0" class="flex justify-between text-gray-500"><span>{{ t('builder.discount') }}</span><span>-{{ fmt(previewDiscount) }}</span></div>
                  <div v-if="previewTax > 0" class="flex justify-between text-gray-500"><span>{{ t('builder.taxVat') }}</span><span>{{ fmt(previewTax) }}</span></div>
                  <div class="flex justify-between font-bold text-sm text-gray-900 pt-1"><span>{{ t('builder.total') }}</span><span>{{ fmt(previewTotal) }} {{ editCurrency }}</span></div>
                </div>

                <div v-if="editClosing" class="mt-4 text-xs text-gray-500 leading-relaxed whitespace-pre-wrap">{{ editClosing }}</div>
              </div>
            </div>
          </div>

          <!-- Streamline: timeline + quick-action sidebar (builder UI above stays untouched) -->
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div class="lg:col-span-2 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4">
              <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">{{ t('recordDetail.tabActivities') }}</h3>
              <ActivityTimeline ref="activityTimelineRef" entityType="proposal" :entityId="currentProposal.id" />
            </div>
            <div>
              <EntitySidebarActionPicker
                entity-type="proposal"
                :entity-id="currentProposal.id"
                @tool-selected="(type) => { activeModalTool = type }"
              />
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>

  <ConfirmDeleteModal
    :open="confirmSendOpen"
    :title="t('builder.sendConfirm')"
    :confirm-label="t('builder.send')"
    @confirm="executeSendProposal"
    @cancel="confirmSendOpen = false"
  />

  <ConfirmDeleteModal
    :open="!!confirmDeleteProposalId"
    :message="t('builder.confirmDelete')"
    @confirm="doDeleteProposal(confirmDeleteProposalId!); confirmDeleteProposalId = null"
    @cancel="confirmDeleteProposalId = null"
  />

  <!-- Streamline Create Modal — opened from sidebar picker -->
  <StreamlineCreateModal
    v-if="currentProposal"
    :model-value="!!activeModalTool"
    :action-type="activeModalTool"
    entity-type="proposal"
    :entity-id="currentProposal.id"
    @update:model-value="(v) => { if (!v) activeModalTool = '' }"
    @activity-added="activityTimelineRef?.load()"
  />
</template>

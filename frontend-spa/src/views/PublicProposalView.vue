<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/api'
import { DocumentIcon, ClockIcon, ClipboardDocumentListIcon, CheckCircleIcon, HandRaisedIcon, CheckIcon, XMarkIcon } from '@heroicons/vue/24/outline'

const route = useRoute()
const token = computed(() => route.params.token as string)

interface ProposalItem {
  id: string
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
}

interface PublicProposal {
  id: string
  title: string
  status: string
  expiry_date: string | null
  currency: string
  notes: string
  intro_text: string
  closing_text: string
  total_value: number
  items: ProposalItem[]
  firm_name: string
  firm_logo_url: string | null
  firm_primary_color: string
  is_expired: boolean
}

const proposal = ref<PublicProposal | null>(null)
const loading = ref(true)
const error = ref('')
const responding = ref(false)
const responded = ref(false)
const responseAction = ref<'accept' | 'reject' | null>(null)

async function loadProposal() {
  loading.value = true
  error.value = ''
  const res = await api.get<PublicProposal>(`/api/v1/crm/public/proposals/${token.value}`)
  loading.value = false
  if (res.ok) {
    proposal.value = res.data
  } else if (res.status === 404) {
    error.value = 'Proposal not found.'
  } else if (res.status === 410) {
    error.value = 'This proposal link has expired.'
  } else {
    error.value = 'Failed to load proposal.'
  }
}

async function respond(action: 'accept' | 'reject') {
  if (!proposal.value || responding.value) return
  if (!confirm(action === 'accept' ? 'Accept this proposal?' : 'Reject this proposal?')) return
  responding.value = true
  const res = await api.post<PublicProposal>(`/api/v1/crm/public/proposals/${token.value}/respond`, {
    action,
  })
  responding.value = false
  if (res.ok) {
    proposal.value = res.data
    responded.value = true
    responseAction.value = action
  } else if (res.status === 410) {
    error.value = 'This proposal link has expired.'
  } else if (res.status === 400) {
    error.value = (res.data as unknown as { detail: string })?.detail ?? 'Failed to respond.'
  } else {
    error.value = 'Failed to respond to proposal.'
  }
}

function fmt(n: number | string) {
  return Number(n).toFixed(2)
}

const subtotal = computed(() =>
  (proposal.value?.items ?? []).reduce((a, i) => a + Number(i.subtotal), 0)
)
const discountTotal = computed(() =>
  (proposal.value?.items ?? []).reduce((a, i) => a + Number(i.discount_amount), 0)
)
const taxTotal = computed(() =>
  (proposal.value?.items ?? []).reduce((a, i) => a + Number(i.tax), 0)
)

onMounted(loadProposal)
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center min-h-screen">
      <div class="animate-pulse space-y-4 w-full max-w-2xl mx-auto p-8">
        <div class="h-8 bg-gray-200 rounded w-64" />
        <div class="h-64 bg-gray-100 rounded-2xl" />
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center min-h-screen p-6">
      <div class="text-center max-w-sm">
        <DocumentIcon class="w-12 h-12 mx-auto mb-4 text-gray-400" />
        <h1 class="text-xl font-semibold text-gray-900 mb-2">Proposal unavailable</h1>
        <p class="text-sm text-gray-500">{{ error }}</p>
      </div>
    </div>

    <!-- Proposal content -->
    <div v-else-if="proposal" class="max-w-3xl mx-auto py-10 px-4">
      <!-- Firm header -->
      <div
        class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 mb-6"
        :style="{ borderTopColor: proposal.firm_primary_color, borderTopWidth: '4px' }"
      >
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <img
              v-if="proposal.firm_logo_url"
              :src="proposal.firm_logo_url"
              alt="Logo"
              class="h-12 mb-3 object-contain"
            />
            <div
              class="text-lg font-bold"
              :style="{ color: proposal.firm_primary_color }"
            >{{ proposal.firm_name }}</div>
          </div>
          <div class="text-right">
            <h1 class="text-2xl font-semibold text-gray-900">{{ proposal.title }}</h1>
            <div class="mt-2 flex flex-wrap gap-2 justify-end">
              <span
                v-if="proposal.status === 'accepted'"
                class="inline-flex items-center gap-1 px-3 py-1 rounded-xl text-sm font-semibold bg-green-100 text-green-700"
              ><CheckIcon class="w-4 h-4" /> Accepted</span>
              <span
                v-else-if="proposal.status === 'rejected'"
                class="inline-flex items-center gap-1 px-3 py-1 rounded-xl text-sm font-semibold bg-red-100 text-red-700"
              ><XMarkIcon class="w-4 h-4" /> Rejected</span>
              <span
                v-else-if="proposal.is_expired"
                class="inline-flex items-center gap-1 px-3 py-1 rounded-xl text-sm font-semibold bg-orange-100 text-orange-700"
              ><ClockIcon class="w-4 h-4" /> Expired</span>
              <span
                v-else
                class="inline-flex items-center gap-1 px-3 py-1 rounded-xl text-sm font-semibold bg-blue-100 text-blue-700"
              ><ClipboardDocumentListIcon class="w-4 h-4" /> Awaiting Response</span>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-4 mt-4 text-xs text-gray-400">
          <span v-if="proposal.expiry_date">
            <span class="font-medium text-gray-600">Valid until:</span> {{ proposal.expiry_date }}
          </span>
          <span>
            <span class="font-medium text-gray-600">Currency:</span> {{ proposal.currency }}
          </span>
        </div>
      </div>

      <!-- Introduction -->
      <div v-if="proposal.intro_text" class="bg-white rounded-2xl border border-gray-100 p-6 mb-6">
        <p class="text-gray-700 leading-relaxed whitespace-pre-wrap text-sm">{{ proposal.intro_text }}</p>
      </div>

      <!-- Line items -->
      <div class="bg-white rounded-2xl border border-gray-100 p-6 mb-6">
        <h2 class="text-sm font-semibold text-gray-900 mb-4">Line Items</h2>

        <div v-if="proposal.items.length === 0" class="text-sm text-gray-400 text-center py-4">
          No items in this proposal.
        </div>
        <table v-else class="w-full text-sm">
          <thead>
            <tr
              class="text-white text-xs"
              :style="{ background: proposal.firm_primary_color }"
            >
              <th class="text-left px-4 py-2.5 rounded-tl-xl">Description</th>
              <th class="text-right px-3 py-2.5">Qty</th>
              <th class="text-right px-3 py-2.5">Unit Price</th>
              <th class="text-right px-3 py-2.5">Disc%</th>
              <th class="text-right px-3 py-2.5">VAT%</th>
              <th class="text-right px-4 py-2.5 rounded-tr-xl">Total</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in proposal.items"
              :key="item.id"
              class="border-b border-gray-50 hover:bg-gray-50 transition-colors"
            >
              <td class="px-4 py-3 text-gray-800">{{ item.description }}</td>
              <td class="px-3 py-3 text-right text-gray-500">{{ item.quantity }}</td>
              <td class="px-3 py-3 text-right text-gray-500">{{ fmt(item.unit_price) }}</td>
              <td class="px-3 py-3 text-right text-gray-500">{{ item.discount }}%</td>
              <td class="px-3 py-3 text-right text-gray-500">{{ item.vat_rate }}%</td>
              <td class="px-4 py-3 text-right font-medium text-gray-800">{{ fmt(item.total) }} {{ proposal.currency }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Totals -->
        <div class="mt-4 flex justify-end">
          <div class="min-w-56 text-sm space-y-1">
            <div class="flex justify-between text-gray-500">
              <span>Subtotal</span>
              <span>{{ fmt(subtotal) }} {{ proposal.currency }}</span>
            </div>
            <div v-if="discountTotal > 0" class="flex justify-between text-gray-500">
              <span>Discount</span>
              <span>-{{ fmt(discountTotal) }} {{ proposal.currency }}</span>
            </div>
            <div v-if="taxTotal > 0" class="flex justify-between text-gray-500">
              <span>Tax / VAT</span>
              <span>{{ fmt(taxTotal) }} {{ proposal.currency }}</span>
            </div>
            <div
              class="flex justify-between font-bold text-base text-gray-900 pt-2 border-t-2"
              :style="{ borderColor: proposal.firm_primary_color }"
            >
              <span>Total</span>
              <span>{{ fmt(proposal.total_value) }} {{ proposal.currency }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Notes (not shown — internal only) -->

      <!-- Closing text -->
      <div v-if="proposal.closing_text" class="bg-white rounded-2xl border border-gray-100 p-6 mb-6">
        <p class="text-gray-600 leading-relaxed whitespace-pre-wrap text-sm">{{ proposal.closing_text }}</p>
      </div>

      <!-- Response buttons -->
      <div
        v-if="!proposal.is_expired && proposal.status !== 'accepted' && proposal.status !== 'rejected'"
        class="bg-white rounded-2xl border border-gray-100 p-6 mb-6"
      >
        <h2 class="text-sm font-semibold text-gray-900 mb-4">Your Response</h2>
        <div class="flex gap-3">
          <button
            class="flex-1 py-3 rounded-xl text-sm font-semibold bg-green-500 text-white hover:bg-green-600 disabled:opacity-50 transition-colors"
            :disabled="responding"
            @click="respond('accept')"
          >
            {{ responding && responseAction === 'accept' ? 'Processing…' : '✓ Accept Proposal' }}
          </button>
          <button
            class="flex-1 py-3 rounded-xl text-sm font-semibold bg-red-100 text-red-700 hover:bg-red-200 disabled:opacity-50 transition-colors"
            :disabled="responding"
            @click="respond('reject')"
          >
            {{ responding && responseAction === 'reject' ? 'Processing…' : 'Decline' }}
          </button>
        </div>
      </div>

      <!-- Response confirmation -->
      <div
        v-if="responded"
        class="rounded-2xl border p-6 mb-6 text-center"
        :class="responseAction === 'accept' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'"
      >
        <component :is="responseAction === 'accept' ? CheckCircleIcon : HandRaisedIcon" class="w-10 h-10 mx-auto mb-2" :class="responseAction === 'accept' ? 'text-green-500' : 'text-red-400'" />
        <p
          class="text-base font-semibold"
          :class="responseAction === 'accept' ? 'text-green-700' : 'text-red-700'"
        >
          {{ responseAction === 'accept' ? 'Thank you for accepting this proposal!' : 'You have declined this proposal.' }}
        </p>
        <p class="text-sm text-gray-500 mt-1">The sender has been notified.</p>
      </div>

      <!-- Expired notice -->
      <div v-if="proposal.is_expired" class="rounded-2xl bg-orange-50 border border-orange-200 p-4 text-center text-sm text-orange-700">
        <ClockIcon class="w-4 h-4 inline-block mr-1 align-text-bottom" /> This proposal link has expired. Please contact the sender to request a new link.
      </div>

      <!-- Footer -->
      <div class="text-center text-xs text-gray-400 mt-8">
        Powered by <span class="font-medium">LeadLab</span>
      </div>
    </div>
  </div>
</template>

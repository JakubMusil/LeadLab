<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import { useI18n } from '@/composables/useI18n'

const router = useRouter()
const { t } = useI18n()

// ─── Types ──────────────────────────────────────────────────────────────────

interface ReportSummary {
  total_minutes: number
  billable_minutes: number
  total_expenses: string
  total_revenues: string
  profit_loss: string
}

interface ExpenseItemOut {
  id: string
  title: string
  amount: string
  currency: string
  date: string
  recurrence: string
  lead_title: string | null
  customer_name: string | null
  user_name: string | null
  notes: string
}

interface RevenueItemOut {
  id: string
  title: string
  amount: string
  currency: string
  date: string
  recurrence: string
  lead_title: string | null
  customer_name: string | null
  user_name: string | null
  notes: string
}

// ─── State ──────────────────────────────────────────────────────────────────

const summary = ref<ReportSummary | null>(null)
const expenses = ref<ExpenseItemOut[]>([])
const revenues = ref<RevenueItemOut[]>([])
const loading = ref(false)
const toast = ref<string | null>(null)

// Filters
const filterDateFrom = ref('')
const filterDateTo = ref('')
const filterLeadId = ref('')
const filterCustomerId = ref('')

// Expense form
const showExpenseForm = ref(false)
const expenseForm = ref({ title: '', amount: '', currency: 'CZK', date: new Date().toISOString().substring(0, 10), recurrence: 'once', notes: '' })
const expenseLoading = ref(false)

// Revenue form
const showRevenueForm = ref(false)
const revenueForm = ref({ title: '', amount: '', currency: 'CZK', date: new Date().toISOString().substring(0, 10), recurrence: 'once', notes: '' })
const revenueLoading = ref(false)

// Active tab
const activeTab = ref<'overview' | 'expenses' | 'revenues'>('overview')

// ─── Helpers ────────────────────────────────────────────────────────────────

function showToast(msg: string) {
  toast.value = msg
  setTimeout(() => { toast.value = null }, 3000)
}

function formatDuration(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function formatMoney(val: string | number): string {
  return Number(val).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function params() {
  const p = new URLSearchParams()
  if (filterDateFrom.value) p.set('date_from', filterDateFrom.value)
  if (filterDateTo.value) p.set('date_to', filterDateTo.value)
  if (filterLeadId.value) p.set('lead_id', filterLeadId.value)
  if (filterCustomerId.value) p.set('customer_id', filterCustomerId.value)
  return p.size ? '?' + p.toString() : ''
}

// ─── Fetch ───────────────────────────────────────────────────────────────────

async function fetchAll() {
  loading.value = true
  try {
    const [s, ex, rev] = await Promise.all([
      api.get<ReportSummary>(`/api/v1/erp/reports/summary${params()}`),
      api.get<ExpenseItemOut[]>(`/api/v1/erp/expenses${params()}`),
      api.get<RevenueItemOut[]>(`/api/v1/erp/revenues${params()}`),
    ])
    if (s.ok) summary.value = s.data
    if (ex.ok) expenses.value = ex.data
    if (rev.ok) revenues.value = rev.data
  } finally {
    loading.value = false
  }
}

onMounted(fetchAll)

// ─── Add expense ─────────────────────────────────────────────────────────────

async function addExpense() {
  expenseLoading.value = true
  try {
    const res = await api.post<ExpenseItemOut>('/api/v1/erp/expenses', {
      title: expenseForm.value.title,
      amount: expenseForm.value.amount,
      currency: expenseForm.value.currency,
      date: expenseForm.value.date,
      recurrence: expenseForm.value.recurrence,
      notes: expenseForm.value.notes,
    })
    if (res.ok) {
      expenses.value.unshift(res.data)
      showExpenseForm.value = false
      expenseForm.value = { title: '', amount: '', currency: 'CZK', date: new Date().toISOString().substring(0, 10), recurrence: 'once', notes: '' }
      showToast('Expense added')
      await fetchAll()
    } else {
      showToast(extractErrorMessage(res.data, 'Failed to add expense'))
    }
  } finally {
    expenseLoading.value = false
  }
}

async function deleteExpense(id: string) {
  if (!confirm('Delete this expense?')) return
  const res = await api.delete(`/api/v1/erp/expenses/${id}`)
  if (res.ok || res.status === 204) {
    expenses.value = expenses.value.filter(e => e.id !== id)
    showToast('Expense deleted')
    await fetchAll()
  }
}

// ─── Add revenue ─────────────────────────────────────────────────────────────

async function addRevenue() {
  revenueLoading.value = true
  try {
    const res = await api.post<RevenueItemOut>('/api/v1/erp/revenues', {
      title: revenueForm.value.title,
      amount: revenueForm.value.amount,
      currency: revenueForm.value.currency,
      date: revenueForm.value.date,
      recurrence: revenueForm.value.recurrence,
      notes: revenueForm.value.notes,
    })
    if (res.ok) {
      revenues.value.unshift(res.data)
      showRevenueForm.value = false
      revenueForm.value = { title: '', amount: '', currency: 'CZK', date: new Date().toISOString().substring(0, 10), recurrence: 'once', notes: '' }
      showToast('Revenue added')
      await fetchAll()
    } else {
      showToast(extractErrorMessage(res.data, 'Failed to add revenue'))
    }
  } finally {
    revenueLoading.value = false
  }
}

async function deleteRevenue(id: string) {
  if (!confirm('Delete this revenue item?')) return
  const res = await api.delete(`/api/v1/erp/revenues/${id}`)
  if (res.ok || res.status === 204) {
    revenues.value = revenues.value.filter(r => r.id !== id)
    showToast('Revenue deleted')
    await fetchAll()
  }
}

// ─── CSV export ───────────────────────────────────────────────────────────────

function exportCSV(type: 'time' | 'expenses' | 'revenues') {
  let rows: string[][] = []
  if (type === 'expenses') {
    rows = [
      ['Date', 'Title', 'Amount', 'Currency', 'Recurrence', 'Linked to', 'Notes'],
      ...expenses.value.map(e => [
        e.date, e.title, e.amount, e.currency, e.recurrence,
        e.lead_title ?? e.customer_name ?? '', e.notes,
      ]),
    ]
  } else if (type === 'revenues') {
    rows = [
      ['Date', 'Title', 'Amount', 'Currency', 'Recurrence', 'Linked to', 'Notes'],
      ...revenues.value.map(r => [
        r.date, r.title, r.amount, r.currency, r.recurrence,
        r.lead_title ?? r.customer_name ?? '', r.notes,
      ]),
    ]
  }
  if (!rows.length) return
  const csv = rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `leadlab-${type}-${new Date().toISOString().substring(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ─── Create proposal from report ─────────────────────────────────────────────

async function createProposalFromReport() {
  const dateRange = [filterDateFrom.value, filterDateTo.value].filter(Boolean).join(' – ')
  const res = await api.post<{ id: string }>('/api/v1/crm/proposals', {
    title: dateRange ? `${t('proposals.createFromReport')} ${dateRange}` : t('proposals.createFromReport'),
    currency: 'CZK',
  })
  if (res.ok) {
    router.push(`/app/proposals/${res.data.id}`)
  } else {
    showToast(t('proposals.errorCreate'))
  }
}

// ─── Fakturoid export ─────────────────────────────────────────────────────────

const fakturoidExporting = ref(false)

async function exportToFakturoid() {
  if (!revenues.value.length) {
    showToast('No revenue items to export.')
    return
  }
  // Validate that all items share the same currency
  const currencies = [...new Set(revenues.value.map(r => r.currency))]
  if (currencies.length > 1) {
    showToast(`Cannot export: revenue items have mixed currencies (${currencies.join(', ')}). Filter to a single currency first.`)
    return
  }
  fakturoidExporting.value = true
  try {
    const lines = revenues.value.map(r => ({
      name: r.title,
      quantity: 1,
      unit_name: 'ks',
      unit_price: Number(r.amount),
      vat_rate: 0,
    }))
    const currency = currencies[0] ?? 'CZK'
    const res = await api.post<{ ok: boolean; invoice?: { id: number; number: string; html_url: string }; error?: string }>(
      '/api/v1/integrations/fakturoid/invoices',
      { lines, currency, due: 14 },
    )
    if (res.ok && res.data?.ok && res.data.invoice) {
      showToast(`Invoice ${res.data.invoice.number} created in Fakturoid.`)
    } else {
      const err = res.data?.error ?? 'Failed to create invoice in Fakturoid.'
      showToast(err)
    }
  } finally {
    fakturoidExporting.value = false
  }
}
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Reports</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">P&amp;L overview, costs and revenues</p>
      </div>
      <button
        class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
        @click="createProposalFromReport"
      >
        {{ t('proposals.createFromReport') }}
      </button>
    </div>

    <!-- Toast -->
    <Transition name="fade">
      <div v-if="toast" class="mb-4 bg-gray-900 text-white text-sm px-4 py-2 rounded-xl w-fit">{{ toast }}</div>
    </Transition>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-6">
      <input v-model="filterDateFrom" type="date"
        class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
      <input v-model="filterDateTo" type="date"
        class="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
      <button class="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors" @click="fetchAll">Apply</button>
      <button class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
        @click="filterDateFrom = ''; filterDateTo = ''; filterLeadId = ''; filterCustomerId = ''; fetchAll()">Clear</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16 text-gray-400">Loading…</div>

    <template v-else>
      <!-- Summary cards -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Total time</div>
          <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ formatDuration(summary?.total_minutes ?? 0) }}</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Billable time</div>
          <div class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ formatDuration(summary?.billable_minutes ?? 0) }}</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Expenses</div>
          <div class="text-xl font-bold text-red-600 dark:text-red-400">{{ formatMoney(summary?.total_expenses ?? 0) }}</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Revenues</div>
          <div class="text-xl font-bold text-green-600 dark:text-green-400">{{ formatMoney(summary?.total_revenues ?? 0) }}</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-4">
          <div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">P&amp;L</div>
          <div
            class="text-xl font-bold"
            :class="Number(summary?.profit_loss ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'"
          >
            {{ formatMoney(summary?.profit_loss ?? 0) }}
          </div>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 bg-gray-100 dark:bg-gray-700/50 rounded-xl p-1 w-fit mb-6">
        <button
          v-for="tab in [
            { id: 'overview', label: 'Overview' },
            { id: 'expenses', label: 'Expenses' },
            { id: 'revenues', label: 'Revenues' },
          ]"
          :key="tab.id"
          class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
          :class="activeTab === tab.id
            ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
            : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'"
          @click="activeTab = tab.id as typeof activeTab"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- OVERVIEW TAB -->
      <div v-if="activeTab === 'overview'" class="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <!-- Expenses breakdown -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Top expenses</h3>
          <div v-if="!expenses.length" class="text-sm text-gray-400">No expenses yet.</div>
          <ul v-else class="space-y-2">
            <li v-for="e in expenses.slice(0, 5)" :key="e.id" class="flex justify-between items-center text-sm">
              <span class="text-gray-700 dark:text-gray-300 truncate mr-2">{{ e.title }}</span>
              <span class="font-medium text-red-600 dark:text-red-400 flex-shrink-0">{{ formatMoney(e.amount) }}</span>
            </li>
          </ul>
        </div>
        <!-- Revenue breakdown -->
        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Top revenues</h3>
          <div v-if="!revenues.length" class="text-sm text-gray-400">No revenues yet.</div>
          <ul v-else class="space-y-2">
            <li v-for="r in revenues.slice(0, 5)" :key="r.id" class="flex justify-between items-center text-sm">
              <span class="text-gray-700 dark:text-gray-300 truncate mr-2">{{ r.title }}</span>
              <span class="font-medium text-green-600 dark:text-green-400 flex-shrink-0">{{ formatMoney(r.amount) }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- EXPENSES TAB -->
      <div v-else-if="activeTab === 'expenses'">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Expense items</h2>
          <div class="flex gap-2">
            <button class="text-sm px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="exportCSV('expenses')">⬇ CSV</button>
            <button class="text-sm px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              @click="showExpenseForm = !showExpenseForm">+ Add expense</button>
          </div>
        </div>

        <!-- Add expense form -->
        <div v-if="showExpenseForm" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 mb-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title</label>
              <input v-model="expenseForm.title" type="text"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
            <div class="flex gap-2">
              <div class="flex-1">
                <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Amount</label>
                <input v-model="expenseForm.amount" type="number" step="0.01"
                  class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
              </div>
              <div class="w-24">
                <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Currency</label>
                <input v-model="expenseForm.currency" type="text" maxlength="3"
                  class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Date</label>
              <input v-model="expenseForm.date" type="date"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Recurrence</label>
              <select v-model="expenseForm.recurrence"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500">
                <option value="once">Once</option>
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </div>
            <div class="sm:col-span-2">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Notes</label>
              <input v-model="expenseForm.notes" type="text"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
          </div>
          <div class="flex gap-3 mt-4 justify-end">
            <button class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl" @click="showExpenseForm = false">Cancel</button>
            <button class="px-4 py-2 text-sm font-medium bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-60 transition-colors"
              :disabled="expenseLoading" @click="addExpense">{{ expenseLoading ? 'Saving…' : 'Save' }}</button>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div v-if="!expenses.length" class="py-10 text-center text-gray-400 text-sm">No expense items yet.</div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100 dark:border-gray-700 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                <th class="px-4 py-3 text-left">Date</th>
                <th class="px-4 py-3 text-left">Title</th>
                <th class="px-4 py-3 text-right">Amount</th>
                <th class="px-4 py-3 text-left">Recurrence</th>
                <th class="px-4 py-3 text-left">Linked to</th>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in expenses" :key="e.id" class="border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ e.date }}</td>
                <td class="px-4 py-3 text-gray-900 dark:text-gray-100">{{ e.title }}</td>
                <td class="px-4 py-3 text-right font-medium text-red-600 dark:text-red-400">{{ formatMoney(e.amount) }} {{ e.currency }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400 capitalize">{{ e.recurrence }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ e.lead_title ?? e.customer_name ?? '—' }}</td>
                <td class="px-4 py-3 text-right">
                  <button class="text-sm text-red-500 hover:text-red-700" @click="deleteExpense(e.id)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- REVENUES TAB -->
      <div v-else-if="activeTab === 'revenues'">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Revenue items</h2>
          <div class="flex gap-2">
            <button class="text-sm px-3 py-1.5 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              @click="exportCSV('revenues')">⬇ CSV</button>
            <button
              class="text-sm px-3 py-1.5 border border-blue-300 dark:border-blue-700 rounded-lg text-blue-700 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-50"
              :disabled="fakturoidExporting || !revenues.length"
              @click="exportToFakturoid"
              title="Create invoice in Fakturoid from all visible revenue items"
            >{{ fakturoidExporting ? 'Exporting…' : '📄 Fakturoid invoice' }}</button>
            <button class="text-sm px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              @click="showRevenueForm = !showRevenueForm">+ Add revenue</button>
          </div>
        </div>

        <!-- Add revenue form -->
        <div v-if="showRevenueForm" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5 mb-4">
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Title</label>
              <input v-model="revenueForm.title" type="text"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
            <div class="flex gap-2">
              <div class="flex-1">
                <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Amount</label>
                <input v-model="revenueForm.amount" type="number" step="0.01"
                  class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
              </div>
              <div class="w-24">
                <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Currency</label>
                <input v-model="revenueForm.currency" type="text" maxlength="3"
                  class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
              </div>
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Date</label>
              <input v-model="revenueForm.date" type="date"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
            <div>
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Recurrence</label>
              <select v-model="revenueForm.recurrence"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500">
                <option value="once">Once</option>
                <option value="monthly">Monthly</option>
                <option value="yearly">Yearly</option>
              </select>
            </div>
            <div class="sm:col-span-2">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Notes</label>
              <input v-model="revenueForm.notes" type="text"
                class="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500" />
            </div>
          </div>
          <div class="flex gap-3 mt-4 justify-end">
            <button class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl" @click="showRevenueForm = false">Cancel</button>
            <button class="px-4 py-2 text-sm font-medium bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-60 transition-colors"
              :disabled="revenueLoading" @click="addRevenue">{{ revenueLoading ? 'Saving…' : 'Save' }}</button>
          </div>
        </div>

        <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div v-if="!revenues.length" class="py-10 text-center text-gray-400 text-sm">No revenue items yet.</div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-100 dark:border-gray-700 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                <th class="px-4 py-3 text-left">Date</th>
                <th class="px-4 py-3 text-left">Title</th>
                <th class="px-4 py-3 text-right">Amount</th>
                <th class="px-4 py-3 text-left">Recurrence</th>
                <th class="px-4 py-3 text-left">Linked to</th>
                <th class="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in revenues" :key="r.id" class="border-b border-gray-50 dark:border-gray-700/50 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ r.date }}</td>
                <td class="px-4 py-3 text-gray-900 dark:text-gray-100">{{ r.title }}</td>
                <td class="px-4 py-3 text-right font-medium text-green-600 dark:text-green-400">{{ formatMoney(r.amount) }} {{ r.currency }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400 capitalize">{{ r.recurrence }}</td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ r.lead_title ?? r.customer_name ?? '—' }}</td>
                <td class="px-4 py-3 text-right">
                  <button class="text-sm text-red-500 hover:text-red-700" @click="deleteRevenue(r.id)">Delete</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

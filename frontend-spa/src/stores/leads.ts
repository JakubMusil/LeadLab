import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import { useFirmStore } from '@/stores/firm'

export interface LeadOut {
  id: string
  firm_id: string
  customer_id: string | null
  title: string
  description: string
  status: string
  source: string
  assigned_to_id: string | null
  value: number | null
  currency: string
  created_at: string
  updated_at: string
  created_by_id: string | null
  created_by_name: string | null
}

export interface LeadIn {
  title: string
  description?: string
  customer_id?: string | null
  status?: string
  source?: string
  assigned_to_id?: string | null
  value?: number | null
  currency?: string
}

export interface LeadFilters {
  status?: string
  source?: string
  assigned_to?: string
  page?: number
  page_size?: number
}

export const LEAD_STATUSES = [
  { value: 'new', label: 'New', color: 'bg-gray-100 text-gray-700' },
  { value: 'contacted', label: 'Contacted', color: 'bg-blue-100 text-blue-700' },
  { value: 'proposal', label: 'Proposal', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'negotiation', label: 'Negotiation', color: 'bg-orange-100 text-orange-700' },
  { value: 'won', label: 'Won', color: 'bg-green-100 text-green-700' },
  { value: 'lost', label: 'Lost', color: 'bg-red-100 text-red-700' },
  { value: 'canceled', label: 'Canceled', color: 'bg-gray-100 text-gray-500' },
]

export const LEAD_SOURCES = [
  { value: 'web', label: 'Web' },
  { value: 'email', label: 'Email' },
  { value: 'referral', label: 'Referral' },
  { value: 'cold_call', label: 'Cold Call' },
  { value: 'social', label: 'Social' },
  { value: 'other', label: 'Other' },
]

export function getStatusMeta(status: string) {
  return LEAD_STATUSES.find((s) => s.value === status) ?? { value: status, label: status, color: 'bg-gray-100 text-gray-700' }
}

export const useLeadsStore = defineStore('leads', () => {
  const leads = ref<LeadOut[]>([])
  const currentLead = ref<LeadOut | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)
  const page = ref(1)
  const pageSize = ref(20)
  const hasMore = ref(true)

  function firmHeader() {
    const firmStore = useFirmStore()
    return firmStore.activeFirm ? { 'X-Firm-ID': String(firmStore.activeFirm.id) } : {}
  }

  async function fetchLeads(filters: LeadFilters = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (filters.status) params.set('status', filters.status)
      if (filters.source) params.set('source', filters.source)
      if (filters.assigned_to) params.set('assigned_to', filters.assigned_to)
      const p = filters.page ?? 1
      const ps = filters.page_size ?? pageSize.value
      params.set('page', String(p))
      params.set('page_size', String(ps))
      const res = await api.get<LeadOut[]>(`/api/v1/crm/opportunities?${params}`)
      if (res.ok) {
        if (p === 1) {
          leads.value = res.data
        } else {
          leads.value = [...leads.value, ...res.data]
        }
        page.value = p
        hasMore.value = res.data.length === ps
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Failed to load leads.') }
    } finally {
      loading.value = false
    }
  }

  async function fetchLead(id: string): Promise<{ ok: boolean; error?: string }> {
    loadingDetail.value = true
    try {
      const res = await api.get<LeadOut>(`/api/v1/crm/opportunities/${id}`)
      if (res.ok) {
        currentLead.value = res.data
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Lead not found.') }
    } finally {
      loadingDetail.value = false
    }
  }

  async function createLead(payload: LeadIn): Promise<{ ok: boolean; data?: LeadOut; error?: string }> {
    const res = await api.post<LeadOut>('/api/v1/crm/opportunities', payload)
    if (res.ok) {
      leads.value.unshift(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create lead.') }
  }

  async function updateLead(id: string, payload: Partial<LeadIn>): Promise<{ ok: boolean; data?: LeadOut; error?: string }> {
    const res = await api.patch<LeadOut>(`/api/v1/crm/opportunities/${id}`, payload)
    if (res.ok) {
      const idx = leads.value.findIndex((l) => l.id === id)
      if (idx !== -1) leads.value[idx] = res.data
      if (currentLead.value?.id === id) currentLead.value = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update lead.') }
  }

  async function patchStatus(id: string, status: string): Promise<{ ok: boolean; error?: string }> {
    // Optimistic update
    const idx = leads.value.findIndex((l) => l.id === id)
    const prevStatus = idx !== -1 ? leads.value[idx]!.status : null
    if (idx !== -1) leads.value[idx] = { ...leads.value[idx]!, status }
    if (currentLead.value?.id === id) currentLead.value = { ...currentLead.value, status }

    const res = await api.patch<LeadOut>(`/api/v1/crm/opportunities/${id}`, { status })
    if (res.ok) {
      if (idx !== -1) leads.value[idx] = res.data
      if (currentLead.value?.id === id) currentLead.value = res.data
      return { ok: true }
    }
    // Roll back
    if (prevStatus !== null && idx !== -1) leads.value[idx] = { ...leads.value[idx]!, status: prevStatus }
    if (prevStatus !== null && currentLead.value?.id === id) currentLead.value = { ...currentLead.value, status: prevStatus }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update status.') }
  }

  async function deleteLead(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/opportunities/${id}`)
    if (res.ok || res.status === 204) {
      leads.value = leads.value.filter((l) => l.id !== id)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete lead.') }
  }

  return {
    leads, currentLead, loading, loadingDetail, page, pageSize, hasMore,
    firmHeader,
    fetchLeads, fetchLead, createLead, updateLead, patchStatus, deleteLead,
  }
})

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import { useFirmStore } from '@/stores/firm'

export interface RecordOut {
  id: string
  firm_id: string
  customer_id: string | null
  title: string
  status: string
  source: string
  assigned_to_id: string | null
  assigned_to_name: string | null
  value: number | null
  currency: string
  score?: number | null
  created_at: string
  updated_at: string
  created_by_id: string | null
  created_by_name: string | null
  company_id: string | null
  company_name: string | null
  contact_person_id: string | null
  contact_person_name: string | null
  // Pipeline fields
  category_id: string | null
  current_stage_id: string | null
  current_stage_name: string | null
  parent_id: string | null
  start_date: string | null
  end_date: string | null
  expires_at: string | null
  notes: string
  extra_data: Record<string, unknown>
}

export interface RecordIn {
  title: string
  customer_id?: string | null
  status?: string
  source?: string
  assigned_to_id?: string | null
  value?: number | null
  currency?: string
  company_id?: string | null
  contact_person_id?: string | null
  // Pipeline fields
  category_id?: string | null
  current_stage_id?: string | null
  parent_id?: string | null
  start_date?: string | null
  end_date?: string | null
  expires_at?: string | null
  notes?: string
  extra_data?: Record<string, unknown>
}

export interface RecordFilters {
  status?: string
  source?: string
  assigned_to?: string
  created_by?: string
  value_min?: number
  value_max?: number
  created_after?: string
  created_before?: string
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  page?: number
  page_size?: number
  // Pipeline filters
  category_id?: string
  stage_id?: string
  parent_id?: string
}

export const RECORD_STATUSES = [
  { value: 'new', label: 'New', color: 'bg-gray-100 text-gray-700' },
  { value: 'contacted', label: 'Contacted', color: 'bg-blue-100 text-blue-700' },
  { value: 'proposal', label: 'Proposal', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'negotiation', label: 'Negotiation', color: 'bg-orange-100 text-orange-700' },
  { value: 'won', label: 'Won', color: 'bg-green-100 text-green-700' },
  { value: 'lost', label: 'Lost', color: 'bg-red-100 text-red-700' },
  { value: 'canceled', label: 'Canceled', color: 'bg-gray-100 text-gray-500' },
]

export const RECORD_SOURCES = [
  { value: 'web', label: 'Web' },
  { value: 'email', label: 'Email' },
  { value: 'referral', label: 'Referral' },
  { value: 'cold_call', label: 'Cold Call' },
  { value: 'social', label: 'Social' },
  { value: 'other', label: 'Other' },
]

export function getStatusMeta(status: string) {
  return RECORD_STATUSES.find((s) => s.value === status) ?? { value: status, label: status, color: 'bg-gray-100 text-gray-700' }
}

export const useRecordsStore = defineStore('records', () => {
  const records = ref<RecordOut[]>([])
  const currentRecord = ref<RecordOut | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)
  const page = ref(1)
  const pageSize = ref(20)
  const hasMore = ref(true)

  function firmHeader() {
    const firmStore = useFirmStore()
    return firmStore.activeFirm ? { 'X-Firm-ID': String(firmStore.activeFirm.id) } : {}
  }

  async function fetchRecords(filters: RecordFilters = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (filters.status) params.set('status', filters.status)
      if (filters.source) params.set('source', filters.source)
      if (filters.assigned_to) params.set('assigned_to', filters.assigned_to)
      if (filters.created_by) params.set('created_by', filters.created_by)
      if (filters.value_min != null) params.set('value_min', String(filters.value_min))
      if (filters.value_max != null) params.set('value_max', String(filters.value_max))
      if (filters.created_after) params.set('created_after', filters.created_after)
      if (filters.created_before) params.set('created_before', filters.created_before)
      if (filters.sort_by) params.set('sort_by', filters.sort_by)
      if (filters.sort_dir) params.set('sort_dir', filters.sort_dir)
      if (filters.category_id) params.set('category_id', filters.category_id)
      if (filters.stage_id) params.set('stage_id', filters.stage_id)
      if (filters.parent_id) params.set('parent_id', filters.parent_id)
      const p = filters.page ?? 1
      const ps = filters.page_size ?? pageSize.value
      params.set('page', String(p))
      params.set('page_size', String(ps))
      const res = await api.get<RecordOut[]>(`/api/v1/crm/records?${params}`)
      if (res.ok) {
        if (p === 1) {
          records.value = res.data
        } else {
          records.value = [...records.value, ...res.data]
        }
        page.value = p
        hasMore.value = res.data.length === ps
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Failed to load records.') }
    } finally {
      loading.value = false
    }
  }

  async function fetchRecord(id: string): Promise<{ ok: boolean; error?: string }> {
    loadingDetail.value = true
    try {
      const res = await api.get<RecordOut>(`/api/v1/crm/records/${id}`)
      if (res.ok) {
        currentRecord.value = res.data
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Record not found.') }
    } finally {
      loadingDetail.value = false
    }
  }

  async function createRecord(payload: RecordIn): Promise<{ ok: boolean; data?: RecordOut; error?: string }> {
    const res = await api.post<RecordOut>('/api/v1/crm/records', payload)
    if (res.ok) {
      if (!records.value.find((l) => l.id === res.data.id)) {
        records.value.unshift(res.data)
      }
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create record.') }
  }

  async function updateRecord(id: string, payload: Partial<RecordIn>): Promise<{ ok: boolean; data?: RecordOut; error?: string }> {
    const res = await api.patch<RecordOut>(`/api/v1/crm/records/${id}`, payload)
    if (res.ok) {
      const idx = records.value.findIndex((l) => l.id === id)
      if (idx !== -1) records.value[idx] = res.data
      if (currentRecord.value?.id === id) currentRecord.value = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update record.') }
  }

  async function patchStatus(id: string, status: string): Promise<{ ok: boolean; error?: string }> {
    // Optimistic update
    const idx = records.value.findIndex((l) => l.id === id)
    const prevStatus = idx !== -1 ? records.value[idx]!.status : null
    if (idx !== -1) records.value[idx] = { ...records.value[idx]!, status }
    if (currentRecord.value?.id === id) currentRecord.value = { ...currentRecord.value, status }

    const res = await api.patch<RecordOut>(`/api/v1/crm/records/${id}`, { status })
    if (res.ok) {
      if (idx !== -1) records.value[idx] = res.data
      if (currentRecord.value?.id === id) currentRecord.value = res.data
      return { ok: true }
    }
    // Roll back
    if (prevStatus !== null && idx !== -1) records.value[idx] = { ...records.value[idx]!, status: prevStatus }
    if (prevStatus !== null && currentRecord.value?.id === id) currentRecord.value = { ...currentRecord.value, status: prevStatus }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update status.') }
  }

  async function patchStage(id: string, stageId: string | null): Promise<{ ok: boolean; error?: string }> {
    // Optimistic update
    const idx = records.value.findIndex((l) => l.id === id)
    const prev = idx !== -1 ? { current_stage_id: records.value[idx]!.current_stage_id, current_stage_name: records.value[idx]!.current_stage_name } : null
    if (idx !== -1) records.value[idx] = { ...records.value[idx]!, current_stage_id: stageId, current_stage_name: null }
    if (currentRecord.value?.id === id) currentRecord.value = { ...currentRecord.value, current_stage_id: stageId, current_stage_name: null }

    const res = await api.patch<RecordOut>(`/api/v1/crm/records/${id}`, { current_stage_id: stageId })
    if (res.ok) {
      if (idx !== -1) records.value[idx] = res.data
      if (currentRecord.value?.id === id) currentRecord.value = res.data
      return { ok: true }
    }
    // Roll back
    if (prev !== null && idx !== -1) records.value[idx] = { ...records.value[idx]!, ...prev }
    if (prev !== null && currentRecord.value?.id === id) currentRecord.value = { ...currentRecord.value, ...prev }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update stage.') }
  }

  async function deleteRecord(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/records/${id}`)
    if (res.ok || res.status === 204) {
      records.value = records.value.filter((l) => l.id !== id)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete record.') }
  }

  return {
    records, currentRecord, loading, loadingDetail, page, pageSize, hasMore,
    firmHeader,
    fetchRecords, fetchRecord, createRecord, updateRecord, patchStatus, patchStage, deleteRecord,
  }
})

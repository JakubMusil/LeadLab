import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface MilestoneOut {
  id: string
  realization_id: string
  name: string
  date: string
  is_completed: boolean
  description: string
  created_at: string
}

export interface RealizationOut {
  id: string
  firm_id: string
  title: string
  status: string
  lead_id: string | null
  lead_title: string | null
  customer_id: string | null
  customer_name: string | null
  assigned_to_id: string | null
  assigned_to_name: string | null
  start_date: string | null
  end_date: string | null
  milestones: MilestoneOut[]
  created_at: string
  updated_at: string
}

export interface RealizationIn {
  title: string
  status?: string
  lead_id?: string | null
  customer_id?: string | null
  assigned_to_id?: string | null
  start_date?: string | null
  end_date?: string | null
}

export const REALIZATION_STATUSES = [
  { value: 'planned', label: 'Naplánováno', color: 'bg-gray-100 text-gray-700' },
  { value: 'in_progress', label: 'Probíhá', color: 'bg-blue-100 text-blue-700' },
  { value: 'on_hold', label: 'Pozastaveno', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'done', label: 'Dokončeno', color: 'bg-green-100 text-green-700' },
  { value: 'cancelled', label: 'Zrušeno', color: 'bg-red-100 text-red-700' },
]

export function getRealizationStatusMeta(status: string) {
  return REALIZATION_STATUSES.find((s) => s.value === status) ?? {
    value: status,
    label: status,
    color: 'bg-gray-100 text-gray-700',
  }
}

export const useRealizationsStore = defineStore('realizations', () => {
  const realizations = ref<RealizationOut[]>([])
  const currentRealization = ref<RealizationOut | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)

  async function fetchRealizations(filters: Record<string, string> = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v)
      }
      const query = params.toString() ? `?${params.toString()}` : ''
      const res = await api.get<RealizationOut[]>(`/api/v1/crm/realizations${query}`)
      if (res.ok) {
        realizations.value = res.data
      } else {
        console.error('fetchRealizations:', extractErrorMessage(res.data, ''))
      }
    } catch (err) {
      console.error('fetchRealizations:', extractErrorMessage(err, ''))
    } finally {
      loading.value = false
    }
  }

  async function fetchRealization(id: string) {
    loadingDetail.value = true
    try {
      const res = await api.get<RealizationOut>(`/api/v1/crm/realizations/${id}`)
      if (res.ok) {
        currentRealization.value = res.data
        return currentRealization.value
      }
      console.error('fetchRealization:', extractErrorMessage(res.data, ''))
      return null
    } catch (err) {
      console.error('fetchRealization:', extractErrorMessage(err, ''))
      return null
    } finally {
      loadingDetail.value = false
    }
  }

  async function createRealization(data: RealizationIn): Promise<RealizationOut | null> {
    try {
      const res = await api.post<RealizationOut>('/api/v1/crm/realizations', data)
      if (res.ok) {
        realizations.value.unshift(res.data)
        return res.data
      }
      console.error('createRealization:', extractErrorMessage(res.data, ''))
      return null
    } catch (err) {
      console.error('createRealization:', extractErrorMessage(err, ''))
      return null
    }
  }

  async function updateRealization(id: string, patch: Partial<RealizationIn>): Promise<RealizationOut | null> {
    try {
      const res = await api.patch<RealizationOut>(`/api/v1/crm/realizations/${id}`, patch)
      if (res.ok) {
        const idx = realizations.value.findIndex((r) => r.id === id)
        if (idx !== -1) realizations.value[idx] = res.data
        if (currentRealization.value?.id === id) currentRealization.value = res.data
        return res.data
      }
      console.error('updateRealization:', extractErrorMessage(res.data, ''))
      return null
    } catch (err) {
      console.error('updateRealization:', extractErrorMessage(err, ''))
      return null
    }
  }

  async function deleteRealization(id: string): Promise<boolean> {
    try {
      const res = await api.delete(`/api/v1/crm/realizations/${id}`)
      if (res.ok || res.status === 204) {
        realizations.value = realizations.value.filter((r) => r.id !== id)
        if (currentRealization.value?.id === id) currentRealization.value = null
        return true
      }
      console.error('deleteRealization:', extractErrorMessage(res.data, ''))
      return false
    } catch (err) {
      console.error('deleteRealization:', extractErrorMessage(err, ''))
      return false
    }
  }

  return {
    realizations,
    currentRealization,
    loading,
    loadingDetail,
    fetchRealizations,
    fetchRealization,
    createRealization,
    updateRealization,
    deleteRealization,
  }
})

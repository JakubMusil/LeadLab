import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import { useFirmStore } from '@/stores/firm'

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
  description: string
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
  description?: string
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

  function firmHeader() {
    const firmStore = useFirmStore()
    return firmStore.activeFirm ? { 'X-Firm-ID': String(firmStore.activeFirm.id) } : {}
  }

  async function fetchRealizations(filters: Record<string, string> = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v)
      }
      const query = params.toString() ? `?${params.toString()}` : ''
      const res = await api.get(`/api/v1/crm/realizations${query}`, {
        headers: firmHeader(),
      })
      realizations.value = res.data as RealizationOut[]
    } catch (err) {
      console.error('fetchRealizations:', extractErrorMessage(err))
    } finally {
      loading.value = false
    }
  }

  async function fetchRealization(id: string) {
    loadingDetail.value = true
    try {
      const res = await api.get(`/api/v1/crm/realizations/${id}`, {
        headers: firmHeader(),
      })
      currentRealization.value = res.data as RealizationOut
      return currentRealization.value
    } catch (err) {
      console.error('fetchRealization:', extractErrorMessage(err))
      return null
    } finally {
      loadingDetail.value = false
    }
  }

  async function createRealization(data: RealizationIn): Promise<RealizationOut | null> {
    try {
      const res = await api.post('/api/v1/crm/realizations', data, {
        headers: firmHeader(),
      })
      const created = res.data as RealizationOut
      realizations.value.unshift(created)
      return created
    } catch (err) {
      console.error('createRealization:', extractErrorMessage(err))
      return null
    }
  }

  async function updateRealization(id: string, patch: Partial<RealizationIn>): Promise<RealizationOut | null> {
    try {
      const res = await api.patch(`/api/v1/crm/realizations/${id}`, patch, {
        headers: firmHeader(),
      })
      const updated = res.data as RealizationOut
      const idx = realizations.value.findIndex((r) => r.id === id)
      if (idx !== -1) realizations.value[idx] = updated
      if (currentRealization.value?.id === id) currentRealization.value = updated
      return updated
    } catch (err) {
      console.error('updateRealization:', extractErrorMessage(err))
      return null
    }
  }

  async function deleteRealization(id: string): Promise<boolean> {
    try {
      await api.delete(`/api/v1/crm/realizations/${id}`, {
        headers: firmHeader(),
      })
      realizations.value = realizations.value.filter((r) => r.id !== id)
      if (currentRealization.value?.id === id) currentRealization.value = null
      return true
    } catch (err) {
      console.error('deleteRealization:', extractErrorMessage(err))
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

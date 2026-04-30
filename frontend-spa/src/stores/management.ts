import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface ManagementOut {
  id: string
  firm_id: string
  title: string
  notes: string
  type: string
  status: string
  realization_id: string | null
  realization_title: string | null
  customer_id: string | null
  customer_name: string | null
  assigned_to_id: string | null
  assigned_to_name: string | null
  expires_at: string | null
  sla_color: 'green' | 'yellow' | 'red' | null
  created_at: string
  updated_at: string
}

export interface ManagementIn {
  title: string
  notes?: string
  type?: string
  status?: string
  realization_id?: string | null
  customer_id?: string | null
  assigned_to_id?: string | null
  expires_at?: string | null
}

export const MANAGEMENT_STATUSES = [
  { value: 'open', label: 'Otevřeno', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  { value: 'in_progress', label: 'Řeší se', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' },
  { value: 'waiting', label: 'Čeká na zákazníka', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' },
  { value: 'closed', label: 'Uzavřeno', color: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
]

export const MANAGEMENT_TYPES = [
  { value: 'sla', label: 'SLA' },
  { value: 'warranty', label: 'Záruka' },
  { value: 'retention', label: 'Retence' },
  { value: 'care', label: 'Péče' },
]

export function getManagementStatusMeta(status: string) {
  return MANAGEMENT_STATUSES.find((s) => s.value === status) ?? {
    value: status,
    label: status,
    color: 'bg-gray-100 text-gray-700',
  }
}

export function getManagementTypeMeta(type: string) {
  return MANAGEMENT_TYPES.find((t) => t.value === type) ?? { value: type, label: type }
}

export const useManagementStore = defineStore('management', () => {
  const records = ref<ManagementOut[]>([])
  const currentRecord = ref<ManagementOut | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)

  async function fetchRecords(filters: Record<string, string> = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v)
      }
      const query = params.toString() ? `?${params.toString()}` : ''
      const res = await api.get<ManagementOut[]>(`/api/v1/crm/management${query}`)
      if (res.ok) {
        records.value = res.data
      } else {
        console.error('fetchManagement:', extractErrorMessage(res.data, ''))
      }
    } catch (err) {
      console.error('fetchManagement:', extractErrorMessage(err, ''))
    } finally {
      loading.value = false
    }
  }

  async function fetchRecord(id: string) {
    loadingDetail.value = true
    try {
      const res = await api.get<ManagementOut>(`/api/v1/crm/management/${id}`)
      if (res.ok) {
        currentRecord.value = res.data
        return currentRecord.value
      }
      console.error('fetchManagementRecord:', extractErrorMessage(res.data, ''))
      return null
    } catch (err) {
      console.error('fetchManagementRecord:', extractErrorMessage(err, ''))
      return null
    } finally {
      loadingDetail.value = false
    }
  }

  async function createRecord(data: ManagementIn): Promise<ManagementOut | null> {
    try {
      const res = await api.post<ManagementOut>('/api/v1/crm/management', data)
      if (res.ok) {
        records.value.unshift(res.data)
        return res.data
      }
      console.error('createManagement:', extractErrorMessage(res.data, ''))
      return null
    } catch (err) {
      console.error('createManagement:', extractErrorMessage(err, ''))
      return null
    }
  }

  async function updateRecord(id: string, patch: Partial<ManagementIn>): Promise<ManagementOut | null> {
    try {
      const res = await api.patch<ManagementOut>(`/api/v1/crm/management/${id}`, patch)
      if (res.ok) {
        const idx = records.value.findIndex((r) => r.id === id)
        if (idx !== -1) records.value[idx] = res.data
        if (currentRecord.value?.id === id) currentRecord.value = res.data
        return res.data
      }
      console.error('updateManagement:', extractErrorMessage(res.data, ''))
      return null
    } catch (err) {
      console.error('updateManagement:', extractErrorMessage(err, ''))
      return null
    }
  }

  async function deleteRecord(id: string): Promise<boolean> {
    try {
      const res = await api.delete(`/api/v1/crm/management/${id}`)
      if (res.ok || res.status === 204) {
        records.value = records.value.filter((r) => r.id !== id)
        if (currentRecord.value?.id === id) currentRecord.value = null
        return true
      }
      console.error('deleteManagement:', extractErrorMessage(res.data, ''))
      return false
    } catch (err) {
      console.error('deleteManagement:', extractErrorMessage(err, ''))
      return false
    }
  }

  return {
    records,
    currentRecord,
    loading,
    loadingDetail,
    fetchRecords,
    fetchRecord,
    createRecord,
    updateRecord,
    deleteRecord,
  }
})

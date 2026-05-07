import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface CustomerOut {
  id: string
  firm_id: string
  type: 'person' | 'company'
  first_name: string
  last_name: string
  email: string
  phone: string
  company_name: string
  company_id: string | null
  ico: string
  dic: string
  address_street: string
  address_city: string
  address_zip: string
  address_country: string
  website: string
  tags: string[]
  metadata: Record<string, string>
  created_at: string
  updated_at: string
}

export interface CustomerIn {
  type?: 'person' | 'company'
  first_name: string
  last_name?: string
  email?: string
  phone?: string
  company_name?: string
  company_id?: string | null
  ico?: string
  dic?: string
  address_street?: string
  address_city?: string
  address_zip?: string
  address_country?: string
  website?: string
  tags?: string[]
  metadata?: Record<string, string>
}

export const useCustomersStore = defineStore('customers', () => {
  const customers = ref<CustomerOut[]>([])
  const currentCustomer = ref<CustomerOut | null>(null)
  const loading = ref(false)
  const loadingDetail = ref(false)
  const search = ref('')
  const page = ref(1)
  const pageSize = ref(20)
  const hasMore = ref(true)

  async function fetchCustomers(opts: { search?: string; page?: number; append?: boolean; type?: string; tag?: string } = {}) {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (opts.search !== undefined) params.set('search', opts.search)
      else if (search.value) params.set('search', search.value)
      if (opts.type) params.set('type', opts.type)
      if (opts.tag) params.set('tag', opts.tag)
      const p = opts.page ?? 1
      params.set('page', String(p))
      params.set('page_size', String(pageSize.value))
      const res = await api.get<CustomerOut[]>(`/api/v1/crm/directory?${params}`)
      if (res.ok) {
        if (opts.append) {
          customers.value = [...customers.value, ...res.data]
        } else {
          customers.value = res.data
        }
        page.value = p
        hasMore.value = res.data.length === pageSize.value
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Failed to load customers.') }
    } finally {
      loading.value = false
    }
  }

  async function fetchCustomer(id: string): Promise<{ ok: boolean; error?: string }> {
    loadingDetail.value = true
    try {
      const res = await api.get<CustomerOut>(`/api/v1/crm/directory/${id}`)
      if (res.ok) {
        currentCustomer.value = res.data
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Customer not found.') }
    } finally {
      loadingDetail.value = false
    }
  }

  async function fetchCompanyEmployees(companyId: string): Promise<{ ok: boolean; data?: CustomerOut[]; error?: string }> {
    const res = await api.get<CustomerOut[]>(`/api/v1/crm/directory/${companyId}/employees`)
    if (res.ok) return { ok: true, data: res.data }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to load employees.') }
  }

  async function createCustomer(payload: CustomerIn): Promise<{ ok: boolean; data?: CustomerOut; error?: string }> {
    const res = await api.post<CustomerOut>('/api/v1/crm/directory', payload)
    if (res.ok) {
      customers.value.unshift(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create customer.') }
  }

  async function updateCustomer(id: string, payload: CustomerIn): Promise<{ ok: boolean; data?: CustomerOut; error?: string }> {
    const res = await api.put<CustomerOut>(`/api/v1/crm/directory/${id}`, payload)
    if (res.ok) {
      const idx = customers.value.findIndex((c) => c.id === id)
      if (idx !== -1) customers.value[idx] = res.data
      if (currentCustomer.value?.id === id) currentCustomer.value = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update customer.') }
  }

  async function deleteCustomer(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/directory/${id}`)
    if (res.ok || res.status === 204) {
      customers.value = customers.value.filter((c) => c.id !== id)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete customer.') }
  }

  return {
    customers, currentCustomer, loading, loadingDetail, search, page, pageSize, hasMore,
    fetchCustomers, fetchCustomer, fetchCompanyEmployees, createCustomer, updateCustomer, deleteCustomer,
  }
})

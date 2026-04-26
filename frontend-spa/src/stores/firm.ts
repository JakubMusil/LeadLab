import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface FirmOut {
  id: number
  name: string
  slug: string
  subscription_tier: string
  subscription_active: boolean
  is_active: boolean
  logo_url: string | null
  primary_color: string
}

const FIRM_ID_KEY = 'firmId'

export const useFirmStore = defineStore('firm', () => {
  const firms = ref<FirmOut[]>([])
  const activeFirm = ref<FirmOut | null>(null)
  const loading = ref(false)

  async function fetchFirms() {
    loading.value = true
    try {
      const res = await api.get<FirmOut[]>('/api/v1/firms/')
      if (res.ok) {
        firms.value = res.data
        const persistedId = localStorage.getItem(FIRM_ID_KEY)
        const first = firms.value[0] ?? null
        if (persistedId) {
          const found = firms.value.find((f) => String(f.id) === persistedId)
          if (found) {
            activeFirm.value = found
          } else if (first) {
            activeFirm.value = first
            localStorage.setItem(FIRM_ID_KEY, String(first.id))
          }
        } else if (first) {
          activeFirm.value = first
          localStorage.setItem(FIRM_ID_KEY, String(first.id))
        }
      }
    } finally {
      loading.value = false
    }
  }

  function setActiveFirm(firmId: string) {
    const found = firms.value.find((f) => String(f.id) === firmId)
    if (found) {
      activeFirm.value = found
      localStorage.setItem(FIRM_ID_KEY, firmId)
    }
  }

  async function createFirm(name: string): Promise<{ ok: boolean; error?: string }> {
    loading.value = true
    try {
      const res = await api.post<FirmOut>('/api/v1/firms/', { name })
      if (res.ok) {
        firms.value.push(res.data)
        activeFirm.value = res.data
        localStorage.setItem(FIRM_ID_KEY, String(res.data.id))
        return { ok: true }
      }
      return { ok: false, error: extractErrorMessage(res.data, 'Failed to create workspace.') }
    } finally {
      loading.value = false
    }
  }

  const isPro = computed(() =>
    activeFirm.value?.subscription_tier === 'pro' &&
    activeFirm.value?.subscription_active === true
  )

  return { firms, activeFirm, loading, fetchFirms, setActiveFirm, createFirm, isPro }
})

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { useFirmStore } from '@/stores/firm'

export interface SavedView {
  id: string
  name: string
  entity: 'opportunities' | 'directory'
  filters: Record<string, string>
  sort_by: string
  sort_dir: string
  created_at: string
}

export interface SavedViewIn {
  name: string
  entity: 'opportunities' | 'directory'
  filters?: Record<string, string>
  sort_by?: string
  sort_dir?: string
}

export const useSavedViewsStore = defineStore('savedViews', () => {
  const views = ref<SavedView[]>([])
  const loading = ref(false)

  async function fetchViews() {
    const firmStore = useFirmStore()
    if (!firmStore.activeFirm) return
    loading.value = true
    try {
      const res = await api.get<SavedView[]>('/api/v1/crm/saved-views')
      if (res.ok) views.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createView(payload: SavedViewIn): Promise<SavedView | null> {
    const res = await api.post<SavedView>('/api/v1/crm/saved-views', payload)
    if (res.ok) {
      views.value.push(res.data)
      return res.data
    }
    return null
  }

  async function deleteView(id: string): Promise<boolean> {
    const res = await api.delete<null>(`/api/v1/crm/saved-views/${id}`)
    if (res.ok) {
      views.value = views.value.filter((v) => v.id !== id)
      return true
    }
    return false
  }

  function viewsForEntity(entity: 'opportunities' | 'directory') {
    return views.value.filter((v) => v.entity === entity)
  }

  return { views, loading, fetchViews, createView, deleteView, viewsForEntity }
})

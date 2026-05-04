import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StageOut {
  id: string
  category_id: string
  name: string
  label: string
  color: string
  order: number
  is_terminal: boolean
  is_won: boolean
}

export interface CategoryFieldOut {
  id: string
  category_id: string
  field_key: string
  is_visible: boolean
  is_required: boolean
  order: number
}

export interface CategoryFieldIn {
  is_visible?: boolean
  is_required?: boolean
  order?: number
}

export interface CategoryOut {
  id: string
  firm_id: string
  name: string
  slug: string
  icon: string
  color: string
  order: number
  is_active: boolean
  stages: StageOut[]
  fields: CategoryFieldOut[]
}

export interface CategoryIn {
  name: string
  icon?: string
  color?: string
  order?: number
  is_active?: boolean
}

export interface StageIn {
  name: string
  label?: string
  color?: string
  order?: number
  is_terminal?: boolean
  is_won?: boolean
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Return 0-100 progress value for a record's current stage within its category. */
export function getStageProgress(stages: StageOut[], currentStageId: string | null): number {
  if (!currentStageId || stages.length === 0) return 0
  const nonTerminal = stages.filter((s) => !s.is_terminal)
  if (nonTerminal.length === 0) return 0
  const idx = nonTerminal.findIndex((s) => s.id === currentStageId)
  if (idx === -1) return 0
  return Math.round(((idx + 1) / nonTerminal.length) * 100)
}

/**
 * Return a Tailwind colour class for SLA / deadline colouring.
 * expiresAt is an ISO date string or null.
 */
export function getSlaColor(expiresAt: string | null): string {
  if (!expiresAt) return 'text-gray-400'
  const diff = new Date(expiresAt).getTime() - Date.now()
  const days = diff / (1000 * 60 * 60 * 24)
  if (days < 0) return 'text-red-600'
  if (days < 3) return 'text-orange-500'
  if (days < 7) return 'text-yellow-500'
  return 'text-green-600'
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const usePipelineStore = defineStore('pipeline', () => {
  const categories = ref<CategoryOut[]>([])
  const loading = ref(false)
  const loadingStages = ref(false)

  // Derived: flat list of all stages across all categories
  const allStages = computed<StageOut[]>(() =>
    categories.value.flatMap((c) => c.stages),
  )

  function getCategoryById(id: string): CategoryOut | undefined {
    return categories.value.find((c) => c.id === id)
  }

  function getStagesForCategory(categoryId: string): StageOut[] {
    return categories.value.find((c) => c.id === categoryId)?.stages ?? []
  }

  function getFieldsForCategory(categoryId: string): CategoryFieldOut[] {
    return categories.value.find((c) => c.id === categoryId)?.fields ?? []
  }

  // ---------------------------------------------------------------------------
  // Fetch
  // ---------------------------------------------------------------------------

  async function fetchCategories(): Promise<{ ok: boolean; error?: string }> {
    loading.value = true
    try {
      const res = await api.get<CategoryOut[]>('/api/v1/crm/categories')
      if (!res.ok) {
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to load categories.') }
      }
      // For each category, load stages and fields
      const withDetails = await Promise.all(
        res.data.map(async (cat) => {
          const [stagesRes, fieldsRes] = await Promise.all([
            api.get<StageOut[]>(`/api/v1/crm/categories/${cat.id}/stages`),
            api.get<CategoryFieldOut[]>(`/api/v1/crm/categories/${cat.id}/fields`),
          ])
          return {
            ...cat,
            stages: stagesRes.ok ? stagesRes.data : [],
            fields: fieldsRes.ok ? fieldsRes.data : [],
          }
        }),
      )
      categories.value = withDetails
      return { ok: true }
    } finally {
      loading.value = false
    }
  }

  // ---------------------------------------------------------------------------
  // Category CRUD
  // ---------------------------------------------------------------------------

  async function createCategory(payload: CategoryIn): Promise<{ ok: boolean; data?: CategoryOut; error?: string }> {
    const res = await api.post<CategoryOut>('/api/v1/crm/categories', payload)
    if (res.ok) {
      categories.value.push({ ...res.data, stages: [], fields: [] })
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create category.') }
  }

  async function updateCategory(id: string, payload: Partial<CategoryIn>): Promise<{ ok: boolean; error?: string }> {
    const res = await api.patch<CategoryOut>(`/api/v1/crm/categories/${id}`, payload)
    if (res.ok) {
      const idx = categories.value.findIndex((c) => c.id === id)
      if (idx !== -1) {
        categories.value[idx] = { ...categories.value[idx]!, ...res.data }
      }
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update category.') }
  }

  async function deleteCategory(id: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/categories/${id}`)
    if (res.ok || res.status === 204) {
      categories.value = categories.value.filter((c) => c.id !== id)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Cannot delete category.') }
  }

  // ---------------------------------------------------------------------------
  // Stage CRUD
  // ---------------------------------------------------------------------------

  async function createStage(categoryId: string, payload: StageIn): Promise<{ ok: boolean; data?: StageOut; error?: string }> {
    const res = await api.post<StageOut>(`/api/v1/crm/categories/${categoryId}/stages`, payload)
    if (res.ok) {
      const cat = categories.value.find((c) => c.id === categoryId)
      if (cat) cat.stages.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create stage.') }
  }

  async function updateStage(categoryId: string, stageId: string, payload: Partial<StageIn>): Promise<{ ok: boolean; error?: string }> {
    const res = await api.patch<StageOut>(`/api/v1/crm/categories/${categoryId}/stages/${stageId}`, payload)
    if (res.ok) {
      const cat = categories.value.find((c) => c.id === categoryId)
      if (cat) {
        const idx = cat.stages.findIndex((s) => s.id === stageId)
        if (idx !== -1) cat.stages[idx] = res.data
      }
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update stage.') }
  }

  async function deleteStage(categoryId: string, stageId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/categories/${categoryId}/stages/${stageId}`)
    if (res.ok || res.status === 204) {
      const cat = categories.value.find((c) => c.id === categoryId)
      if (cat) cat.stages = cat.stages.filter((s) => s.id !== stageId)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Cannot delete stage.') }
  }

  // ---------------------------------------------------------------------------
  // CategoryField CRUD
  // ---------------------------------------------------------------------------

  async function createField(
    categoryId: string,
    fieldKey: string,
    payload: CategoryFieldIn,
  ): Promise<{ ok: boolean; data?: CategoryFieldOut; error?: string }> {
    const res = await api.post<CategoryFieldOut>(
      `/api/v1/crm/categories/${categoryId}/fields/${fieldKey}`,
      payload,
    )
    if (res.ok) {
      const cat = categories.value.find((c) => c.id === categoryId)
      if (cat) {
        const existing = cat.fields.findIndex((f) => f.field_key === fieldKey)
        if (existing !== -1) {
          cat.fields[existing] = res.data
        } else {
          cat.fields.push(res.data)
        }
      }
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create field.') }
  }

  async function updateField(
    categoryId: string,
    fieldKey: string,
    payload: CategoryFieldIn,
  ): Promise<{ ok: boolean; error?: string }> {
    const res = await api.patch<CategoryFieldOut>(
      `/api/v1/crm/categories/${categoryId}/fields/${fieldKey}`,
      payload,
    )
    if (res.ok) {
      const cat = categories.value.find((c) => c.id === categoryId)
      if (cat) {
        const idx = cat.fields.findIndex((f) => f.field_key === fieldKey)
        if (idx !== -1) cat.fields[idx] = res.data
      }
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update field.') }
  }

  async function deleteField(
    categoryId: string,
    fieldKey: string,
  ): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete(`/api/v1/crm/categories/${categoryId}/fields/${fieldKey}`)
    if (res.ok || res.status === 204) {
      const cat = categories.value.find((c) => c.id === categoryId)
      if (cat) cat.fields = cat.fields.filter((f) => f.field_key !== fieldKey)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Cannot delete field.') }
  }

  // ---------------------------------------------------------------------------
  // React to WS category.updated event
  // ---------------------------------------------------------------------------

  function handleCategoryUpdated() {
    fetchCategories()
  }

  return {
    categories,
    loading,
    loadingStages,
    allStages,
    getCategoryById,
    getStagesForCategory,
    getFieldsForCategory,
    getStageProgress,
    getSlaColor,
    fetchCategories,
    createCategory,
    updateCategory,
    deleteCategory,
    createStage,
    updateStage,
    deleteStage,
    createField,
    updateField,
    deleteField,
    handleCategoryUpdated,
  }
})

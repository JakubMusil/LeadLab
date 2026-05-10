import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface ConditionRuleOut {
  id: string
  firm_id: string
  name: string
  description: string
  is_active: boolean
  scope_type: string
  category_id: string | null
  stage_id: string | null
  source_stage_id: string | null
  target_stage_id: string | null
  trigger_type: string
  condition_tree: Record<string, unknown>
  effect: string
  severity: string
  effect_config: Record<string, unknown>
  activity_type: string
  priority: number
  created_by_id: string | null
  created_at: string
  updated_at: string
}

export interface ConditionRuleFilters {
  categoryId?: string
  stageId?: string
  triggerType?: string
  isActive?: boolean
}

export interface ConditionRulePatchIn {
  name?: string
  description?: string
  is_active?: boolean
  scope_type?: string
  category_id?: string | null
  stage_id?: string | null
  source_stage_id?: string | null
  target_stage_id?: string | null
  trigger_type?: string
  condition_tree?: Record<string, unknown>
  effect?: string
  severity?: string
  effect_config?: Record<string, unknown>
  activity_type?: string
  priority?: number
}

export const useConditionRulesStore = defineStore('conditionRules', () => {
  const rules = ref<ConditionRuleOut[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchRules(filters: ConditionRuleFilters = {}): Promise<{ ok: boolean; error?: string }> {
    loading.value = true
    error.value = null
    try {
      const params = new URLSearchParams()
      if (filters.categoryId) params.set('category_id', filters.categoryId)
      if (filters.stageId) params.set('stage_id', filters.stageId)
      if (filters.triggerType) params.set('trigger_type', filters.triggerType)
      if (filters.isActive !== undefined) params.set('is_active', String(filters.isActive))
      const query = params.toString()
      const res = await api.get<ConditionRuleOut[]>(`/api/v1/crm/condition-rules${query ? `?${query}` : ''}`)
      if (res.ok) {
        rules.value = res.data
        return { ok: true }
      }
      const message = extractErrorMessage(res.data, 'Failed to load condition rules.')
      rules.value = []
      error.value = message
      return { ok: false, error: message }
    } finally {
      loading.value = false
    }
  }

  async function updateRule(ruleId: string, payload: ConditionRulePatchIn): Promise<{ ok: boolean; error?: string }> {
    const res = await api.patch<ConditionRuleOut>(`/api/v1/crm/condition-rules/${ruleId}`, payload)
    if (res.ok) {
      const idx = rules.value.findIndex((rule) => rule.id === ruleId)
      if (idx !== -1) rules.value[idx] = res.data
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update condition rule.') }
  }

  return {
    rules,
    loading,
    error,
    fetchRules,
    updateRule,
  }
})

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

export interface ConditionRuleIn {
  name: string
  description?: string
  is_active?: boolean
  scope_type?: string
  category_id?: string | null
  stage_id?: string | null
  source_stage_id?: string | null
  target_stage_id?: string | null
  trigger_type: string
  condition_tree?: Record<string, unknown>
  effect?: string
  severity?: string
  effect_config?: Record<string, unknown>
  activity_type?: string
  priority?: number
}

export interface ConditionRuleTestEvaluationIn {
  record_id: string
  rule_id?: string
  condition_tree?: Record<string, unknown>
  effect?: string
  severity?: string
  effect_config?: Record<string, unknown>
  activity_type?: string
}

export interface ConditionRuleTestEvaluationOut {
  matched: boolean
  outputs: Record<string, unknown>[]
  blocking: Record<string, unknown>[]
  warnings: Record<string, unknown>[]
}

function deepCloneRecord(value?: Record<string, unknown> | null): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(value) as Record<string, unknown>
    } catch {
      return {}
    }
  }
  try {
    return JSON.parse(JSON.stringify(value)) as Record<string, unknown>
  } catch {
    return {}
  }
}

export function buildCreateConditionRulePayloadFromExisting(
  rule: ConditionRuleOut,
  overrides: Partial<ConditionRuleIn> = {},
): ConditionRuleIn {
  return {
    name: rule.name,
    description: rule.description,
    is_active: rule.is_active,
    scope_type: rule.scope_type,
    category_id: rule.category_id,
    stage_id: rule.stage_id,
    source_stage_id: rule.source_stage_id,
    target_stage_id: rule.target_stage_id,
    trigger_type: rule.trigger_type,
    condition_tree: deepCloneRecord(rule.condition_tree),
    effect: rule.effect,
    severity: rule.severity,
    effect_config: deepCloneRecord(rule.effect_config),
    activity_type: rule.activity_type,
    priority: rule.priority,
    ...overrides,
  }
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

  async function createRule(payload: ConditionRuleIn): Promise<{ ok: boolean; data?: ConditionRuleOut; error?: string }> {
    const res = await api.post<ConditionRuleOut>('/api/v1/crm/condition-rules', payload)
    if (res.ok) {
      rules.value.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create condition rule.') }
  }

  async function createRuleFromExisting(
    rule: ConditionRuleOut,
    overrides: Partial<ConditionRuleIn> = {},
  ): Promise<{ ok: boolean; data?: ConditionRuleOut; error?: string }> {
    return createRule(buildCreateConditionRulePayloadFromExisting(rule, overrides))
  }

  async function deactivateRule(ruleId: string): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete<null>(`/api/v1/crm/condition-rules/${ruleId}`)
    if (res.ok || res.status === 204) {
      const idx = rules.value.findIndex((rule) => rule.id === ruleId)
      if (idx !== -1) {
        const existingRule = rules.value[idx]
        if (existingRule) {
          rules.value[idx] = { ...existingRule, is_active: false }
        }
      }
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to deactivate condition rule.') }
  }

  async function testEvaluation(
    payload: ConditionRuleTestEvaluationIn,
  ): Promise<{ ok: boolean; data?: ConditionRuleTestEvaluationOut; error?: string }> {
    const res = await api.post<ConditionRuleTestEvaluationOut>('/api/v1/crm/condition-rules/test-evaluation/run', payload)
    if (res.ok) {
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to test condition rule evaluation.') }
  }

  return {
    rules,
    loading,
    error,
    fetchRules,
    createRule,
    createRuleFromExisting,
    updateRule,
    deactivateRule,
    testEvaluation,
  }
})

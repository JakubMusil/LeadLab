import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface StageScenarioOut {
  id: string
  firm_id: string
  category_id: string
  stage_id: string
  name: string
  description: string
  activation_condition: Record<string, unknown>
  completion_condition: Record<string, unknown>
  recommended_next_stage_id: string | null
  priority: number
  is_active: boolean
  created_by_id: string | null
  created_at: string
  updated_at: string
}

export interface StageScenarioIn {
  name: string
  description?: string
  activation_condition?: Record<string, unknown>
  completion_condition?: Record<string, unknown>
  recommended_next_stage_id?: string | null
  priority?: number
  is_active?: boolean
}

export interface StageScenarioPatchIn {
  name?: string
  description?: string
  activation_condition?: Record<string, unknown>
  completion_condition?: Record<string, unknown>
  recommended_next_stage_id?: string | null
  priority?: number
  is_active?: boolean
}

export interface StageRequirementOut {
  id: string
  firm_id: string
  scenario_id: string
  name: string
  description: string
  requirement_type: string
  condition: Record<string, unknown>
  blocking: boolean
  visible_to_user: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface StageRequirementIn {
  name: string
  description?: string
  requirement_type?: string
  condition?: Record<string, unknown>
  blocking?: boolean
  visible_to_user?: boolean
  sort_order?: number
}

export interface StageRequirementPatchIn {
  name?: string
  description?: string
  requirement_type?: string
  condition?: Record<string, unknown>
  blocking?: boolean
  visible_to_user?: boolean
  sort_order?: number
}

export interface ActiveStageRequirementsOut {
  record_id: string
  active_stage_scenario_id: string | null
  active_stage_scenario_name: string | null
  recommended_next_stage_id: string | null
  recommended_next_stage_name: string | null
  active_stage_requirements: Array<Record<string, unknown>>
}

export const useStageScenariosStore = defineStore('stageScenarios', () => {
  const scenarios = ref<StageScenarioOut[]>([])
  const requirements = ref<StageRequirementOut[]>([])
  const loadingScenarios = ref(false)
  const loadingRequirements = ref(false)
  const error = ref<string | null>(null)

  async function fetchScenarios(
    categoryId: string,
    stageId: string,
  ): Promise<{ ok: boolean; error?: string }> {
    loadingScenarios.value = true
    error.value = null
    try {
      const res = await api.get<StageScenarioOut[]>(
        `/api/v1/crm/categories/${categoryId}/stages/${stageId}/scenarios`,
      )
      if (res.ok) {
        scenarios.value = res.data
        return { ok: true }
      }
      const message = extractErrorMessage(res.data, 'Failed to load stage scenarios.')
      scenarios.value = []
      error.value = message
      return { ok: false, error: message }
    } finally {
      loadingScenarios.value = false
    }
  }

  async function createScenario(
    categoryId: string,
    stageId: string,
    payload: StageScenarioIn,
  ): Promise<{ ok: boolean; data?: StageScenarioOut; error?: string }> {
    const res = await api.post<StageScenarioOut>(
      `/api/v1/crm/categories/${categoryId}/stages/${stageId}/scenarios`,
      payload,
    )
    if (res.ok) {
      scenarios.value.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create stage scenario.') }
  }

  async function updateScenario(
    categoryId: string,
    stageId: string,
    scenarioId: string,
    payload: StageScenarioPatchIn,
  ): Promise<{ ok: boolean; data?: StageScenarioOut; error?: string }> {
    const res = await api.patch<StageScenarioOut>(
      `/api/v1/crm/categories/${categoryId}/stages/${stageId}/scenarios/${scenarioId}`,
      payload,
    )
    if (res.ok) {
      const idx = scenarios.value.findIndex((scenario) => scenario.id === scenarioId)
      if (idx !== -1) scenarios.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update stage scenario.') }
  }

  async function deleteScenario(
    categoryId: string,
    stageId: string,
    scenarioId: string,
  ): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete<null>(
      `/api/v1/crm/categories/${categoryId}/stages/${stageId}/scenarios/${scenarioId}`,
    )
    if (res.ok || res.status === 204) {
      scenarios.value = scenarios.value.filter((scenario) => scenario.id !== scenarioId)
      if (requirements.value.some((requirement) => requirement.scenario_id === scenarioId)) {
        requirements.value = []
      }
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete stage scenario.') }
  }

  async function fetchRequirements(scenarioId: string): Promise<{ ok: boolean; error?: string }> {
    loadingRequirements.value = true
    error.value = null
    try {
      const res = await api.get<StageRequirementOut[]>(`/api/v1/crm/scenarios/${scenarioId}/requirements`)
      if (res.ok) {
        requirements.value = res.data
        return { ok: true }
      }
      const message = extractErrorMessage(res.data, 'Failed to load stage requirements.')
      requirements.value = []
      error.value = message
      return { ok: false, error: message }
    } finally {
      loadingRequirements.value = false
    }
  }

  async function createRequirement(
    scenarioId: string,
    payload: StageRequirementIn,
  ): Promise<{ ok: boolean; data?: StageRequirementOut; error?: string }> {
    const res = await api.post<StageRequirementOut>(`/api/v1/crm/scenarios/${scenarioId}/requirements`, payload)
    if (res.ok) {
      requirements.value.push(res.data)
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to create stage requirement.') }
  }

  async function updateRequirement(
    scenarioId: string,
    requirementId: string,
    payload: StageRequirementPatchIn,
  ): Promise<{ ok: boolean; data?: StageRequirementOut; error?: string }> {
    const res = await api.patch<StageRequirementOut>(
      `/api/v1/crm/scenarios/${scenarioId}/requirements/${requirementId}`,
      payload,
    )
    if (res.ok) {
      const idx = requirements.value.findIndex((requirement) => requirement.id === requirementId)
      if (idx !== -1) requirements.value[idx] = res.data
      return { ok: true, data: res.data }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to update stage requirement.') }
  }

  async function deleteRequirement(
    scenarioId: string,
    requirementId: string,
  ): Promise<{ ok: boolean; error?: string }> {
    const res = await api.delete<null>(`/api/v1/crm/scenarios/${scenarioId}/requirements/${requirementId}`)
    if (res.ok || res.status === 204) {
      requirements.value = requirements.value.filter((requirement) => requirement.id !== requirementId)
      return { ok: true }
    }
    return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete stage requirement.') }
  }

  async function previewForRecord(
    recordId: string,
  ): Promise<{ ok: boolean; data?: ActiveStageRequirementsOut; error?: string }> {
    const res = await api.get<ActiveStageRequirementsOut>(
      `/api/v1/crm/records/${recordId}/active-stage-requirements`,
    )
    if (res.ok) return { ok: true, data: res.data }
    return {
      ok: false,
      error: extractErrorMessage(res.data, 'Failed to load stage scenario preview for record.'),
    }
  }

  function clearRequirements() {
    requirements.value = []
  }

  return {
    scenarios,
    requirements,
    loadingScenarios,
    loadingRequirements,
    error,
    fetchScenarios,
    createScenario,
    updateScenario,
    deleteScenario,
    fetchRequirements,
    createRequirement,
    updateRequirement,
    deleteRequirement,
    previewForRecord,
    clearRequirements,
  }
})

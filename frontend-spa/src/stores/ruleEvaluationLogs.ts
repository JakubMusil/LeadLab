import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'

export interface RuleEvaluationLogOut {
  id: string
  firm_id: string
  record_id: string | null
  rule_id: string | null
  scenario_id: string | null
  requirement_id: string | null
  trigger_type: string
  result: string
  messages: unknown[]
  recommendations: unknown[]
  error_message: string
  input_context: Record<string, unknown>
  evaluated_by_id: string | null
  evaluated_at: string
}

export interface RuleEvaluationLogsFilters {
  triggerType?: string
  result?: string
  recordId?: string
  ruleId?: string
  page?: number
  pageSize?: number
}

export const useRuleEvaluationLogsStore = defineStore('ruleEvaluationLogs', () => {
  const logs = ref<RuleEvaluationLogOut[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const page = ref(1)
  const pageSize = ref(50)
  const hasMore = ref(false)

  async function fetchLogs(filters: RuleEvaluationLogsFilters = {}): Promise<{ ok: boolean; error?: string }> {
    loading.value = true
    error.value = null
    try {
      const p = Math.max(1, filters.page ?? 1)
      const ps = Math.max(1, Math.min(200, filters.pageSize ?? pageSize.value))
      const params = new URLSearchParams()
      params.set('page', String(p))
      params.set('page_size', String(ps))
      if (filters.triggerType) params.set('trigger_type', filters.triggerType)
      if (filters.result) params.set('result', filters.result)
      if (filters.recordId) params.set('record_id', filters.recordId)
      if (filters.ruleId) params.set('rule_id', filters.ruleId)

      const res = await api.get<RuleEvaluationLogOut[]>(`/api/v1/crm/rule-evaluation-logs?${params}`)
      if (res.ok) {
        logs.value = res.data
        page.value = p
        pageSize.value = ps
        hasMore.value = res.data.length === ps
        return { ok: true }
      }
      const message = extractErrorMessage(res.data, 'Failed to load rule evaluation logs.')
      logs.value = []
      hasMore.value = false
      error.value = message
      return { ok: false, error: message }
    } finally {
      loading.value = false
    }
  }

  function clear() {
    logs.value = []
    page.value = 1
    hasMore.value = false
    error.value = null
  }

  return {
    logs,
    loading,
    error,
    page,
    pageSize,
    hasMore,
    fetchLogs,
    clear,
  }
})

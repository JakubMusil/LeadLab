import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import { useFirmStore } from '@/stores/firm'

export interface RecordScoringRule {
  id: string
  field: string
  operand: unknown
  score_delta: number
}

export interface RecordScoringRuleIn {
  field: string
  operand: unknown
  score_delta: number
}

export const SCORING_FIELDS = [
  { value: 'status', label: 'Status equals' },
  { value: 'source', label: 'Source equals' },
  { value: 'value_gte', label: 'Value ≥' },
  { value: 'last_activity_days_lte', label: 'Last activity within N days' },
]

export const useRecordScoringStore = defineStore('leadScoring', () => {
  const rules = ref<RecordScoringRule[]>([])
  const loading = ref(false)

  async function fetchRules() {
    const firmStore = useFirmStore()
    if (!firmStore.activeFirm) return
    loading.value = true
    try {
      const res = await api.get<RecordScoringRule[]>('/api/v1/crm/record-scoring-rules')
      if (res.ok) rules.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function createRule(payload: RecordScoringRuleIn): Promise<RecordScoringRule | null> {
    const res = await api.post<RecordScoringRule>('/api/v1/crm/record-scoring-rules', payload)
    if (res.ok) {
      rules.value.push(res.data)
      return res.data
    }
    return null
  }

  async function deleteRule(id: string): Promise<boolean> {
    const res = await api.delete<null>(`/api/v1/crm/record-scoring-rules/${id}`)
    if (res.ok) {
      rules.value = rules.value.filter((r) => r.id !== id)
      return true
    }
    return false
  }

  return { rules, loading, fetchRules, createRule, deleteRule }
})

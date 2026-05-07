import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'

export interface MemberOut {
  id: string
  user_id: string
  user_email: string
  user_full_name: string
  role: string
  firm_id: string
  roles: string[]
  expires_at: string | null
}

export const useMembersStore = defineStore('members', () => {
  const members = ref<MemberOut[]>([])
  const loading = ref(false)
  const loadedFirmId = ref<string | null>(null)

  function memberById(id: string): MemberOut | undefined {
    return members.value.find((m) => m.id === id)
  }

  function displayNameById(id: string): string {
    const m = members.value.find((mm) => mm.id === id)
    if (!m) return id
    return m.user_full_name?.trim() || m.user_email
  }

  async function fetchMembers(firmId: string, force = false) {
    if (!firmId) return
    if (!force && loadedFirmId.value === firmId) return
    loading.value = true
    try {
      const res = await api.get<MemberOut[]>(`/api/v1/firms/${firmId}/members`)
      if (res.ok && res.data) {
        members.value = res.data
        loadedFirmId.value = firmId
      }
    } finally {
      loading.value = false
    }
  }

  async function searchMembers(firmId: string, q: string): Promise<MemberOut[]> {
    if (!q.trim()) return members.value
    const res = await api.get<MemberOut[]>(`/api/v1/firms/${firmId}/members?q=${encodeURIComponent(q)}`)
    if (res.ok && res.data) return res.data
    return []
  }

  function $reset() {
    members.value = []
    loadedFirmId.value = null
  }

  return { members, loading, memberById, displayNameById, fetchMembers, searchMembers, $reset }
})

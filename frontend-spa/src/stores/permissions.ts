import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

export interface PermissionCatalogueItem {
  code: string
  group: string
  description: string
}

export interface RoleOut {
  id: string
  code: string
  name: string
  is_system: boolean
  description: string
  permissions: string[]
  member_count: number
}

export interface TeamMemberOut {
  membership_id: string
  user_id: string
  user_email: string
  user_full_name: string
}

export interface TeamOut {
  id: string
  name: string
  slug: string
  color: string
  member_count: number
  members: TeamMemberOut[]
}

export interface MyPermissionsOut {
  permissions: string[]
  scope: string
  role: string
  roles: string[]
  can_manage_roles: boolean
  can_manage_teams: boolean
}

export interface RolePreset {
  code: string
  name: string
  description: string
  permissions: string[]
}

export const usePermissionsStore = defineStore('permissions', () => {
  const catalogue = ref<PermissionCatalogueItem[]>([])
  const roles = ref<RoleOut[]>([])
  const teams = ref<TeamOut[]>([])
  const myEffectivePermissions = ref<Set<string>>(new Set())
  const myScope = ref<string>('own')
  const myRole = ref<string>('')
  const myRoles = ref<string[]>([])
  const canManageRoles = ref(false)
  const canManageTeams = ref(false)
  const loading = ref(false)

  const catalogueByGroup = computed(() => {
    const grouped: Record<string, PermissionCatalogueItem[]> = {}
    for (const item of catalogue.value) {
      if (!grouped[item.group]) grouped[item.group] = []
      grouped[item.group].push(item)
    }
    return grouped
  })

  function can(action: string): boolean {
    return myEffectivePermissions.value.has(action)
  }

  async function fetchMyPermissions(firmId: string | number) {
    const res = await api.get<MyPermissionsOut>(`/api/v1/firms/${firmId}/me/permissions`)
    if (res.ok && res.data) {
      myEffectivePermissions.value = new Set(res.data.permissions)
      myScope.value = res.data.scope
      myRole.value = res.data.role
      myRoles.value = res.data.roles
      canManageRoles.value = res.data.can_manage_roles
      canManageTeams.value = res.data.can_manage_teams
    }
  }

  async function fetchCatalogue(firmId: string | number) {
    const res = await api.get<PermissionCatalogueItem[]>(`/api/v1/firms/${firmId}/permission-catalogue`)
    if (res.ok && res.data) {
      catalogue.value = res.data
    }
  }

  async function fetchRolePresets(firmId: string | number): Promise<RolePreset[]> {
    const res = await api.get<RolePreset[]>(`/api/v1/firms/${firmId}/role-presets`)
    if (res.ok && res.data) return res.data
    return []
  }

  async function fetchRoles(firmId: string | number) {
    const res = await api.get<RoleOut[]>(`/api/v1/firms/${firmId}/roles`)
    if (res.ok && res.data) {
      roles.value = res.data
    }
  }

  async function fetchTeams(firmId: string | number) {
    const res = await api.get<TeamOut[]>(`/api/v1/firms/${firmId}/teams`)
    if (res.ok && res.data) {
      teams.value = res.data
    }
  }

  async function createRole(firmId: string | number, payload: { code: string; name: string; description?: string; permissions?: string[] }): Promise<RoleOut | null> {
    const res = await api.post<RoleOut>(`/api/v1/firms/${firmId}/roles`, payload)
    if (res.ok && res.data) {
      roles.value.push(res.data)
      return res.data
    }
    return null
  }

  async function updateRole(firmId: string | number, roleId: string, payload: { name?: string; description?: string }): Promise<RoleOut | null> {
    const res = await api.patch<RoleOut>(`/api/v1/firms/${firmId}/roles/${roleId}`, payload)
    if (res.ok && res.data) {
      const idx = roles.value.findIndex(r => r.id === roleId)
      if (idx >= 0) roles.value[idx] = res.data
      return res.data
    }
    return null
  }

  async function deleteRole(firmId: string | number, roleId: string): Promise<boolean> {
    const res = await api.delete(`/api/v1/firms/${firmId}/roles/${roleId}`)
    if (res.ok || res.status === 204) {
      roles.value = roles.value.filter(r => r.id !== roleId)
      return true
    }
    return false
  }

  async function setRolePermissions(firmId: string | number, roleId: string, permissions: string[]): Promise<RoleOut | null> {
    const res = await api.put<RoleOut>(`/api/v1/firms/${firmId}/roles/${roleId}/permissions`, { permissions })
    if (res.ok && res.data) {
      const idx = roles.value.findIndex(r => r.id === roleId)
      if (idx >= 0) roles.value[idx] = res.data
      return res.data
    }
    return null
  }

  async function createTeam(firmId: string | number, payload: { name: string; color?: string }): Promise<TeamOut | null> {
    const res = await api.post<TeamOut>(`/api/v1/firms/${firmId}/teams`, payload)
    if (res.ok && res.data) {
      teams.value.push(res.data)
      return res.data
    }
    return null
  }

  async function updateTeam(firmId: string | number, teamId: string, payload: { name?: string; color?: string }): Promise<TeamOut | null> {
    const res = await api.patch<TeamOut>(`/api/v1/firms/${firmId}/teams/${teamId}`, payload)
    if (res.ok && res.data) {
      const idx = teams.value.findIndex(t => t.id === teamId)
      if (idx >= 0) teams.value[idx] = res.data
      return res.data
    }
    return null
  }

  async function deleteTeam(firmId: string | number, teamId: string): Promise<boolean> {
    const res = await api.delete(`/api/v1/firms/${firmId}/teams/${teamId}`)
    if (res.ok || res.status === 204) {
      teams.value = teams.value.filter(t => t.id !== teamId)
      return true
    }
    return false
  }

  async function addTeamMember(firmId: string | number, teamId: string, membershipId: string): Promise<boolean> {
    const res = await api.post(`/api/v1/firms/${firmId}/teams/${teamId}/members/${membershipId}`, {})
    return res.ok || res.status === 201
  }

  async function removeTeamMember(firmId: string | number, teamId: string, membershipId: string): Promise<boolean> {
    const res = await api.delete(`/api/v1/firms/${firmId}/teams/${teamId}/members/${membershipId}`)
    return res.ok || res.status === 204
  }

  async function init(firmId: string | number) {
    loading.value = true
    try {
      await Promise.all([
        fetchMyPermissions(firmId),
        fetchRoles(firmId),
        fetchTeams(firmId),
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    catalogue,
    roles,
    teams,
    myEffectivePermissions,
    myScope,
    myRole,
    myRoles,
    canManageRoles,
    canManageTeams,
    loading,
    catalogueByGroup,
    can,
    fetchMyPermissions,
    fetchCatalogue,
    fetchRolePresets,
    fetchRoles,
    fetchTeams,
    createRole,
    updateRole,
    deleteRole,
    setRolePermissions,
    createTeam,
    updateTeam,
    deleteTeam,
    addTeamMember,
    removeTeamMember,
    init,
  }
})

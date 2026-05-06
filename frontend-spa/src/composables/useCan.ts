import { computed } from 'vue'
import { usePermissionsStore } from '@/stores/permissions'
import { storeToRefs } from 'pinia'

/**
 * useCan – lightweight composable for permission checks in templates.
 *
 * Usage:
 *   const { can, canManageRoles, canManageTeams } = useCan()
 *   // in template: v-if="can('record.create')"
 */
export function useCan() {
  const store = usePermissionsStore()
  const { myEffectivePermissions, canManageRoles, canManageTeams, myScope, myRole } = storeToRefs(store)

  function can(action: string): boolean {
    return myEffectivePermissions.value.has(action)
  }

  const isOwner = computed(() => myRole.value === 'owner')
  const isAdmin = computed(() => myRole.value === 'admin' || myRole.value === 'owner')

  return {
    can,
    canManageRoles,
    canManageTeams,
    myScope,
    isOwner,
    isAdmin,
  }
}

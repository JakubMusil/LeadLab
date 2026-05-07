import { computed } from 'vue'
import { usePermissionsStore } from '@/stores/permissions'
import { storeToRefs } from 'pinia'
import { useI18n } from '@/composables/useI18n'

export interface CanResult {
  allowed: boolean
  reason?: string
}

/**
 * useCan – lightweight composable for permission checks in templates.
 *
 * Usage:
 *   const { can, canWithReason, canManageRoles, canManageTeams } = useCan()
 *   // in template: v-if="can('record.create')"
 *   // for tooltip:  :disabled="!can('record.delete')"  :title="canWithReason('record.delete').reason"
 */
export function useCan() {
  const store = usePermissionsStore()
  const { myEffectivePermissions, canManageRoles, canManageTeams, myScope, myRole } = storeToRefs(store)
  const { t } = useI18n()

  function can(action: string): boolean {
    return myEffectivePermissions.value.has(action)
  }

  /**
   * Returns { allowed, reason? } – reason is a human-readable explanation when denied.
   * Use to populate tooltip content on disabled buttons.
   */
  function canWithReason(action: string): CanResult {
    if (myEffectivePermissions.value.has(action)) {
      return { allowed: true }
    }
    // Build a helpful denial reason
    const role = myRole.value
    const scope = myScope.value
    let reason: string
    if (!role || role === 'guest') {
      reason = t('permissions.reasonGuest')
    } else if (scope === 'own' && (action.startsWith('record.') || action.startsWith('category.'))) {
      reason = t('permissions.reasonScopeOwn')
    } else {
      reason = t('permissions.reasonMissingPermission', { action })
    }
    return { allowed: false, reason }
  }

  const isOwner = computed(() => myRole.value === 'owner')
  const isAdmin = computed(() => myRole.value === 'admin' || myRole.value === 'owner')

  return {
    can,
    canWithReason,
    canManageRoles,
    canManageTeams,
    myScope,
    isOwner,
    isAdmin,
  }
}

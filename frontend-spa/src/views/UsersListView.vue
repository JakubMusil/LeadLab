<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useFirmStore } from '@/stores/firm'
import { useMembersStore, type MemberOut } from '@/stores/members'
import { usePermissionsStore } from '@/stores/permissions'
import { useAuthStore } from '@/stores/auth'
import { useCan } from '@/composables/useCan'

type MembershipStatusFilter = 'all' | 'active' | 'expired'

const firmStore = useFirmStore()
const membersStore = useMembersStore()
const permissionsStore = usePermissionsStore()
const authStore = useAuthStore()
const { can } = useCan()
const { myRole, myRoles } = storeToRefs(permissionsStore)

const search = ref('')
const roleFilter = ref('')
const teamFilter = ref('')
const membershipStatus = ref<MembershipStatusFilter>('all')
const loadError = ref('')

const firmId = computed(() => (firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''))

const isStaffOrSuperuser = computed(() => !!(authStore.user?.is_staff || authStore.user?.is_superuser))

const hasRoleAccess = computed(() => {
  const roleCodes = [myRole.value, ...myRoles.value].filter(Boolean)
  return roleCodes.some((r) => ['owner', 'admin', 'manager'].includes(r))
})

const hasPermissionAccess = computed(() => can('team.manage') || can('role.manage'))
const canAccessUsersView = computed(() => isStaffOrSuperuser.value || hasRoleAccess.value || hasPermissionAccess.value)

function isExpired(member: MemberOut): boolean {
  if (!member.expires_at) return false
  return new Date(member.expires_at) < new Date()
}

function formatExpiry(member: MemberOut): string {
  if (!member.expires_at) return 'Bez expirace'
  return new Date(member.expires_at).toLocaleDateString('cs-CZ')
}

function roleLabel(member: MemberOut): string {
  if (member.roles?.length) return member.roles.join(', ')
  return member.role
}

const roleOptions = computed(() => {
  const codes = new Set<string>()
  for (const m of membersStore.members) {
    if (m.role) codes.add(m.role)
    for (const code of m.roles ?? []) codes.add(code)
  }
  return Array.from(codes).sort((a, b) => a.localeCompare(b))
})

const teamOptions = computed(() => {
  const map = new Map<string, string>()
  for (const m of membersStore.members) {
    if (m.team_id && m.team_name) map.set(m.team_id, m.team_name)
  }
  return Array.from(map.entries()).map(([id, name]) => ({ id, name }))
})

const filteredMembers = computed(() => {
  const q = search.value.trim().toLowerCase()
  return membersStore.members.filter((member) => {
    const fullName = member.user_full_name?.toLowerCase() ?? ''
    const email = member.user_email?.toLowerCase() ?? ''
    const roleValues = [member.role, ...(member.roles ?? [])]
    const memberIsExpired = isExpired(member)

    const matchSearch = !q || fullName.includes(q) || email.includes(q)
    const matchRole = !roleFilter.value || roleValues.includes(roleFilter.value)
    const matchTeam = !teamFilter.value || member.team_id === teamFilter.value
    const matchStatus =
      membershipStatus.value === 'all'
        ? true
        : membershipStatus.value === 'active'
          ? !memberIsExpired
          : memberIsExpired

    return matchSearch && matchRole && matchTeam && matchStatus
  })
})

async function loadMembers() {
  if (!firmId.value) return
  loadError.value = ''
  try {
    await Promise.all([
      permissionsStore.fetchMyPermissions(firmId.value),
      membersStore.fetchMembers(firmId.value, true),
    ])
  } catch (error) {
    console.error('UsersListView: failed to load members', error)
    loadError.value = 'Nepodařilo se načíst uživatele.'
  }
}

onMounted(loadMembers)
watch(firmId, () => {
  void loadMembers()
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
    <header class="space-y-1">
      <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Users</h1>
      <p class="text-sm text-gray-500 dark:text-gray-400">Seznam členů aktivní firmy</p>
    </header>

    <div
      v-if="!canAccessUsersView"
      class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"
    >
      Pro zobrazení uživatelů nemáte oprávnění.
    </div>

    <template v-else>
      <section class="grid grid-cols-1 gap-3 md:grid-cols-4">
        <input
          v-model="search"
          type="search"
          placeholder="Hledat jméno nebo email"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        />
        <select
          v-model="roleFilter"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        >
          <option value="">Všechny role</option>
          <option v-for="role in roleOptions" :key="role" :value="role">{{ role }}</option>
        </select>
        <select
          v-model="teamFilter"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        >
          <option value="">Všechny týmy</option>
          <option v-for="team in teamOptions" :key="team.id" :value="team.id">{{ team.name }}</option>
        </select>
        <select
          v-model="membershipStatus"
          class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        >
          <option value="all">Všechny stavy</option>
          <option value="active">Aktivní</option>
          <option value="expired">Expirované</option>
        </select>
      </section>

      <div
        v-if="loadError"
        class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"
      >
        {{ loadError }}
      </div>

      <div class="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-800">
          <thead class="bg-gray-50 dark:bg-gray-900">
            <tr class="text-left text-xs font-medium uppercase tracking-wider text-gray-500 dark:text-gray-400">
              <th class="px-4 py-3">Jméno</th>
              <th class="px-4 py-3">Email</th>
              <th class="px-4 py-3">Role</th>
              <th class="px-4 py-3">Tým</th>
              <th class="px-4 py-3">Expirace</th>
              <th class="px-4 py-3">Akce</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 bg-white dark:divide-gray-800 dark:bg-gray-950">
            <tr v-if="membersStore.loading">
              <td colspan="6" class="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">Načítám uživatele…</td>
            </tr>
            <tr v-else-if="filteredMembers.length === 0">
              <td colspan="6" class="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">Žádní uživatelé pro zvolený filtr.</td>
            </tr>
            <tr v-for="member in filteredMembers" :key="member.id" class="text-sm text-gray-800 dark:text-gray-200">
              <td class="px-4 py-3">{{ member.user_full_name || '—' }}</td>
              <td class="px-4 py-3">{{ member.user_email }}</td>
              <td class="px-4 py-3">{{ roleLabel(member) }}</td>
              <td class="px-4 py-3">{{ member.team_name || '—' }}</td>
              <td class="px-4 py-3">{{ formatExpiry(member) }}</td>
              <td class="px-4 py-3">
                <RouterLink class="text-brand hover:underline" :to="`/app/users/${member.id}`">
                  Detail
                </RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { usePermissionsStore } from '@/stores/permissions'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { XMarkIcon, UserPlusIcon, UsersIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'
import InviteMemberWizard from '@/components/InviteMemberWizard.vue'

const firmStore = useFirmStore()
const authStore = useAuthStore()
const permissionsStore = usePermissionsStore()
const toast = useToast()
const { t } = useI18n()
const router = useRouter()

interface Member {
  id: string
  user_email: string
  user_full_name: string
  role: string
  firm_id: string
  expires_at?: string | null
  team_id?: string | null
  team_name?: string | null
  team_color?: string | null
}
interface Invitation { id: string; email: string; role: string; is_expired: boolean; is_accepted: boolean; expires_at: string }

interface CategoryGrantItem {
  id: string
  level: string
  category_id: string
  category_name: string | null
  expires_at: string | null
}
interface RecordGrantItem {
  id: string
  level: string
  record_id: string
  record_title: string | null
  expires_at: string | null
}
interface MemberGrants {
  category_grants: CategoryGrantItem[]
  record_grants: RecordGrantItem[]
}

const members = ref<Member[]>([])
const invitations = ref<Invitation[]>([])
const loading = ref(false)
const showWizard = ref(false)
const inviteLoading = ref(false)
const confirmRemoveId = ref<string | null>(null)
const editingRoleId = ref<string | null>(null)
const editingRole = ref('')
const editingExpiresAt = ref<string>('')

// Member grants panel
const expandedGrantsMemberId = ref<string | null>(null)
const memberGrantsLoading = ref(false)
const memberGrantsData = ref<Record<string, MemberGrants>>({})

// Bulk assignment
const selectedMemberIds = ref<Set<string>>(new Set())
const showBulkTeamPicker = ref(false)
const bulkTeamId = ref<string>('')
const bulkAssignLoading = ref(false)

const ROLES = ['worker', 'admin', 'owner']

const roleColors: Record<string, string> = {
  owner: 'bg-red-100 text-red-700',
  admin: 'bg-blue-100 text-blue-700',
  worker: 'bg-gray-100 text-gray-700',
}

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

const currentUserMember = computed(() =>
  members.value.find((m) => m.user_email === authStore.user?.email)
)
const canManage = computed(() =>
  currentUserMember.value?.role === 'admin' || currentUserMember.value?.role === 'owner'
)

const selectedCount = computed(() => selectedMemberIds.value.size)
const hasSelection = computed(() => selectedCount.value > 0)

async function loadTeam() {
  if (!firmId.value) return
  loading.value = true
  try {
    const [membersRes, invRes] = await Promise.all([
      api.get<Member[]>(`/api/v1/firms/${firmId.value}/members`),
      api.get<Invitation[]>(`/api/v1/firms/${firmId.value}/invitations/`),
      permissionsStore.fetchTeams(firmId.value),
    ])
    if (membersRes.ok) members.value = membersRes.data
    if (invRes.ok) invitations.value = invRes.data
  } finally {
    loading.value = false
  }
}

async function toggleMemberGrants(memberId: string) {
  if (expandedGrantsMemberId.value === memberId) {
    expandedGrantsMemberId.value = null
    return
  }
  expandedGrantsMemberId.value = memberId
  if (!memberGrantsData.value[memberId]) {
    memberGrantsLoading.value = true
    const res = await api.get<MemberGrants>(`/api/v1/firms/${firmId.value}/members/${memberId}/grants`)
    memberGrantsLoading.value = false
    if (res.ok) {
      memberGrantsData.value = { ...memberGrantsData.value, [memberId]: res.data }
    }
  }
}

function levelBadgeClass(level: string): string {
  if (level === 'manage') return 'bg-green-100 text-green-700'
  if (level === 'edit') return 'bg-blue-100 text-blue-700'
  return 'bg-gray-100 text-gray-700'
}

async function removeMember(membershipId: string) {
  confirmRemoveId.value = null
  const res = await api.delete(`/api/v1/firms/${firmId.value}/members/${membershipId}`)
  if (res.ok || res.status === 204) {
    members.value = members.value.filter((m) => m.id !== membershipId)
    selectedMemberIds.value.delete(membershipId)
    toast.success(t('team.memberRemoved'))
  } else {
    toast.error(t('team.failedToRemove'))
  }
}

function startEditRole(member: Member) {
  editingRoleId.value = member.id
  editingRole.value = member.role
  // Pre-populate expires_at field (convert ISO datetime to date string for <input type="date">)
  if (member.expires_at) {
    editingExpiresAt.value = member.expires_at.slice(0, 10)
  } else {
    editingExpiresAt.value = ''
  }
}

async function saveRole(membershipId: string) {
  const payload: { role: string; expires_at?: string | null } = { role: editingRole.value }
  // Send expires_at: ISO string if set, null to clear it
  payload.expires_at = editingExpiresAt.value
    ? new Date(editingExpiresAt.value).toISOString()
    : null
  const res = await api.patch<Member>(`/api/v1/firms/${firmId.value}/members/${membershipId}`, payload)
  editingRoleId.value = null
  if (res.ok) {
    const idx = members.value.findIndex((m) => m.id === membershipId)
    if (idx !== -1) members.value[idx] = res.data
    toast.success(t('team.roleUpdated'))
  } else {
    toast.error(t('team.failedToUpdateRole'))
  }
}

function invitationStatusKey(inv: Invitation): 'accepted' | 'expired' | 'pending' {
  if (inv.is_accepted) return 'accepted'
  if (inv.is_expired) return 'expired'
  return 'pending'
}

function invitationStatus(inv: Invitation): string {
  if (inv.is_accepted) return t('team.acceptedLabel')
  if (inv.is_expired) return t('team.expiredLabel')
  return t('team.pendingLabel')
}

/** Return true when member.expires_at is in the past. */
function isMemberExpired(m: Member): boolean {
  if (!m.expires_at) return false
  // Full datetime comparison: a membership that expired at 10:00 will show as expired at 10:01.
  return new Date(m.expires_at) <= new Date()
}

/** Milliseconds in one day – used for day-count calculations below. */
const MS_PER_DAY = 86_400_000

/** Return a human-readable summary of membership expiry for display in the UI. */
function memberExpiryLabel(m: Member): string {
  if (!m.expires_at) return ''
  const exp = new Date(m.expires_at)
  const now = new Date()
  if (exp <= now) return t('team.memberExpired')
  const daysLeft = Math.ceil((exp.getTime() - now.getTime()) / MS_PER_DAY)
  if (daysLeft === 1) return t('team.memberExpiresTomorrow')
  return t('team.memberExpiresInDays', { days: daysLeft })
}

const manageableMembers = computed(() =>
  members.value.filter(
    (m) => m.role !== 'owner' && m.user_email !== authStore.user?.email
  )
)

function toggleSelect(memberId: string) {
  if (selectedMemberIds.value.has(memberId)) {
    selectedMemberIds.value.delete(memberId)
  } else {
    selectedMemberIds.value.add(memberId)
  }
}

function openUserDetail(membershipId: string) {
  router.push(`/app/users/${membershipId}`)
}

function selectAll() {
  if (selectedMemberIds.value.size === manageableMembers.value.length) {
    selectedMemberIds.value = new Set()
  } else {
    selectedMemberIds.value = new Set(manageableMembers.value.map((m) => m.id))
  }
}

async function applyBulkTeamAssign() {
  if (!bulkTeamId.value || selectedMemberIds.value.size === 0) return
  bulkAssignLoading.value = true
  const ids = Array.from(selectedMemberIds.value)
  let successCount = 0
  for (const membershipId of ids) {
    const res = await api.post(
      `/api/v1/firms/${firmId.value}/teams/${bulkTeamId.value}/members/${membershipId}`,
      {}
    )
    if (res.ok || res.status === 201) {
      successCount++
      // Update local member's team info
      const idx = members.value.findIndex((m) => m.id === membershipId)
      if (idx !== -1) {
        const team = permissionsStore.teams.find((t) => t.id === bulkTeamId.value)
        members.value[idx] = {
          ...members.value[idx],
          team_id: bulkTeamId.value,
          team_name: team?.name ?? null,
          team_color: team?.color ?? null,
        }
      }
    }
  }
  bulkAssignLoading.value = false
  showBulkTeamPicker.value = false
  bulkTeamId.value = ''
  selectedMemberIds.value = new Set()
  if (successCount > 0) {
    toast.success(t('team.bulkAssignedToTeam', { count: successCount }))
    await permissionsStore.fetchTeams(firmId.value)
  } else {
    toast.error(t('team.bulkAssignFailed'))
  }
}

const pendingInvitations = computed(() => invitations.value.filter((i) => !i.is_accepted))

onMounted(loadTeam)
</script>

<template>
  <div class="p-6 space-y-5">
    <!-- Members -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('team.title') }}</h2>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-400 dark:text-gray-500">{{ members.length }} {{ members.length !== 1 ? t('team.membersPlural') : t('team.memberSingular') }}</span>
          <button
            v-if="canManage"
            @click="showWizard = true"
            class="inline-flex items-center gap-1 px-3 py-1.5 bg-brand text-white text-xs font-medium rounded-lg hover:opacity-90"
          >
            <UserPlusIcon class="h-4 w-4" />
            {{ t('team.inviteMember') }}
          </button>
        </div>
      </div>

      <!-- Bulk action toolbar -->
      <div v-if="canManage && hasSelection" class="flex items-center gap-3 px-5 py-2 bg-indigo-50 dark:bg-indigo-900/20 border-b border-indigo-100 dark:border-indigo-800">
        <span class="text-xs font-medium text-indigo-700 dark:text-indigo-300">
          {{ t('team.bulkSelected', { count: selectedCount }) }}
        </span>
        <div v-if="!showBulkTeamPicker" class="flex items-center gap-2">
          <button
            @click="showBulkTeamPicker = true"
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-indigo-300 dark:border-indigo-600 text-xs text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-800"
          >
            <UsersIcon class="h-3.5 w-3.5" />
            {{ t('team.bulkAssignToTeam') }}
          </button>
        </div>
        <div v-else class="flex items-center gap-2">
          <select
            v-model="bulkTeamId"
            class="rounded border border-indigo-300 dark:border-indigo-600 bg-white dark:bg-gray-700 text-xs px-2 py-1 text-gray-900 dark:text-gray-100"
          >
            <option value="">{{ t('team.selectTeam') }}</option>
            <option v-for="team in permissionsStore.teams" :key="team.id" :value="team.id">
              {{ team.name }}
            </option>
          </select>
          <button
            @click="applyBulkTeamAssign"
            :disabled="!bulkTeamId || bulkAssignLoading"
            class="px-2.5 py-1 rounded-md bg-indigo-600 text-white text-xs disabled:opacity-50 hover:bg-indigo-700"
          >{{ bulkAssignLoading ? '…' : t('team.apply') }}</button>
          <button @click="showBulkTeamPicker = false; bulkTeamId = ''" class="px-2.5 py-1 rounded-md border border-gray-300 dark:border-gray-600 text-xs text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700">
            {{ t('team.cancel') }}
          </button>
        </div>
        <button @click="selectedMemberIds = new Set()" class="ml-auto text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
          {{ t('team.clearSelection') }}
        </button>
      </div>

      <div v-if="loading" class="animate-pulse p-4 space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>
      <div v-else-if="members.length === 0" class="flex flex-col items-center justify-center py-12 text-center px-4">
        <div class="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-3">
          <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        </div>
        <p class="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">{{ t('team.noMembers') }}</p>
        <p class="text-xs text-gray-400 dark:text-gray-500">{{ t('team.noMembersHint') }}</p>
      </div>
      <div v-else class="divide-y divide-gray-50 dark:divide-gray-700">
        <!-- Select-all row (only visible for admins) -->
        <div v-if="canManage" class="flex items-center gap-3 px-5 py-2 bg-gray-50 dark:bg-gray-800/50">
          <input
            type="checkbox"
            :checked="selectedMemberIds.size > 0 && selectedMemberIds.size === manageableMembers.length"
            :indeterminate="selectedMemberIds.size > 0 && selectedMemberIds.size < manageableMembers.length"
            @change="selectAll"
            class="rounded border-gray-300 text-indigo-600"
          />
          <span class="text-xs text-gray-500 dark:text-gray-400">{{ t('team.selectAll') }}</span>
        </div>

        <template v-for="m in members" :key="m.id">
          <div class="flex items-center gap-3 px-5 py-3" :class="selectedMemberIds.has(m.id) ? 'bg-indigo-50/50 dark:bg-indigo-900/10' : ''">
          <!-- Checkbox (only for manageable members) -->
          <input
            v-if="canManage && m.role !== 'owner' && m.user_email !== authStore.user?.email"
            type="checkbox"
            :checked="selectedMemberIds.has(m.id)"
            @change="toggleSelect(m.id)"
            class="rounded border-gray-300 text-indigo-600 flex-shrink-0"
          />
          <div v-else class="w-4 flex-shrink-0" />

          <!-- Avatar -->
          <div class="w-9 h-9 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center text-red-600 dark:text-red-400 text-sm font-semibold flex-shrink-0" aria-hidden="true">
            {{ (m.user_full_name || m.user_email)[0]?.toUpperCase() ?? '?' }}
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ m.user_full_name || m.user_email }}</p>
              <!-- Team chip -->
              <span
                v-if="m.team_name"
                class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium text-white"
                :style="{ backgroundColor: m.team_color || '#6366f1' }"
              >
                <UsersIcon class="h-3 w-3" />
                {{ m.team_name }}
              </span>
            </div>
            <p class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ m.user_email }}</p>
            <!-- Expiry badge -->
            <span
              v-if="m.expires_at"
              class="inline-block mt-0.5 text-xs px-2 py-0.5 rounded-full font-medium"
              :class="isMemberExpired(m)
                ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 badge-expired'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 badge-expiring'"
            >{{ memberExpiryLabel(m) }}</span>
          </div>

          <!-- Role badge / editor -->
          <div v-if="editingRoleId === m.id && canManage" class="flex items-center gap-2 flex-wrap">
            <select v-model="editingRole" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-2 py-1 focus:outline-none focus:border-red-400">
              <option v-for="r in ROLES.filter(r => r !== 'owner')" :key="r" :value="r">{{ r }}</option>
            </select>
            <input
              v-model="editingExpiresAt"
              type="date"
              :title="t('team.memberExpiresAtLabel')"
              class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-xs px-2 py-1 focus:outline-none focus:border-red-400"
            />
            <button class="text-xs bg-red-600 text-white px-2 py-1 rounded-lg" @click="saveRole(m.id)">{{ t('team.save') }}</button>
            <button class="text-xs border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 px-2 py-1 rounded-lg" @click="editingRoleId = null">{{ t('team.cancel') }}</button>
          </div>
          <template v-else>
            <button
              class="text-xs px-2.5 py-1 rounded-full font-medium"
              :class="roleColors[m.role] ?? 'bg-gray-100 text-gray-700'"
              :disabled="!canManage || m.role === 'owner'"
              @click="canManage && m.role !== 'owner' ? startEditRole(m) : undefined"
              :title="canManage && m.role !== 'owner' ? 'Click to change role' : ''"
              :aria-label="`Role: ${m.role}${canManage && m.role !== 'owner' ? '. Click to change.' : ''}`"
            >{{ m.role }}</button>
          </template>

          <button
            class="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            @click="openUserDetail(m.id)"
          >
            {{ t('usersView.list.actions.detail') }}
          </button>

          <!-- Access grants toggle (admin/owner only) -->
          <button
            v-if="canManage"
            @click="toggleMemberGrants(m.id)"
            class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 dark:text-gray-500 text-xs flex items-center gap-1"
            :title="expandedGrantsMemberId === m.id ? t('team.hideAccesses') : t('team.viewAccesses')"
            :aria-label="expandedGrantsMemberId === m.id ? t('team.hideAccesses') : t('team.viewAccesses')"
          >
            <ChevronUpIcon v-if="expandedGrantsMemberId === m.id" class="w-4 h-4" />
            <ChevronDownIcon v-else class="w-4 h-4" />
          </button>

          <!-- Remove -->
          <button
            v-if="canManage && m.role !== 'owner' && m.user_email !== authStore.user?.email"
            class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 text-xs"
            :aria-label="`Remove ${m.user_full_name || m.user_email}`"
            @click="confirmRemoveId = m.id"><XMarkIcon class="w-4 h-4" /></button>
        </div>
        <!-- Grants expansion panel -->
        <div
          v-if="canManage && expandedGrantsMemberId === m.id"
          class="border-t border-gray-50 dark:border-gray-700 px-14 py-3 bg-gray-50/50 dark:bg-gray-800/50"
        >
          <div v-if="memberGrantsLoading && !memberGrantsData[m.id]" class="text-xs text-gray-400 animate-pulse">…</div>
          <div v-else-if="memberGrantsData[m.id]">
            <p class="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-2">{{ t('team.memberAccesses') }}</p>
            <!-- Category grants -->
            <div v-if="memberGrantsData[m.id].category_grants.length > 0" class="mb-2">
              <p class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ t('team.categoryGrants') }}</p>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="g in memberGrantsData[m.id].category_grants"
                  :key="g.id"
                  class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                  :class="levelBadgeClass(g.level)"
                >
                  {{ g.category_name || g.category_id }}
                  <span class="opacity-70">({{ g.level }})</span>
                  <span v-if="g.expires_at" class="opacity-50">· {{ new Date(g.expires_at).toLocaleDateString() }}</span>
                </span>
              </div>
            </div>
            <!-- Record grants -->
            <div v-if="memberGrantsData[m.id].record_grants.length > 0" class="mb-2">
              <p class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ t('team.recordGrants') }}</p>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="g in memberGrantsData[m.id].record_grants"
                  :key="g.id"
                  class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
                  :class="levelBadgeClass(g.level)"
                >
                  {{ g.record_title || g.record_id }}
                  <span class="opacity-70">({{ g.level }})</span>
                  <span v-if="g.expires_at" class="opacity-50">· {{ new Date(g.expires_at).toLocaleDateString() }}</span>
                </span>
              </div>
            </div>
            <!-- Empty state -->
            <p
              v-if="memberGrantsData[m.id].category_grants.length === 0 && memberGrantsData[m.id].record_grants.length === 0"
              class="text-xs text-gray-400 dark:text-gray-500 italic"
            >{{ t('team.noGrantsFound') }}</p>
          </div>
        </div>
        </template>
      </div>
    </div>

    <!-- Pending invitations -->
    <div v-if="canManage && pendingInvitations.length > 0" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
      <div class="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('team.pendingInvitations') }}</h3>
      </div>
      <div class="divide-y divide-gray-50 dark:divide-gray-700">
        <div v-for="inv in pendingInvitations" :key="inv.id" class="flex items-center gap-3 px-5 py-3">
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-900 dark:text-gray-100 truncate">{{ inv.email }}</p>
            <p class="text-xs text-gray-400 dark:text-gray-500">{{ t('team.role') }}: {{ inv.role }}</p>
          </div>
          <span
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="{
              'bg-yellow-100 text-yellow-700': invitationStatusKey(inv) === 'pending',
              'bg-green-100 text-green-700': invitationStatusKey(inv) === 'accepted',
              'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400': invitationStatusKey(inv) === 'expired',
            }"
          >{{ invitationStatus(inv) }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Remove confirm -->
  <Teleport to="body">
    <ConfirmDeleteModal
      :open="!!confirmRemoveId"
      :title="t('team.removeMemberTitle')"
      :message="t('team.removeMemberDesc')"
      :confirm-label="t('team.remove')"
      @confirm="removeMember(confirmRemoveId!)"
      @cancel="confirmRemoveId = null"
    />
  </Teleport>

  <!-- Invite member wizard -->
  <InviteMemberWizard
    :open="showWizard"
    @close="showWizard = false"
    @invited="loadTeam"
  />
</template>

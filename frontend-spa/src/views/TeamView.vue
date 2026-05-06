<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { XMarkIcon, UserIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

const firmStore = useFirmStore()
const authStore = useAuthStore()
const toast = useToast()
const { t } = useI18n()

interface Member { id: string; user_email: string; user_full_name: string; role: string; firm_id: string; expires_at?: string | null }
interface Invitation { id: string; email: string; role: string; is_expired: boolean; is_accepted: boolean; expires_at: string }

const members = ref<Member[]>([])
const invitations = ref<Invitation[]>([])
const loading = ref(false)
const inviteEmail = ref('')
const inviteRole = ref('worker')
const inviteLoading = ref(false)
const inviteError = ref('')
const confirmRemoveId = ref<string | null>(null)
const editingRoleId = ref<string | null>(null)
const editingRole = ref('')
const editingExpiresAt = ref<string>('')

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

async function loadTeam() {
  if (!firmId.value) return
  loading.value = true
  try {
    const [membersRes, invRes] = await Promise.all([
      api.get<Member[]>(`/api/v1/firms/${firmId.value}/members`),
      api.get<Invitation[]>(`/api/v1/firms/${firmId.value}/invitations/`),
    ])
    if (membersRes.ok) members.value = membersRes.data
    if (invRes.ok) invitations.value = invRes.data
  } finally {
    loading.value = false
  }
}

async function sendInvitation() {
  if (!inviteEmail.value.trim()) { inviteError.value = t('team.emailRequired'); return }
  inviteLoading.value = true
  inviteError.value = ''
  const res = await api.post(`/api/v1/firms/${firmId.value}/invitations/`, {
    email: inviteEmail.value.trim(),
    role: inviteRole.value,
  })
  inviteLoading.value = false
  if (res.ok || res.status === 202) {
    toast.success(t('team.invitationSent'))
    inviteEmail.value = ''
    await loadTeam()
  } else {
    const data = res.data as Record<string, string> | null
    inviteError.value = data?.detail ?? t('team.failedToInvite')
  }
}

async function removeMember(membershipId: string) {
  confirmRemoveId.value = null
  const res = await api.delete(`/api/v1/firms/${firmId.value}/members/${membershipId}`)
  if (res.ok || res.status === 204) {
    members.value = members.value.filter((m) => m.id !== membershipId)
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

const pendingInvitations = computed(() => invitations.value.filter((i) => !i.is_accepted))

onMounted(loadTeam)
</script>

<template>
  <div class="p-6 space-y-5">
    <!-- Members -->
    <div class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700">
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700">
        <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('team.title') }}</h2>
        <span class="text-xs text-gray-400 dark:text-gray-500">{{ members.length }} {{ members.length !== 1 ? t('team.membersPlural') : t('team.memberSingular') }}</span>
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
        <div v-for="m in members" :key="m.id" class="flex items-center gap-3 px-5 py-3">
          <!-- Avatar -->
          <div class="w-9 h-9 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center text-red-600 dark:text-red-400 text-sm font-semibold flex-shrink-0" aria-hidden="true">
            {{ (m.user_full_name || m.user_email)[0]?.toUpperCase() ?? '?' }}
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{{ m.user_full_name || m.user_email }}</p>
            <p class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ m.user_email }}</p>
            <!-- Expiry badge -->
            <span
              v-if="m.expires_at"
              class="inline-block mt-0.5 text-xs px-2 py-0.5 rounded-full font-medium"
              :class="isMemberExpired(m) ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'"
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

          <!-- Remove -->
          <button
            v-if="canManage && m.role !== 'owner' && m.user_email !== authStore.user?.email"
            class="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 text-xs"
            :aria-label="`Remove ${m.user_full_name || m.user_email}`"
            @click="confirmRemoveId = m.id"><XMarkIcon class="w-4 h-4" /></button>
        </div>
      </div>
    </div>

    <!-- Invite member -->
    <div v-if="canManage" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('team.inviteMember') }}</h3>
      <div v-if="inviteError" class="mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" role="alert">{{ inviteError }}</div>
      <div class="flex gap-2 flex-wrap">
        <input
          v-model="inviteEmail"
          type="email"
          :placeholder="t('team.emailPlaceholder')"
          class="flex-1 min-w-48 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <select v-model="inviteRole" class="rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
          <option value="worker">{{ t('team.roleWorker') }}</option>
          <option value="admin">{{ t('team.roleAdmin') }}</option>
        </select>
        <button
          :disabled="inviteLoading"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
          @click="sendInvitation"
        >{{ inviteLoading ? t('team.sending') : t('team.sendInvite') }}</button>
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
</template>

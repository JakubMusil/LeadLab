<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { api } from '@/api'

const firmStore = useFirmStore()
const authStore = useAuthStore()
const toast = useToast()

interface Member { id: string; user_email: string; user_full_name: string; role: string; firm_id: string }
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
  if (!inviteEmail.value.trim()) { inviteError.value = 'Email is required.'; return }
  inviteLoading.value = true
  inviteError.value = ''
  const res = await api.post(`/api/v1/firms/${firmId.value}/invitations/`, {
    email: inviteEmail.value.trim(),
    role: inviteRole.value,
  })
  inviteLoading.value = false
  if (res.ok || res.status === 202) {
    toast.success('Invitation sent.')
    inviteEmail.value = ''
    await loadTeam()
  } else {
    const data = res.data as Record<string, string> | null
    inviteError.value = data?.detail ?? 'Failed to send invitation.'
  }
}

async function removeMember(membershipId: string) {
  confirmRemoveId.value = null
  const res = await api.delete(`/api/v1/firms/${firmId.value}/members/${membershipId}`)
  if (res.ok || res.status === 204) {
    members.value = members.value.filter((m) => m.id !== membershipId)
    toast.success('Member removed.')
  } else {
    toast.error('Failed to remove member.')
  }
}

function startEditRole(member: Member) {
  editingRoleId.value = member.id
  editingRole.value = member.role
}

async function saveRole(membershipId: string) {
  const res = await api.patch<Member>(`/api/v1/firms/${firmId.value}/members/${membershipId}`, { role: editingRole.value })
  editingRoleId.value = null
  if (res.ok) {
    const idx = members.value.findIndex((m) => m.id === membershipId)
    if (idx !== -1) members.value[idx] = res.data
    toast.success('Role updated.')
  } else {
    toast.error('Failed to update role.')
  }
}

function invitationStatus(inv: Invitation): string {
  if (inv.is_accepted) return 'accepted'
  if (inv.is_expired) return 'expired'
  return 'pending'
}

const pendingInvitations = computed(() => invitations.value.filter((i) => !i.is_accepted))

onMounted(loadTeam)
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto space-y-5">
    <!-- Members -->
    <div class="bg-white rounded-2xl border border-gray-100">
      <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <h2 class="text-sm font-semibold text-gray-900">Team Members</h2>
        <span class="text-xs text-gray-400">{{ members.length }} member{{ members.length !== 1 ? 's' : '' }}</span>
      </div>

      <div v-if="loading" class="animate-pulse p-4 space-y-2">
        <div v-for="i in 3" :key="i" class="h-12 bg-gray-100 rounded-xl" />
      </div>
      <div v-else-if="members.length === 0" class="px-5 py-8 text-center text-sm text-gray-400">No members found.</div>
      <div v-else class="divide-y divide-gray-50">
        <div v-for="m in members" :key="m.id" class="flex items-center gap-3 px-5 py-3">
          <!-- Avatar -->
          <div class="w-9 h-9 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-sm font-semibold flex-shrink-0">
            {{ (m.user_full_name || m.user_email)[0]?.toUpperCase() ?? '?' }}
          </div>

          <!-- Info -->
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">{{ m.user_full_name || m.user_email }}</p>
            <p class="text-xs text-gray-400 truncate">{{ m.user_email }}</p>
          </div>

          <!-- Role badge / editor -->
          <div v-if="editingRoleId === m.id && canManage" class="flex items-center gap-2">
            <select v-model="editingRole" class="rounded-xl border border-gray-200 text-xs px-2 py-1 focus:outline-none focus:border-red-400">
              <option v-for="r in ROLES.filter(r => r !== 'owner')" :key="r" :value="r">{{ r }}</option>
            </select>
            <button class="text-xs bg-red-600 text-white px-2 py-1 rounded-lg" @click="saveRole(m.id)">Save</button>
            <button class="text-xs border border-gray-200 px-2 py-1 rounded-lg" @click="editingRoleId = null">Cancel</button>
          </div>
          <template v-else>
            <button
              class="text-xs px-2.5 py-1 rounded-full font-medium"
              :class="roleColors[m.role] ?? 'bg-gray-100 text-gray-700'"
              :disabled="!canManage || m.role === 'owner'"
              @click="canManage && m.role !== 'owner' ? startEditRole(m) : undefined"
              :title="canManage && m.role !== 'owner' ? 'Click to change role' : ''"
            >{{ m.role }}</button>
          </template>

          <!-- Remove -->
          <button
            v-if="canManage && m.role !== 'owner' && m.user_email !== authStore.user?.email"
            class="p-1.5 rounded-lg hover:bg-red-50 text-red-500 text-xs"
            @click="confirmRemoveId = m.id"
          >✕</button>
        </div>
      </div>
    </div>

    <!-- Invite member -->
    <div v-if="canManage" class="bg-white rounded-2xl border border-gray-100 p-5">
      <h3 class="text-sm font-semibold text-gray-900 mb-3">Invite Member</h3>
      <div v-if="inviteError" class="mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">{{ inviteError }}</div>
      <div class="flex gap-2 flex-wrap">
        <input
          v-model="inviteEmail"
          type="email"
          placeholder="Email address…"
          class="flex-1 min-w-48 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
        <select v-model="inviteRole" class="rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400">
          <option value="worker">Worker</option>
          <option value="admin">Admin</option>
        </select>
        <button
          :disabled="inviteLoading"
          class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60"
          @click="sendInvitation"
        >{{ inviteLoading ? 'Sending…' : 'Send Invite' }}</button>
      </div>
    </div>

    <!-- Pending invitations -->
    <div v-if="canManage && pendingInvitations.length > 0" class="bg-white rounded-2xl border border-gray-100">
      <div class="px-5 py-4 border-b border-gray-100">
        <h3 class="text-sm font-semibold text-gray-900">Pending Invitations</h3>
      </div>
      <div class="divide-y divide-gray-50">
        <div v-for="inv in pendingInvitations" :key="inv.id" class="flex items-center gap-3 px-5 py-3">
          <div class="flex-1 min-w-0">
            <p class="text-sm text-gray-900 truncate">{{ inv.email }}</p>
            <p class="text-xs text-gray-400">Role: {{ inv.role }}</p>
          </div>
          <span
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            :class="{
              'bg-yellow-100 text-yellow-700': invitationStatus(inv) === 'pending',
              'bg-green-100 text-green-700': invitationStatus(inv) === 'accepted',
              'bg-gray-100 text-gray-500': invitationStatus(inv) === 'expired',
            }"
          >{{ invitationStatus(inv) }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Remove confirm -->
  <Teleport to="body">
    <div v-if="confirmRemoveId" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" @click.self="confirmRemoveId = null">
      <div class="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 text-center">
        <div class="text-3xl mb-3">👤</div>
        <h3 class="text-base font-semibold text-gray-900 mb-2">Remove this member?</h3>
        <p class="text-sm text-gray-500 mb-4">They will lose access to this workspace.</p>
        <div class="flex gap-3">
          <button class="flex-1 rounded-xl border border-gray-200 py-2 text-sm" @click="confirmRemoveId = null">Cancel</button>
          <button class="flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700" @click="removeMember(confirmRemoveId!)">Remove</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePermissionsStore, type TeamOut } from '@/stores/permissions'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { PlusIcon, TrashIcon, PencilIcon, CheckIcon, XMarkIcon, UserPlusIcon, UserMinusIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'
import PeoplePicker from '@/components/PeoplePicker.vue'
import { useMembersStore } from '@/stores/members'
import { VueDraggable } from 'vue-draggable-plus'

const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const membersStore = useMembersStore()
const toast = useToast()
const { t } = useI18n()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

const loading = ref(false)

// Create team
const showCreateForm = ref(false)
const createName = ref('')
const createColor = ref('#6366f1')
const createError = ref('')
const createLoading = ref(false)

// Edit team
const editingTeamId = ref<string | null>(null)
const editName = ref('')
const editColor = ref('#6366f1')
const editLoading = ref(false)

// Delete team
const pendingDeleteTeam = ref<TeamOut | null>(null)

// Members management
const expandedTeamId = ref<string | null>(null)
const addMemberLoading = ref(false)
const selectedMembershipId = ref('')

// Drag state
const dragLoading = ref(false)

async function loadData() {
  if (!firmId.value) return
  loading.value = true
  try {
    await Promise.all([
      permissionsStore.fetchTeams(firmId.value),
      membersStore.fetchMembers(firmId.value, true),
    ])
  } finally {
    loading.value = false
  }
}

async function createTeam() {
  if (!createName.value.trim()) {
    createError.value = t('permissions.teamName') + ' is required.'
    return
  }
  createLoading.value = true
  createError.value = ''
  const result = await permissionsStore.createTeam(firmId.value, {
    name: createName.value.trim(),
    color: createColor.value,
  })
  createLoading.value = false
  if (result) {
    toast.success(t('permissions.teamCreated'))
    createName.value = ''
    createColor.value = '#6366f1'
    showCreateForm.value = false
  } else {
    createError.value = t('permissions.failedToCreateTeam')
  }
}

function startEditTeam(team: TeamOut) {
  editingTeamId.value = team.id
  editName.value = team.name
  editColor.value = team.color
}

async function saveEditTeam(teamId: string) {
  editLoading.value = true
  const result = await permissionsStore.updateTeam(firmId.value, teamId, {
    name: editName.value,
    color: editColor.value,
  })
  editLoading.value = false
  if (result) {
    toast.success(t('permissions.teamUpdated'))
    editingTeamId.value = null
  } else {
    toast.error(t('permissions.failedToUpdateTeam'))
  }
}

async function deleteTeam() {
  if (!pendingDeleteTeam.value) return
  const ok = await permissionsStore.deleteTeam(firmId.value, pendingDeleteTeam.value.id)
  pendingDeleteTeam.value = null
  if (ok) {
    toast.success(t('permissions.teamDeleted'))
    expandedTeamId.value = null
    await loadData()
  } else {
    toast.error(t('permissions.failedToDeleteTeam'))
  }
}

function toggleTeamMembers(teamId: string) {
  expandedTeamId.value = expandedTeamId.value === teamId ? null : teamId
  selectedMembershipId.value = ''
}

async function addMember(teamId: string) {
  if (!selectedMembershipId.value) return
  addMemberLoading.value = true
  const ok = await permissionsStore.addTeamMember(firmId.value, teamId, selectedMembershipId.value)
  addMemberLoading.value = false
  if (ok) {
    toast.success(t('permissions.memberAdded'))
    selectedMembershipId.value = ''
    await loadData()
  } else {
    toast.error(t('permissions.failedToAddMember'))
  }
}

async function removeMember(teamId: string, membershipId: string) {
  const ok = await permissionsStore.removeTeamMember(firmId.value, teamId, membershipId)
  if (ok) {
    toast.success(t('permissions.memberRemoved'))
    await loadData()
  } else {
    toast.error(t('permissions.failedToRemoveMember'))
  }
}

/** Set of membership IDs that are in any team (for the unassigned pool) */
const assignedMembershipIds = computed(() => {
  const ids = new Set<string>()
  for (const team of permissionsStore.teams) {
    for (const m of team.members) {
      ids.add(m.membership_id)
    }
  }
  return ids
})

/** Members not assigned to any team */
const unassignedMembers = computed(() =>
  membersStore.members.filter((m) => !assignedMembershipIds.value.has(m.id))
)

/** Called when a member is dragged from the unassigned pool into a team */
async function onDragToTeam(event: { item: HTMLElement }, teamId: string) {
  const membershipId = event.item.dataset.membershipId
  if (!membershipId) return
  dragLoading.value = true
  const ok = await permissionsStore.addTeamMember(firmId.value, teamId, membershipId)
  dragLoading.value = false
  if (ok) {
    toast.success(t('permissions.memberAdded'))
    await loadData()
  } else {
    toast.error(t('permissions.failedToAddMember'))
    await loadData() // Revert UI on failure
  }
}

/** Called when a member is dragged from a team into the unassigned pool */
async function onDragToUnassigned(event: { item: HTMLElement }, fromTeamId: string) {
  const membershipId = event.item.dataset.membershipId
  if (!membershipId) return
  dragLoading.value = true
  const ok = await permissionsStore.removeTeamMember(firmId.value, fromTeamId, membershipId)
  dragLoading.value = false
  if (ok) {
    toast.success(t('permissions.memberRemoved'))
    await loadData()
  } else {
    toast.error(t('permissions.failedToRemoveMember'))
    await loadData() // Revert UI on failure
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
        {{ t('permissions.teams') }}
      </h3>
      <button
        v-if="permissionsStore.canManageTeams"
        @click="showCreateForm = !showCreateForm"
        class="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
      >
        <PlusIcon class="h-4 w-4" />
        {{ t('permissions.createTeam') }}
      </button>
    </div>

    <!-- Create form -->
    <div v-if="showCreateForm" class="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
      <div class="flex items-end gap-3">
        <div class="flex-1">
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('permissions.teamName') }}</label>
          <input v-model="createName" type="text" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100" :placeholder="t('permissions.teamName')" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('permissions.teamColor') }}</label>
          <input v-model="createColor" type="color" class="h-9 w-12 rounded border border-gray-300 dark:border-gray-600 cursor-pointer" />
        </div>
        <button @click="createTeam" :disabled="createLoading" class="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
          <CheckIcon class="h-4 w-4" />
        </button>
        <button @click="showCreateForm = false" class="inline-flex items-center gap-1 rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">
          <XMarkIcon class="h-4 w-4" />
        </button>
      </div>
      <p v-if="createError" class="mt-2 text-xs text-red-600">{{ createError }}</p>
    </div>

    <!-- Unassigned members pool (drag source) -->
    <div v-if="membersStore.members.length > 0" class="rounded-lg border border-dashed border-gray-300 dark:border-gray-600">
      <div class="px-3 py-2 bg-gray-50 dark:bg-gray-800 rounded-t-lg border-b border-gray-200 dark:border-gray-700">
        <h4 class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
          {{ t('permissions.unassignedMembers') }}
          <span class="ml-1 text-gray-400">({{ unassignedMembers.length }})</span>
        </h4>
        <p class="text-xs text-gray-400 mt-0.5">{{ t('permissions.dragToTeamHint') }}</p>
      </div>
      <VueDraggable
        v-model="membersStore.members"
        group="team-members"
        class="min-h-[48px] flex flex-wrap gap-2 p-3"
        :item-key="'id'"
        :disabled="!permissionsStore.canManageTeams || dragLoading"
        :filter="(el: HTMLElement) => assignedMembershipIds.has(el.dataset.membershipId ?? '')"
        @add="(e: any) => { /* handled by team zone's @remove */ }"
      >
        <template #item="{ element: member }">
          <div
            v-if="!assignedMembershipIds.has(member.id)"
            :data-membership-id="member.id"
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 text-sm text-gray-800 dark:text-gray-200 cursor-grab active:cursor-grabbing select-none"
          >
            <div class="w-5 h-5 rounded-full bg-gray-200 dark:bg-gray-500 flex items-center justify-center text-xs font-semibold">
              {{ (member.user_full_name || member.user_email)[0]?.toUpperCase() ?? '?' }}
            </div>
            {{ member.user_full_name || member.user_email }}
          </div>
        </template>
      </VueDraggable>
      <div v-if="unassignedMembers.length === 0" class="px-3 py-2 text-xs text-gray-400 italic">
        {{ t('permissions.allMembersAssigned') }}
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="permissionsStore.teams.length === 0 && !loading" class="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
      {{ t('permissions.noTeams') }}
    </div>

    <!-- Teams list -->
    <div class="space-y-3">
      <div v-for="team in permissionsStore.teams" :key="team.id" class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <!-- Team header -->
        <div class="flex items-center gap-3 px-4 py-3 bg-white dark:bg-gray-900">
          <!-- Color dot -->
          <span class="h-3 w-3 rounded-full flex-shrink-0" :style="{ backgroundColor: team.color }" />

          <!-- Name (editable) -->
          <template v-if="editingTeamId === team.id">
            <input v-model="editName" type="text" class="flex-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1 text-sm" />
            <input v-model="editColor" type="color" class="h-8 w-10 rounded border border-gray-300 dark:border-gray-600 cursor-pointer" />
          </template>
          <span v-else class="flex-1 text-sm font-medium text-gray-900 dark:text-gray-100">
            {{ team.name }}
            <span class="ml-2 text-xs text-gray-400">({{ team.member_count }} members)</span>
          </span>

          <!-- Actions -->
          <div class="flex items-center gap-1">
            <template v-if="editingTeamId === team.id">
              <button @click="saveEditTeam(team.id)" :disabled="editLoading" class="p-1 text-green-600 hover:text-green-700">
                <CheckIcon class="h-4 w-4" />
              </button>
              <button @click="editingTeamId = null" class="p-1 text-gray-400 hover:text-gray-600">
                <XMarkIcon class="h-4 w-4" />
              </button>
            </template>
            <template v-else>
              <button @click="toggleTeamMembers(team.id)" class="p-1 text-gray-400 hover:text-indigo-600 dark:hover:text-indigo-400" :title="t('permissions.teamMembers')">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
              </button>
              <button v-if="permissionsStore.canManageTeams" @click="startEditTeam(team)" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                <PencilIcon class="h-4 w-4" />
              </button>
              <button v-if="permissionsStore.canManageTeams" @click="pendingDeleteTeam = team" class="p-1 text-gray-400 hover:text-red-600">
                <TrashIcon class="h-4 w-4" />
              </button>
            </template>
          </div>
        </div>

        <!-- Members panel (expanded) -->
        <div v-if="expandedTeamId === team.id" class="border-t border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800 p-4">
          <h4 class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-3">{{ t('permissions.teamMembers') }}</h4>

          <!-- Droppable member list for this team -->
          <VueDraggable
            v-model="team.members"
            group="team-members"
            class="space-y-1.5 mb-3 min-h-[36px]"
            :disabled="!permissionsStore.canManageTeams || dragLoading"
            @add="(e: any) => onDragToTeam(e, team.id)"
            @remove="(e: any) => onDragToUnassigned(e, team.id)"
          >
            <template #item="{ element: member }">
              <div
                :data-membership-id="member.membership_id"
                class="flex items-center justify-between rounded px-2 py-1.5 bg-white dark:bg-gray-900 cursor-grab active:cursor-grabbing select-none"
              >
                <div>
                  <p class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ member.user_full_name || member.user_email }}</p>
                  <p class="text-xs text-gray-500">{{ member.user_email }}</p>
                </div>
                <button
                  v-if="permissionsStore.canManageTeams"
                  @click.stop="removeMember(team.id, member.membership_id)"
                  class="p-1 text-gray-400 hover:text-red-600"
                  :title="t('permissions.removeFromTeam')"
                >
                  <UserMinusIcon class="h-4 w-4" />
                </button>
              </div>
            </template>
          </VueDraggable>
          <div v-if="team.members.length === 0" class="text-xs text-gray-400 py-1">
            {{ t('permissions.noMembers') }}
          </div>

          <!-- Add member (picker fallback) -->
          <div v-if="permissionsStore.canManageTeams" class="flex items-center gap-2">
            <div class="flex-1">
              <PeoplePicker
                v-model="selectedMembershipId"
                :firm-id="firmId"
                :placeholder="t('peoplePicker.addMember')"
              />
            </div>
            <button
              @click="addMember(team.id)"
              :disabled="!selectedMembershipId || addMemberLoading"
              class="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              <UserPlusIcon class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <ConfirmDeleteModal
      :open="!!pendingDeleteTeam"
      :title="t('permissions.deleteTeam')"
      :message="t('permissions.deleteTeamConfirm')"
      @confirm="deleteTeam"
      @cancel="pendingDeleteTeam = null"
    />
  </div>
</template>

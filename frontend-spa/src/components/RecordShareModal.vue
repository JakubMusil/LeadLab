<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useFirmStore } from '@/stores/firm'
import { useMembersStore } from '@/stores/members'
import { usePermissionsStore } from '@/stores/permissions'
import { Modal, Tooltip } from '@/components/ui'
import PeoplePicker from '@/components/PeoplePicker.vue'
import { UserPlusIcon, TrashIcon, UsersIcon } from '@heroicons/vue/24/outline'

interface RecordGrant {
  id: string
  principal_type: string
  principal_id: string
  principal_name: string | null
  level: string
  granted_by_id: string | null
  granted_at: string
  expires_at: string | null
}

const props = defineProps<{
  open: boolean
  recordId: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const toast = useToast()
const { t } = useI18n()
const firmStore = useFirmStore()
const membersStore = useMembersStore()
const permissionsStore = usePermissionsStore()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

type Tab = 'people' | 'teams'
const activeTab = ref<Tab>('people')

const grants = ref<RecordGrant[]>([])
const loading = ref(false)
const grantLoading = ref(false)
const levelUpdating = ref<string | null>(null)

const selectedMembershipId = ref('')
const selectedTeamId = ref('')
const selectedLevel = ref<'view' | 'edit' | 'manage'>('view')
const expiresAt = ref('')

const userGrants = computed(() => grants.value.filter(g => g.principal_type === 'user'))
const teamGrants = computed(() => grants.value.filter(g => g.principal_type === 'team'))

const teams = computed(() => permissionsStore.teams)

async function loadData() {
  if (!props.recordId || !firmId.value) return
  loading.value = true
  try {
    await Promise.all([
      api.get<RecordGrant[]>(`/api/v1/crm/records/${props.recordId}/grants`).then((res) => {
        if (res.ok && res.data) grants.value = res.data
      }),
      membersStore.fetchMembers(firmId.value),
      permissionsStore.fetchTeams(firmId.value),
    ])
  } finally {
    loading.value = false
  }
}

function grantDisplayName(grant: RecordGrant): string {
  if (grant.principal_name) return grant.principal_name
  if (grant.principal_type === 'user') return membersStore.displayNameById(grant.principal_id)
  const team = teams.value.find(t => t.id === grant.principal_id)
  return team ? team.name : grant.principal_id
}

// Expiry countdown helpers
function expiryDaysLeft(expires_at: string | null): number | null {
  if (!expires_at) return null
  const diff = new Date(expires_at).getTime() - Date.now()
  return Math.ceil(diff / 86400000)
}

function expiryBadgeClass(days: number | null): string {
  if (days === null) return ''
  if (days <= 0) return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  if (days <= 3) return 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
  if (days <= 7) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
}

function expiryLabel(expires_at: string | null): string {
  const days = expiryDaysLeft(expires_at)
  if (days === null) return ''
  if (days <= 0) return t('permissions.expiryExpired')
  if (days === 1) return t('permissions.expiryTomorrow')
  return t('permissions.expiryInDays', { days })
}

function switchTab(tab: Tab) {
  activeTab.value = tab
  selectedMembershipId.value = ''
  selectedTeamId.value = ''
  selectedLevel.value = 'view'
  expiresAt.value = ''
}

async function grantAccess() {
  const principalId = activeTab.value === 'people' ? selectedMembershipId.value : selectedTeamId.value
  if (!principalId) return
  grantLoading.value = true
  const payload: Record<string, unknown> = {
    principal_type: activeTab.value === 'people' ? 'user' : 'team',
    principal_id: principalId,
    level: selectedLevel.value,
  }
  if (expiresAt.value) payload.expires_at = expiresAt.value
  const res = await api.post<RecordGrant>(`/api/v1/crm/records/${props.recordId}/grants`, payload)
  grantLoading.value = false
  if (res.ok && res.data) {
    const idx = grants.value.findIndex(g => g.id === res.data!.id)
    if (idx >= 0) grants.value[idx] = res.data
    else grants.value.push(res.data)
    toast.success(t('permissions.shareGranted'))
    selectedMembershipId.value = ''
    selectedTeamId.value = ''
    expiresAt.value = ''
    selectedLevel.value = 'view'
  } else {
    toast.error(t('permissions.failedToShare'))
  }
}

async function changeLevel(grant: RecordGrant, newLevel: string) {
  if (grant.level === newLevel) return
  levelUpdating.value = grant.id
  const payload: Record<string, unknown> = {
    principal_type: grant.principal_type,
    principal_id: grant.principal_id,
    level: newLevel,
  }
  if (grant.expires_at) payload.expires_at = grant.expires_at
  const res = await api.post<RecordGrant>(`/api/v1/crm/records/${props.recordId}/grants`, payload)
  levelUpdating.value = null
  if (res.ok && res.data) {
    // The backend upserts by (record, principal_type, principal_id), so the returned ID may
    // differ from the local grant.id if the record was replaced. Match by original ID first,
    // then fall back to the new ID returned by the server.
    const idx = grants.value.findIndex(g => g.id === grant.id || g.id === res.data!.id)
    if (idx >= 0) grants.value[idx] = res.data
    toast.success(t('permissions.levelChanged'))
  } else {
    toast.error(t('permissions.failedToShare'))
  }
}

async function removeGrant(grantId: string) {
  const res = await api.delete(`/api/v1/crm/records/${props.recordId}/grants/${grantId}`)
  if (res.ok || res.status === 204) {
    grants.value = grants.value.filter(g => g.id !== grantId)
    toast.success(t('permissions.shareRevoked'))
  } else {
    toast.error(t('permissions.failedToRevoke'))
  }
}

function levelLabel(level: string): string {
  if (level === 'view') return t('permissions.accessView')
  if (level === 'edit') return t('permissions.accessEdit')
  return t('permissions.accessManage')
}

function levelPillClass(level: string): string {
  if (level === 'view') return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
  if (level === 'edit') return 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'
  return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'
}

function close() {
  emit('update:open', false)
}

onMounted(() => {
  if (props.open) loadData()
})

watch(() => props.open, (val) => {
  if (val) {
    activeTab.value = 'people'
    loadData()
  }
})
</script>

<template>
  <Modal :open="open" :title="t('permissions.shareRecord')" @close="close">

    <div class="space-y-4">
      <!-- Tabs -->
      <div class="flex border-b border-gray-200 dark:border-gray-700">
        <button
          v-for="tab in (['people', 'teams'] as const)"
          :key="tab"
          @click="switchTab(tab)"
          class="flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors"
          :class="activeTab === tab
            ? 'border-brand text-brand'
            : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'"
        >
          <UserPlusIcon v-if="tab === 'people'" class="h-4 w-4" />
          <UsersIcon v-else class="h-4 w-4" />
          {{ tab === 'people' ? t('permissions.tabPeople') : t('permissions.tabTeams') }}
          <span
            class="ml-1 rounded-full bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 text-xs"
            :class="activeTab === tab ? 'bg-brand/10 text-brand' : ''"
          >
            {{ tab === 'people' ? userGrants.length : teamGrants.length }}
          </span>
        </button>
      </div>

      <!-- Grant list -->
      <div>
        <div v-if="loading" class="text-sm text-gray-400 py-2">…</div>
        <template v-else>
          <div
            v-if="(activeTab === 'people' ? userGrants : teamGrants).length === 0"
            class="text-sm text-gray-400 py-2"
          >
            {{ t('permissions.noGrants') }}
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="grant in (activeTab === 'people' ? userGrants : teamGrants)"
              :key="grant.id"
              class="flex items-center justify-between rounded-lg border border-gray-100 dark:border-gray-700 px-3 py-2.5 bg-gray-50 dark:bg-gray-800"
            >
              <!-- Name + expiry badge -->
              <div class="min-w-0 flex-1 mr-3">
                <p class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {{ grantDisplayName(grant) }}
                </p>
                <div class="flex items-center gap-2 mt-0.5">
                  <!-- Expiry countdown badge -->
                  <span
                    v-if="grant.expires_at"
                    class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
                    :class="expiryBadgeClass(expiryDaysLeft(grant.expires_at))"
                  >
                    {{ expiryLabel(grant.expires_at) }}
                  </span>
                </div>
              </div>

              <!-- Inline level quick-actions -->
              <div class="flex items-center gap-1 shrink-0">
                <Tooltip
                  v-for="lvl in ['view', 'edit', 'manage'] as const"
                  :key="lvl"
                  :content="levelLabel(lvl)"
                  placement="top"
                >
                  <button
                    @click="changeLevel(grant, lvl)"
                    :disabled="levelUpdating === grant.id"
                    class="rounded px-2 py-0.5 text-xs font-medium transition-colors"
                    :class="grant.level === lvl
                      ? levelPillClass(lvl)
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'"
                  >
                    {{ levelLabel(lvl) }}
                  </button>
                </Tooltip>
                <button @click="removeGrant(grant.id)" class="ml-1 p-1 text-gray-400 hover:text-red-600 rounded">
                  <TrashIcon class="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Add new grant -->
      <div class="border-t border-gray-100 dark:border-gray-800 pt-4">
        <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{{ t('permissions.shareWith') }}</h4>
        <div class="space-y-3">
          <!-- People tab: PeoplePicker -->
          <div v-if="activeTab === 'people'">
            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('team.title') }}</label>
            <PeoplePicker
              v-model="selectedMembershipId"
              :firm-id="firmId"
              :placeholder="t('peoplePicker.placeholder')"
            />
          </div>
          <!-- Teams tab: team select -->
          <div v-else>
            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.tabTeams') }}</label>
            <select
              v-model="selectedTeamId"
              class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100"
            >
              <option value="">{{ t('permissions.selectTeam') }}</option>
              <option v-for="team in teams" :key="team.id" :value="team.id">{{ team.name }}</option>
            </select>
          </div>

          <div class="flex gap-3">
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.accessLevel') }}</label>
              <select v-model="selectedLevel" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100">
                <option value="view">{{ t('permissions.accessView') }}</option>
                <option value="edit">{{ t('permissions.accessEdit') }}</option>
                <option value="manage">{{ t('permissions.accessManage') }}</option>
              </select>
            </div>
            <div class="flex-1">
              <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('permissions.expiresAt') }}</label>
              <input v-model="expiresAt" type="date" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100" />
            </div>
          </div>
          <button
            @click="addGrant"
            :disabled="!(activeTab === 'people' ? selectedMembershipId : selectedTeamId) || grantLoading"
            class="w-full inline-flex items-center justify-center gap-2 rounded-md bg-brand px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            <UserPlusIcon class="h-4 w-4" />
            {{ t('permissions.grantAccess') }}
          </button>
        </div>
      </div>
    </div>

    <template #footer>
      <button @click="close" class="rounded-md border border-gray-300 dark:border-gray-600 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">
        {{ t('common.cancel') }}
      </button>
    </template>
  </Modal>
</template>

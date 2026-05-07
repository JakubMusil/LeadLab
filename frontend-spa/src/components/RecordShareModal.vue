<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { useFirmStore } from '@/stores/firm'
import { useMembersStore } from '@/stores/members'
import { Modal } from '@/components/ui'
import PeoplePicker from '@/components/PeoplePicker.vue'
import { UserPlusIcon, TrashIcon } from '@heroicons/vue/24/outline'

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

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

const grants = ref<RecordGrant[]>([])
const loading = ref(false)
const grantLoading = ref(false)

const selectedMembershipId = ref('')
const selectedLevel = ref<'view' | 'edit' | 'manage'>('view')
const expiresAt = ref('')

const ACCESS_LEVELS = [
  { value: 'view' as const },
  { value: 'edit' as const },
  { value: 'manage' as const },
]

async function loadData() {
  if (!props.recordId || !firmId.value) return
  loading.value = true
  try {
    await Promise.all([
      api.get<RecordGrant[]>(`/api/v1/crm/records/${props.recordId}/grants`).then((res) => {
        if (res.ok && res.data) grants.value = res.data
      }),
      membersStore.fetchMembers(firmId.value),
    ])
  } finally {
    loading.value = false
  }
}

function grantDisplayName(grant: RecordGrant): string {
  if (grant.principal_name) return grant.principal_name
  // fallback: try members store
  if (grant.principal_type === 'user') return membersStore.displayNameById(grant.principal_id)
  return grant.principal_id
}

async function addGrant() {
  if (!selectedMembershipId.value) return
  grantLoading.value = true
  const payload: Record<string, unknown> = {
    principal_type: 'user',
    principal_id: selectedMembershipId.value,
    level: selectedLevel.value,
  }
  if (expiresAt.value) payload.expires_at = expiresAt.value
  const res = await api.post<RecordGrant>(`/api/v1/crm/records/${props.recordId}/grants`, payload)
  grantLoading.value = false
  if (res.ok && res.data) {
    // upsert
    const idx = grants.value.findIndex(g => g.id === res.data!.id)
    if (idx >= 0) grants.value[idx] = res.data
    else grants.value.push(res.data)
    toast.success(t('permissions.shareGranted'))
    selectedMembershipId.value = ''
    expiresAt.value = ''
    selectedLevel.value = 'view'
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

function formatDate(date: string | null): string {
  if (!date) return '—'
  return new Date(date).toLocaleDateString()
}

function close() {
  emit('update:open', false)
}

onMounted(() => {
  if (props.open) loadData()
})

// Watch for open changes
watch(() => props.open, (val) => {
  if (val) loadData()
})
</script>

<template>
  <Modal :open="open" :title="t('permissions.shareRecord')" @close="close">

    <div class="space-y-5">
      <!-- Current grants -->
      <div>
        <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('permissions.currentAccess') }}</h4>
        <div v-if="loading" class="text-sm text-gray-400">…</div>
        <div v-else-if="grants.length === 0" class="text-sm text-gray-400">{{ t('permissions.noGrants') }}</div>
        <div v-else class="space-y-1.5">
          <div
            v-for="grant in grants"
            :key="grant.id"
            class="flex items-center justify-between rounded-md border border-gray-100 dark:border-gray-800 px-3 py-2 bg-gray-50 dark:bg-gray-800"
          >
            <div>
              <p class="text-sm font-medium text-gray-900 dark:text-gray-100">
                {{ grantDisplayName(grant) }}
                <span v-if="grant.principal_type === 'team'" class="ml-1 text-xs text-gray-400">({{ t('permissions.team') }})</span>
              </p>
              <p class="text-xs text-gray-500">
                {{ levelLabel(grant.level) }}
                <template v-if="grant.expires_at">
                  · {{ t('permissions.expiresAt') }}: {{ formatDate(grant.expires_at) }}
                </template>
              </p>
            </div>
            <button @click="removeGrant(grant.id)" class="p-1 text-gray-400 hover:text-red-600">
              <TrashIcon class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      <!-- Add new grant -->
      <div class="border-t border-gray-100 dark:border-gray-800 pt-4">
        <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">{{ t('permissions.shareWith') }}</h4>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{{ t('team.title') }}</label>
            <PeoplePicker
              v-model="selectedMembershipId"
              :firm-id="firmId"
              :placeholder="t('peoplePicker.placeholder')"
            />
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
            :disabled="!selectedMembershipId || grantLoading"
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

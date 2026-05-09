<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useFirmStore } from '@/stores/firm'
import { useMembersStore, type MemberOut } from '@/stores/members'
import { usePermissionsStore } from '@/stores/permissions'
import { useAuthStore } from '@/stores/auth'
import { useCan } from '@/composables/useCan'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'

type MembershipStatus = 'active' | 'expired'
type EntityFilter = 'all' | 'record' | 'customer' | 'proposal' | 'task' | 'other'
const USER_TIMELINE_PAGE_SIZE = 40

interface MemberGrants {
  category_grants: Array<{
    id: string
    level: string
    category_id: string
    category_name: string | null
    expires_at: string | null
  }>
  record_grants: Array<{
    id: string
    level: string
    record_id: string
    record_title: string | null
    expires_at: string | null
  }>
}

interface ActivityFeedItem {
  id: string
  entity_type: EntityFilter
  entity_id: string
  record_id: string | null
  record_title: string | null
  customer_id: string | null
  customer_name: string | null
  proposal_id: string | null
  proposal_title: string | null
  task_id: string | null
  task_title: string | null
  user_id: string | null
  type: string
  content_text: string
  metadata: Record<string, unknown>
  created_at: string
}

interface UserTimelineResponse {
  items: ActivityFeedItem[]
  total_count: number
  page: number
  page_size: number
}

const route = useRoute()
const firmStore = useFirmStore()
const membersStore = useMembersStore()
const permissionsStore = usePermissionsStore()
const authStore = useAuthStore()
const { can } = useCan()
const { t, locale } = useI18n()
const { myRole, myRoles } = storeToRefs(permissionsStore)

const loadError = ref('')
const actionError = ref('')
const actionSuccess = ref('')
const loading = ref(false)
const savingRole = ref(false)
const savingTeam = ref(false)
const grantsLoading = ref(false)
const grantsError = ref('')
const grants = ref<MemberGrants | null>(null)

const activityLoading = ref(false)
const activityError = ref('')
const activities = ref<ActivityFeedItem[]>([])
const activitiesTotalCount = ref<number | null>(null)
const activitiesNextPage = ref(1)
const activitiesHasMore = ref(true)
const activityTypeFilter = ref('all')
const activityEntityFilter = ref<EntityFilter>('all')

const roleDraft = ref('')
const expiryDraft = ref('')
const teamDraft = ref('')

const membershipId = computed(() => String(route.params.membershipId ?? ''))
const firmId = computed(() => (firmStore.activeFirm ? String(firmStore.activeFirm.id) : ''))

const currentMember = computed(() => membersStore.memberById(membershipId.value))
const isTargetExpired = computed(() => {
  if (!currentMember.value?.expires_at) return false
  return new Date(currentMember.value.expires_at) <= new Date()
})
const targetStatus = computed<MembershipStatus>(() => (isTargetExpired.value ? 'expired' : 'active'))

const isStaffOrSuperuser = computed(() => !!(authStore.user?.is_staff || authStore.user?.is_superuser))
const roleCodes = computed(() => [myRole.value, ...myRoles.value].filter(Boolean))
const hasUsersViewRole = computed(() => roleCodes.value.some((r) => ['owner', 'admin', 'manager'].includes(r)))
const canAccessUsersView = computed(() => isStaffOrSuperuser.value || hasUsersViewRole.value || can('team.manage') || can('role.manage'))

const canManageRole = computed(() => isStaffOrSuperuser.value || can('role.manage'))
const canManageTeam = computed(() => isStaffOrSuperuser.value || can('team.manage'))
const canViewGrants = computed(() => isStaffOrSuperuser.value || roleCodes.value.some((r) => ['owner', 'admin'].includes(r)))

function roleLabel(member: MemberOut): string {
  if (member.roles?.length) return member.roles.join(', ')
  return member.role
}

function formatDate(value: string | null | undefined): string {
  if (!value) return t('usersView.common.notSet')
  return new Date(value).toLocaleString(locale.value)
}

function formatDateOnly(value: string | null | undefined): string {
  if (!value) return t('usersView.common.notSet')
  return new Date(value).toLocaleDateString(locale.value)
}

function initialiseDrafts(member: MemberOut | undefined) {
  roleDraft.value = member?.role ?? ''
  const expiresAt = member?.expires_at
  const isoDatePrefix = expiresAt && /^\\d{4}-\\d{2}-\\d{2}/.test(expiresAt) ? expiresAt.slice(0, 10) : ''
  expiryDraft.value = isoDatePrefix
  teamDraft.value = member?.team_id ?? ''
}

const activityTypeOptions = computed(() => {
  const set = new Set<string>()
  for (const item of activities.value) {
    if (item.type) set.add(item.type)
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b))
})

const filteredActivities = computed(() => {
  return activities.value.filter((item) => {
    const typeOk = activityTypeFilter.value === 'all' || item.type === activityTypeFilter.value
    const entityType = item.entity_type || 'other'
    const entityOk = activityEntityFilter.value === 'all' || entityType === activityEntityFilter.value
    return typeOk && entityOk
  })
})

const teamOptions = computed(() => permissionsStore.teams)
const memberPermissions = computed(() => {
  const member = currentMember.value as (MemberOut & { permissions?: string[] }) | undefined
  return member?.permissions ?? []
})

async function loadMembersAndPermissions() {
  if (!firmId.value) return
  await Promise.all([
    permissionsStore.fetchMyPermissions(firmId.value),
    permissionsStore.fetchTeams(firmId.value),
    membersStore.fetchMembers(firmId.value, true),
  ])
}

async function loadGrants() {
  if (!firmId.value || !membershipId.value || !canViewGrants.value) {
    grants.value = null
    grantsError.value = ''
    return
  }
  grantsLoading.value = true
  grantsError.value = ''
  try {
    const res = await api.get<MemberGrants>(`/api/v1/firms/${firmId.value}/members/${membershipId.value}/grants`)
    if (res.ok && res.data) {
      grants.value = res.data
      return
    }
    grants.value = null
    grantsError.value = t('usersView.detail.errors.loadGrants')
  } catch {
    grants.value = null
    grantsError.value = t('usersView.detail.errors.loadGrants')
  } finally {
    grantsLoading.value = false
  }
}

async function loadActivityChunk() {
  if (!firmId.value || !membershipId.value || !activitiesHasMore.value) return
  activityLoading.value = true
  activityError.value = ''

  try {
    const res = await api.get<UserTimelineResponse>(
      `/api/v1/crm/reports/users/${membershipId.value}/timeline?page=${activitiesNextPage.value}&page_size=${USER_TIMELINE_PAGE_SIZE}`,
    )
    const payload = res.data
    if (!res.ok || !payload || !Array.isArray(payload.items)) {
      activityError.value = t('usersView.detail.errors.loadTimeline')
      return
    }

    activitiesTotalCount.value = typeof payload.total_count === 'number' ? payload.total_count : null
    const pageItems = payload.items
    activities.value = [...activities.value, ...pageItems]
    activitiesNextPage.value += 1
    const hasMoreByPage = pageItems.length === USER_TIMELINE_PAGE_SIZE
    const hasMoreByTotal = activitiesTotalCount.value === null || activities.value.length < activitiesTotalCount.value
    activitiesHasMore.value = hasMoreByPage && hasMoreByTotal
  } catch {
    activityError.value = t('usersView.detail.errors.loadTimeline')
  } finally {
    activityLoading.value = false
  }
}

async function reloadActivities() {
  activities.value = []
  activitiesTotalCount.value = null
  activitiesNextPage.value = 1
  activitiesHasMore.value = true
  await loadActivityChunk()
}

async function saveRoleAndExpiry() {
  if (!firmId.value || !membershipId.value || !roleDraft.value || !canManageRole.value) return
  savingRole.value = true
  actionError.value = ''
  actionSuccess.value = ''
  try {
    const payload: { role: string; expires_at?: string | null } = { role: roleDraft.value }
    const expiryValue = expiryDraft.value.trim()
    if (expiryValue) {
      const [yearStr, monthStr, dayStr] = expiryValue.split('-')
      const year = Number(yearStr)
      const month = Number(monthStr)
      const day = Number(dayStr)
      const hasValidParts = Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)
        && month >= 1 && month <= 12 && day >= 1 && day <= 31
      if (hasValidParts) {
        const date = new Date(Date.UTC(year, month - 1, day))
        const sameDate =
          date.getUTCFullYear() === year
          && date.getUTCMonth() === month - 1
          && date.getUTCDate() === day
        payload.expires_at = sameDate ? date.toISOString() : null
      } else {
        payload.expires_at = null
      }
    } else {
      payload.expires_at = null
    }
    const res = await api.patch<MemberOut>(`/api/v1/firms/${firmId.value}/members/${membershipId.value}`, payload)
    if (!res.ok || !res.data) {
      actionError.value = t('usersView.detail.errors.saveRoleExpiry')
      return
    }
    const idx = membersStore.members.findIndex((m) => m.id === membershipId.value)
    if (idx !== -1) {
      membersStore.members[idx] = res.data
    }
    initialiseDrafts(res.data)
    actionSuccess.value = t('usersView.detail.success.roleExpirySaved')
  } catch {
    actionError.value = t('usersView.detail.errors.saveRoleExpiry')
  } finally {
    savingRole.value = false
  }
}

async function saveTeam() {
  if (!firmId.value || !membershipId.value || !canManageTeam.value) return
  savingTeam.value = true
  actionError.value = ''
  actionSuccess.value = ''

  try {
    const member = currentMember.value
    if (!member) {
      actionError.value = t('usersView.detail.errors.memberNotFound')
      return
    }

    if (member.team_id) {
      const deleteRes = await api.delete(`/api/v1/firms/${firmId.value}/teams/${member.team_id}/members/${membershipId.value}`)
      if (!deleteRes.ok && deleteRes.status !== 404) {
        actionError.value = t('usersView.detail.errors.removeFromTeam')
        return
      }
    }

    if (teamDraft.value) {
      const addRes = await api.post(`/api/v1/firms/${firmId.value}/teams/${teamDraft.value}/members/${membershipId.value}`, {})
      if (!addRes.ok) {
        actionError.value = t('usersView.detail.errors.assignTeam')
        return
      }
    }

    await membersStore.fetchMembers(firmId.value, true)
    initialiseDrafts(currentMember.value)
    actionSuccess.value = t('usersView.detail.success.teamSaved')
  } catch {
    actionError.value = t('usersView.detail.errors.saveTeam')
  } finally {
    savingTeam.value = false
  }
}

async function loadAll() {
  if (!firmId.value || !membershipId.value) return
  loading.value = true
  loadError.value = ''
  actionError.value = ''
  actionSuccess.value = ''
  try {
    await loadMembersAndPermissions()
    if (!canAccessUsersView.value) return
    if (!currentMember.value) {
      loadError.value = t('usersView.detail.errors.userNotFound')
      return
    }

    initialiseDrafts(currentMember.value)
    await Promise.all([loadGrants(), reloadActivities()])
  } catch {
    loadError.value = t('usersView.detail.errors.loadDetail')
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
watch([firmId, membershipId], () => {
  void loadAll()
})
watch(currentMember, (next) => {
  if (!next) return
  initialiseDrafts(next)
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div class="space-y-1">
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">{{ t('usersView.detail.title') }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ t('usersView.detail.subtitle') }}</p>
      </div>
      <RouterLink to="/app/users" class="text-sm text-brand hover:underline">
        {{ t('usersView.detail.backToList') }}
      </RouterLink>
    </header>

    <div
      v-if="!canAccessUsersView"
      class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"
    >
      {{ t('usersView.detail.noAccess') }}
    </div>

    <template v-else>
      <div v-if="loadError" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        {{ loadError }}
      </div>

      <div v-if="loading" class="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400">
        {{ t('usersView.detail.loadingDetail') }}
      </div>

      <template v-else-if="currentMember">
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <section class="lg:col-span-2 space-y-4">
            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <div class="flex flex-wrap items-center gap-2">
                <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('usersView.detail.timeline.title') }}</h2>
                <span class="text-xs px-2 py-0.5 rounded-full"
                  :class="targetStatus === 'expired' ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300' : 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300'"
                >
                  {{ targetStatus === 'expired' ? t('usersView.detail.memberStatus.expired') : t('usersView.detail.memberStatus.active') }}
                </span>
              </div>

              <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <select
                  v-model="activityTypeFilter"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                >
                  <option value="all">{{ t('usersView.detail.timeline.filters.allActivityTypes') }}</option>
                  <option v-for="type in activityTypeOptions" :key="type" :value="type">{{ type }}</option>
                </select>

                <select
                  v-model="activityEntityFilter"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                >
                  <option value="all">{{ t('usersView.detail.timeline.filters.allEntities') }}</option>
                  <option value="record">{{ t('usersView.detail.timeline.entities.record') }}</option>
                  <option value="customer">{{ t('usersView.detail.timeline.entities.customer') }}</option>
                  <option value="proposal">{{ t('usersView.detail.timeline.entities.proposal') }}</option>
                  <option value="task">{{ t('usersView.detail.timeline.entities.task') }}</option>
                  <option value="other">{{ t('usersView.detail.timeline.entities.other') }}</option>
                </select>
              </div>

              <div v-if="activityError" class="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
                {{ activityError }}
              </div>

              <div class="mt-3 divide-y divide-gray-100 dark:divide-gray-800">
                <div
                  v-for="item in filteredActivities"
                  :key="item.id"
                  class="py-3"
                >
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <p class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ item.type }}</p>
                    <span class="text-xs text-gray-400 dark:text-gray-500">{{ formatDate(item.created_at) }}</span>
                  </div>
                  <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">{{ item.content_text || t('usersView.common.notSet') }}</p>
                  <RouterLink
                    v-if="item.record_id"
                    :to="`/app/records/${item.record_id}`"
                    class="mt-1 inline-block text-xs text-brand hover:underline"
                  >
                    {{ t('usersView.detail.timeline.openRecord', { record: item.record_title || item.record_id }) }}
                  </RouterLink>
                  <RouterLink
                    v-else-if="item.customer_id"
                    :to="`/app/directory/${item.customer_id}`"
                    class="mt-1 inline-block text-xs text-brand hover:underline"
                  >
                    {{ t('usersView.detail.timeline.openCustomer', { customer: item.customer_name || item.customer_id }) }}
                  </RouterLink>
                  <RouterLink
                    v-else-if="item.proposal_id"
                    :to="`/app/proposals/${item.proposal_id}`"
                    class="mt-1 inline-block text-xs text-brand hover:underline"
                  >
                    {{ t('usersView.detail.timeline.openProposal', { proposal: item.proposal_title || item.proposal_id }) }}
                  </RouterLink>
                  <RouterLink
                    v-else-if="item.task_id"
                    :to="`/app/tasks/${item.task_id}`"
                    class="mt-1 inline-block text-xs text-brand hover:underline"
                  >
                    {{ t('usersView.detail.timeline.openTask', { task: item.task_title || item.task_id }) }}
                  </RouterLink>
                </div>

                <div v-if="!activityLoading && filteredActivities.length === 0" class="py-6 text-sm text-gray-500 dark:text-gray-400">
                  {{ t('usersView.detail.timeline.empty') }}
                </div>

                <div v-if="activityLoading" class="py-4 text-sm text-gray-500 dark:text-gray-400">{{ t('usersView.detail.timeline.loading') }}</div>
              </div>

              <div class="mt-4">
                <button
                  v-if="activitiesHasMore"
                  class="rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  :disabled="activityLoading"
                  @click="loadActivityChunk"
                >
                  {{ activityLoading ? t('usersView.detail.timeline.loadingMore') : t('usersView.detail.timeline.loadMore') }}
                </button>
                <p
                  v-if="activitiesTotalCount !== null && activities.length > 0"
                  class="mt-2 text-xs text-gray-500 dark:text-gray-400"
                >
                  {{ t('usersView.detail.timeline.loadedCount', { loaded: activities.length, total: activitiesTotalCount }) }}
                </p>
              </div>
            </div>
          </section>

          <aside class="space-y-4">
            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('usersView.detail.profile.title') }}</h2>
              <dl class="mt-3 space-y-2 text-sm">
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">{{ t('usersView.detail.profile.name') }}</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ currentMember.user_full_name || t('usersView.common.notSet') }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">{{ t('usersView.detail.profile.email') }}</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ currentMember.user_email }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">{{ t('usersView.detail.profile.role') }}</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ roleLabel(currentMember) }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">{{ t('usersView.detail.profile.team') }}</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ currentMember.team_name || t('usersView.common.notSet') }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">{{ t('usersView.detail.profile.expiry') }}</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ formatDateOnly(currentMember.expires_at) }}</dd>
                </div>
              </dl>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('usersView.detail.actions.title') }}</h2>

              <div class="mt-3 space-y-2">
                <label class="block text-xs text-gray-500 dark:text-gray-400">{{ t('usersView.detail.actions.role') }}</label>
                <input
                  v-model="roleDraft"
                  type="text"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  :disabled="!canManageRole || currentMember.role === 'owner'"
                />

                <label class="block text-xs text-gray-500 dark:text-gray-400">{{ t('usersView.detail.actions.expiry') }}</label>
                <input
                  v-model="expiryDraft"
                  type="date"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  :disabled="!canManageRole || currentMember.role === 'owner'"
                />

                <button
                  class="w-full rounded-lg bg-brand px-3 py-2 text-xs font-medium text-white disabled:opacity-60"
                  :disabled="!canManageRole || currentMember.role === 'owner' || savingRole"
                  @click="saveRoleAndExpiry"
                >
                  {{ savingRole ? t('usersView.detail.actions.saving') : t('usersView.detail.actions.saveRoleExpiry') }}
                </button>
              </div>

              <div class="mt-4 space-y-2">
                <label class="block text-xs text-gray-500 dark:text-gray-400">{{ t('usersView.detail.actions.team') }}</label>
                <select
                  v-model="teamDraft"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  :disabled="!canManageTeam || savingTeam"
                >
                  <option value="">{{ t('usersView.detail.actions.noTeam') }}</option>
                  <option v-for="team in teamOptions" :key="team.id" :value="team.id">{{ team.name }}</option>
                </select>

                <button
                  class="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 disabled:opacity-60 dark:border-gray-700 dark:text-gray-200"
                  :disabled="!canManageTeam || savingTeam"
                  @click="saveTeam"
                >
                  {{ savingTeam ? t('usersView.detail.actions.saving') : t('usersView.detail.actions.saveTeam') }}
                </button>
              </div>

              <p v-if="actionSuccess" class="mt-3 text-xs text-green-700 dark:text-green-400">{{ actionSuccess }}</p>
              <p v-if="actionError" class="mt-3 text-xs text-red-700 dark:text-red-400">{{ actionError }}</p>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('usersView.detail.permissionsSnapshot.title') }}</h2>
              <div class="mt-2 flex flex-wrap gap-1">
                <span
                  v-for="perm in memberPermissions"
                  :key="perm"
                  class="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-200"
                >
                  {{ perm }}
                </span>
                <span
                  v-if="memberPermissions.length === 0"
                  class="text-xs text-gray-400 dark:text-gray-500"
                >
                  {{ t('usersView.detail.permissionsSnapshot.empty') }}
                </span>
              </div>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ t('usersView.detail.grantsSnapshot.title') }}</h2>

              <p v-if="!canViewGrants" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
                {{ t('usersView.detail.grantsSnapshot.noAccess') }}
              </p>
              <p v-else-if="grantsLoading" class="mt-2 text-xs text-gray-500 dark:text-gray-400">{{ t('usersView.detail.grantsSnapshot.loading') }}</p>
              <p v-else-if="grantsError" class="mt-2 text-xs text-red-700 dark:text-red-400">{{ grantsError }}</p>
              <div v-else-if="grants" class="mt-2 space-y-2 text-xs">
                <div>
                  <p class="font-medium text-gray-700 dark:text-gray-200">
                    {{ t('usersView.detail.grantsSnapshot.categoryGrants', { count: grants.category_grants.length }) }}
                  </p>
                  <ul class="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                    <li v-for="g in grants.category_grants" :key="g.id">
                      {{ g.category_name || g.category_id }} · {{ g.level }}
                    </li>
                  </ul>
                </div>
                <div>
                  <p class="font-medium text-gray-700 dark:text-gray-200">
                    {{ t('usersView.detail.grantsSnapshot.recordGrants', { count: grants.record_grants.length }) }}
                  </p>
                  <ul class="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                    <li v-for="g in grants.record_grants" :key="g.id">
                      {{ g.record_title || g.record_id }} · {{ g.level }}
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </template>
    </template>
  </div>
</template>

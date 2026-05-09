<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useFirmStore } from '@/stores/firm'
import { useMembersStore, type MemberOut } from '@/stores/members'
import { usePermissionsStore } from '@/stores/permissions'
import { useAuthStore } from '@/stores/auth'
import { useCan } from '@/composables/useCan'
import { api } from '@/api'

type MembershipStatus = 'active' | 'expired'
type EntityFilter = 'all' | 'record' | 'customer' | 'proposal' | 'task' | 'other'

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
  record_id: string | null
  record_title: string | null
  user_id: string | null
  type: string
  content_text: string
  metadata: Record<string, unknown>
  created_at: string
}

const route = useRoute()
const firmStore = useFirmStore()
const membersStore = useMembersStore()
const permissionsStore = usePermissionsStore()
const authStore = useAuthStore()
const { can } = useCan()
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
  if (!value) return '—'
  return new Date(value).toLocaleString('cs-CZ')
}

function formatDateOnly(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('cs-CZ')
}

function initialiseDrafts(member: MemberOut | undefined) {
  roleDraft.value = member?.role ?? ''
  const expiresAt = member?.expires_at
  expiryDraft.value = expiresAt && expiresAt.trim() ? expiresAt.slice(0, 10) : ''
  teamDraft.value = member?.team_id ?? ''
}

function detectEntityType(item: ActivityFeedItem): EntityFilter {
  if (item.record_id) return 'record'
  if (item.metadata?.customer_id) return 'customer'
  if (item.metadata?.proposal_id) return 'proposal'
  if (item.metadata?.task_id) return 'task'
  return 'other'
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
    const entityType = detectEntityType(item)
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
    grantsError.value = 'Nepodařilo se načíst grants.'
  } catch {
    grants.value = null
    grantsError.value = 'Nepodařilo se načíst grants.'
  } finally {
    grantsLoading.value = false
  }
}

async function loadActivityChunk() {
  if (!firmId.value || !currentMember.value?.user_id || !activitiesHasMore.value) return
  activityLoading.value = true
  activityError.value = ''

  const pageSize = 100
  const maxPagesPerChunk = 3
  const startPage = activitiesNextPage.value
  const requests: Array<Promise<Awaited<ReturnType<typeof api.get<ActivityFeedItem[]>>>>> = []

  try {
    for (let page = startPage; page < startPage + maxPagesPerChunk; page += 1) {
      requests.push(api.get<ActivityFeedItem[]>(`/api/v1/crm/reports/activities?page=${page}&page_size=${pageSize}`))
    }

    const responses = await Promise.all(requests)
    const targetUserId = currentMember.value.user_id
    const chunk: ActivityFeedItem[] = []
    let reachedEnd = false

    for (const res of responses) {
      if (!res.ok || !Array.isArray(res.data)) {
        activityError.value = 'Nepodařilo se načíst timeline aktivit.'
        break
      }

      const pageItems = res.data
      const matchedItems = pageItems.filter((item) => item.user_id === targetUserId)
      chunk.push(...matchedItems)
      if (pageItems.length < pageSize) {
        reachedEnd = true
        break
      }
    }

    if (!activityError.value) {
      activities.value = [...activities.value, ...chunk]
      activitiesNextPage.value = startPage + responses.length
      activitiesHasMore.value = !reachedEnd
    }
  } catch {
    activityError.value = 'Nepodařilo se načíst timeline aktivit.'
  } finally {
    activityLoading.value = false
  }
}

async function reloadActivities() {
  activities.value = []
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
      payload.expires_at = Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)
        ? new Date(Date.UTC(year, month - 1, day)).toISOString()
        : null
    } else {
      payload.expires_at = null
    }
    const res = await api.patch<MemberOut>(`/api/v1/firms/${firmId.value}/members/${membershipId.value}`, payload)
    if (!res.ok || !res.data) {
      actionError.value = 'Uložení role/expirace selhalo.'
      return
    }
    const idx = membersStore.members.findIndex((m) => m.id === membershipId.value)
    if (idx !== -1) {
      membersStore.members[idx] = res.data
    }
    initialiseDrafts(res.data)
    actionSuccess.value = 'Role a expirace byly uloženy.'
  } catch {
    actionError.value = 'Uložení role/expirace selhalo.'
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
      actionError.value = 'Člen nebyl nalezen.'
      return
    }

    if (member.team_id) {
      const deleteRes = await api.delete(`/api/v1/firms/${firmId.value}/teams/${member.team_id}/members/${membershipId.value}`)
      if (!deleteRes.ok && deleteRes.status !== 404) {
        actionError.value = 'Uložení týmu selhalo.'
        return
      }
    }

    if (teamDraft.value) {
      const addRes = await api.post(`/api/v1/firms/${firmId.value}/teams/${teamDraft.value}/members/${membershipId.value}`, {})
      if (!addRes.ok) {
        actionError.value = 'Uložení týmu selhalo.'
        return
      }
    }

    await membersStore.fetchMembers(firmId.value, true)
    initialiseDrafts(currentMember.value)
    actionSuccess.value = 'Tým byl uložen.'
  } catch {
    actionError.value = 'Uložení týmu selhalo.'
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
      loadError.value = 'Uživatel nebyl nalezen.'
      return
    }

    initialiseDrafts(currentMember.value)
    await Promise.all([loadGrants(), reloadActivities()])
  } catch {
    loadError.value = 'Nepodařilo se načíst detail uživatele.'
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
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">User detail</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">Detail člena firmy a jeho aktivit</p>
      </div>
      <RouterLink to="/app/users" class="text-sm text-brand hover:underline">← Zpět na users list</RouterLink>
    </header>

    <div
      v-if="!canAccessUsersView"
      class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300"
    >
      Pro zobrazení detailu uživatele nemáte oprávnění.
    </div>

    <template v-else>
      <div v-if="loadError" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-300">
        {{ loadError }}
      </div>

      <div v-if="loading" class="rounded-xl border border-gray-200 bg-white p-6 text-sm text-gray-500 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400">
        Načítám detail uživatele…
      </div>

      <template v-else-if="currentMember">
        <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <section class="lg:col-span-2 space-y-4">
            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <div class="flex flex-wrap items-center gap-2">
                <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Timeline aktivit</h2>
                <span class="text-xs px-2 py-0.5 rounded-full"
                  :class="targetStatus === 'expired' ? 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-300' : 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-300'"
                >
                  {{ targetStatus === 'expired' ? 'Expirovaný člen' : 'Aktivní člen' }}
                </span>
              </div>

              <p class="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Timeline je aktuálně čtena z endpointu report aktivit, proto může obsahovat hlavně záznamy navázané na records.
              </p>

              <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <select
                  v-model="activityTypeFilter"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                >
                  <option value="all">Všechny typy aktivit</option>
                  <option v-for="type in activityTypeOptions" :key="type" :value="type">{{ type }}</option>
                </select>

                <select
                  v-model="activityEntityFilter"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                >
                  <option value="all">Všechny entity</option>
                  <option value="record">Record</option>
                  <option value="customer">Customer</option>
                  <option value="proposal">Proposal</option>
                  <option value="task">Task</option>
                  <option value="other">Other</option>
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
                  <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">{{ item.content_text || '—' }}</p>
                  <RouterLink
                    v-if="item.record_id"
                    :to="`/app/records/${item.record_id}`"
                    class="mt-1 inline-block text-xs text-brand hover:underline"
                  >
                    Otevřít record: {{ item.record_title || item.record_id }}
                  </RouterLink>
                </div>

                <div v-if="!activityLoading && filteredActivities.length === 0" class="py-6 text-sm text-gray-500 dark:text-gray-400">
                  Pro tohoto uživatele nebyly nalezeny žádné aktivity.
                </div>

                <div v-if="activityLoading" class="py-4 text-sm text-gray-500 dark:text-gray-400">Načítám aktivity…</div>
              </div>

              <div class="mt-4">
                <button
                  v-if="activitiesHasMore"
                  class="rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  :disabled="activityLoading"
                  @click="loadActivityChunk"
                >
                  {{ activityLoading ? 'Načítám…' : 'Načíst další aktivity' }}
                </button>
              </div>
            </div>
          </section>

          <aside class="space-y-4">
            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Profil člena</h2>
              <dl class="mt-3 space-y-2 text-sm">
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">Jméno</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ currentMember.user_full_name || '—' }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">Email</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ currentMember.user_email }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">Role</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ roleLabel(currentMember) }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">Tým</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ currentMember.team_name || '—' }}</dd>
                </div>
                <div class="flex justify-between gap-3">
                  <dt class="text-gray-500 dark:text-gray-400">Expirace</dt>
                  <dd class="text-right text-gray-900 dark:text-gray-100">{{ formatDateOnly(currentMember.expires_at) }}</dd>
                </div>
              </dl>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Akce podle oprávnění</h2>

              <div class="mt-3 space-y-2">
                <label class="block text-xs text-gray-500 dark:text-gray-400">Role</label>
                <input
                  v-model="roleDraft"
                  type="text"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  :disabled="!canManageRole || currentMember.role === 'owner'"
                />

                <label class="block text-xs text-gray-500 dark:text-gray-400">Expirace</label>
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
                  {{ savingRole ? 'Ukládám…' : 'Uložit roli a expiraci' }}
                </button>
              </div>

              <div class="mt-4 space-y-2">
                <label class="block text-xs text-gray-500 dark:text-gray-400">Tým</label>
                <select
                  v-model="teamDraft"
                  class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                  :disabled="!canManageTeam || savingTeam"
                >
                  <option value="">Bez týmu</option>
                  <option v-for="team in teamOptions" :key="team.id" :value="team.id">{{ team.name }}</option>
                </select>

                <button
                  class="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 disabled:opacity-60 dark:border-gray-700 dark:text-gray-200"
                  :disabled="!canManageTeam || savingTeam"
                  @click="saveTeam"
                >
                  {{ savingTeam ? 'Ukládám…' : 'Uložit tým' }}
                </button>
              </div>

              <p v-if="actionSuccess" class="mt-3 text-xs text-green-700 dark:text-green-400">{{ actionSuccess }}</p>
              <p v-if="actionError" class="mt-3 text-xs text-red-700 dark:text-red-400">{{ actionError }}</p>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Permissions snapshot</h2>
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
                  Žádná explicitní permission.
                </span>
              </div>
            </div>

            <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-800 dark:bg-gray-950">
              <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Scope / grants snapshot</h2>

              <p v-if="!canViewGrants" class="mt-2 text-xs text-gray-500 dark:text-gray-400">
                Pro detail grants je potřeba role owner/admin.
              </p>
              <p v-else-if="grantsLoading" class="mt-2 text-xs text-gray-500 dark:text-gray-400">Načítám grants…</p>
              <p v-else-if="grantsError" class="mt-2 text-xs text-red-700 dark:text-red-400">{{ grantsError }}</p>
              <div v-else-if="grants" class="mt-2 space-y-2 text-xs">
                <div>
                  <p class="font-medium text-gray-700 dark:text-gray-200">Category grants ({{ grants.category_grants.length }})</p>
                  <ul class="mt-1 space-y-1 text-gray-500 dark:text-gray-400">
                    <li v-for="g in grants.category_grants" :key="g.id">
                      {{ g.category_name || g.category_id }} · {{ g.level }}
                    </li>
                  </ul>
                </div>
                <div>
                  <p class="font-medium text-gray-700 dark:text-gray-200">Record grants ({{ grants.record_grants.length }})</p>
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

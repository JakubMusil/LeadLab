<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePermissionsStore } from '@/stores/permissions'
import { useMembersStore } from '@/stores/members'
import { useI18n } from '@/composables/useI18n'
import { Tooltip } from '@/components/ui'
import { ArrowDownTrayIcon } from '@heroicons/vue/24/outline'

const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const membersStore = useMembersStore()
const { t } = useI18n()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')
const loading = ref(false)

// ─── Data loading ────────────────────────────────────────────────────────────

onMounted(async () => {
  if (!firmId.value) return
  loading.value = true
  try {
    await Promise.all([
      membersStore.fetchMembers(firmId.value),
      permissionsStore.fetchCatalogue(firmId.value),
      permissionsStore.fetchRoles(firmId.value),
    ])
  } finally {
    loading.value = false
  }
})

// ─── Derived data ─────────────────────────────────────────────────────────────

/** Sorted list of unique permission groups from catalogue */
const groups = computed<string[]>(() => {
  return Object.keys(permissionsStore.catalogueByGroup).sort()
})

/** Map: role code → set of permission codes it grants */
const rolePermMap = computed<Map<string, Set<string>>>(() => {
  const map = new Map<string, Set<string>>()
  for (const role of permissionsStore.roles) {
    map.set(role.code, new Set(role.permissions))
  }
  return map
})

/** Map: permission code → group */
const permGroupMap = computed<Map<string, string>>(() => {
  const map = new Map<string, string>()
  for (const [group, items] of Object.entries(permissionsStore.catalogueByGroup)) {
    for (const item of items) {
      map.set(item.code, group)
    }
  }
  return map
})

/** All permission codes per group from the catalogue */
const groupPermCodes = computed<Map<string, string[]>>(() => {
  const map = new Map<string, string[]>()
  for (const [group, items] of Object.entries(permissionsStore.catalogueByGroup)) {
    map.set(group, items.map(i => i.code))
  }
  return map
})

interface MemberRow {
  id: string
  name: string
  email: string
  roleCodes: string[]
  effectivePerms: Set<string>
}

/** Compute effective permissions per member from their role codes */
const memberRows = computed<MemberRow[]>(() => {
  return membersStore.members.map(m => {
    const perms = new Set<string>()
    for (const code of m.roles) {
      const rolePerms = rolePermMap.value.get(code)
      if (rolePerms) {
        for (const p of rolePerms) perms.add(p)
      }
    }
    return {
      id: m.id,
      name: m.user_full_name?.trim() || m.user_email,
      email: m.user_email,
      roleCodes: m.roles,
      effectivePerms: perms,
    }
  })
})

/** Coverage type for a cell: 'full' | 'partial' | 'none' */
function cellCoverage(member: MemberRow, group: string): 'full' | 'partial' | 'none' {
  const codes = groupPermCodes.value.get(group) ?? []
  if (codes.length === 0) return 'none'
  const count = codes.filter(c => member.effectivePerms.has(c)).length
  if (count === 0) return 'none'
  if (count === codes.length) return 'full'
  return 'partial'
}

function cellClass(coverage: 'full' | 'partial' | 'none'): string {
  if (coverage === 'full') return 'bg-green-100 text-green-700 font-semibold'
  if (coverage === 'partial') return 'bg-amber-100 text-amber-700'
  return 'bg-gray-50 text-gray-300'
}

function cellLabel(coverage: 'full' | 'partial' | 'none'): string {
  if (coverage === 'full') return '✓'
  if (coverage === 'partial') return '~'
  return '–'
}

function cellTooltip(member: MemberRow, group: string): string {
  const codes = groupPermCodes.value.get(group) ?? []
  const granted = codes.filter(c => member.effectivePerms.has(c))
  const denied = codes.filter(c => !member.effectivePerms.has(c))
  const parts: string[] = []
  if (granted.length) parts.push(`✓ ${granted.join(', ')}`)
  if (denied.length) parts.push(`✗ ${denied.join(', ')}`)
  return parts.join(' | ')
}

// ─── Insights ────────────────────────────────────────────────────────────────

/** Most-used custom role: the role code appearing most across all members */
const mostUsedCustomRole = computed<{ code: string; count: number } | null>(() => {
  const customRoleCodes = new Set(
    permissionsStore.roles.filter(r => !r.is_system).map(r => r.code)
  )
  const freq = new Map<string, number>()
  for (const m of membersStore.members) {
    for (const code of m.roles) {
      if (customRoleCodes.has(code)) {
        freq.set(code, (freq.get(code) ?? 0) + 1)
      }
    }
  }
  if (freq.size === 0) return null
  let best = ''
  let bestCount = 0
  for (const [code, count] of freq) {
    if (count > bestCount) { bestCount = count; best = code }
  }
  return { code: best, count: bestCount }
})

/** Members with no roles assigned */
const membersWithNoRoles = computed<MemberRow[]>(() =>
  memberRows.value.filter(m => m.roleCodes.length === 0)
)

/** Permission groups where no member has any coverage */
const uncoveredGroups = computed<string[]>(() =>
  groups.value.filter(g =>
    memberRows.value.every(m => cellCoverage(m, g) === 'none')
  )
)

/** Pre-computed coverage matrix: heatmapData[memberIdx][groupIdx] = 'full'|'partial'|'none' */
const heatmapData = computed<Array<Array<'full' | 'partial' | 'none'>>>(() => {
  return memberRows.value.map(m =>
    groups.value.map(g => cellCoverage(m, g))
  )
})

function exportCsv() {
  const headers = [t('permissions.overviewCsvName'), t('permissions.overviewCsvEmail'), ...groups.value]
  const rows = memberRows.value.map((m, mIdx) => {
    const cells = heatmapData.value[mIdx].map(cov =>
      cov === 'full' ? 'full' : cov === 'partial' ? 'partial' : '-'
    )
    return [m.name, m.email, ...cells]
  })
  const csv = [headers, ...rows]
    .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `permissions-overview.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="space-y-6">

    <!-- Header row -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-semibold text-gray-900">{{ t('permissions.overviewTitle') }}</h2>
        <p class="text-sm text-gray-500 mt-0.5">{{ t('permissions.overviewHint') }}</p>
      </div>
      <button
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition-colors"
        @click="exportCsv"
      >
        <ArrowDownTrayIcon class="w-4 h-4" />
        {{ t('permissions.overviewExportCsv') }}
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 4" :key="i" class="h-9 bg-gray-100 rounded-lg animate-pulse" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="memberRows.length === 0 || groups.length === 0"
      class="text-center py-12 text-gray-400 text-sm"
    >
      {{ t('permissions.overviewEmpty') }}
    </div>

    <!-- Heatmap table -->
    <div v-else class="overflow-x-auto rounded-xl border border-gray-100">
      <table class="w-full text-sm border-collapse">
        <thead>
          <tr class="bg-gray-50">
            <th class="text-left px-4 py-2 font-semibold text-gray-700 sticky left-0 bg-gray-50 border-b border-gray-100 min-w-[180px]">
              {{ t('permissions.overviewMember') }}
            </th>
            <th
              v-for="group in groups"
              :key="group"
              class="px-3 py-2 font-semibold text-gray-600 border-b border-gray-100 text-center capitalize whitespace-nowrap"
            >
              {{ group }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(member, mIdx) in memberRows"
            :key="member.id"
            class="group hover:bg-gray-50 border-b border-gray-50 last:border-0"
          >
            <!-- Member name cell (sticky – stays white, follows row hover via group-hover) -->
            <td class="px-4 py-2 sticky left-0 bg-white group-hover:bg-gray-50 font-medium text-gray-900 max-w-[220px] truncate border-r border-gray-100">
              <div class="truncate" :title="member.name">{{ member.name }}</div>
              <div class="text-xs text-gray-400 truncate">{{ member.email }}</div>
            </td>
            <!-- Coverage cells (use pre-computed matrix to avoid triple call per cell) -->
            <td
              v-for="(group, gIdx) in groups"
              :key="group"
              class="px-3 py-2 text-center"
            >
              <Tooltip :content="cellTooltip(member, group)" placement="top">
                <span
                  class="inline-block w-8 h-6 leading-6 rounded text-xs cursor-default"
                  :class="cellClass(heatmapData[mIdx][gIdx])"
                >
                  {{ cellLabel(heatmapData[mIdx][gIdx]) }}
                </span>
              </Tooltip>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Legend -->
    <div v-if="!loading && memberRows.length > 0" class="flex items-center gap-4 text-xs text-gray-500">
      <span class="flex items-center gap-1">
        <span class="inline-block w-5 h-4 bg-green-100 rounded text-center text-green-700 font-semibold leading-4">✓</span>
        {{ t('permissions.overviewLegendFull') }}
      </span>
      <span class="flex items-center gap-1">
        <span class="inline-block w-5 h-4 bg-amber-100 rounded text-center text-amber-700 leading-4">~</span>
        {{ t('permissions.overviewLegendPartial') }}
      </span>
      <span class="flex items-center gap-1">
        <span class="inline-block w-5 h-4 bg-gray-50 rounded text-center text-gray-300 leading-4">–</span>
        {{ t('permissions.overviewLegendNone') }}
      </span>
    </div>

    <!-- Insights section -->
    <div v-if="!loading && memberRows.length > 0" class="grid grid-cols-1 sm:grid-cols-3 gap-4">

      <!-- Most-used custom role -->
      <div class="bg-white rounded-xl border border-gray-100 p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          {{ t('permissions.overviewInsightTopRole') }}
        </p>
        <div v-if="mostUsedCustomRole" class="text-sm text-gray-900">
          <span class="font-semibold text-indigo-600">{{ mostUsedCustomRole.code }}</span>
          <span class="text-gray-400 ml-1">
            ({{ mostUsedCustomRole.count }}×)
          </span>
        </div>
        <div v-else class="text-sm text-gray-400 italic">
          {{ t('permissions.overviewInsightNoCustomRoles') }}
        </div>
      </div>

      <!-- Members with no roles -->
      <div class="bg-white rounded-xl border border-gray-100 p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          {{ t('permissions.overviewInsightNoRoles') }}
        </p>
        <div v-if="membersWithNoRoles.length > 0" class="space-y-1">
          <div
            v-for="m in membersWithNoRoles"
            :key="m.id"
            class="text-sm text-amber-700 truncate"
            :title="m.email"
          >
            {{ m.name }}
          </div>
        </div>
        <div v-else class="text-sm text-green-600">
          {{ t('permissions.overviewInsightAllHaveRoles') }}
        </div>
      </div>

      <!-- Uncovered permission groups -->
      <div class="bg-white rounded-xl border border-gray-100 p-4">
        <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
          {{ t('permissions.overviewInsightUncovered') }}
        </p>
        <div v-if="uncoveredGroups.length > 0" class="flex flex-wrap gap-1">
          <span
            v-for="g in uncoveredGroups"
            :key="g"
            class="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs capitalize"
          >{{ g }}</span>
        </div>
        <div v-else class="text-sm text-green-600">
          {{ t('permissions.overviewInsightAllCovered') }}
        </div>
      </div>

    </div>

  </div>
</template>

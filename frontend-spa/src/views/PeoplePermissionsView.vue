<script setup lang="ts">
/**
 * PeoplePermissionsView — Unified "People & permissions" page.
 *
 * Consolidates what previously lived in five different places:
 *   - TeamView                       → "Members" tab
 *   - Settings → Roles               → "Account types" tab
 *   - Settings → Teams               → "Teams" tab
 *   - Settings → Permissions overview → Advanced › "Overview"
 *   - Settings → Audit log           → Advanced › "Audit"
 *
 * Hierarchy goes from frequent (Members) → less frequent (Account types,
 * Teams) → rare diagnostic tabs collapsed under "Advanced".
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useFirmStore } from '@/stores/firm'
import { usePermissionsStore } from '@/stores/permissions'
import { useI18n } from '@/composables/useI18n'
import {
  UsersIcon,
  IdentificationIcon,
  UserGroupIcon,
  ChartBarIcon,
  ClipboardDocumentListIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/vue/24/outline'

import TeamView from '@/views/TeamView.vue'
import RolesSettingsView from '@/views/RolesSettingsView.vue'
import TeamsSettingsView from '@/views/TeamsSettingsView.vue'
import PermissionsOverviewView from '@/views/PermissionsOverviewView.vue'
import AuditLogSettingsView from '@/views/AuditLogSettingsView.vue'

const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const { t } = useI18n()
const route = useRoute()
const router = useRouter()

type SubTab = 'members' | 'accountTypes' | 'teams' | 'overview' | 'audit'

const VALID_TABS: SubTab[] = ['members', 'accountTypes', 'teams', 'overview', 'audit']
const ADVANCED_TABS: SubTab[] = ['overview', 'audit']

function readTabFromQuery(): SubTab {
  const q = route.query.section
  if (typeof q === 'string' && (VALID_TABS as string[]).includes(q)) {
    return q as SubTab
  }
  return 'members'
}

const activeTab = ref<SubTab>(readTabFromQuery())
const advancedOpen = ref(ADVANCED_TABS.includes(activeTab.value))

watch(() => route.query.section, () => {
  const next = readTabFromQuery()
  if (next !== activeTab.value) {
    activeTab.value = next
    if (ADVANCED_TABS.includes(next)) advancedOpen.value = true
  }
})

function selectTab(tab: SubTab) {
  activeTab.value = tab
  if (route.query.section !== tab) {
    router.replace({ query: { ...route.query, section: tab } })
  }
}

interface NavItem {
  key: SubTab
  label: string
  icon: typeof UsersIcon
}

const mainItems = computed<NavItem[]>(() => [
  { key: 'members', label: t('permissions.subnavMembers'), icon: UsersIcon },
  { key: 'accountTypes', label: t('permissions.subnavAccountTypes'), icon: IdentificationIcon },
  { key: 'teams', label: t('permissions.subnavTeams'), icon: UserGroupIcon },
])

const advancedItems = computed<NavItem[]>(() => [
  { key: 'overview', label: t('permissions.subnavOverview'), icon: ChartBarIcon },
  { key: 'audit', label: t('permissions.subnavAudit'), icon: ClipboardDocumentListIcon },
])

onMounted(async () => {
  // Make sure we have a snapshot of permissions / roles / teams loaded so
  // every embedded sub-view sees consistent state.
  if (firmStore.activeFirm) {
    await permissionsStore.init(String(firmStore.activeFirm.id))
  }
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <!-- Page header -->
    <header class="mb-6">
      <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
        {{ t('nav.people') }}
      </h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400 max-w-3xl">
        {{ t('permissions.intro') }}
      </p>
    </header>

    <div class="grid grid-cols-1 md:grid-cols-[220px_1fr] gap-6">
      <!-- Sub-navigation sidebar -->
      <nav aria-label="People & permissions navigation" class="space-y-1">
        <button
          v-for="item in mainItems"
          :key="item.key"
          type="button"
          @click="selectTab(item.key)"
          class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors"
          :class="activeTab === item.key
            ? 'bg-brand/10 text-brand font-medium'
            : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'"
          :aria-current="activeTab === item.key ? 'page' : undefined"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
          <span class="flex-1 text-left">{{ item.label }}</span>
        </button>

        <!-- Advanced expander -->
        <div class="pt-2">
          <button
            type="button"
            @click="advancedOpen = !advancedOpen"
            class="w-full flex items-center gap-2 px-3 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wide hover:text-gray-600 dark:hover:text-gray-200"
            :aria-expanded="advancedOpen"
          >
            <ChevronDownIcon v-if="advancedOpen" class="h-3.5 w-3.5" />
            <ChevronRightIcon v-else class="h-3.5 w-3.5" />
            {{ t('permissions.subnavAdvanced') }}
          </button>
          <div v-if="advancedOpen" class="mt-1 space-y-1">
            <button
              v-for="item in advancedItems"
              :key="item.key"
              type="button"
              @click="selectTab(item.key)"
              class="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors"
              :class="activeTab === item.key
                ? 'bg-brand/10 text-brand font-medium'
                : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'"
              :aria-current="activeTab === item.key ? 'page' : undefined"
            >
              <component :is="item.icon" class="h-4 w-4 shrink-0" aria-hidden="true" />
              <span class="flex-1 text-left">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </nav>

      <!-- Active section -->
      <section>
        <TeamView v-if="activeTab === 'members'" />
        <RolesSettingsView v-else-if="activeTab === 'accountTypes'" />
        <TeamsSettingsView v-else-if="activeTab === 'teams'" />
        <PermissionsOverviewView v-else-if="activeTab === 'overview'" />
        <AuditLogSettingsView v-else-if="activeTab === 'audit'" />
      </section>
    </div>
  </div>
</template>

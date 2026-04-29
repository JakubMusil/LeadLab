<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useLeadsStore, type LeadOut } from '@/stores/leads'
import { useNotificationsStore } from '@/stores/notifications'
import { useSavedViewsStore } from '@/stores/savedViews'
import { useWebSocket } from '@/composables/useWebSocket'
import { useTheme } from '@/composables/useTheme'
import { useKeyboardShortcuts, shortcutHelpOpen, commandPaletteOpen, SHORTCUTS } from '@/composables/useKeyboardShortcuts'
import { useI18n } from '@/composables/useI18n'
import { pluginRegistry } from '@/plugins'
import CommandPalette from '@/components/CommandPalette.vue'
import TimerWidget from '@/components/TimerWidget.vue'
import {
  Squares2X2Icon,
  FunnelIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  CalendarDaysIcon,
  ChartBarIcon,
  EnvelopeIcon,
  BoltIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
  DocumentDuplicateIcon,
  ClockIcon,
  DocumentChartBarIcon,
  WrenchScrewdriverIcon,
  ShieldExclamationIcon,
  FolderOpenIcon,
  PuzzlePieceIcon,
  ArchiveBoxIcon,
  RectangleStackIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const leadsStore = useLeadsStore()
const notifStore = useNotificationsStore()
const savedViewsStore = useSavedViewsStore()
const { isDark, toggleDark } = useTheme()
const { t } = useI18n()

watchEffect(() => {
  const color = firmStore.activeFirm?.primary_color ?? '#dc2626'
  document.documentElement.style.setProperty('--brand-color', color)
})

const sidebarOpen = ref(true)
const mobileMenuOpen = ref(false)
const firmSwitcherOpen = ref(false)
const notifOpen = ref(false)

const { on, off } = useWebSocket()

// ---------------------------------------------------------------------------
// WebSocket event handlers
// ---------------------------------------------------------------------------

function onLeadCreated(payload: Record<string, unknown>) {
  const lead = payload as unknown as LeadOut
  if (!leadsStore.leads.find((l) => l.id === lead.id)) {
    leadsStore.leads.unshift(lead)
  }
  notifStore.pushNotification('lead.created', payload)
}

function onLeadUpdated(payload: Record<string, unknown>) {
  const lead = payload as unknown as LeadOut
  const idx = leadsStore.leads.findIndex((l) => l.id === lead.id)
  if (idx !== -1) leadsStore.leads[idx] = lead
  if (leadsStore.currentLead?.id === lead.id) leadsStore.currentLead = lead
  notifStore.pushNotification('lead.updated', payload)
}

function onLeadDeleted(payload: Record<string, unknown>) {
  const id = payload.id as string
  leadsStore.leads = leadsStore.leads.filter((l) => l.id !== id)
  notifStore.pushNotification('lead.deleted', payload)
}

function onActivityCreated(payload: Record<string, unknown>) {
  notifStore.pushNotification('activity.created', payload)
}

function onTaskCompleted(payload: Record<string, unknown>) {
  notifStore.pushNotification('task.completed', payload)
}

function onRealizationCreated(payload: Record<string, unknown>) {
  notifStore.pushNotification('realization.created', payload)
}

function onRealizationUpdated(payload: Record<string, unknown>) {
  notifStore.pushNotification('realization.updated', payload)
}

function onRealizationDeleted(payload: Record<string, unknown>) {
  notifStore.pushNotification('realization.deleted', payload)
}

function onManagementCreated(payload: Record<string, unknown>) {
  notifStore.pushNotification('management.created', payload)
}

function onManagementUpdated(payload: Record<string, unknown>) {
  notifStore.pushNotification('management.updated', payload)
}

function onManagementDeleted(payload: Record<string, unknown>) {
  notifStore.pushNotification('management.deleted', payload)
}

onMounted(async () => {
  if (!authStore.user) await authStore.fetchMe()
  if (firmStore.firms.length === 0) await firmStore.fetchFirms()
  await notifStore.fetchNotifications()
  savedViewsStore.fetchViews()

  on('lead.created', onLeadCreated)
  on('lead.updated', onLeadUpdated)
  on('lead.deleted', onLeadDeleted)
  on('activity.created', onActivityCreated)
  on('task.completed', onTaskCompleted)
  on('realization.created', onRealizationCreated)
  on('realization.updated', onRealizationUpdated)
  on('realization.deleted', onRealizationDeleted)
  on('management.created', onManagementCreated)
  on('management.updated', onManagementUpdated)
  on('management.deleted', onManagementDeleted)
})

onUnmounted(() => {
  off('lead.created', onLeadCreated)
  off('lead.updated', onLeadUpdated)
  off('lead.deleted', onLeadDeleted)
  off('activity.created', onActivityCreated)
  off('task.completed', onTaskCompleted)
  off('realization.created', onRealizationCreated)
  off('realization.updated', onRealizationUpdated)
  off('realization.deleted', onRealizationDeleted)
  off('management.created', onManagementCreated)
  off('management.updated', onManagementUpdated)
  off('management.deleted', onManagementDeleted)
})

// Keyboard shortcuts (no "new opportunity" trigger here – LeadsView handles that)
useKeyboardShortcuts()

const userInitials = computed(() => {
  const u = authStore.user
  if (!u) return '?'
  return `${u.first_name?.[0] ?? ''}${u.last_name?.[0] ?? ''}`.toUpperCase() || (u.email[0]?.toUpperCase() ?? '?')
})

const navSections = computed(() => [
  {
    label: t('appShell.sectionCrm'),
    items: [
      { label: t('nav.overview'), icon: Squares2X2Icon, path: '/app/dashboard' },
      { label: t('nav.leads'), icon: FunnelIcon, path: '/app/opportunities' },
      { label: t('nav.customers'), icon: UsersIcon, path: '/app/directory' },
      { label: t('nav.proposals'), icon: DocumentDuplicateIcon, path: '/app/proposals' },
    ],
  },
  {
    label: t('appShell.sectionProjects'),
    items: [
      { label: t('nav.realizations'), icon: WrenchScrewdriverIcon, path: '/app/realizations' },
      { label: t('nav.management'), icon: ShieldExclamationIcon, path: '/app/management' },
      { label: t('nav.tasks'), icon: ClipboardDocumentListIcon, path: '/app/tasks' },
      { label: t('nav.calendar'), icon: CalendarDaysIcon, path: '/app/calendar' },
      { label: t('nav.timesheets'), icon: ClockIcon, path: '/app/timesheets' },
    ],
  },
  {
    label: t('appShell.sectionInsights'),
    items: [
      { label: t('nav.analytics'), icon: ChartBarIcon, path: '/app/analytics' },
      { label: t('nav.reports'), icon: DocumentChartBarIcon, path: '/app/reports' },
      { label: t('nav.sequences'), icon: EnvelopeIcon, path: '/app/sequences' },
      { label: t('appShell.sectionAutomations'), icon: BoltIcon, path: '/app/automations' },
      ...pluginRegistry.flatMap((p) => p.navItems ?? []).filter((i) => i.path !== '/app/sequences'),
    ],
  },
  {
    label: t('appShell.sectionConfig'),
    items: [
      { label: t('nav.documents'), icon: FolderOpenIcon, path: '/app/documents' },
      { label: t('nav.taskTemplates'), icon: DocumentDuplicateIcon, path: '/app/task-templates' },
      { label: t('appShell.sectionProposalTemplates'), icon: RectangleStackIcon, path: '/app/proposal-templates' },
      { label: t('appShell.sectionCatalog'), icon: ArchiveBoxIcon, path: '/app/catalog' },
      { label: t('nav.team'), icon: UserGroupIcon, path: '/app/team' },
      { label: t('appShell.sectionPlugins'), icon: PuzzlePieceIcon, path: '/app/plugins' },
      { label: t('nav.settings'), icon: Cog6ToothIcon, path: '/app/settings' },
      ...(authStore.user?.is_staff || authStore.user?.is_superuser ? [{ label: t('nav.superAdmin'), icon: ShieldCheckIcon, path: '/app/superadmin' }] : []),
    ],
  },
])

// Keep for mobile menu and other consumers
const navItems = computed(() => navSections.value.flatMap((s) => s.items))

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

async function signOut() {
  await authStore.logout()
}

function toggleFirmSwitcher() {
  firmSwitcherOpen.value = !firmSwitcherOpen.value
}

function switchFirm(id: string) {
  firmStore.setActiveFirm(id)
  firmSwitcherOpen.value = false
}

function toggleNotifPanel() {
  notifOpen.value = !notifOpen.value
  if (notifOpen.value && notifStore.unreadCount > 0) {
    notifStore.markAllRead()
  }
}

function eventLabel(event: string): string {
  const map: Record<string, string> = {
    'lead.created': t('appShell.eventLeadCreated'),
    'lead.updated': t('appShell.eventLeadUpdated'),
    'lead.deleted': t('appShell.eventLeadDeleted'),
    'activity.created': t('appShell.eventActivityCreated'),
    'task.completed': t('appShell.eventTaskCompleted'),
  }
  return map[event] ?? event
}

function eventIcon(event: string): string {
  const map: Record<string, string> = {
    'lead.created': '◎',
    'lead.updated': '✎',
    'lead.deleted': '🗑',
    'activity.created': '💬',
    'task.completed': '✅',
  }
  return map[event] ?? '🔔'
}

function notifTitle(n: { event: string; payload: Record<string, unknown> }): string {
  if (n.event === 'lead.created' || n.event === 'lead.updated') {
    return (n.payload.title as string) || eventLabel(n.event)
  }
  if (n.event === 'activity.created') {
    return (n.payload.content_text as string) || (n.payload.type as string) || t('appShell.notifActivity')
  }
  if (n.event === 'task.completed') {
    return (n.payload.title as string) || t('appShell.notifTaskCompleted')
  }
  if (n.event === 'lead.deleted') {
    return t('appShell.notifLeadDeleted', { id: n.payload.id as string })
  }
  return eventLabel(n.event)
}

function formatNotifTime(ts: string): string {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <!-- Skip-to-content link -->
  <a
    href="#main-content"
    class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-red-600 focus:text-white focus:rounded-xl focus:text-sm focus:font-medium"
  >
    {{ t('appShell.skipToContent') }}
  </a>

  <div class="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <!-- Mobile sidebar overlay -->
    <div
      v-if="mobileMenuOpen"
      class="fixed inset-0 z-20 bg-black/40 lg:hidden"
      @click="mobileMenuOpen = false"
      aria-hidden="true"
    />

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 flex flex-col bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 lg:static"
      :class="[
        sidebarOpen ? 'w-64' : 'w-16',
        mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      ]"
      aria-label="Sidebar navigation"
    >
      <!-- Logo + workspace -->
      <div class="flex items-center h-16 px-4 border-b border-gray-100 dark:border-gray-700 gap-3 min-w-0">
        <img
          v-if="firmStore.activeFirm?.logo_url"
          :src="firmStore.activeFirm.logo_url"
          :alt="firmStore.activeFirm?.name ?? 'Logo'"
          class="w-8 h-8 rounded-lg object-cover flex-shrink-0"
        />
        <div
          v-else
          class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          :style="{ backgroundColor: firmStore.activeFirm?.primary_color ?? '#dc2626' }"
        >
          <span class="text-white text-sm font-bold" aria-hidden="true">L</span>
        </div>
        <div v-if="sidebarOpen" class="min-w-0 flex-1">
          <div class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
            {{ firmStore.activeFirm?.name ?? 'LeadLab' }}
          </div>
          <div class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ t('appShell.workspace') }}</div>
        </div>
        <button
          class="hidden lg:flex ml-auto items-center justify-center w-6 h-6 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex-shrink-0"
          @click="sidebarOpen = !sidebarOpen"
          :aria-label="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
          :title="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
        >
          <span class="text-xs" aria-hidden="true">{{ sidebarOpen ? '‹' : '›' }}</span>
        </button>
      </div>

      <!-- Nav sections -->
      <nav class="flex-1 px-2 py-4 overflow-y-auto sidebar-scrollbar" aria-label="Main navigation">
        <template v-for="section in navSections" :key="section.label">
          <!-- Section label (only when expanded) -->
          <div v-if="sidebarOpen" class="px-3 pt-3 pb-1 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider select-none">
            {{ section.label }}
          </div>
          <div :class="sidebarOpen ? 'mb-2 space-y-0.5' : 'mb-3 space-y-1'">
            <template v-for="item in section.items" :key="item.path">
              <RouterLink
                :to="item.path"
                class="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors group"
                :class="
                  isActive(item.path)
                    ? 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100'
                "
                :aria-current="isActive(item.path) ? 'page' : undefined"
                @click="mobileMenuOpen = false"
              >
                <component v-if="typeof item.icon !== 'string'" :is="item.icon" class="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                <span v-else class="text-base flex-shrink-0 w-5 text-center" aria-hidden="true">{{ item.icon }}</span>
                <span v-if="sidebarOpen" class="truncate">{{ item.label }}</span>
              </RouterLink>

              <!-- Saved views for Leads -->
              <template v-if="sidebarOpen && item.path === '/app/opportunities' && savedViewsStore.viewsForEntity('opportunities').length > 0">
                <RouterLink
                  v-for="view in savedViewsStore.viewsForEntity('opportunities')"
                  :key="view.id"
                  :to="`/app/opportunities?view=${view.id}`"
                  class="flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300"
                  @click="mobileMenuOpen = false"
                >
                  <span aria-hidden="true">🔖</span>
                  <span class="truncate">{{ view.name }}</span>
                </RouterLink>
              </template>

              <!-- Saved views for Customers -->
              <template v-if="sidebarOpen && item.path === '/app/directory' && savedViewsStore.viewsForEntity('directory').length > 0">
                <RouterLink
                  v-for="view in savedViewsStore.viewsForEntity('directory')"
                  :key="view.id"
                  :to="`/app/directory?view=${view.id}`"
                  class="flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300"
                  @click="mobileMenuOpen = false"
                >
                  <span aria-hidden="true">🔖</span>
                  <span class="truncate">{{ view.name }}</span>
                </RouterLink>
              </template>
            </template>
          </div>
        </template>
      </nav>

      <!-- Dark mode toggle + user section -->
      <div class="border-t border-gray-100 dark:border-gray-700 p-3">
        <!-- Theme toggle -->
        <button
          class="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors mb-2"
          :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggleDark"
        >
          <span class="text-base flex-shrink-0 w-5 text-center" aria-hidden="true">{{ isDark ? '☀' : '🌙' }}</span>
          <span v-if="sidebarOpen" class="truncate text-xs">{{ isDark ? t('appShell.lightMode') : t('appShell.darkMode') }}</span>
        </button>

        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center flex-shrink-0 text-white text-xs font-semibold" aria-hidden="true">
            {{ userInitials }}
          </div>
          <div v-if="sidebarOpen" class="min-w-0 flex-1">
            <div class="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">{{ authStore.user?.full_name }}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ authStore.user?.email }}</div>
          </div>
          <button
            v-if="sidebarOpen"
            class="flex-shrink-0 text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Sign out"
            title="Sign out"
            @click="signOut"
          >
            ↩
          </button>
        </div>
        <button
          v-if="!sidebarOpen"
          class="mt-2 w-full flex items-center justify-center text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Sign out"
          title="Sign out"
          @click="signOut"
        >
          ↩
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Top bar -->
      <header class="flex items-center h-16 px-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 gap-4" role="banner">
        <!-- Mobile hamburger -->
        <button
          class="lg:hidden p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Open navigation menu"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <!-- Page title -->
        <h1 class="text-base font-semibold text-gray-900 dark:text-gray-100 flex-shrink-0">
          {{ (route.meta?.title as string) ?? 'LeadLab' }}
        </h1>

        <div class="flex-1" />

        <!-- Global search / command palette trigger -->
        <div class="hidden md:flex items-center w-64 bg-gray-100 dark:bg-gray-700 rounded-xl px-3 py-2 gap-2 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" role="button" tabindex="0" aria-label="Open command palette (Cmd+K)" @click="commandPaletteOpen = true" @keydown.enter="commandPaletteOpen = true">
          <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span class="text-sm text-gray-400 dark:text-gray-500 flex-1">Search…</span>
          <kbd class="text-xs text-gray-400 dark:text-gray-500 font-mono">⌘K</kbd>
        </div>

        <!-- Notification bell -->
        <div class="relative">
          <button
            class="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 relative"
            aria-label="Notifications"
            :aria-expanded="notifOpen"
            @click="toggleNotifPanel"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <span
              v-if="notifStore.unreadCount > 0"
              class="absolute -top-0.5 -right-0.5 min-w-4 h-4 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1"
              aria-label="`${notifStore.unreadCount} unread notifications`"
            >{{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}</span>
          </button>

          <!-- Notification slide-over panel -->
          <Teleport to="body">
            <div
              v-if="notifOpen"
              class="fixed inset-0 z-40"
              @click.self="notifOpen = false"
            >
              <div
                class="absolute right-0 top-0 h-full w-full max-w-sm bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-2xl flex flex-col"
                role="dialog"
                aria-label="Notifications panel"
                aria-modal="true"
              >
                <!-- Panel header -->
                <div class="flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-700">
                  <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex-1">{{ t('appShell.notifications') }}</h2>
                  <button
                    v-if="notifStore.unreadCount > 0"
                    class="text-xs text-red-600 hover:underline"
                    @click="notifStore.markAllRead()"
                  >{{ t('appShell.markAllRead') }}</button>
                  <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-lg leading-none" aria-label="Close notifications" @click="notifOpen = false">✕</button>
                </div>

                <!-- Notification list -->
                <div class="flex-1 overflow-y-auto">
                  <div v-if="notifStore.loading" class="p-4 space-y-2">
                    <div v-for="i in 4" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl animate-pulse" />
                  </div>
                  <div v-else-if="notifStore.notifications.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
                    <div class="text-4xl mb-3" aria-hidden="true">🔔</div>
                    <p class="text-sm">{{ t('appShell.noNotifications') }}</p>
                  </div>
                  <ul v-else class="divide-y divide-gray-50 dark:divide-gray-700" role="list">
                    <li
                      v-for="n in notifStore.notifications"
                      :key="n.id"
                      class="flex items-start gap-3 px-5 py-3.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      :class="n.is_read ? '' : 'bg-red-50/40 dark:bg-red-900/10'"
                    >
                      <span class="text-lg flex-shrink-0 mt-0.5" aria-hidden="true">{{ eventIcon(n.event) }}</span>
                      <div class="min-w-0 flex-1">
                        <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">{{ eventLabel(n.event) }}</p>
                        <p class="text-sm text-gray-900 dark:text-gray-100 leading-snug truncate">{{ notifTitle(n) }}</p>
                        <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ formatNotifTime(n.created_at) }}</p>
                      </div>
                      <span v-if="!n.is_read" class="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5" aria-label="Unread" />
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </Teleport>
        </div>

        <!-- Workspace switcher -->
        <div v-if="firmStore.firms.length > 1" class="relative">
          <button
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            :aria-expanded="firmSwitcherOpen"
            aria-haspopup="listbox"
            @click="toggleFirmSwitcher"
          >
            <span class="max-w-32 truncate">{{ firmStore.activeFirm?.name }}</span>
            <span class="text-gray-400" aria-hidden="true">▾</span>
          </button>
          <div
            v-if="firmSwitcherOpen"
            class="absolute right-0 top-10 z-10 w-48 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg py-1"
            role="listbox"
            aria-label="Select workspace"
          >
            <button
              v-for="firm in firmStore.firms"
              :key="firm.id"
              class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
              role="option"
              :aria-selected="firm.id === firmStore.activeFirm?.id"
              @click="switchFirm(String(firm.id))"
            >
              <span class="flex-1 truncate">{{ firm.name }}</span>
              <span v-if="firm.id === firmStore.activeFirm?.id" class="text-red-600 text-xs" aria-hidden="true">✓</span>
            </button>
          </div>
        </div>
      </header>

      <!-- Page content -->
      <main id="main-content" class="flex-1 overflow-y-auto dark:bg-gray-900" tabindex="-1">
        <RouterView />
      </main>
    </div>
  </div>

  <!-- Sitewide Timer Widget -->
  <TimerWidget />

  <!-- Keyboard shortcuts help modal -->
  <Teleport to="body">
    <div
      v-if="shortcutHelpOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @click.self="shortcutHelpOpen = false"
    >
      <div
        class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 id="shortcuts-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('appShell.keyboardShortcuts') }}</h3>
          <button
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            aria-label="Close shortcuts help"
            @click="shortcutHelpOpen = false"
          >✕</button>
        </div>
        <ul class="space-y-2" role="list">
          <li v-for="sc in SHORTCUTS" :key="sc.keys" class="flex items-center justify-between gap-4">
            <span class="text-sm text-gray-600 dark:text-gray-400">{{ sc.description }}</span>
            <kbd class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-xs font-mono text-gray-700 dark:text-gray-300">{{ sc.keys }}</kbd>
          </li>
        </ul>
      </div>
    </div>
  </Teleport>

  <!-- Command Palette (Cmd/Ctrl + K) -->
  <Teleport to="body">
    <CommandPalette v-if="commandPaletteOpen" @close="commandPaletteOpen = false" />
  </Teleport>
</template>

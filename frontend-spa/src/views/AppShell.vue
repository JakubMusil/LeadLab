<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useLeadsStore, type LeadOut } from '@/stores/leads'
import { useNotificationsStore } from '@/stores/notifications'
import { useWebSocket } from '@/composables/useWebSocket'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const leadsStore = useLeadsStore()
const notifStore = useNotificationsStore()

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
  // Only prepend if not already in the list (e.g. created by this client already via API)
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

onMounted(async () => {
  if (!authStore.user) await authStore.fetchMe()
  if (firmStore.firms.length === 0) await firmStore.fetchFirms()
  await notifStore.fetchNotifications()

  on('lead.created', onLeadCreated)
  on('lead.updated', onLeadUpdated)
  on('lead.deleted', onLeadDeleted)
  on('activity.created', onActivityCreated)
  on('task.completed', onTaskCompleted)
})

onUnmounted(() => {
  off('lead.created', onLeadCreated)
  off('lead.updated', onLeadUpdated)
  off('lead.deleted', onLeadDeleted)
  off('activity.created', onActivityCreated)
  off('task.completed', onTaskCompleted)
})

const userInitials = computed(() => {
  const u = authStore.user
  if (!u) return '?'
  return `${u.first_name?.[0] ?? ''}${u.last_name?.[0] ?? ''}`.toUpperCase() || (u.email[0]?.toUpperCase() ?? '?')
})

const navItems = [
  { label: 'Overview', icon: '⊞', path: '/app/dashboard' },
  { label: 'Leads', icon: '◎', path: '/app/leads' },
  { label: 'Customers', icon: '👥', path: '/app/customers' },
  { label: 'Calendar', icon: '📅', path: '/app/calendar' },
  { label: 'Team', icon: '🤝', path: '/app/team' },
  { label: 'Settings', icon: '⚙', path: '/app/settings' },
]

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
    'lead.created': 'New lead created',
    'lead.updated': 'Lead updated',
    'lead.deleted': 'Lead deleted',
    'activity.created': 'New activity logged',
    'task.completed': 'Task completed',
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
    return (n.payload.content_text as string) || (n.payload.type as string) || 'Activity'
  }
  if (n.event === 'task.completed') {
    return (n.payload.title as string) || 'Task completed'
  }
  if (n.event === 'lead.deleted') {
    return `Lead ${n.payload.id as string} deleted`
  }
  return eventLabel(n.event)
}

function formatNotifTime(ts: string): string {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="flex h-screen bg-gray-50 overflow-hidden">
    <!-- Mobile sidebar overlay -->
    <div
      v-if="mobileMenuOpen"
      class="fixed inset-0 z-20 bg-black/40 lg:hidden"
      @click="mobileMenuOpen = false"
    />

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 flex flex-col bg-white border-r border-gray-200 transition-all duration-200 lg:static"
      :class="[
        sidebarOpen ? 'w-64' : 'w-16',
        mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      ]"
    >
      <!-- Logo + workspace -->
      <div class="flex items-center h-16 px-4 border-b border-gray-100 gap-3 min-w-0">
        <div class="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center flex-shrink-0">
          <span class="text-white text-sm font-bold">L</span>
        </div>
        <div v-if="sidebarOpen" class="min-w-0 flex-1">
          <div class="text-sm font-semibold text-gray-900 truncate">
            {{ firmStore.activeFirm?.name ?? 'LeadLab' }}
          </div>
          <div class="text-xs text-gray-400 truncate">Workspace</div>
        </div>
        <button
          class="hidden lg:flex ml-auto items-center justify-center w-6 h-6 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 flex-shrink-0"
          @click="sidebarOpen = !sidebarOpen"
          :title="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
        >
          <span class="text-xs">{{ sidebarOpen ? '‹' : '›' }}</span>
        </button>
      </div>

      <!-- Nav items -->
      <nav class="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors group"
          :class="
            isActive(item.path)
              ? 'bg-red-50 text-red-600'
              : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
          "
          @click="mobileMenuOpen = false"
        >
          <span class="text-base flex-shrink-0 w-5 text-center">{{ item.icon }}</span>
          <span v-if="sidebarOpen" class="truncate">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <!-- User section -->
      <div class="border-t border-gray-100 p-3">
        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center flex-shrink-0 text-white text-xs font-semibold">
            {{ userInitials }}
          </div>
          <div v-if="sidebarOpen" class="min-w-0 flex-1">
            <div class="text-xs font-medium text-gray-900 truncate">{{ authStore.user?.full_name }}</div>
            <div class="text-xs text-gray-400 truncate">{{ authStore.user?.email }}</div>
          </div>
          <button
            v-if="sidebarOpen"
            class="flex-shrink-0 text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100"
            title="Sign out"
            @click="signOut"
          >
            ↩
          </button>
        </div>
        <button
          v-if="!sidebarOpen"
          class="mt-2 w-full flex items-center justify-center text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100"
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
      <header class="flex items-center h-16 px-4 bg-white border-b border-gray-200 gap-4">
        <!-- Mobile hamburger -->
        <button
          class="lg:hidden p-2 rounded-lg text-gray-500 hover:bg-gray-100"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <!-- Page title -->
        <h1 class="text-base font-semibold text-gray-900 flex-shrink-0">
          {{ (route.meta?.title as string) ?? 'LeadLab' }}
        </h1>

        <div class="flex-1" />

        <!-- Global search -->
        <div class="hidden md:flex items-center w-64 bg-gray-100 rounded-xl px-3 py-2 gap-2">
          <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input type="text" placeholder="Search…" class="bg-transparent text-sm text-gray-600 placeholder-gray-400 outline-none flex-1" />
        </div>

        <!-- Notification bell -->
        <div class="relative">
          <button
            class="p-2 rounded-lg text-gray-500 hover:bg-gray-100 relative"
            title="Notifications"
            @click="toggleNotifPanel"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <!-- Unread badge -->
            <span
              v-if="notifStore.unreadCount > 0"
              class="absolute -top-0.5 -right-0.5 min-w-4 h-4 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1"
            >{{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}</span>
          </button>

          <!-- Notification slide-over panel -->
          <Teleport to="body">
            <div
              v-if="notifOpen"
              class="fixed inset-0 z-40"
              @click.self="notifOpen = false"
            >
              <div class="absolute right-0 top-0 h-full w-full max-w-sm bg-white border-l border-gray-200 shadow-2xl flex flex-col">
                <!-- Panel header -->
                <div class="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
                  <h2 class="text-sm font-semibold text-gray-900 flex-1">Notifications</h2>
                  <button
                    v-if="notifStore.unreadCount > 0"
                    class="text-xs text-red-600 hover:underline"
                    @click="notifStore.markAllRead()"
                  >Mark all read</button>
                  <button class="text-gray-400 hover:text-gray-600 text-lg leading-none" @click="notifOpen = false">✕</button>
                </div>

                <!-- Notification list -->
                <div class="flex-1 overflow-y-auto">
                  <div v-if="notifStore.loading" class="p-4 space-y-2">
                    <div v-for="i in 4" :key="i" class="h-14 bg-gray-100 rounded-xl animate-pulse" />
                  </div>
                  <div v-else-if="notifStore.notifications.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
                    <div class="text-4xl mb-3">🔔</div>
                    <p class="text-sm">No notifications yet.</p>
                  </div>
                  <ul v-else class="divide-y divide-gray-50">
                    <li
                      v-for="n in notifStore.notifications"
                      :key="n.id"
                      class="flex items-start gap-3 px-5 py-3.5 transition-colors hover:bg-gray-50"
                      :class="n.is_read ? '' : 'bg-red-50/40'"
                    >
                      <span class="text-lg flex-shrink-0 mt-0.5">{{ eventIcon(n.event) }}</span>
                      <div class="min-w-0 flex-1">
                        <p class="text-xs font-medium text-gray-500 uppercase tracking-wide mb-0.5">{{ eventLabel(n.event) }}</p>
                        <p class="text-sm text-gray-900 leading-snug truncate">{{ notifTitle(n) }}</p>
                        <p class="text-xs text-gray-400 mt-0.5">{{ formatNotifTime(n.created_at) }}</p>
                      </div>
                      <span v-if="!n.is_read" class="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5" />
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
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-700 hover:bg-gray-50"
            @click="toggleFirmSwitcher"
          >
            <span class="max-w-32 truncate">{{ firmStore.activeFirm?.name }}</span>
            <span class="text-gray-400">▾</span>
          </button>
          <div
            v-if="firmSwitcherOpen"
            class="absolute right-0 top-10 z-10 w-48 bg-white rounded-xl border border-gray-200 shadow-lg py-1"
          >
            <button
              v-for="firm in firmStore.firms"
              :key="firm.id"
              class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center gap-2"
              @click="switchFirm(String(firm.id))"
            >
              <span class="flex-1 truncate">{{ firm.name }}</span>
              <span v-if="firm.id === firmStore.activeFirm?.id" class="text-red-600 text-xs">✓</span>
            </button>
          </div>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto">
        <RouterView />
      </main>
    </div>
  </div>
</template>

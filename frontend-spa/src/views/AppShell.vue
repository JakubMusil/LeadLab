<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const firmStore = useFirmStore()

const sidebarOpen = ref(true)
const mobileMenuOpen = ref(false)
const firmSwitcherOpen = ref(false)

onMounted(async () => {
  if (!authStore.user) await authStore.fetchMe()
  if (firmStore.firms.length === 0) await firmStore.fetchFirms()
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
        <button class="p-2 rounded-lg text-gray-500 hover:bg-gray-100 relative">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
          </svg>
        </button>

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

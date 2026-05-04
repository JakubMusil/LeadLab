<script setup lang="ts">
/**
 * Global Command Palette — Cmd/Ctrl + K
 *
 * Fuzzy-searches records, customers, navigation targets, and documents.
 * Triggered by the keyboard shortcut; closed with Escape or click-outside.
 */
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import type { Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import { useRecordsStore } from '@/stores/records'
import { useCustomersStore } from '@/stores/customers'
import { api } from '@/api'
import {
  Squares2X2Icon,
  FunnelIcon,
  UsersIcon,
  CalendarDaysIcon,
  UserGroupIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  FolderOpenIcon,
  DocumentIcon,
  UserIcon,
  BuildingOfficeIcon,
} from '@heroicons/vue/24/outline'

interface CommandItem {
  id: string
  label: string
  description?: string
  icon: Component
  action: () => void
  category: 'navigation' | 'record' | 'customer' | 'document' | 'recent'
}

interface DocumentOut {
  id: string
  name: string
  content_type: string
  lead_title?: string
  customer_name?: string
  realization_title?: string
}

const emit = defineEmits<{ close: [] }>()

const router = useRouter()
const { t } = useI18n()
const leadsStore = useRecordsStore()
const customersStore = useCustomersStore()

const searchQuery = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const selectedIndex = ref(0)
const documents = ref<DocumentOut[]>([])

const navCommands = computed<CommandItem[]>(() => [
  { id: 'nav-dashboard', label: t('nav.overview'), icon: Squares2X2Icon, category: 'navigation', action: () => router.push('/app/dashboard') },
  { id: 'nav-records', label: t('nav.records'), icon: FunnelIcon, category: 'navigation', action: () => router.push('/app/records') },
  { id: 'nav-directory', label: t('nav.customers'), icon: UsersIcon, category: 'navigation', action: () => router.push('/app/directory') },
  { id: 'nav-calendar', label: t('nav.calendar'), icon: CalendarDaysIcon, category: 'navigation', action: () => router.push('/app/calendar') },
  { id: 'nav-team', label: t('nav.team'), icon: UserGroupIcon, category: 'navigation', action: () => router.push('/app/team') },
  { id: 'nav-analytics', label: t('nav.analytics'), icon: ChartBarIcon, category: 'navigation', action: () => router.push('/app/analytics') },
  { id: 'nav-settings', label: t('nav.settings'), icon: Cog6ToothIcon, category: 'navigation', action: () => router.push('/app/settings') },
  { id: 'nav-documents', label: t('nav.documents'), icon: FolderOpenIcon, category: 'navigation', action: () => router.push('/app/documents') },
])

const leadItems = computed<CommandItem[]>(() =>
  leadsStore.records.slice(0, 50).map((l) => ({
    id: `record-${l.id}`,
    label: l.title,
    description: `Record · ${l.status}`,
    icon: FunnelIcon,
    category: 'record' as const,
    action: () => router.push(`/app/records/${l.id}`),
  })),
)

const customerItems = computed<CommandItem[]>(() =>
  customersStore.customers.slice(0, 50).map((c) => ({
    id: `customer-${c.id}`,
    label: `${c.first_name} ${c.last_name}`.trim(),
    description: c.company_name || (c.type === 'company' ? t('commandPalette.company') : t('commandPalette.contact')),
    icon: c.type === 'company' ? BuildingOfficeIcon : UserIcon,
    category: 'customer' as const,
    action: () => router.push(`/app/directory/${c.id}`),
  })),
)

const documentItems = computed<CommandItem[]>(() =>
  documents.value.slice(0, 30).map((doc) => ({
    id: `doc-${doc.id}`,
    label: doc.name,
    description: `Document · ${doc.lead_title ?? doc.customer_name ?? doc.realization_title ?? t('commandPalette.unlinked')}`,
    icon: DocumentIcon,
    category: 'document' as const,
    action: () => router.push('/app/documents'),
  })),
)

async function loadDocuments() {
  try {
    const res = await api.get<DocumentOut[]>('/api/v1/erp/documents?page_size=100')
    if (res.ok) documents.value = res.data
  } catch {
    // ignore
  }
}

const RECENT_KEY = 'commandPaletteRecent'

function getRecent(): CommandItem[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    if (!raw) return []
    const ids: string[] = JSON.parse(raw)
    const all = [...navCommands.value, ...leadItems.value, ...customerItems.value, ...documentItems.value]
    return ids
      .map((id) => all.find((i) => i.id === id))
      .filter((i): i is CommandItem => !!i)
      .slice(0, 5)
  } catch {
    return []
  }
}

function saveRecent(item: CommandItem) {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    const ids: string[] = raw ? JSON.parse(raw) : []
    const filtered = ids.filter((i) => i !== item.id)
    localStorage.setItem(RECENT_KEY, JSON.stringify([item.id, ...filtered].slice(0, 10)))
  } catch {
    // ignore
  }
}

function fuzzyMatch(query: string, target: string): boolean {
  if (!query) return true
  const q = query.toLowerCase()
  const t = target.toLowerCase()
  let qi = 0
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] === q[qi]) qi++
  }
  return qi === q.length
}

const filteredItems = computed<CommandItem[]>(() => {
  const q = searchQuery.value.trim()
  if (!q) {
    const recent = getRecent()
    if (recent.length) return recent
    return navCommands.value.slice(0, 7)
  }
  const all = [...navCommands.value, ...leadItems.value, ...customerItems.value, ...documentItems.value]
  return all.filter((item) => fuzzyMatch(q, item.label) || fuzzyMatch(q, item.description ?? '')).slice(0, 12)
})

watch(filteredItems, () => {
  selectedIndex.value = 0
})

function selectItem(item: CommandItem) {
  saveRecent(item)
  item.action()
  emit('close')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = Math.min(selectedIndex.value + 1, filteredItems.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    const item = filteredItems.value[selectedIndex.value]
    if (item) selectItem(item)
  } else if (e.key === 'Escape') {
    emit('close')
  }
}

onMounted(async () => {
  await nextTick()
  inputRef.value?.focus()
  loadDocuments()
})
</script>

<template>
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50 backdrop-blur-sm"
    @click.self="$emit('close')"
    role="dialog"
    aria-modal="true"
    aria-label="Command palette"
  >
    <div
      class="w-full max-w-lg mx-4 bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden"
    >
      <!-- Search input -->
      <div class="flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <span class="text-gray-400 text-lg flex-shrink-0">🔍</span>
        <input
          ref="inputRef"
          v-model="searchQuery"
          type="text"
          :placeholder="t('commandPalette.placeholder')"
          class="flex-1 bg-transparent outline-none text-gray-900 dark:text-white placeholder-gray-400 text-sm"
          @keydown="onKeydown"
          aria-autocomplete="list"
          aria-controls="command-palette-results"
        />
        <kbd class="hidden sm:flex items-center gap-1 px-1.5 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded border border-gray-300 dark:border-gray-600 flex-shrink-0">
          Esc
        </kbd>
      </div>

      <!-- Results -->
      <ul
        id="command-palette-results"
        role="listbox"
        class="max-h-80 overflow-y-auto py-1"
      >
        <li v-if="filteredItems.length === 0" class="px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400">
          {{ t('commandPalette.noResults', { query: searchQuery }) }}
        </li>

        <li
          v-for="(item, index) in filteredItems"
          :key="item.id"
          role="option"
          :aria-selected="index === selectedIndex"
          class="flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors"
          :class="index === selectedIndex
            ? 'bg-[color:var(--brand-color)] text-white'
            : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white'"
          @click="selectItem(item)"
          @mouseenter="selectedIndex = index"
        >
          <component :is="item.icon" class="w-5 h-5 flex-shrink-0" />
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate">{{ item.label }}</div>
            <div v-if="item.description" class="text-xs truncate" :class="index === selectedIndex ? 'text-white/70' : 'text-gray-500 dark:text-gray-400'">
              {{ item.description }}
            </div>
          </div>
          <span
            class="text-xs flex-shrink-0"
            :class="index === selectedIndex ? 'text-white/60' : 'text-gray-400'"
          >
            {{
              item.category === 'navigation' ? 'Page' :
              item.category === 'record' ? 'Record' :
              item.category === 'customer' ? 'Customer' :
              item.category === 'document' ? 'Document' : 'Recent'
            }}
          </span>
        </li>
      </ul>

      <!-- Footer hints -->
      <div class="px-4 py-2 border-t border-gray-200 dark:border-gray-700 flex items-center gap-4 text-xs text-gray-400">
        <span><kbd class="font-mono">↑↓</kbd> navigate</span>
        <span><kbd class="font-mono">↵</kbd> select</span>
        <span><kbd class="font-mono">Esc</kbd> close</span>
      </div>
    </div>
  </div>
</template>

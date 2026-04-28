<script setup lang="ts">
/**
 * Global Command Palette — Cmd/Ctrl + K
 *
 * Fuzzy-searches leads, customers, navigation targets, and documents.
 * Triggered by the keyboard shortcut; closed with Escape or click-outside.
 */
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useLeadsStore } from '@/stores/leads'
import { useCustomersStore } from '@/stores/customers'
import { api } from '@/api'

interface CommandItem {
  id: string
  label: string
  description?: string
  icon: string
  action: () => void
  category: 'navigation' | 'lead' | 'customer' | 'document' | 'recent'
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
const leadsStore = useLeadsStore()
const customersStore = useCustomersStore()

const searchQuery = ref('')
const inputRef = ref<HTMLInputElement | null>(null)
const selectedIndex = ref(0)
const documents = ref<DocumentOut[]>([])

const NAV_COMMANDS: CommandItem[] = [
  { id: 'nav-dashboard', label: 'Dashboard', icon: '⊞', category: 'navigation', action: () => router.push('/app/dashboard') },
  { id: 'nav-opportunities', label: 'Opportunities', icon: '◎', category: 'navigation', action: () => router.push('/app/opportunities') },
  { id: 'nav-directory', label: 'Directory', icon: '👥', category: 'navigation', action: () => router.push('/app/directory') },
  { id: 'nav-calendar', label: 'Calendar', icon: '📅', category: 'navigation', action: () => router.push('/app/calendar') },
  { id: 'nav-team', label: 'Team', icon: '🤝', category: 'navigation', action: () => router.push('/app/team') },
  { id: 'nav-analytics', label: 'Analytics', icon: '📊', category: 'navigation', action: () => router.push('/app/analytics') },
  { id: 'nav-settings', label: 'Settings', icon: '⚙', category: 'navigation', action: () => router.push('/app/settings') },
  { id: 'nav-documents', label: 'Documents', icon: '📁', category: 'navigation', action: () => router.push('/app/documents') },
]

const leadItems = computed<CommandItem[]>(() =>
  leadsStore.leads.slice(0, 50).map((l) => ({
    id: `lead-${l.id}`,
    label: l.title,
    description: `Lead · ${l.status}`,
    icon: '◎',
    category: 'lead' as const,
    action: () => router.push(`/app/opportunities/${l.id}`),
  })),
)

const customerItems = computed<CommandItem[]>(() =>
  customersStore.customers.slice(0, 50).map((c) => ({
    id: `customer-${c.id}`,
    label: `${c.first_name} ${c.last_name}`.trim(),
    description: c.company_name || (c.type === 'company' ? 'Company' : 'Contact'),
    icon: c.type === 'company' ? '🏢' : '👤',
    category: 'customer' as const,
    action: () => router.push(`/app/directory/${c.id}`),
  })),
)

const documentItems = computed<CommandItem[]>(() =>
  documents.value.slice(0, 30).map((doc) => ({
    id: `doc-${doc.id}`,
    label: doc.name,
    description: `Document · ${doc.lead_title ?? doc.customer_name ?? doc.realization_title ?? 'Unlinked'}`,
    icon: '📄',
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
    const all = [...NAV_COMMANDS, ...leadItems.value, ...customerItems.value, ...documentItems.value]
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
    return NAV_COMMANDS.slice(0, 7)
  }
  const all = [...NAV_COMMANDS, ...leadItems.value, ...customerItems.value, ...documentItems.value]
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
          placeholder="Search leads, customers, or navigate…"
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
          No results for "{{ searchQuery }}"
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
          <span class="text-base flex-shrink-0">{{ item.icon }}</span>
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
              item.category === 'lead' ? 'Lead' :
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

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import { pluginRegistry } from '@/plugins'
import type { ConfigSchemaProperty } from '@/plugins'
import { useI18n } from '@/composables/useI18n'

const toast = useToast()
const firmStore = useFirmStore()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PluginConfigEntry {
  plugin_name: string
  enabled: boolean
  config: Record<string, unknown>
  plugin: {
    name: string
    version: string
    description: string
    icon_url: string
    permissions: string[]
    config_schema: {
      type: string
      properties?: Record<string, ConfigSchemaProperty>
      required?: string[]
    }
  } | null
}

interface MarketplacePlugin {
  name: string
  version: string
  description: string
  author: string
  icon_url?: string
  tags?: string[]
  install_url?: string
}

// ---------------------------------------------------------------------------
// Installed plugins state
// ---------------------------------------------------------------------------

const pluginConfigs = ref<PluginConfigEntry[]>([])
const pluginsLoading = ref(false)
const expandedPlugin = ref<string | null>(null)
const pluginSaving = ref<Record<string, boolean>>({})
const pluginDraftConfigs = ref<Record<string, Record<string, unknown>>>({})

async function loadPluginConfigs() {
  if (!firmStore.activeFirm) return
  pluginsLoading.value = true
  const res = await api.get<PluginConfigEntry[]>(
    `/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/`,
  )
  pluginsLoading.value = false
  if (res.ok && Array.isArray(res.data)) {
    pluginConfigs.value = res.data
    for (const pc of res.data) {
      pluginDraftConfigs.value[pc.plugin_name] = { ...pc.config }
    }
  }
}

async function togglePlugin(pc: PluginConfigEntry) {
  if (!firmStore.activeFirm) return
  const res = await api.patch<PluginConfigEntry>(
    `/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/${pc.plugin_name}/`,
    { enabled: !pc.enabled },
  )
  if (res.ok && res.data) {
    const idx = pluginConfigs.value.findIndex((p) => p.plugin_name === pc.plugin_name)
    if (idx !== -1) pluginConfigs.value.splice(idx, 1, res.data)
    toast.success(res.data.enabled ? t('plugins.pluginEnabled', { name: pc.plugin_name }) : t('plugins.pluginDisabled', { name: pc.plugin_name }))
  } else {
    toast.error(t('plugins.failedToUpdatePlugin'))
  }
}

async function savePluginConfig(pc: PluginConfigEntry) {
  if (!firmStore.activeFirm) return
  pluginSaving.value[pc.plugin_name] = true
  const config = pluginDraftConfigs.value[pc.plugin_name] ?? {}
  const res = await api.patch<PluginConfigEntry>(
    `/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/${pc.plugin_name}/`,
    { config },
  )
  pluginSaving.value[pc.plugin_name] = false
  if (res.ok && res.data) {
    const idx = pluginConfigs.value.findIndex((p) => p.plugin_name === pc.plugin_name)
    if (idx !== -1) pluginConfigs.value.splice(idx, 1, res.data)
    toast.success(t('plugins.pluginSettingsSaved'))
    expandedPlugin.value = null
  } else {
    toast.error(t('plugins.failedToSavePluginSettings'))
  }
}

function getDraftValue(pluginName: string, key: string): unknown {
  return pluginDraftConfigs.value[pluginName]?.[key] ?? ''
}

function setDraftValue(pluginName: string, key: string, value: unknown) {
  if (!pluginDraftConfigs.value[pluginName]) {
    pluginDraftConfigs.value[pluginName] = {}
  }
  pluginDraftConfigs.value[pluginName][key] = value
}

const localPluginCount = computed(() => pluginRegistry.length)

// ---------------------------------------------------------------------------
// Marketplace
// ---------------------------------------------------------------------------

const marketplacePlugins = ref<MarketplacePlugin[]>([])
const marketplaceLoading = ref(false)
const marketplaceSearch = ref('')
const marketplaceError = ref('')

const filteredMarketplacePlugins = computed(() => {
  const q = marketplaceSearch.value.toLowerCase()
  if (!q) return marketplacePlugins.value
  return marketplacePlugins.value.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q) ||
      (p.author ?? '').toLowerCase().includes(q) ||
      (p.tags ?? []).some((t) => t.toLowerCase().includes(q)),
  )
})

async function loadMarketplace() {
  marketplaceLoading.value = true
  marketplaceError.value = ''
  try {
    const res = await api.get<MarketplacePlugin[]>('/api/v1/plugins/marketplace/')
    if (res.ok && Array.isArray(res.data)) {
      marketplacePlugins.value = res.data
    } else {
      // Fallback: show local plugin registry as marketplace entries
      marketplacePlugins.value = pluginRegistry.map((p) => ({
        name: p.manifest.name,
        version: p.manifest.version ?? '1.0.0',
        description: p.manifest.description ?? '',
        author: 'LeadLab',
        icon_url: p.manifest.iconUrl,
        tags: (p.manifest.permissions ?? []) as string[],
      }))
    }
  } catch {
    marketplacePlugins.value = pluginRegistry.map((p) => ({
      name: p.manifest.name,
      version: p.manifest.version ?? '1.0.0',
      description: p.manifest.description ?? '',
      author: 'LeadLab',
      icon_url: p.manifest.iconUrl,
      tags: (p.manifest.permissions ?? []) as string[],
    }))
  }
  marketplaceLoading.value = false
}

// Active tab
const activeTab = ref<'installed' | 'marketplace'>('installed')

onMounted(() => {
  firmStore.fetchFirms().then(() => {
    loadPluginConfigs()
  })
  loadMarketplace()
})
</script>

<template>
  <div class="p-6 max-w-4xl mx-auto space-y-5">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">{{ t('plugins.title') }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          {{ t('plugins.subtitle') }}
        </p>
      </div>
      <a
        href="/docs/plugins/"
        target="_blank"
        class="text-xs text-red-600 hover:underline"
      >{{ t('plugins.authoringGuide') }}</a>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1 w-fit">
      <button
        :class="activeTab === 'installed' ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
        class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
        @click="activeTab = 'installed'"
      >
        {{ t('plugins.tabInstalled') }}
        <span class="ml-1.5 text-xs bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 rounded-full px-1.5 py-0.5">{{ localPluginCount }}</span>
      </button>
      <button
        :class="activeTab === 'marketplace' ? 'bg-white dark:bg-gray-700 shadow-sm text-gray-900 dark:text-gray-100' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'"
        class="px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
        @click="activeTab = 'marketplace'"
      >
        {{ t('plugins.tabMarketplace') }}
      </button>
    </div>

    <!-- ===== INSTALLED TAB ===== -->
    <div v-if="activeTab === 'installed'" class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5">
      <!-- Loading state -->
      <div v-if="pluginsLoading" class="animate-pulse space-y-3">
        <div v-for="i in 3" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" />
      </div>

      <!-- Plugin list -->
      <div v-else-if="pluginConfigs.length === 0" class="text-sm text-gray-400 dark:text-gray-500 py-8 text-center">
        {{ t('plugins.noInstalled') }}
        <button class="block mx-auto mt-2 text-red-600 hover:underline text-xs" @click="activeTab = 'marketplace'">
          {{ t('plugins.browseMarketplace') }}
        </button>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="pc in pluginConfigs"
          :key="pc.plugin_name"
          class="border border-gray-100 dark:border-gray-700 rounded-xl overflow-hidden"
        >
          <!-- Plugin header row -->
          <div class="flex items-center gap-3 px-4 py-3">
            <!-- Icon -->
            <div class="w-10 h-10 rounded-xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 overflow-hidden">
              <img
                v-if="pc.plugin?.icon_url"
                :src="pc.plugin.icon_url"
                :alt="pc.plugin_name"
                class="w-full h-full object-cover"
                @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
              />
              <span v-else class="text-xl">🧩</span>
            </div>

            <!-- Name + version + description -->
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-semibold text-gray-800 dark:text-gray-100">{{ pc.plugin_name }}</span>
                <span class="text-xs text-gray-400 dark:text-gray-500">v{{ pc.plugin?.version ?? '?' }}</span>
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 truncate">{{ pc.plugin?.description ?? '' }}</p>
            </div>

            <!-- Actions -->
            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                v-if="pc.plugin && Object.keys(pc.plugin.config_schema?.properties ?? {}).length > 0"
                class="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1"
                @click="expandedPlugin = expandedPlugin === pc.plugin_name ? null : pc.plugin_name"
              >
                {{ expandedPlugin === pc.plugin_name ? t('plugins.close') : t('plugins.configure') }}
              </button>

              <button
                :class="pc.enabled ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-600'"
                class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0"
                role="switch"
                :aria-checked="pc.enabled"
                :aria-label="`Toggle ${pc.plugin_name}`"
                @click="togglePlugin(pc)"
              >
                <span
                  :class="pc.enabled ? 'translate-x-6' : 'translate-x-1'"
                  class="inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform"
                />
              </button>
            </div>
          </div>

          <!-- Permissions chips -->
          <div
            v-if="pc.plugin?.permissions?.length"
            class="px-4 pb-2 flex flex-wrap gap-1"
          >
            <span
              v-for="perm in pc.plugin.permissions"
              :key="perm"
              class="text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-full px-2 py-0.5"
            >{{ perm }}</span>
          </div>

          <!-- Config form (expanded) -->
          <div
            v-if="expandedPlugin === pc.plugin_name && pc.plugin"
            class="border-t border-gray-100 dark:border-gray-700 px-4 pb-4 pt-3 space-y-3"
          >
            <template
              v-for="(prop, key) in (pc.plugin.config_schema?.properties ?? {})"
              :key="key"
            >
              <div v-if="prop.type === 'boolean'" class="flex items-center justify-between">
                <div>
                  <label class="text-xs font-medium text-gray-700 dark:text-gray-300">{{ prop.title ?? key }}</label>
                  <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500">{{ prop.description }}</p>
                </div>
                <input
                  type="checkbox"
                  :checked="Boolean(getDraftValue(pc.plugin_name, key) ?? prop.default ?? false)"
                  class="rounded"
                  @change="setDraftValue(pc.plugin_name, key, ($event.target as HTMLInputElement).checked)"
                />
              </div>

              <div v-else-if="prop.type === 'number'">
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ prop.title ?? key }}</label>
                <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ prop.description }}</p>
                <input
                  type="number"
                  :value="getDraftValue(pc.plugin_name, key) ?? prop.default ?? ''"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  @input="setDraftValue(pc.plugin_name, key, Number(($event.target as HTMLInputElement).value))"
                />
              </div>

              <div v-else-if="prop.secret">
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ prop.title ?? key }}</label>
                <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ prop.description }}</p>
                <input
                  type="password"
                  autocomplete="new-password"
                  :value="getDraftValue(pc.plugin_name, key) ?? ''"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  placeholder="••••••••"
                  @input="setDraftValue(pc.plugin_name, key, ($event.target as HTMLInputElement).value)"
                />
              </div>

              <div v-else>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ prop.title ?? key }}</label>
                <p v-if="prop.description" class="text-xs text-gray-400 dark:text-gray-500 mb-1">{{ prop.description }}</p>
                <input
                  type="text"
                  :value="getDraftValue(pc.plugin_name, key) ?? prop.default ?? ''"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  @input="setDraftValue(pc.plugin_name, key, ($event.target as HTMLInputElement).value)"
                />
              </div>
            </template>

            <button
              :disabled="pluginSaving[pc.plugin_name]"
              class="px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              @click="savePluginConfig(pc)"
            >{{ pluginSaving[pc.plugin_name] ? t('plugins.saving') : t('plugins.saveSettings') }}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== MARKETPLACE TAB ===== -->
    <div v-if="activeTab === 'marketplace'" class="space-y-4">
      <!-- Search -->
      <div class="relative">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="marketplaceSearch"
          type="text"
          :placeholder="t('plugins.searchPlaceholder')"
          class="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:border-red-400"
        />
      </div>

      <!-- Loading -->
      <div v-if="marketplaceLoading" class="animate-pulse grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="i in 6" :key="i" class="h-32 bg-gray-100 dark:bg-gray-800 rounded-2xl" />
      </div>

      <!-- Error -->
      <div v-else-if="marketplaceError" class="text-sm text-red-600 bg-red-50 dark:bg-red-900/20 rounded-xl px-4 py-3">
        {{ marketplaceError }}
      </div>

      <!-- Empty search result -->
      <div v-else-if="filteredMarketplacePlugins.length === 0 && marketplaceSearch" class="text-center py-12 text-gray-400 dark:text-gray-500">
        <p class="text-sm">{{ t('plugins.noMatch') }}</p>
        <button class="mt-2 text-xs text-red-600 hover:underline" @click="marketplaceSearch = ''">{{ t('plugins.clearSearch') }}</button>
      </div>

      <!-- Empty state -->
      <div v-else-if="filteredMarketplacePlugins.length === 0" class="text-center py-12 text-gray-400 dark:text-gray-500">
        <p class="text-lg mb-2">🧩</p>
        <p class="text-sm">{{ t('plugins.noMarketplace') }}</p>
        <a href="/docs/plugins/" target="_blank" class="mt-2 block text-xs text-red-600 hover:underline">{{ t('plugins.buildOwn') }}</a>
      </div>

      <!-- Plugin grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div
          v-for="plugin in filteredMarketplacePlugins"
          :key="plugin.name"
          class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 flex flex-col gap-3 hover:shadow-md transition-shadow"
        >
          <div class="flex items-start gap-3">
            <div class="w-10 h-10 rounded-xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 overflow-hidden">
              <img
                v-if="plugin.icon_url"
                :src="plugin.icon_url"
                :alt="plugin.name"
                class="w-full h-full object-cover"
                @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
              />
              <span v-else class="text-xl">🧩</span>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-gray-800 dark:text-gray-100 truncate">{{ plugin.name }}</span>
                <span class="text-xs text-gray-400 dark:text-gray-500 flex-shrink-0">v{{ plugin.version }}</span>
              </div>
              <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ t('plugins.by', { author: plugin.author }) }}</p>
            </div>
          </div>
          <p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed flex-1">{{ plugin.description }}</p>
          <div v-if="plugin.tags?.length" class="flex flex-wrap gap-1">
            <span
              v-for="tag in plugin.tags"
              :key="tag"
              class="text-[10px] bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded-full px-2 py-0.5"
            >{{ tag }}</span>
          </div>
          <a
            v-if="plugin.install_url"
            :href="plugin.install_url"
            target="_blank"
            class="text-xs text-center bg-red-600 text-white rounded-xl px-3 py-1.5 hover:bg-red-700 transition-colors"
          >{{ t('plugins.install') }}</a>
          <span v-else class="text-xs text-center text-gray-400 dark:text-gray-500 border border-gray-200 dark:border-gray-600 rounded-xl px-3 py-1.5">
            {{ pluginConfigs.some((pc) => pc.plugin_name === plugin.name) ? t('plugins.installed') : t('plugins.available') }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

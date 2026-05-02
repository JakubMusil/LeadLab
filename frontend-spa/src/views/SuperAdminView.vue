<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { CheckIcon, XMarkIcon } from '@heroicons/vue/24/outline'

interface FirmRow {
  id: string
  name: string
  slug: string
  subscription_tier: string
  subscription_active: boolean
  is_active: boolean
  member_count: number
}

const firms = ref<FirmRow[]>([])
const loading = ref(false)
const error = ref('')
const adjustingId = ref<string | null>(null)

async function loadFirms() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/superadmin/firms/', { credentials: 'include' })
    if (res.ok) {
      const data = await res.json()
      firms.value = data.firms
    } else {
      error.value = 'Failed to load firms.'
    }
  } finally {
    loading.value = false
  }
}

async function setTier(firmId: string, tier: string, active: boolean) {
  adjustingId.value = firmId
  try {
    await fetch(`/superadmin/firms/${firmId}/adjust-subscription/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
      body: JSON.stringify({ subscription_tier: tier, subscription_active: active }),
    })
    await loadFirms()
  } finally {
    adjustingId.value = null
  }
}

function getCsrf(): string {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  return m?.[1] ?? ''
}

onMounted(loadFirms)
</script>

<template>
  <div class="p-6 space-y-6">
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">🛡 Super Admin</h1>
      <button
        class="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600"
        @click="loadFirms"
      >Refresh</button>
    </div>

    <div v-if="error" class="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">{{ error }}</div>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="h-12 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />
    </div>

    <div v-else class="bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-100 dark:border-gray-700">
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Name</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Slug</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Tier</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Active</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Members</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50 dark:divide-gray-700">
          <tr v-for="firm in firms" :key="firm.id" class="hover:bg-gray-50 dark:hover:bg-gray-700/50">
            <td class="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{{ firm.name }}</td>
            <td class="px-4 py-3 text-gray-500 dark:text-gray-400 font-mono text-xs">{{ firm.slug }}</td>
            <td class="px-4 py-3">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="firm.subscription_tier === 'pro' ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'"
              >{{ firm.subscription_tier }}</span>
            </td>
            <td class="px-4 py-3">
              <component :is="firm.subscription_active ? CheckIcon : XMarkIcon" :class="firm.subscription_active ? 'text-green-600' : 'text-red-500'" class="w-4 h-4" aria-hidden="true" />
            </td>
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400">{{ firm.member_count }}</td>
            <td class="px-4 py-3">
              <div class="flex gap-2">
                <button
                  v-if="firm.subscription_tier !== 'pro'"
                  :disabled="adjustingId === firm.id"
                  class="px-2 py-1 bg-purple-600 text-white rounded text-xs hover:bg-purple-700 disabled:opacity-50"
                  @click="setTier(firm.id, 'pro', true)"
                >→ Pro</button>
                <button
                  v-else
                  :disabled="adjustingId === firm.id"
                  class="px-2 py-1 bg-gray-500 text-white rounded text-xs hover:bg-gray-600 disabled:opacity-50"
                  @click="setTier(firm.id, 'free', true)"
                >→ Free</button>
              </div>
            </td>
          </tr>
          <tr v-if="firms.length === 0">
            <td colspan="6" class="px-4 py-8 text-center text-gray-400">No firms found.</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

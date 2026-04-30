/**
 * Streamline filter preferences — per-user, persisted on the backend.
 *
 * The backend stores `visible_activity_types` as a list (or null when the
 * user has never customised the filter).  The frontend computes the
 * effective set of visible activity types by combining the saved value
 * with each tool's `default_visibility` returned from
 * `/api/v1/streamline/tools`:
 *
 *   visible(type) = saved !== null
 *                 ? saved.includes(type)
 *                 : tool.default_visibility === 'important'
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'

export interface StreamlineToolMeta {
  activity_type: string
  category: string
  default_visibility: 'important' | 'secondary'
}

interface PreferencePayload {
  visible_activity_types: string[] | null
}

export const useStreamlinePreferencesStore = defineStore('streamlinePreferences', () => {
  // null  → user has never customised; defaults apply
  // []    → user has explicitly hidden everything
  // [...] → user's explicit visible set
  const savedVisible = ref<string[] | null>(null)
  const loaded = ref(false)
  const loading = ref(false)

  async function load(force = false): Promise<void> {
    if (loaded.value && !force) return
    if (loading.value) return
    loading.value = true
    try {
      const res = await api.get<PreferencePayload>('/api/v1/users/me/streamline-preferences')
      if (res.ok) {
        savedVisible.value = res.data?.visible_activity_types ?? null
        loaded.value = true
      }
    } finally {
      loading.value = false
    }
  }

  /**
   * Persist the explicit visible set.  Pass `null` to reset back to defaults.
   */
  async function save(visible: string[] | null): Promise<boolean> {
    const res = await api.put<PreferencePayload>(
      '/api/v1/users/me/streamline-preferences',
      { visible_activity_types: visible },
    )
    if (res.ok) {
      savedVisible.value = res.data?.visible_activity_types ?? null
      loaded.value = true
      return true
    }
    return false
  }

  /**
   * Compute the effective set of visible activity types given the registry
   * of tools (with their `default_visibility`).
   */
  function effectiveVisible(tools: StreamlineToolMeta[]): Set<string> {
    if (savedVisible.value !== null) {
      return new Set(savedVisible.value)
    }
    return new Set(tools.filter((t) => t.default_visibility === 'important').map((t) => t.activity_type))
  }

  const isCustomised = computed(() => savedVisible.value !== null)

  return {
    savedVisible,
    loaded,
    loading,
    isCustomised,
    load,
    save,
    effectiveVisible,
  }
})

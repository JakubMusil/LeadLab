/**
 * usePlugin — Plugin API Sandbox (v2.4)
 *
 * Returns a scoped API for a plugin identified by *pluginName*.
 * Access is gated by the permissions declared in the plugin's manifest.
 * Any call to a method that requires a permission not declared by the plugin
 * throws a PluginPermissionError.
 *
 * Usage:
 *   const api = usePlugin('slack-notifications')
 *   api.toast.success('Connected!')
 */

import { useRouter } from 'vue-router'
import { useToast } from './useToast'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { pluginRegistry } from '@/plugins'
import type { LeadLabPlugin, PluginPermission } from '@/plugins'

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class PluginPermissionError extends Error {
  constructor(pluginName: string, requiredPermission: PluginPermission) {
    super(
      `Plugin "${pluginName}" attempted to use "${requiredPermission}" but did not declare it in its manifest permissions.`,
    )
    this.name = 'PluginPermissionError'
  }
}

// ---------------------------------------------------------------------------
// Scoped plugin API
// ---------------------------------------------------------------------------

export interface PluginAPI {
  /** Show a toast notification */
  toast: ReturnType<typeof useToast>
  /** Navigate to an app route */
  navigate(path: string): void
  /** Access current firm data (requires no specific permission) */
  useFirm(): ReturnType<typeof useFirmStore>
  /** Access current user/auth data (requires no specific permission) */
  useAuth(): ReturnType<typeof useAuthStore>
  /** Open a simple alert modal with a message */
  openModal(title: string, message: string): void
}

export function usePlugin(pluginName: string): PluginAPI {
  const plugin = pluginRegistry.find((p: LeadLabPlugin) => p.manifest.name === pluginName)

  if (!plugin) {
    throw new Error(`usePlugin: plugin "${pluginName}" is not registered.`)
  }

  const permissions = new Set<PluginPermission>(plugin.manifest.permissions ?? [])

  function assertPermission(permission: PluginPermission): void {
    if (!permissions.has(permission)) {
      throw new PluginPermissionError(pluginName, permission)
    }
  }

  const toast = useToast()
  const router = useRouter()
  const authStore = useAuthStore()
  const firmStore = useFirmStore()

  return {
    toast,

    navigate(path: string) {
      router.push(path)
    },

    useFirm() {
      return firmStore
    },

    useAuth() {
      return authStore
    },

    openModal(title: string, message: string) {
      // Simple fallback — plugins can replace this with a custom modal implementation.
      // A more sophisticated implementation would integrate with an app-level modal store.
      window.alert(`${title}\n\n${message}`)
    },
  }
}

/** Return the plugin object for *pluginName*, or undefined if not registered. */
export function getRegisteredPlugin(pluginName: string): LeadLabPlugin | undefined {
  return pluginRegistry.find((p: LeadLabPlugin) => p.manifest.name === pluginName)
}

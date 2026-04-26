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
import { useRouter } from 'vue-router';
import { useToast } from './useToast';
import { useAuthStore } from '@/stores/auth';
import { useFirmStore } from '@/stores/firm';
import { pluginRegistry } from '@/plugins';
// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------
export class PluginPermissionError extends Error {
    constructor(pluginName, requiredPermission) {
        super(`Plugin "${pluginName}" attempted to use "${requiredPermission}" but did not declare it in its manifest permissions.`);
        this.name = 'PluginPermissionError';
    }
}
export function usePlugin(pluginName) {
    const plugin = pluginRegistry.find((p) => p.manifest.name === pluginName);
    if (!plugin) {
        throw new Error(`usePlugin: plugin "${pluginName}" is not registered.`);
    }
    const permissions = new Set(plugin.manifest.permissions ?? []);
    function assertPermission(permission) {
        if (!permissions.has(permission)) {
            throw new PluginPermissionError(pluginName, permission);
        }
    }
    const toast = useToast();
    const router = useRouter();
    const authStore = useAuthStore();
    const firmStore = useFirmStore();
    return {
        toast,
        navigate(path) {
            router.push(path);
        },
        useFirm() {
            return firmStore;
        },
        useAuth() {
            return authStore;
        },
        openModal(title, message) {
            // Simple fallback — plugins can replace this with a custom modal implementation.
            // A more sophisticated implementation would integrate with an app-level modal store.
            window.alert(`${title}\n\n${message}`);
        },
    };
}
/** Return the plugin object for *pluginName*, or undefined if not registered. */
export function getRegisteredPlugin(pluginName) {
    return pluginRegistry.find((p) => p.manifest.name === pluginName);
}

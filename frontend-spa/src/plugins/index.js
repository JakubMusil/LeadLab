// ---------------------------------------------------------------------------
// Manifest validation
// ---------------------------------------------------------------------------
const SEMVER_RE = /^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$/;
export class PluginManifestError extends Error {
    constructor(message) {
        super(message);
        this.name = 'PluginManifestError';
    }
}
export function validateManifest(manifest) {
    if (!manifest || typeof manifest !== 'object') {
        throw new PluginManifestError('manifest must be an object');
    }
    if (!manifest.name || typeof manifest.name !== 'string') {
        throw new PluginManifestError("manifest is missing required field 'name'");
    }
    if (!manifest.version || typeof manifest.version !== 'string') {
        throw new PluginManifestError("manifest is missing required field 'version'");
    }
    if (!SEMVER_RE.test(manifest.version)) {
        throw new PluginManifestError(`manifest 'version' must be a semver string (e.g. "1.0.0"), got "${manifest.version}"`);
    }
    if (!manifest.description || typeof manifest.description !== 'string') {
        throw new PluginManifestError("manifest is missing required field 'description'");
    }
}
// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------
export const pluginRegistry = [];
export function registerPlugin(plugin) {
    try {
        validateManifest(plugin.manifest);
    }
    catch (err) {
        console.warn(`[LeadLab] Plugin registration failed for "${plugin.manifest?.name ?? 'unknown'}":`, err instanceof Error ? err.message : err);
        return;
    }
    pluginRegistry.push(plugin);
    console.info(`[LeadLab] Plugin registered: ${plugin.manifest.name} v${plugin.manifest.version}`);
}
/** @deprecated use registerPlugin() with a manifest — kept for backwards compatibility */
export function registerLegacyPlugin(plugin) {
    const manifest = {
        name: plugin.name ?? 'unknown',
        version: plugin.version ?? '0.0.0',
        description: '',
    };
    registerPlugin({ ...plugin, manifest });
}

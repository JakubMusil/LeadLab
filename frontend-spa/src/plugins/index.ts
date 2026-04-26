import type { App } from 'vue'

// ---------------------------------------------------------------------------
// Manifest schema (v2.4)
// ---------------------------------------------------------------------------

export interface ConfigSchemaProperty {
  type: 'string' | 'number' | 'boolean'
  title?: string
  description?: string
  default?: unknown
  /** When true the settings UI renders a password input */
  secret?: boolean
}

export interface ConfigSchema {
  type: 'object'
  properties?: Record<string, ConfigSchemaProperty>
  required?: string[]
}

export type PluginPermission =
  | 'activities:read'
  | 'activities:write'
  | 'leads:read'
  | 'leads:write'
  | 'customers:read'
  | 'customers:write'
  | 'notifications:send'
  | 'webhooks:send'

export interface PluginManifest {
  /** Unique kebab-case identifier, e.g. "slack-notifications" */
  name: string
  /** Semver string, e.g. "1.0.0" */
  version: string
  description: string
  iconUrl?: string
  permissions?: PluginPermission[]
  configSchema?: ConfigSchema
}

// ---------------------------------------------------------------------------
// Extension point interfaces
// ---------------------------------------------------------------------------

export interface ActivityTypeDefinition {
  type: string
  label: string
  icon: string
}

export interface NavItemDefinition {
  label: string
  icon: string
  path: string
  requiresPro?: boolean
}

// ---------------------------------------------------------------------------
// Plugin interface
// ---------------------------------------------------------------------------

export interface LeadLabPlugin {
  manifest: PluginManifest
  activityTypes?: ActivityTypeDefinition[]
  navItems?: NavItemDefinition[]
  webhookEventTypes?: string[]
  install(app: App): void
}

// ---------------------------------------------------------------------------
// Manifest validation
// ---------------------------------------------------------------------------

const SEMVER_RE = /^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$/

export class PluginManifestError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PluginManifestError'
  }
}

export function validateManifest(manifest: PluginManifest): void {
  if (!manifest || typeof manifest !== 'object') {
    throw new PluginManifestError('manifest must be an object')
  }
  if (!manifest.name || typeof manifest.name !== 'string') {
    throw new PluginManifestError("manifest is missing required field 'name'")
  }
  if (!manifest.version || typeof manifest.version !== 'string') {
    throw new PluginManifestError("manifest is missing required field 'version'")
  }
  if (!SEMVER_RE.test(manifest.version)) {
    throw new PluginManifestError(
      `manifest 'version' must be a semver string (e.g. "1.0.0"), got "${manifest.version}"`,
    )
  }
  if (!manifest.description || typeof manifest.description !== 'string') {
    throw new PluginManifestError("manifest is missing required field 'description'")
  }
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const pluginRegistry: LeadLabPlugin[] = []

export function registerPlugin(plugin: LeadLabPlugin): void {
  try {
    validateManifest(plugin.manifest)
  } catch (err) {
    console.warn(
      `[LeadLab] Plugin registration failed for "${plugin.manifest?.name ?? 'unknown'}":`,
      err instanceof Error ? err.message : err,
    )
    return
  }
  pluginRegistry.push(plugin)
  console.info(
    `[LeadLab] Plugin registered: ${plugin.manifest.name} v${plugin.manifest.version}`,
  )
}

/** @deprecated use registerPlugin() with a manifest — kept for backwards compatibility */
export function registerLegacyPlugin(plugin: Omit<LeadLabPlugin, 'manifest'> & { name?: string; version?: string }): void {
  const manifest: PluginManifest = {
    name: plugin.name ?? 'unknown',
    version: plugin.version ?? '0.0.0',
    description: '',
  }
  registerPlugin({ ...plugin, manifest } as LeadLabPlugin)
}

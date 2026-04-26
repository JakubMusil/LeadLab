import type { App } from 'vue'

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

export interface LeadLabPlugin {
  name: string
  version: string
  activityTypes?: ActivityTypeDefinition[]
  navItems?: NavItemDefinition[]
  webhookEventTypes?: string[]
  install(app: App): void
}

export const pluginRegistry: LeadLabPlugin[] = []

export function registerPlugin(plugin: LeadLabPlugin): void {
  pluginRegistry.push(plugin)
}

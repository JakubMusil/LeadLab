<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watchEffect } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFirmStore } from '@/stores/firm'
import { useRecordsStore, type RecordOut } from '@/stores/records'
import { usePipelineStore } from '@/stores/pipeline'
import { useNotificationsStore, type NotificationOut } from '@/stores/notifications'
import { useSavedViewsStore } from '@/stores/savedViews'
import { useTasksStore } from '@/stores/tasks'
import { usePermissionsStore } from '@/stores/permissions'
import { useCan } from '@/composables/useCan'
import { useWebSocket } from '@/composables/useWebSocket'
import { useTheme } from '@/composables/useTheme'
import { useKeyboardShortcuts, shortcutHelpOpen, commandPaletteOpen, SHORTCUTS } from '@/composables/useKeyboardShortcuts'
import { useI18n } from '@/composables/useI18n'
import { useClipboard } from '@/composables/useClipboard'
import { pluginRegistry } from '@/plugins'
import { api } from '@/api'
import CommandPalette from '@/components/CommandPalette.vue'
import TimerWidget from '@/components/TimerWidget.vue'
import {
  Squares2X2Icon,
  FunnelIcon,
  UsersIcon,
  ClipboardDocumentListIcon,
  CalendarDaysIcon,
  ChartBarIcon,
  EnvelopeIcon,
  BoltIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  ShieldCheckIcon,
  DocumentDuplicateIcon,
  ClockIcon,
  DocumentChartBarIcon,
  FolderOpenIcon,
  PuzzlePieceIcon,
  ArchiveBoxIcon,
  RectangleStackIcon,
  XMarkIcon,
  TrashIcon,
  ChatBubbleLeftIcon,
  CheckCircleIcon,
  PlusCircleIcon,
  PencilSquareIcon,
  BellIcon,
  LinkIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const firmStore = useFirmStore()
const recordsStore = useRecordsStore()
const pipelineStore = usePipelineStore()
const notifStore = useNotificationsStore()
const savedViewsStore = useSavedViewsStore()
const tasksStore = useTasksStore()
const permissionsStore = usePermissionsStore()
const { can } = useCan()
const { isDark, toggleDark } = useTheme()
const { t, te } = useI18n()
const { copiedId: navPermalinkCopiedId, copyToClipboard: copyNavPermalink } = useClipboard()
const currentPageUrl = computed(() => window.location.href)
const isRecordDetailPage = computed(() => !!route.meta?.isRecordDetail)
const isRecordsListPage = computed(() => route.path === '/app/records' && !isRecordDetailPage.value)
const currentRecordCategory = computed(() =>
  recordsStore.currentRecord?.category_id
    ? pipelineStore.getCategoryById(recordsStore.currentRecord.category_id)
    : undefined,
)
const recordsListTitle = computed(() => {
  if (!isRecordsListPage.value) return (route.meta?.title as string) ?? 'LeadLab'
  const catId = route.query.category_id as string | undefined
  if (catId) {
    const cat = pipelineStore.getCategoryById(catId)
    if (cat) return cat.name
  }
  return t('leads.title')
})

watchEffect(() => {
  const color = firmStore.activeFirm?.primary_color ?? '#dc2626'
  document.documentElement.style.setProperty('--brand-color', color)
})

const sidebarOpen = ref(true)
const mobileMenuOpen = ref(false)
const firmSwitcherOpen = ref(false)
const notifOpen = ref(false)

const { on, off } = useWebSocket()

// ---------------------------------------------------------------------------
// WebSocket event handlers
// ---------------------------------------------------------------------------

function onRecordCreated(payload: Record<string, unknown>) {
  const record = payload as unknown as RecordOut
  if (!recordsStore.records.find((r) => r.id === record.id)) {
    recordsStore.records.unshift(record)
  }
  notifStore.pushNotification('record.created', payload)
  fetchCategoryCounts()
}

function onRecordUpdated(payload: Record<string, unknown>) {
  const record = payload as unknown as RecordOut
  const idx = recordsStore.records.findIndex((r) => r.id === record.id)
  if (idx !== -1) recordsStore.records[idx] = record
  if (recordsStore.currentRecord?.id === record.id) recordsStore.currentRecord = record
  notifStore.pushNotification('record.updated', payload)
}

function onRecordDeleted(payload: Record<string, unknown>) {
  const id = payload.id as string
  recordsStore.records = recordsStore.records.filter((r) => r.id !== id)
  notifStore.pushNotification('record.deleted', payload)
  fetchCategoryCounts()
}

function onActivityCreated(payload: Record<string, unknown>) {
  notifStore.pushNotification('activity.created', payload)
}

function onTaskCompleted(payload: Record<string, unknown>) {
  notifStore.pushNotification('task.completed', payload)
}

function onTaskOutcomePrompt(payload: Record<string, unknown>) {
  // Refresh the in-memory task so the SPA picks up the new
  // ``outcome_prompted_at`` timestamp without a manual reload — that
  // timestamp is what TaskDetailView/CalendarView use to render the
  // outcome banner / amber chip.
  const taskId = payload['task_id'] as string | undefined
  if (taskId) {
    void tasksStore.fetchTask(taskId).catch(() => undefined)
  }
  notifStore.pushNotification('task.outcome_prompt', payload)
}

function onTaskExpired(payload: Record<string, unknown>) {
  const taskId = payload['task_id'] as string | undefined
  if (taskId) {
    void tasksStore.fetchTask(taskId).catch(() => undefined)
  }
  notifStore.pushNotification('task.expired', payload)
}

const categoryCounts = ref<Record<string, number>>({})

async function fetchCategoryCounts() {
  const res = await api.get<Record<string, number>>('/api/v1/crm/records/counts-by-category')
  if (res.ok) categoryCounts.value = res.data
}

onMounted(async () => {
  if (!authStore.user) await authStore.fetchMe()
  if (firmStore.firms.length === 0) await firmStore.fetchFirms()
  await notifStore.fetchNotifications()
  savedViewsStore.fetchViews()
  pipelineStore.fetchCategories()
  fetchCategoryCounts()
  // Initialize permissions store with current firm
  if (firmStore.activeFirm) {
    permissionsStore.fetchMyPermissions(firmStore.activeFirm.id)
  }

  on('record.created', onRecordCreated)
  on('record.updated', onRecordUpdated)
  on('record.deleted', onRecordDeleted)
  on('activity.created', onActivityCreated)
  on('task.completed', onTaskCompleted)
  on('task.outcome_prompt', onTaskOutcomePrompt)
  on('task.expired', onTaskExpired)
  on('category.updated', pipelineStore.handleCategoryUpdated)
})

onUnmounted(() => {
  off('record.created', onRecordCreated)
  off('record.updated', onRecordUpdated)
  off('record.deleted', onRecordDeleted)
  off('activity.created', onActivityCreated)
  off('task.completed', onTaskCompleted)
  off('task.outcome_prompt', onTaskOutcomePrompt)
  off('task.expired', onTaskExpired)
  off('category.updated', pipelineStore.handleCategoryUpdated)
})

// Keyboard shortcuts (no "new record" trigger here – RecordsView handles that)
useKeyboardShortcuts()

const userInitials = computed(() => {
  const u = authStore.user
  if (!u) return '?'
  return `${u.first_name?.[0] ?? ''}${u.last_name?.[0] ?? ''}`.toUpperCase() || (u.email[0]?.toUpperCase() ?? '?')
})

const navSections = computed(() => [
  {
    label: t('appShell.sectionCrm'),
    items: [
      { label: t('nav.overview'), icon: Squares2X2Icon, path: '/app/dashboard' },
      { label: t('nav.records'), icon: FunnelIcon, path: '/app/records' },
      { label: t('nav.proposals'), icon: DocumentDuplicateIcon, path: '/app/proposals' },
      { label: t('nav.customers'), icon: UsersIcon, path: '/app/directory' },
    ],
  },
  {
    label: t('appShell.sectionProjects'),
    items: [
      { label: t('nav.tasks'), icon: ClipboardDocumentListIcon, path: '/app/tasks' },
      { label: t('nav.calendar'), icon: CalendarDaysIcon, path: '/app/calendar' },
      { label: t('nav.timesheets'), icon: ClockIcon, path: '/app/timesheets' },
      // Reports – only visible to users with report.view permission
      ...(can('report.view') ? [{ label: t('nav.reports'), icon: DocumentChartBarIcon, path: '/app/reports' }] : []),
    ],
  },
  {
    label: t('appShell.sectionInsights'),
    items: [
      { label: t('nav.analytics'), icon: ChartBarIcon, path: '/app/analytics' },
      { label: t('nav.sequences'), icon: EnvelopeIcon, path: '/app/sequences' },
      { label: t('appShell.sectionAutomations'), icon: BoltIcon, path: '/app/automations' },
      ...pluginRegistry.flatMap((p) => p.navItems ?? []).filter((i) => i.path !== '/app/sequences'),
    ],
  },
  {
    label: t('appShell.sectionConfig'),
    items: [
      { label: t('nav.documents'), icon: FolderOpenIcon, path: '/app/documents' },
      { label: t('nav.taskTemplates'), icon: DocumentDuplicateIcon, path: '/app/task-templates' },
      { label: t('appShell.sectionProposalTemplates'), icon: RectangleStackIcon, path: '/app/proposal-templates' },
      { label: t('appShell.sectionCatalog'), icon: ArchiveBoxIcon, path: '/app/catalog' },
    ],
  },
  {
    label: t('appShell.sectionSettings'),
    items: [
      { label: t('nav.team'), icon: UserGroupIcon, path: '/app/team' },
      // Plugins/Integrations – only visible to users with integrations.manage permission
      ...(can('integrations.manage') ? [{ label: t('appShell.sectionPlugins'), icon: PuzzlePieceIcon, path: '/app/plugins' }] : []),
      { label: t('nav.settings'), icon: Cog6ToothIcon, path: '/app/settings' },
      ...(authStore.user?.is_staff || authStore.user?.is_superuser ? [{ label: t('nav.superAdmin'), icon: ShieldCheckIcon, path: '/app/superadmin' }] : []),
    ],
  },
])

// Keep for mobile menu and other consumers
const navItems = computed(() => navSections.value.flatMap((s) => s.items))

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

async function signOut() {
  await authStore.logout()
}

function toggleFirmSwitcher() {
  firmSwitcherOpen.value = !firmSwitcherOpen.value
}

function switchFirm(id: string) {
  firmStore.setActiveFirm(id)
  firmSwitcherOpen.value = false
}

function toggleNotifPanel() {
  notifOpen.value = !notifOpen.value
  if (notifOpen.value && notifStore.unreadCount > 0) {
    notifStore.markAllRead()
  }
}

function eventLabel(event: string): string {
  const normalized = event.trim().toLowerCase()
  const map: Record<string, string> = {
    'record.created': t('appShell.eventLeadCreated'),
    'record.updated': t('appShell.eventLeadUpdated'),
    'record.deleted': t('appShell.eventLeadDeleted'),
    'record.status_changed': t('appShell.eventRecordStatusChanged'),
    'activity.created': t('appShell.eventActivityCreated'),
    'activity.assigned': t('appShell.eventActivityAssigned'),
    'activity.mention': t('appShell.eventActivityMention'),
    'activity.deleted': t('appShell.eventActivityDeleted'),
    'task.assigned': t('appShell.eventTaskAssigned'),
    'task.created': t('appShell.eventTaskCreated'),
    'task.updated': t('appShell.eventTaskUpdated'),
    'task.completed': t('appShell.eventTaskCompleted'),
    'task.approval_requested': t('appShell.eventTaskApprovalRequested'),
    'task.approval_resolved': t('appShell.eventTaskApprovalResolved'),
    'task.time_logged': t('appShell.eventTaskTimeLogged'),
    'task.outcome_prompt': t('appShell.eventTaskOutcomePrompt'),
    'task.expired': t('appShell.eventTaskExpired'),
    'proposal.viewed': t('appShell.eventProposalViewed'),
    'payment.received': t('appShell.eventPaymentReceived'),
    'invitation.sent': t('appShell.eventInvitationSent'),
  }
  if (map[normalized]) return map[normalized]
  const dynamicKey = `appShell.eventDynamic.${normalized.replace(/[.\s-]+/g, '_')}`
  if (te(dynamicKey)) return t(dynamicKey)
  return normalized
    .replace(/[.\s-]+/g, ' ')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

import type { Component } from 'vue'

function eventIcon(event: string): Component {
  const map: Record<string, Component> = {
    'record.created': PlusCircleIcon,
    'record.updated': PencilSquareIcon,
    'record.deleted': TrashIcon,
    'record.status_changed': PencilSquareIcon,
    'activity.created': ChatBubbleLeftIcon,
    'activity.assigned': PencilSquareIcon,
    'activity.mention': ChatBubbleLeftIcon,
    'activity.deleted': TrashIcon,
    'task.assigned': ClipboardDocumentListIcon,
    'task.created': PlusCircleIcon,
    'task.updated': PencilSquareIcon,
    'task.completed': CheckCircleIcon,
    'task.approval_requested': ClockIcon,
    'task.approval_resolved': CheckCircleIcon,
    'task.time_logged': ClockIcon,
    'task.outcome_prompt': ClockIcon,
    'task.expired': ClockIcon,
    'proposal.viewed': DocumentDuplicateIcon,
    'payment.received': CheckCircleIcon,
    'invitation.sent': UserGroupIcon,
  }
  return map[event] ?? BellIcon
}

function payloadString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key]
  if (typeof value === 'string' && value.trim()) return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return null
}

function payloadTitle(payload: Record<string, unknown>): string | null {
  return (
    payloadString(payload, 'title')
    ?? payloadString(payload, 'task_title')
    ?? payloadString(payload, 'record_title')
    ?? payloadString(payload, 'entity_title')
    ?? payloadString(payload, 'proposal')
    ?? payloadString(payload, 'record')
    ?? payloadString(payload, 'content_preview')
    ?? payloadString(payload, 'preview')
    ?? payloadString(payload, 'email')
  )
}

function translateRecordStatus(status: string): string {
  const map: Record<string, string> = {
    new: t('leads.statusNew'),
    contacted: t('leads.statusContacted'),
    proposal: t('leads.statusProposal'),
    negotiation: t('leads.statusNegotiation'),
    won: t('leads.statusWon'),
    lost: t('leads.statusLost'),
    canceled: t('leads.statusCanceled'),
  }
  return map[status] ?? status
}

function activityTypeLabel(type: string): string {
  const normalized = type.trim().toLowerCase().replace(/[.\s-]+/g, '_')
  const key = `appShell.activityType.${normalized}`
  if (te(key)) return t(key)
  return type.replace(/_/g, ' ')
}

function entityLink(entityType: string, entityId: string): string | null {
  if (entityType === 'record') return `/app/records/${entityId}`
  if (entityType === 'customer') return `/app/directory/${entityId}`
  if (entityType === 'proposal') return `/app/proposals/${entityId}`
  if (entityType === 'task') return `/app/tasks/${entityId}`
  return null
}

function notifLink(n: { event: string; payload: Record<string, unknown> }): string | null {
  const explicitPath = payloadString(n.payload, 'path') ?? payloadString(n.payload, 'url') ?? payloadString(n.payload, 'link')
  if (explicitPath) {
    if (explicitPath.startsWith('/')) return explicitPath
    if (explicitPath.startsWith(window.location.origin)) return explicitPath.slice(window.location.origin.length)
  }

  const activityId = payloadString(n.payload, 'activity_id')
  const entityType = payloadString(n.payload, 'entity_type')
  const entityId = payloadString(n.payload, 'entity_id')
  if (entityType && entityId) {
    const base = entityLink(entityType, entityId)
    if (base) return activityId ? `${base}#${activityId}` : base
  }

  const recordId = payloadString(n.payload, 'record_id') ?? (n.event.startsWith('record.') ? payloadString(n.payload, 'id') : null)
  if (recordId) {
    const base = `/app/records/${recordId}`
    return activityId ? `${base}#${activityId}` : base
  }

  const proposalId = payloadString(n.payload, 'proposal_id')
  if (proposalId) return `/app/proposals/${proposalId}`

  const customerId = payloadString(n.payload, 'customer_id')
  if (customerId) return `/app/directory/${customerId}`

  const taskId = payloadString(n.payload, 'task_id') ?? (n.event.startsWith('task.') ? payloadString(n.payload, 'id') : null)
  if (taskId) {
    const base = `/app/tasks/${taskId}`
    return activityId ? `${base}#${activityId}` : base
  }

  return null
}

type NotificationRow = NotificationOut & { link: string | null }

const notificationsWithLinks = computed<NotificationRow[]>(() =>
  notifStore.notifications.map((n) => ({ ...n, link: notifLink(n) })),
)

function handleNotificationClick(n: { id: string; is_read: boolean }) {
  notifOpen.value = false
  if (!n.is_read) {
    void notifStore.markRead([n.id])
  }
}

function notifTitle(n: { event: string; payload: Record<string, unknown> }): string {
  const event = n.event.trim().toLowerCase()
  if (event === 'record.created' || event === 'record.updated') {
    return payloadString(n.payload, 'title') || eventLabel(n.event)
  }
  if (event === 'record.status_changed') {
    const title = payloadTitle(n.payload)
    const fromStatus = payloadString(n.payload, 'from')
    const toStatus = payloadString(n.payload, 'to')
    if (title && fromStatus && toStatus) {
      return t('appShell.notifRecordStatusChanged', {
        title,
        from: translateRecordStatus(fromStatus),
        to: translateRecordStatus(toStatus),
      })
    }
    return title || eventLabel(n.event)
  }
  if (event === 'activity.created') {
    return (
      payloadString(n.payload, 'content_text')
      ?? payloadString(n.payload, 'content_preview')
      ?? payloadString(n.payload, 'preview')
      ?? (payloadString(n.payload, 'type') ? activityTypeLabel(payloadString(n.payload, 'type') ?? '') : null)
      ?? t('appShell.notifActivity')
    )
  }
  if (event === 'activity.assigned') {
    const entity = payloadTitle(n.payload)
    return entity ? t('appShell.notifActivityAssigned', { entity }) : t('appShell.notifActivity')
  }
  if (event === 'activity.mention') {
    const entity = payloadTitle(n.payload) ?? t('appShell.notifActivity')
    const byUser = payloadString(n.payload, 'by_user')
    return byUser
      ? t('appShell.notifActivityMentionBy', { byUser, entity })
      : t('appShell.notifActivityMention', { entity })
  }
  if (event === 'task.completed') {
    return payloadString(n.payload, 'title') || payloadString(n.payload, 'task_title') || t('appShell.notifTaskCompleted')
  }
  if (event === 'task.assigned') {
    return payloadTitle(n.payload) || t('appShell.notifTaskAssigned')
  }
  if (event === 'task.created' || event === 'task.updated') {
    return payloadTitle(n.payload) || t(`appShell.${event === 'task.created' ? 'notifTaskCreated' : 'notifTaskUpdated'}`)
  }
  if (event === 'task.outcome_prompt') {
    return payloadString(n.payload, 'task_title') || t('appShell.notifTaskOutcomePrompt')
  }
  if (event === 'task.expired') {
    return payloadString(n.payload, 'task_title') || t('appShell.notifTaskExpired')
  }
  if (event === 'proposal.viewed') {
    const proposal = payloadString(n.payload, 'proposal') ?? payloadString(n.payload, 'proposal_title')
    const viewer = payloadString(n.payload, 'viewer')
    if (proposal && viewer) return t('appShell.notifProposalViewedBy', { proposal, viewer })
    return proposal ? t('appShell.notifProposalViewed', { proposal }) : eventLabel(n.event)
  }
  if (event === 'payment.received') {
    const amount = payloadString(n.payload, 'amount')
    const currency = payloadString(n.payload, 'currency')
    const record = payloadString(n.payload, 'record') ?? payloadString(n.payload, 'record_title')
    if (amount && currency && record) return t('appShell.notifPaymentReceived', { amount, currency, record })
    return record || eventLabel(n.event)
  }
  if (event === 'invitation.sent') {
    const email = payloadString(n.payload, 'email')
    return email ? t('appShell.notifInvitationSent', { email }) : eventLabel(n.event)
  }
  if (event === 'record.deleted') {
    return t('appShell.notifLeadDeleted', { id: n.payload.id as string })
  }
  return payloadTitle(n.payload) || eventLabel(n.event)
}

function formatNotifTime(ts: string): string {
  return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <!-- Skip-to-content link -->
  <a
    href="#main-content"
    class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-red-600 focus:text-white focus:rounded-xl focus:text-sm focus:font-medium"
  >
    {{ t('appShell.skipToContent') }}
  </a>

  <div class="flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden">
    <!-- Mobile sidebar overlay -->
    <div
      v-if="mobileMenuOpen"
      class="fixed inset-0 z-20 bg-black/40 lg:hidden"
      @click="mobileMenuOpen = false"
      aria-hidden="true"
    />

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 flex flex-col bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 lg:static"
      :class="[
        sidebarOpen ? 'w-64' : 'w-16',
        mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
      ]"
      aria-label="Sidebar navigation"
    >
      <!-- Logo + workspace -->
      <div class="flex items-center h-16 px-4 border-b border-gray-100 dark:border-gray-700 gap-3 min-w-0">
        <img
          v-if="firmStore.activeFirm?.logo_url"
          :src="firmStore.activeFirm.logo_url"
          :alt="firmStore.activeFirm?.name ?? 'Logo'"
          class="w-8 h-8 rounded-lg object-cover flex-shrink-0"
        />
        <div
          v-else
          class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          :style="{ backgroundColor: firmStore.activeFirm?.primary_color ?? '#dc2626' }"
        >
          <span class="text-white text-sm font-bold" aria-hidden="true">L</span>
        </div>
        <div v-if="sidebarOpen" class="min-w-0 flex-1">
          <div class="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
            {{ firmStore.activeFirm?.name ?? 'LeadLab' }}
          </div>
          <div class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ t('appShell.workspace') }}</div>
        </div>
        <button
          class="hidden lg:flex ml-auto items-center justify-center w-6 h-6 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex-shrink-0"
          @click="sidebarOpen = !sidebarOpen"
          :aria-label="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
          :title="sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'"
        >
          <span class="text-xs" aria-hidden="true">{{ sidebarOpen ? '‹' : '›' }}</span>
        </button>
      </div>

      <!-- Nav sections -->
      <nav class="flex-1 px-2 py-4 overflow-y-auto sidebar-scrollbar" aria-label="Main navigation">
        <template v-for="section in navSections" :key="section.label">
          <!-- Section label (only when expanded) -->
          <div v-if="sidebarOpen" class="px-3 pt-3 pb-1 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider select-none">
            {{ section.label }}
          </div>
          <div :class="sidebarOpen ? 'mb-2 space-y-0.5' : 'mb-3 space-y-1'">
            <template v-for="item in section.items" :key="item.path">
              <RouterLink
                :to="item.path"
                class="flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors group"
                :class="
                  isActive(item.path)
                    ? 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100'
                "
                :aria-current="isActive(item.path) ? 'page' : undefined"
                @click="mobileMenuOpen = false"
              >
                <component v-if="typeof item.icon !== 'string'" :is="item.icon" class="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                <span v-else class="text-base flex-shrink-0 w-5 text-center" aria-hidden="true">{{ item.icon }}</span>
                <span v-if="sidebarOpen" class="truncate">{{ item.label }}</span>
              </RouterLink>

              <!-- Saved views for Records -->
              <template v-if="sidebarOpen && item.path === '/app/records' && savedViewsStore.viewsForEntity('records').length > 0">
                <RouterLink
                  v-for="view in savedViewsStore.viewsForEntity('records')"
                  :key="view.id"
                  :to="`/app/records?view=${view.id}`"
                  class="flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300"
                  @click="mobileMenuOpen = false"
                >
                  <span aria-hidden="true">🔖</span>
                  <span class="truncate">{{ view.name }}</span>
                </RouterLink>
              </template>

              <!-- Pipeline categories -->
              <template v-if="sidebarOpen && item.path === '/app/records' && pipelineStore.categories.length > 0">
                <RouterLink
                  v-for="cat in pipelineStore.categories.filter((c) => c.is_active)"
                  :key="cat.id"
                  :to="`/app/records?category_id=${cat.id}`"
                  class="flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300"
                  @click="mobileMenuOpen = false"
                >
                  <span
                    class="w-2 h-2 rounded-full flex-shrink-0"
                    :style="{ backgroundColor: cat.color || '#94A3B8' }"
                    aria-hidden="true"
                  ></span>
                  <span class="truncate flex-1">{{ cat.name }}</span>
                  <span
                    v-if="categoryCounts[cat.id]"
                    class="ml-auto flex-shrink-0 min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-semibold flex items-center justify-center text-white"
                    :style="{ backgroundColor: cat.color || '#94A3B8' }"
                    :aria-label="t('pipeline.categoryCountLabel', { count: categoryCounts[cat.id] })"
                  >{{ categoryCounts[cat.id] }}</span>
                </RouterLink>
              </template>

            </template>
          </div>
        </template>
      </nav>

      <!-- Dark mode toggle + user section -->
      <div class="border-t border-gray-100 dark:border-gray-700 p-3">
        <!-- Theme toggle -->
        <button
          class="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors mb-2"
          :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
          @click="toggleDark"
        >
          <span class="text-base flex-shrink-0 w-5 text-center" aria-hidden="true">{{ isDark ? '☀' : '🌙' }}</span>
          <span v-if="sidebarOpen" class="truncate text-xs">{{ isDark ? t('appShell.lightMode') : t('appShell.darkMode') }}</span>
        </button>

        <div class="flex items-center gap-3 min-w-0">
          <div class="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center flex-shrink-0 text-white text-xs font-semibold" aria-hidden="true">
            {{ userInitials }}
          </div>
          <div v-if="sidebarOpen" class="min-w-0 flex-1">
            <div class="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">{{ authStore.user?.full_name }}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500 truncate">{{ authStore.user?.email }}</div>
          </div>
          <button
            v-if="sidebarOpen"
            class="flex-shrink-0 text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Sign out"
            title="Sign out"
            @click="signOut"
          >
            ↩
          </button>
        </div>
        <button
          v-if="!sidebarOpen"
          class="mt-2 w-full flex items-center justify-center text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Sign out"
          title="Sign out"
          @click="signOut"
        >
          ↩
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Top bar -->
      <header class="flex items-center h-16 px-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 gap-4" role="banner">
        <!-- Mobile hamburger -->
        <button
          class="lg:hidden p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Open navigation menu"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <!-- Page title -->
        <div class="flex items-center gap-1.5 min-w-0 flex-shrink overflow-hidden">
          <template v-if="isRecordDetailPage && recordsStore.currentRecord">
            <template v-if="currentRecordCategory">
              <RouterLink
                :to="`/app/records?category_id=${currentRecordCategory.id}`"
                class="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors flex-shrink-0"
              >
                <span class="w-2 h-2 rounded-full flex-shrink-0" :style="{ backgroundColor: currentRecordCategory.color || '#94A3B8' }" aria-hidden="true"></span>
                <span class="truncate max-w-[8rem]">{{ currentRecordCategory.name }}</span>
              </RouterLink>
              <span class="text-gray-300 dark:text-gray-600 flex-shrink-0" aria-hidden="true">/</span>
            </template>
            <span class="text-base font-semibold text-gray-900 dark:text-gray-100 truncate">{{ recordsStore.currentRecord.title }}</span>
            <button
              class="flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors relative group/nav-permalink"
              :title="navPermalinkCopiedId === 'nav-page' ? 'Zkopírováno!' : 'Kopírovat odkaz'"
              @click="copyNavPermalink(currentPageUrl, 'nav-page')"
            >
              <LinkIcon class="w-4 h-4" />
              <span
                v-if="navPermalinkCopiedId === 'nav-page'"
                class="absolute -top-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-gray-900 dark:bg-gray-700 px-2 py-0.5 text-[10px] text-white pointer-events-none z-10"
              >Zkopírováno!</span>
            </button>
          </template>
          <h1 v-else class="text-base font-semibold text-gray-900 dark:text-gray-100 flex-shrink-0">
            {{ recordsListTitle }}
          </h1>
        </div>

        <div class="flex-1" />

        <!-- Global search / command palette trigger -->
        <div class="hidden md:flex items-center w-64 bg-gray-100 dark:bg-gray-700 rounded-xl px-3 py-2 gap-2 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" role="button" tabindex="0" aria-label="Open command palette (Cmd+K)" @click="commandPaletteOpen = true" @keydown.enter="commandPaletteOpen = true">
          <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span class="text-sm text-gray-400 dark:text-gray-500 flex-1">Search…</span>
          <kbd class="text-xs text-gray-400 dark:text-gray-500 font-mono">⌘K</kbd>
        </div>

        <!-- Time tracking (inline header) -->
        <TimerWidget variant="inline" />

        <!-- Notification bell -->
        <div class="relative">
          <button
            class="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 relative"
            aria-label="Notifications"
            :aria-expanded="notifOpen"
            @click="toggleNotifPanel"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <span
              v-if="notifStore.unreadCount > 0"
              class="absolute -top-0.5 -right-0.5 min-w-4 h-4 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1"
              :aria-label="t('appShell.unreadNotificationsAria', { count: notifStore.unreadCount })"
            >{{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}</span>
          </button>

          <!-- Notification slide-over panel -->
          <Teleport to="body">
            <div
              v-if="notifOpen"
              class="fixed inset-0 z-40"
              @click.self="notifOpen = false"
            >
              <div
                class="absolute right-0 top-0 h-full w-full max-w-sm bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-2xl flex flex-col"
                role="dialog"
                aria-label="Notifications panel"
                aria-modal="true"
              >
                <!-- Panel header -->
                <div class="flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-700">
                  <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100 flex-1">{{ t('appShell.notifications') }}</h2>
                  <button
                    v-if="notifStore.unreadCount > 0"
                    class="text-xs text-red-600 hover:underline"
                    @click="notifStore.markAllRead()"
                  >{{ t('appShell.markAllRead') }}</button>
                  <button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300" aria-label="Close notifications" @click="notifOpen = false"><XMarkIcon class="w-5 h-5" /></button>
                </div>

                <!-- Notification list -->
                <div class="flex-1 overflow-y-auto">
                  <div v-if="notifStore.loading" class="p-4 space-y-2">
                    <div v-for="i in 4" :key="i" class="h-14 bg-gray-100 dark:bg-gray-700 rounded-xl animate-pulse" />
                  </div>
                  <div v-else-if="notifStore.notifications.length === 0" class="flex flex-col items-center justify-center py-20 text-gray-400">
                    <BellIcon class="w-10 h-10 mx-auto mb-3 text-gray-300 dark:text-gray-600" aria-hidden="true" />
                    <p class="text-sm">{{ t('appShell.noNotifications') }}</p>
                  </div>
                  <ul v-else class="divide-y divide-gray-50 dark:divide-gray-700" role="list">
                    <li
                      v-for="n in notificationsWithLinks"
                      :key="n.id"
                      class="px-5 py-3.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      :class="n.is_read ? '' : 'bg-red-50/40 dark:bg-red-900/10'"
                    >
                      <RouterLink
                        v-if="n.link"
                        :to="n.link"
                        class="group flex items-start gap-3 w-full"
                        @click="handleNotificationClick(n)"
                      >
                        <component :is="eventIcon(n.event)" class="w-5 h-5 flex-shrink-0 mt-0.5 text-gray-500 dark:text-gray-400" aria-hidden="true" />
                        <div class="min-w-0 flex-1">
                          <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">{{ eventLabel(n.event) }}</p>
                          <p class="text-sm text-gray-900 dark:text-gray-100 leading-snug truncate group-hover:text-red-600 dark:group-hover:text-red-400">{{ notifTitle(n) }}</p>
                          <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ formatNotifTime(n.created_at) }}</p>
                        </div>
                        <LinkIcon class="w-4 h-4 text-gray-400 group-hover:text-red-600 dark:group-hover:text-red-400 flex-shrink-0 mt-1" aria-hidden="true" />
                        <span v-if="!n.is_read" class="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5" aria-hidden="true" />
                      </RouterLink>
                      <div v-else class="flex items-start gap-3 w-full">
                        <component :is="eventIcon(n.event)" class="w-5 h-5 flex-shrink-0 mt-0.5 text-gray-500 dark:text-gray-400" aria-hidden="true" />
                        <div class="min-w-0 flex-1">
                          <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5">{{ eventLabel(n.event) }}</p>
                          <p class="text-sm text-gray-900 dark:text-gray-100 leading-snug truncate">{{ notifTitle(n) }}</p>
                          <p class="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{{ formatNotifTime(n.created_at) }}</p>
                        </div>
                        <span v-if="!n.is_read" class="w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5" aria-hidden="true" />
                      </div>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </Teleport>
        </div>

        <!-- Workspace switcher -->
        <div v-if="firmStore.firms.length > 1" class="relative">
          <button
            class="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            :aria-expanded="firmSwitcherOpen"
            aria-haspopup="listbox"
            @click="toggleFirmSwitcher"
          >
            <span class="max-w-32 truncate">{{ firmStore.activeFirm?.name }}</span>
            <span class="text-gray-400" aria-hidden="true">▾</span>
          </button>
          <div
            v-if="firmSwitcherOpen"
            class="absolute right-0 top-10 z-10 w-48 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg py-1"
            role="listbox"
            aria-label="Select workspace"
          >
            <button
              v-for="firm in firmStore.firms"
              :key="firm.id"
              class="w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
              role="option"
              :aria-selected="firm.id === firmStore.activeFirm?.id"
              @click="switchFirm(String(firm.id))"
            >
              <span class="flex-1 truncate">{{ firm.name }}</span>
              <span v-if="firm.id === firmStore.activeFirm?.id" aria-hidden="true"><CheckCircleIcon class="w-3.5 h-3.5 text-red-600" /></span>
            </button>
          </div>
        </div>
      </header>

      <!-- Page content -->
      <main id="main-content" class="flex-1 overflow-y-auto dark:bg-gray-900" tabindex="-1">
        <RouterView />
      </main>
    </div>
  </div>

  <!-- Keyboard shortcuts help modal -->
  <Teleport to="body">
    <div
      v-if="shortcutHelpOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
      @click.self="shortcutHelpOpen = false"
    >
      <div
        class="bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
      >
        <div class="flex items-center justify-between mb-4">
          <h3 id="shortcuts-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('appShell.keyboardShortcuts') }}</h3>
          <button
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            aria-label="Close shortcuts help"
            @click="shortcutHelpOpen = false"
          ><XMarkIcon class="w-5 h-5" /></button>
        </div>
        <ul class="space-y-2" role="list">
          <li v-for="sc in SHORTCUTS" :key="sc.keys" class="flex items-center justify-between gap-4">
            <span class="text-sm text-gray-600 dark:text-gray-400">{{ sc.description }}</span>
            <kbd class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-xs font-mono text-gray-700 dark:text-gray-300">{{ sc.keys }}</kbd>
          </li>
        </ul>
      </div>
    </div>
  </Teleport>

  <!-- Command Palette (Cmd/Ctrl + K) -->
  <Teleport to="body">
    <CommandPalette v-if="commandPaletteOpen" @close="commandPaletteOpen = false" />
  </Teleport>
</template>

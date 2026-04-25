import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/api'
import { extractErrorMessage } from '@/api/errors'
import { useFirmStore } from '@/stores/firm'

export interface NotificationOut {
  id: string
  event: string
  payload: Record<string, unknown>
  is_read: boolean
  created_at: string
}

export const useNotificationsStore = defineStore('notifications', () => {
  const notifications = ref<NotificationOut[]>([])
  const unreadCount = ref(0)
  const loading = ref(false)

  function firmHeader() {
    const firmStore = useFirmStore()
    return firmStore.activeFirm ? { 'X-Firm-ID': String(firmStore.activeFirm.id) } : {}
  }

  const unread = computed(() => notifications.value.filter((n) => !n.is_read))

  async function fetchUnreadCount() {
    const res = await api.get<{ count: number }>('/api/v1/crm/notifications/unread-count')
    if (res.ok) unreadCount.value = res.data.count
  }

  async function fetchNotifications(unreadOnly = false): Promise<void> {
    loading.value = true
    try {
      const params = unreadOnly ? '?unread_only=true' : ''
      const res = await api.get<NotificationOut[]>(`/api/v1/crm/notifications${params}`)
      if (res.ok) {
        notifications.value = res.data
        unreadCount.value = res.data.filter((n) => !n.is_read).length
      }
    } finally {
      loading.value = false
    }
  }

  async function markAllRead(): Promise<void> {
    const res = await api.post<{ updated: number }>('/api/v1/crm/notifications/mark-read', {})
    if (res.ok) {
      notifications.value = notifications.value.map((n) => ({ ...n, is_read: true }))
      unreadCount.value = 0
    }
  }

  async function markRead(ids: string[]): Promise<void> {
    if (!ids.length) return
    const res = await api.post<{ updated: number }>('/api/v1/crm/notifications/mark-read', { ids })
    if (res.ok) {
      notifications.value = notifications.value.map((n) => (ids.includes(n.id) ? { ...n, is_read: true } : n))
      unreadCount.value = notifications.value.filter((n) => !n.is_read).length
    }
  }

  /** Called when a WS event arrives — prepend to the local list and bump unread count. */
  function pushNotification(event: string, payload: Record<string, unknown>) {
    const n: NotificationOut = {
      id: crypto.randomUUID(),
      event,
      payload,
      is_read: false,
      created_at: new Date().toISOString(),
    }
    notifications.value.unshift(n)
    unreadCount.value += 1
  }

  return {
    notifications,
    unreadCount,
    loading,
    unread,
    fetchUnreadCount,
    fetchNotifications,
    markAllRead,
    markRead,
    pushNotification,
  }
})

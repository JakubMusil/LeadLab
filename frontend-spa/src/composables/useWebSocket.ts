/**
 * useWebSocket — composable for a firm-scoped real-time WebSocket connection.
 *
 * Features:
 *   - Connects to ws(s)://<host>/ws/firms/<firmId>/ on mount.
 *   - Reconnects automatically with exponential back-off (capped at 30 s).
 *   - Dispatches incoming events to registered handlers.
 *   - Gracefully disconnects on unmount / firm change.
 *
 * Usage:
 *   const { on } = useWebSocket()
 *   on('lead.created', (payload) => leadsStore.handleLeadCreated(payload))
 */

import { ref, watch, onUnmounted } from 'vue'
import { useFirmStore } from '@/stores/firm'

type EventHandler = (payload: Record<string, unknown>) => void

const handlers = new Map<string, Set<EventHandler>>()

let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectDelay = 1000 // ms, doubles on each failure up to MAX_DELAY
const MAX_DELAY = 30_000

function getWsUrl(firmId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws/firms/${firmId}/`
}

function clearReconnectTimer() {
  if (reconnectTimer !== null) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
}

function scheduleReconnect(firmId: string) {
  clearReconnectTimer()
  reconnectTimer = setTimeout(() => {
    connect(firmId)
  }, reconnectDelay)
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_DELAY)
}

function connect(firmId: string) {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }

  socket = new WebSocket(getWsUrl(firmId))

  socket.onopen = () => {
    reconnectDelay = 1000 // reset back-off on successful connect
  }

  socket.onmessage = (ev: MessageEvent) => {
    try {
      const msg = JSON.parse(ev.data as string) as { event: string; payload: Record<string, unknown> }
      const listeners = handlers.get(msg.event)
      if (listeners) {
        for (const fn of listeners) fn(msg.payload)
      }
    } catch {
      // malformed message — ignore
    }
  }

  socket.onclose = (ev: CloseEvent) => {
    socket = null
    // 4001 = authentication denied by consumer — do not reconnect
    if (ev.code !== 4001) {
      scheduleReconnect(firmId)
    }
  }

  socket.onerror = () => {
    socket?.close()
  }
}

function disconnect() {
  clearReconnectTimer()
  if (socket) {
    socket.onclose = null // prevent reconnect loop on intentional close
    socket.close()
    socket = null
  }
}

// Module-level connection state so the composable shares one socket.
let activeFirmId: string | null = null

export function useWebSocket() {
  const firmStore = useFirmStore()

  function ensureConnected() {
    const fid = firmStore.activeFirm ? String(firmStore.activeFirm.id) : null
    if (!fid) {
      disconnect()
      activeFirmId = null
      return
    }
    if (fid !== activeFirmId) {
      disconnect()
      activeFirmId = fid
      connect(fid)
    }
  }

  // Watch for firm changes at the composable level.
  const stopWatch = watch(
    () => firmStore.activeFirm?.id,
    () => ensureConnected(),
    { immediate: true },
  )

  onUnmounted(() => {
    stopWatch()
    // We intentionally keep the socket alive across component unmounts because
    // AppShell is persistent; only disconnect when the firm changes or the user
    // logs out.
  })

  function on(event: string, handler: EventHandler) {
    if (!handlers.has(event)) handlers.set(event, new Set())
    handlers.get(event)!.add(handler)
  }

  function off(event: string, handler: EventHandler) {
    handlers.get(event)?.delete(handler)
  }

  return { on, off, disconnect }
}

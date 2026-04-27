import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

export const shortcutHelpOpen = ref(false)
export const commandPaletteOpen = ref(false)

export const SHORTCUTS = [
  { keys: 'Cmd/Ctrl + K', description: 'Open command palette' },
  { keys: 'G L', description: 'Go to Opportunities' },
  { keys: 'G C', description: 'Go to Directory' },
  { keys: 'G D', description: 'Go to Dashboard' },
  { keys: 'N', description: 'New Opportunity (on Opportunities page)' },
  { keys: '?', description: 'Show this help' },
]

export function useKeyboardShortcuts(onNewLead?: () => void) {
  const router = useRouter()
  const route = useRoute()
  let pendingKey = ''
  let pendingTimer: ReturnType<typeof setTimeout> | null = null

  function handleKeydown(e: KeyboardEvent) {
    // Cmd/Ctrl + K → command palette (fires even inside inputs)
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault()
      commandPaletteOpen.value = !commandPaletteOpen.value
      return
    }

    const tag = (e.target as HTMLElement).tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
    if (e.metaKey || e.ctrlKey || e.altKey) return

    const key = e.key.toUpperCase()

    if (key === '?') {
      shortcutHelpOpen.value = !shortcutHelpOpen.value
      return
    }

    if (pendingKey === 'G') {
      if (pendingTimer) clearTimeout(pendingTimer)
      pendingKey = ''
      if (key === 'L') { router.push('/app/opportunities'); return }
      if (key === 'C') { router.push('/app/directory'); return }
      if (key === 'D') { router.push('/app/dashboard'); return }
      return
    }

    if (key === 'G') {
      pendingKey = 'G'
      pendingTimer = setTimeout(() => { pendingKey = '' }, 1000)
      return
    }

    if (key === 'N' && route.path === '/app/opportunities') {
      onNewLead?.()
    }
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown))
  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
    if (pendingTimer) clearTimeout(pendingTimer)
  })
}

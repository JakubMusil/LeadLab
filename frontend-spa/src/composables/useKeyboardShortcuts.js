import { onMounted, onUnmounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';
export const shortcutHelpOpen = ref(false);
export const commandPaletteOpen = ref(false);
export const SHORTCUTS = [
    { keys: 'Cmd/Ctrl + K', description: 'Open command palette' },
    { keys: 'G L', description: 'Go to Leads' },
    { keys: 'G C', description: 'Go to Customers' },
    { keys: 'G D', description: 'Go to Dashboard' },
    { keys: 'N', description: 'New Lead (on Leads page)' },
    { keys: '?', description: 'Show this help' },
];
export function useKeyboardShortcuts(onNewLead) {
    const router = useRouter();
    const route = useRoute();
    let pendingKey = '';
    let pendingTimer = null;
    function handleKeydown(e) {
        // Cmd/Ctrl + K → command palette (fires even inside inputs)
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            commandPaletteOpen.value = !commandPaletteOpen.value;
            return;
        }
        const tag = e.target.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT')
            return;
        if (e.metaKey || e.ctrlKey || e.altKey)
            return;
        const key = e.key.toUpperCase();
        if (key === '?') {
            shortcutHelpOpen.value = !shortcutHelpOpen.value;
            return;
        }
        if (pendingKey === 'G') {
            if (pendingTimer)
                clearTimeout(pendingTimer);
            pendingKey = '';
            if (key === 'L') {
                router.push('/app/leads');
                return;
            }
            if (key === 'C') {
                router.push('/app/customers');
                return;
            }
            if (key === 'D') {
                router.push('/app/dashboard');
                return;
            }
            return;
        }
        if (key === 'G') {
            pendingKey = 'G';
            pendingTimer = setTimeout(() => { pendingKey = ''; }, 1000);
            return;
        }
        if (key === 'N' && route.path === '/app/leads') {
            onNewLead?.();
        }
    }
    onMounted(() => window.addEventListener('keydown', handleKeydown));
    onUnmounted(() => {
        window.removeEventListener('keydown', handleKeydown);
        if (pendingTimer)
            clearTimeout(pendingTimer);
    });
}

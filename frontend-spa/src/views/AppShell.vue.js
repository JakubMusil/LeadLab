/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, onMounted, onUnmounted, watchEffect } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useFirmStore } from '@/stores/firm';
import { useLeadsStore } from '@/stores/leads';
import { useNotificationsStore } from '@/stores/notifications';
import { useSavedViewsStore } from '@/stores/savedViews';
import { useWebSocket } from '@/composables/useWebSocket';
import { useTheme } from '@/composables/useTheme';
import { useKeyboardShortcuts, shortcutHelpOpen, commandPaletteOpen, SHORTCUTS } from '@/composables/useKeyboardShortcuts';
import { useI18n } from '@/composables/useI18n';
import { pluginRegistry } from '@/plugins';
import CommandPalette from '@/components/CommandPalette.vue';
const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const firmStore = useFirmStore();
const leadsStore = useLeadsStore();
const notifStore = useNotificationsStore();
const savedViewsStore = useSavedViewsStore();
const { isDark, toggleDark } = useTheme();
const { t } = useI18n();
watchEffect(() => {
    const color = firmStore.activeFirm?.primary_color ?? '#dc2626';
    document.documentElement.style.setProperty('--brand-color', color);
});
const sidebarOpen = ref(true);
const mobileMenuOpen = ref(false);
const firmSwitcherOpen = ref(false);
const notifOpen = ref(false);
const { on, off } = useWebSocket();
// ---------------------------------------------------------------------------
// WebSocket event handlers
// ---------------------------------------------------------------------------
function onLeadCreated(payload) {
    const lead = payload;
    if (!leadsStore.leads.find((l) => l.id === lead.id)) {
        leadsStore.leads.unshift(lead);
    }
    notifStore.pushNotification('lead.created', payload);
}
function onLeadUpdated(payload) {
    const lead = payload;
    const idx = leadsStore.leads.findIndex((l) => l.id === lead.id);
    if (idx !== -1)
        leadsStore.leads[idx] = lead;
    if (leadsStore.currentLead?.id === lead.id)
        leadsStore.currentLead = lead;
    notifStore.pushNotification('lead.updated', payload);
}
function onLeadDeleted(payload) {
    const id = payload.id;
    leadsStore.leads = leadsStore.leads.filter((l) => l.id !== id);
    notifStore.pushNotification('lead.deleted', payload);
}
function onActivityCreated(payload) {
    notifStore.pushNotification('activity.created', payload);
}
function onTaskCompleted(payload) {
    notifStore.pushNotification('task.completed', payload);
}
onMounted(async () => {
    if (!authStore.user)
        await authStore.fetchMe();
    if (firmStore.firms.length === 0)
        await firmStore.fetchFirms();
    await notifStore.fetchNotifications();
    savedViewsStore.fetchViews();
    on('lead.created', onLeadCreated);
    on('lead.updated', onLeadUpdated);
    on('lead.deleted', onLeadDeleted);
    on('activity.created', onActivityCreated);
    on('task.completed', onTaskCompleted);
});
onUnmounted(() => {
    off('lead.created', onLeadCreated);
    off('lead.updated', onLeadUpdated);
    off('lead.deleted', onLeadDeleted);
    off('activity.created', onActivityCreated);
    off('task.completed', onTaskCompleted);
});
// Keyboard shortcuts (no "new lead" trigger here – LeadsView handles that)
useKeyboardShortcuts();
const userInitials = computed(() => {
    const u = authStore.user;
    if (!u)
        return '?';
    return `${u.first_name?.[0] ?? ''}${u.last_name?.[0] ?? ''}`.toUpperCase() || (u.email[0]?.toUpperCase() ?? '?');
});
const navItems = computed(() => [
    { label: t('nav.overview'), icon: '⊞', path: '/app/dashboard' },
    { label: t('nav.leads'), icon: '◎', path: '/app/leads' },
    { label: t('nav.customers'), icon: '👥', path: '/app/customers' },
    { label: t('nav.calendar'), icon: '📅', path: '/app/calendar' },
    { label: t('nav.team'), icon: '🤝', path: '/app/team' },
    { label: t('nav.analytics'), icon: '📊', path: '/app/analytics' },
    ...(authStore.user?.is_staff ? [{ label: t('nav.superAdmin'), icon: '🛡', path: '/app/superadmin' }] : []),
    ...pluginRegistry.flatMap((p) => p.navItems ?? []),
    { label: t('nav.settings'), icon: '⚙', path: '/app/settings' },
]);
function isActive(path) {
    return route.path === path || route.path.startsWith(path + '/');
}
async function signOut() {
    await authStore.logout();
}
function toggleFirmSwitcher() {
    firmSwitcherOpen.value = !firmSwitcherOpen.value;
}
function switchFirm(id) {
    firmStore.setActiveFirm(id);
    firmSwitcherOpen.value = false;
}
function toggleNotifPanel() {
    notifOpen.value = !notifOpen.value;
    if (notifOpen.value && notifStore.unreadCount > 0) {
        notifStore.markAllRead();
    }
}
function eventLabel(event) {
    const map = {
        'lead.created': 'New lead created',
        'lead.updated': 'Lead updated',
        'lead.deleted': 'Lead deleted',
        'activity.created': 'New activity logged',
        'task.completed': 'Task completed',
    };
    return map[event] ?? event;
}
function eventIcon(event) {
    const map = {
        'lead.created': '◎',
        'lead.updated': '✎',
        'lead.deleted': '🗑',
        'activity.created': '💬',
        'task.completed': '✅',
    };
    return map[event] ?? '🔔';
}
function notifTitle(n) {
    if (n.event === 'lead.created' || n.event === 'lead.updated') {
        return n.payload.title || eventLabel(n.event);
    }
    if (n.event === 'activity.created') {
        return n.payload.content_text || n.payload.type || 'Activity';
    }
    if (n.event === 'task.completed') {
        return n.payload.title || 'Task completed';
    }
    if (n.event === 'lead.deleted') {
        return `Lead ${n.payload.id} deleted`;
    }
    return eventLabel(n.event);
}
function formatNotifTime(ts) {
    return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
const __VLS_ctx = ({ ...{} });
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)(({
	href: '#main-content',
	class: 'sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:px-4 focus:py-2 focus:bg-red-600 focus:text-white focus:rounded-xl focus:text-sm focus:font-medium'
}));
/** @type {__VLS_StyleScopedClasses['sr-only']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:not-sr-only']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:top-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:left-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:font-medium']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex h-screen bg-gray-50 dark:bg-gray-900 overflow-hidden' }));
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
if (__VLS_ctx.mobileMenuOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.mobileMenuOpen) return;
		__VLS_ctx.mobileMenuOpen = false;
		[mobileMenuOpen, mobileMenuOpen];
	},
	...{ class: 'fixed inset-0 z-20 bg-black/40 lg:hidden' },
	'aria-hidden': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-20']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-black/40']} */ ;
    /** @type {__VLS_StyleScopedClasses['lg:hidden']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.aside, __VLS_intrinsics.aside)(({
	class: 'fixed inset-y-0 left-0 z-30 flex flex-col bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 lg:static',
	...{ class: [__VLS_ctx.sidebarOpen ? 'w-64' : 'w-16', __VLS_ctx.mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'] },
	'aria-label': 'Sidebar navigation'
}));
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-y-0']} */ ;
/** @type {__VLS_StyleScopedClasses['left-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-30']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['border-r']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-200']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:static']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center h-16 px-4 border-b border-gray-100 dark:border-gray-700 gap-3 min-w-0' }));
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
if (__VLS_ctx.firmStore.activeFirm?.logo_url) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.img)(({
	src: __VLS_ctx.firmStore.activeFirm.logo_url,
	alt: __VLS_ctx.firmStore.activeFirm?.name ?? 'Logo',
	class: 'w-8 h-8 rounded-lg object-cover flex-shrink-0'
}));
    /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
	...{ style: { backgroundColor: __VLS_ctx.firmStore.activeFirm?.primary_color ?? '#dc2626' } }
}));
    /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-white text-sm font-bold',
	'aria-hidden': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
}
if (__VLS_ctx.sidebarOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'min-w-0 flex-1' }));
    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-sm font-semibold text-gray-900 dark:text-gray-100 truncate' }));
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
    (__VLS_ctx.firmStore.activeFirm?.name ?? 'LeadLab');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-xs text-gray-400 dark:text-gray-500 truncate' }));
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		__VLS_ctx.sidebarOpen = !__VLS_ctx.sidebarOpen;
		[
			mobileMenuOpen,
			sidebarOpen,
			sidebarOpen,
			sidebarOpen,
			sidebarOpen,
			firmStore,
			firmStore,
			firmStore,
			firmStore,
			firmStore
		];
	},
	...{ class: 'hidden lg:flex ml-auto items-center justify-center w-6 h-6 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex-shrink-0' },
	'aria-label': __VLS_ctx.sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar',
	title: __VLS_ctx.sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'
}));
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:flex']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-xs',
	'aria-hidden': 'true'
}));
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
(__VLS_ctx.sidebarOpen ? '‹' : '›');
__VLS_asFunctionalElement1(__VLS_intrinsics.nav, __VLS_intrinsics.nav)(({
	class: 'flex-1 px-2 py-4 space-y-1 overflow-y-auto',
	'aria-label': 'Main navigation'
}));
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
for (const [item] of __VLS_vFor((__VLS_ctx.navItems))) {
    (item.path);
    let __VLS_0;
    /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
    RouterLink;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0(({
	'onClick': {},
	to: item.path,
	...{ class: 'flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors group' },
	...{ class: __VLS_ctx.isActive(item.path) ? 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100' },
	'aria-current': __VLS_ctx.isActive(item.path) ? 'page' : undefined
})));
    const __VLS_2 = __VLS_1(({
	'onClick': {},
	to: item.path,
	...{ class: 'flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors group' },
	...{ class: __VLS_ctx.isActive(item.path) ? 'bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100' },
	'aria-current': __VLS_ctx.isActive(item.path) ? 'page' : undefined
}), ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_5;
    const __VLS_6 = ({ click: {} },
        { onClick: (...[$event]) => {
                __VLS_ctx.mobileMenuOpen = false;
                // @ts-ignore
                [mobileMenuOpen, sidebarOpen, sidebarOpen, sidebarOpen, navItems, isActive, isActive,];
            } });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['group']} */ ;
    const { default: __VLS_7 } = __VLS_3.slots;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-base flex-shrink-0 w-5 text-center',
	'aria-hidden': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    (item.icon);
    if (__VLS_ctx.sidebarOpen) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'truncate' }));
        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
        (item.label);
    }
    // @ts-ignore
    [sidebarOpen,];
    var __VLS_3;
    var __VLS_4;
    if (__VLS_ctx.sidebarOpen && item.path === '/app/leads' && __VLS_ctx.savedViewsStore.viewsForEntity('leads').length > 0) {
        for (const [view] of __VLS_vFor((__VLS_ctx.savedViewsStore.viewsForEntity('leads')))) {
            let __VLS_8;
            /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
            RouterLink;
            // @ts-ignore
            const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8(({
	'onClick': {},
	key: view.id,
	to: `/app/leads?view=${view.id}`,
	...{ class: 'flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300' }
})));
            const __VLS_10 = __VLS_9(({
	'onClick': {},
	key: view.id,
	to: `/app/leads?view=${view.id}`,
	...{ class: 'flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300' }
}), ...__VLS_functionalComponentArgsRest(__VLS_9));
            let __VLS_13;
            const __VLS_14 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!(__VLS_ctx.sidebarOpen && item.path === '/app/leads' && __VLS_ctx.savedViewsStore.viewsForEntity('leads').length > 0))
                            return;
                        __VLS_ctx.mobileMenuOpen = false;
                        // @ts-ignore
                        [mobileMenuOpen, sidebarOpen, savedViewsStore, savedViewsStore,];
                    } });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['pl-10']} */ ;
            /** @type {__VLS_StyleScopedClasses['pr-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-300']} */ ;
            const { default: __VLS_15 } = __VLS_11.slots;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                'aria-hidden': "true",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'truncate' }));
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (view.name);
            // @ts-ignore
            [];
            var __VLS_11;
            var __VLS_12;
            // @ts-ignore
            [];
        }
    }
    if (__VLS_ctx.sidebarOpen && item.path === '/app/customers' && __VLS_ctx.savedViewsStore.viewsForEntity('customers').length > 0) {
        for (const [view] of __VLS_vFor((__VLS_ctx.savedViewsStore.viewsForEntity('customers')))) {
            let __VLS_16;
            /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
            RouterLink;
            // @ts-ignore
            const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16(({
	'onClick': {},
	key: view.id,
	to: `/app/customers?view=${view.id}`,
	...{ class: 'flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300' }
})));
            const __VLS_18 = __VLS_17(({
	'onClick': {},
	key: view.id,
	to: `/app/customers?view=${view.id}`,
	...{ class: 'flex items-center gap-2 pl-10 pr-3 py-1.5 rounded-xl text-xs font-medium transition-colors text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300' }
}), ...__VLS_functionalComponentArgsRest(__VLS_17));
            let __VLS_21;
            const __VLS_22 = ({ click: {} },
                { onClick: (...[$event]) => {
                        if (!(__VLS_ctx.sidebarOpen && item.path === '/app/customers' && __VLS_ctx.savedViewsStore.viewsForEntity('customers').length > 0))
                            return;
                        __VLS_ctx.mobileMenuOpen = false;
                        // @ts-ignore
                        [mobileMenuOpen, sidebarOpen, savedViewsStore, savedViewsStore,];
                    } });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['pl-10']} */ ;
            /** @type {__VLS_StyleScopedClasses['pr-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-300']} */ ;
            const { default: __VLS_23 } = __VLS_19.slots;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                'aria-hidden': "true",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'truncate' }));
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (view.name);
            // @ts-ignore
            [];
            var __VLS_19;
            var __VLS_20;
            // @ts-ignore
            [];
        }
    }
    // @ts-ignore
    [];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'border-t border-gray-100 dark:border-gray-700 p-3' }));
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.toggleDark,
	...{ class: 'w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors mb-2' },
	'aria-label': __VLS_ctx.isDark ? 'Switch to light mode' : 'Switch to dark mode',
	title: __VLS_ctx.isDark ? 'Switch to light mode' : 'Switch to dark mode'
}));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-base flex-shrink-0 w-5 text-center',
	'aria-hidden': 'true'
}));
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['w-5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
(__VLS_ctx.isDark ? '☀' : '🌙');
if (__VLS_ctx.sidebarOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'truncate text-xs' }));
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    (__VLS_ctx.isDark ? 'Light mode' : 'Dark mode');
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-3 min-w-0' }));
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'w-8 h-8 rounded-full bg-red-600 flex items-center justify-center flex-shrink-0 text-white text-xs font-semibold',
	'aria-hidden': 'true'
}));
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
(__VLS_ctx.userInitials);
if (__VLS_ctx.sidebarOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'min-w-0 flex-1' }));
    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-xs font-medium text-gray-900 dark:text-gray-100 truncate' }));
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
    (__VLS_ctx.authStore.user?.full_name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-xs text-gray-400 dark:text-gray-500 truncate' }));
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
    (__VLS_ctx.authStore.user?.email);
}
if (__VLS_ctx.sidebarOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.signOut,
	...{ class: 'flex-shrink-0 text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700' },
	'aria-label': 'Sign out',
	title: 'Sign out'
}));
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
}
if (!__VLS_ctx.sidebarOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.signOut,
	...{ class: 'mt-2 w-full flex items-center justify-center text-gray-400 hover:text-red-600 text-xs p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700' },
	'aria-label': 'Sign out',
	title: 'Sign out'
}));
    /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex-1 flex flex-col min-w-0 overflow-hidden' }));
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.header, __VLS_intrinsics.header)(({
	class: 'flex items-center h-16 px-4 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 gap-4',
	role: 'banner'
}));
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		__VLS_ctx.mobileMenuOpen = !__VLS_ctx.mobileMenuOpen;
		[
			mobileMenuOpen,
			mobileMenuOpen,
			sidebarOpen,
			sidebarOpen,
			sidebarOpen,
			sidebarOpen,
			toggleDark,
			isDark,
			isDark,
			isDark,
			isDark,
			userInitials,
			authStore,
			authStore,
			signOut,
			signOut
		];
	},
	...{ class: 'lg:hidden p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700' },
	'aria-label': 'Open navigation menu'
}));
/** @type {__VLS_StyleScopedClasses['lg:hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'w-5 h-5',
	fill: 'none',
	stroke: 'currentColor',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
/** @type {__VLS_StyleScopedClasses['w-5']} */ ;
/** @type {__VLS_StyleScopedClasses['h-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.path)({
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
    'stroke-width': "2",
    d: "M4 6h16M4 12h16M4 18h16",
});
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)(({ class: 'text-base font-semibold text-gray-900 dark:text-gray-100 flex-shrink-0' }));
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
(__VLS_ctx.route.meta?.title ?? 'LeadLab');
__VLS_asFunctionalElement1(__VLS_intrinsics.div)(({ class: 'flex-1' }));
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		__VLS_ctx.commandPaletteOpen = true;
		[route, commandPaletteOpen];
	},
	...{ onKeydown: (...[$event]) => {
		__VLS_ctx.commandPaletteOpen = true;
		[commandPaletteOpen];
	} },
	...{ class: 'hidden md:flex items-center w-64 bg-gray-100 dark:bg-gray-700 rounded-xl px-3 py-2 gap-2 cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors' },
	role: 'button',
	tabindex: '0',
	'aria-label': 'Open command palette (Cmd+K)'
}));
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['md:flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-64']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'w-4 h-4 text-gray-400 flex-shrink-0',
	fill: 'none',
	stroke: 'currentColor',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.path)({
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
    'stroke-width': "2",
    d: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z",
});
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-sm text-gray-400 dark:text-gray-500 flex-1' }));
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.kbd, __VLS_intrinsics.kbd)(({ class: 'text-xs text-gray-400 dark:text-gray-500 font-mono' }));
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'relative' }));
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.toggleNotifPanel,
	...{ class: 'p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 relative' },
	'aria-label': 'Notifications',
	'aria-expanded': __VLS_ctx.notifOpen
}));
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'w-5 h-5',
	fill: 'none',
	stroke: 'currentColor',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
/** @type {__VLS_StyleScopedClasses['w-5']} */ ;
/** @type {__VLS_StyleScopedClasses['h-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.path)({
    'stroke-linecap': "round",
    'stroke-linejoin': "round",
    'stroke-width': "2",
    d: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6 6 0 10-12 0v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
});
if (__VLS_ctx.notifStore.unreadCount > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'absolute -top-0.5 -right-0.5 min-w-4 h-4 bg-red-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1',
	'aria-label': '`${notifStore.unreadCount} unread notifications`'
}));
    /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
    /** @type {__VLS_StyleScopedClasses['-top-0.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['-right-0.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-1']} */ ;
    (__VLS_ctx.notifStore.unreadCount > 99 ? '99+' : __VLS_ctx.notifStore.unreadCount);
}
let __VLS_24;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent1(__VLS_24, new __VLS_24({
    to: "body",
}));
const __VLS_26 = __VLS_25({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
const { default: __VLS_29 } = __VLS_27.slots;
if (__VLS_ctx.notifOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.notifOpen) return;
		__VLS_ctx.notifOpen = false;
		[
			toggleNotifPanel,
			notifOpen,
			notifOpen,
			notifOpen,
			notifStore,
			notifStore,
			notifStore
		];
	},
	...{ class: 'fixed inset-0 z-40' }
}));
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-40']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'absolute right-0 top-0 h-full w-full max-w-sm bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 shadow-2xl flex flex-col',
	role: 'dialog',
	'aria-label': 'Notifications panel',
	'aria-modal': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
    /** @type {__VLS_StyleScopedClasses['right-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['top-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-l']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-700' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-5']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)(({ class: 'text-sm font-semibold text-gray-900 dark:text-gray-100 flex-1' }));
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    if (__VLS_ctx.notifStore.unreadCount > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.notifOpen) return;
		if (!(__VLS_ctx.notifStore.unreadCount > 0)) return;
		__VLS_ctx.notifStore.markAllRead();
		[notifStore, notifStore];
	},
	...{ class: 'text-xs text-red-600 hover:underline' }
}));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.notifOpen) return;
		__VLS_ctx.notifOpen = false;
		[notifOpen];
	},
	...{ class: 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-lg leading-none' },
	'aria-label': 'Close notifications'
}));
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['leading-none']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex-1 overflow-y-auto' }));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
    if (__VLS_ctx.notifStore.loading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'p-4 space-y-2' }));
        /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
        for (const [i] of __VLS_vFor((4))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	key: i,
	class: 'h-14 bg-gray-100 dark:bg-gray-700 rounded-xl animate-pulse'
}));
            /** @type {__VLS_StyleScopedClasses['h-14']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
            // @ts-ignore
            [notifStore,];
        }
    }
    else if (__VLS_ctx.notifStore.notifications.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex flex-col items-center justify-center py-20 text-gray-400' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-20']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'text-4xl mb-3',
	'aria-hidden': 'true'
}));
        /** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)(({
	class: 'divide-y divide-gray-50 dark:divide-gray-700',
	role: 'list'
}));
        /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
        /** @type {__VLS_StyleScopedClasses['divide-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:divide-gray-700']} */ ;
        for (const [n] of __VLS_vFor((__VLS_ctx.notifStore.notifications))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)(({
	key: n.id,
	class: 'flex items-start gap-3 px-5 py-3.5 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50',
	...{ class: n.is_read ? '' : 'bg-red-50/40 dark:bg-red-900/10' }
}));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-5']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700/50']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-lg flex-shrink-0 mt-0.5',
	'aria-hidden': 'true'
}));
            /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
            (__VLS_ctx.eventIcon(n.event));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'min-w-0 flex-1' }));
            /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-0.5' }));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-0.5']} */ ;
            (__VLS_ctx.eventLabel(n.event));
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm text-gray-900 dark:text-gray-100 leading-snug truncate' }));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['leading-snug']} */ ;
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (__VLS_ctx.notifTitle(n));
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-xs text-gray-400 dark:text-gray-500 mt-0.5' }));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
            (__VLS_ctx.formatNotifTime(n.created_at));
            if (!n.is_read) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span)(({
	class: 'w-2 h-2 rounded-full bg-red-500 flex-shrink-0 mt-1.5',
	'aria-label': 'Unread'
}));
                /** @type {__VLS_StyleScopedClasses['w-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['h-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-red-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                /** @type {__VLS_StyleScopedClasses['mt-1.5']} */ ;
            }
            // @ts-ignore
            [notifStore, notifStore, eventIcon, eventLabel, notifTitle, formatNotifTime,];
        }
    }
}
// @ts-ignore
[];
var __VLS_27;
if (__VLS_ctx.firmStore.firms.length > 1) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'relative' }));
    /** @type {__VLS_StyleScopedClasses['relative']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.toggleFirmSwitcher,
	...{ class: 'flex items-center gap-2 px-3 py-1.5 rounded-xl border border-gray-200 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700' },
	'aria-expanded': __VLS_ctx.firmSwitcherOpen,
	'aria-haspopup': 'listbox'
}));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'max-w-32 truncate' }));
    /** @type {__VLS_StyleScopedClasses['max-w-32']} */ ;
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
    (__VLS_ctx.firmStore.activeFirm?.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-gray-400',
	'aria-hidden': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    if (__VLS_ctx.firmSwitcherOpen) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'absolute right-0 top-10 z-10 w-48 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg py-1',
	role: 'listbox',
	'aria-label': 'Select workspace'
}));
        /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
        /** @type {__VLS_StyleScopedClasses['right-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['top-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['z-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-48']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        for (const [firm] of __VLS_vFor((__VLS_ctx.firmStore.firms))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!(__VLS_ctx.firmStore.firms.length > 1)) return;
		if (!__VLS_ctx.firmSwitcherOpen) return;
		__VLS_ctx.switchFirm(String(firm.id));
		[
			firmStore,
			firmStore,
			firmStore,
			toggleFirmSwitcher,
			firmSwitcherOpen,
			firmSwitcherOpen,
			switchFirm
		];
	},
	key: firm.id,
	...{ class: 'w-full text-left px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2' },
	role: 'option',
	'aria-selected': firm.id === __VLS_ctx.firmStore.activeFirm?.id
}));
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'flex-1 truncate' }));
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (firm.name);
            if (firm.id === __VLS_ctx.firmStore.activeFirm?.id) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-red-600 text-xs',
	'aria-hidden': 'true'
}));
                /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            }
            // @ts-ignore
            [firmStore, firmStore,];
        }
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.main, __VLS_intrinsics.main)(({
	id: 'main-content',
	class: 'flex-1 overflow-y-auto dark:bg-gray-900',
	tabindex: '-1'
}));
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
let __VLS_30;
/** @ts-ignore @type {typeof __VLS_components.RouterView} */
RouterView;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({}));
const __VLS_32 = __VLS_31({}, ...__VLS_functionalComponentArgsRest(__VLS_31));
let __VLS_35;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent1(__VLS_35, new __VLS_35({
    to: "body",
}));
const __VLS_37 = __VLS_36({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_36));
const { default: __VLS_40 } = __VLS_38.slots;
if (__VLS_ctx.shortcutHelpOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.shortcutHelpOpen) return;
		__VLS_ctx.shortcutHelpOpen = false;
		[shortcutHelpOpen, shortcutHelpOpen];
	},
	...{ class: 'fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40' }
}));
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-black/40']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6',
	role: 'dialog',
	'aria-modal': 'true',
	'aria-labelledby': 'shortcuts-title'
}));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center justify-between mb-4' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({
	id: 'shortcuts-title',
	class: 'text-base font-semibold text-gray-900 dark:text-gray-100'
}));
    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.shortcutHelpOpen) return;
		__VLS_ctx.shortcutHelpOpen = false;
		[shortcutHelpOpen];
	},
	...{ class: 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300' },
	'aria-label': 'Close shortcuts help'
}));
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)(({
	class: 'space-y-2',
	role: 'list'
}));
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    for (const [sc] of __VLS_vFor((__VLS_ctx.SHORTCUTS))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)(({
	key: sc.keys,
	class: 'flex items-center justify-between gap-4'
}));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-sm text-gray-600 dark:text-gray-400' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        (sc.description);
        __VLS_asFunctionalElement1(__VLS_intrinsics.kbd, __VLS_intrinsics.kbd)(({ class: 'inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-100 dark:bg-gray-700 text-xs font-mono text-gray-700 dark:text-gray-300' }));
        /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        (sc.keys);
        // @ts-ignore
        [SHORTCUTS,];
    }
}
// @ts-ignore
[];
var __VLS_38;
let __VLS_41;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent1(__VLS_41, new __VLS_41({
    to: "body",
}));
const __VLS_43 = __VLS_42({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
const { default: __VLS_46 } = __VLS_44.slots;
if (__VLS_ctx.commandPaletteOpen) {
    const __VLS_47 = CommandPalette;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent1(__VLS_47, new __VLS_47(({ 'onClose': {} })));
    const __VLS_49 = __VLS_48(({ 'onClose': {} }), ...__VLS_functionalComponentArgsRest(__VLS_48));
    let __VLS_52;
    const __VLS_53 = ({ close: {} },
        { onClose: (...[$event]) => {
                if (!(__VLS_ctx.commandPaletteOpen))
                    return;
                __VLS_ctx.commandPaletteOpen = false;
                // @ts-ignore
                [commandPaletteOpen, commandPaletteOpen,];
            } });
    var __VLS_50;
    var __VLS_51;
}
// @ts-ignore
[];
var __VLS_44;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

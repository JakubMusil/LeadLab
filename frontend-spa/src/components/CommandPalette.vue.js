/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
/**
 * Global Command Palette — Cmd/Ctrl + K
 *
 * Fuzzy-searches leads, customers, and navigation targets.
 * Triggered by the keyboard shortcut; closed with Escape or click-outside.
 */
import { ref, computed, watch, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useLeadsStore } from '@/stores/leads';
import { useCustomersStore } from '@/stores/customers';
const emit = defineEmits();
const router = useRouter();
const leadsStore = useLeadsStore();
const customersStore = useCustomersStore();
const searchQuery = ref('');
const inputRef = ref(null);
const selectedIndex = ref(0);
const NAV_COMMANDS = [
    { id: 'nav-dashboard', label: 'Dashboard', icon: '⊞', category: 'navigation', action: () => router.push('/app/dashboard') },
    { id: 'nav-leads', label: 'Leads', icon: '◎', category: 'navigation', action: () => router.push('/app/leads') },
    { id: 'nav-customers', label: 'Customers', icon: '👥', category: 'navigation', action: () => router.push('/app/customers') },
    { id: 'nav-calendar', label: 'Calendar', icon: '📅', category: 'navigation', action: () => router.push('/app/calendar') },
    { id: 'nav-team', label: 'Team', icon: '🤝', category: 'navigation', action: () => router.push('/app/team') },
    { id: 'nav-analytics', label: 'Analytics', icon: '📊', category: 'navigation', action: () => router.push('/app/analytics') },
    { id: 'nav-settings', label: 'Settings', icon: '⚙', category: 'navigation', action: () => router.push('/app/settings') },
];
const leadItems = computed(() => leadsStore.leads.slice(0, 50).map((l) => ({
    id: `lead-${l.id}`,
    label: l.title,
    description: `Lead · ${l.status}`,
    icon: '◎',
    category: 'lead',
    action: () => router.push(`/app/leads/${l.id}`),
})));
const customerItems = computed(() => customersStore.customers.slice(0, 50).map((c) => ({
    id: `customer-${c.id}`,
    label: `${c.first_name} ${c.last_name}`.trim(),
    description: c.company_name || 'Customer',
    icon: '👤',
    category: 'customer',
    action: () => router.push(`/app/customers/${c.id}`),
})));
const RECENT_KEY = 'commandPaletteRecent';
function getRecent() {
    try {
        const raw = localStorage.getItem(RECENT_KEY);
        if (!raw)
            return [];
        const ids = JSON.parse(raw);
        const all = [...NAV_COMMANDS, ...leadItems.value, ...customerItems.value];
        return ids
            .map((id) => all.find((i) => i.id === id))
            .filter((i) => !!i)
            .slice(0, 5);
    }
    catch {
        return [];
    }
}
function saveRecent(item) {
    try {
        const raw = localStorage.getItem(RECENT_KEY);
        const ids = raw ? JSON.parse(raw) : [];
        const filtered = ids.filter((i) => i !== item.id);
        localStorage.setItem(RECENT_KEY, JSON.stringify([item.id, ...filtered].slice(0, 10)));
    }
    catch {
        // ignore
    }
}
function fuzzyMatch(query, target) {
    if (!query)
        return true;
    const q = query.toLowerCase();
    const t = target.toLowerCase();
    let qi = 0;
    for (let i = 0; i < t.length && qi < q.length; i++) {
        if (t[i] === q[qi])
            qi++;
    }
    return qi === q.length;
}
const filteredItems = computed(() => {
    const q = searchQuery.value.trim();
    if (!q) {
        const recent = getRecent();
        if (recent.length)
            return recent;
        return NAV_COMMANDS.slice(0, 7);
    }
    const all = [...NAV_COMMANDS, ...leadItems.value, ...customerItems.value];
    return all.filter((item) => fuzzyMatch(q, item.label) || fuzzyMatch(q, item.description ?? '')).slice(0, 12);
});
watch(filteredItems, () => {
    selectedIndex.value = 0;
});
function selectItem(item) {
    saveRecent(item);
    item.action();
    emit('close');
}
function onKeydown(e) {
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex.value = Math.min(selectedIndex.value + 1, filteredItems.value.length - 1);
    }
    else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex.value = Math.max(selectedIndex.value - 1, 0);
    }
    else if (e.key === 'Enter') {
        const item = filteredItems.value[selectedIndex.value];
        if (item)
            selectItem(item);
    }
    else if (e.key === 'Escape') {
        emit('close');
    }
}
onMounted(async () => {
    await nextTick();
    inputRef.value?.focus();
});
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.$emit('close');
            // @ts-ignore
            [$emit,];
        } },
    ...{ class: "fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/50 backdrop-blur-sm" },
    role: "dialog",
    'aria-modal': "true",
    'aria-label': "Command palette",
});
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-[15vh]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-black/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "w-full max-w-lg mx-4 bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-3 px-4 py-3 border-b border-gray-200 dark:border-gray-700" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text-gray-400 text-lg flex-shrink-0" },
});
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    ...{ onKeydown: (__VLS_ctx.onKeydown) },
    ref: "inputRef",
    value: (__VLS_ctx.searchQuery),
    type: "text",
    placeholder: "Search leads, customers, or navigate…",
    ...{ class: "flex-1 bg-transparent outline-none text-gray-900 dark:text-white placeholder-gray-400 text-sm" },
    'aria-autocomplete': "list",
    'aria-controls': "command-palette-results",
});
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.kbd, __VLS_intrinsics.kbd)({
    ...{ class: "hidden sm:flex items-center gap-1 px-1.5 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded border border-gray-300 dark:border-gray-600 flex-shrink-0" },
});
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['sm:flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
    id: "command-palette-results",
    role: "listbox",
    ...{ class: "max-h-80 overflow-y-auto py-1" },
});
/** @type {__VLS_StyleScopedClasses['max-h-80']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
if (__VLS_ctx.filteredItems.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "px-4 py-6 text-center text-sm text-gray-500 dark:text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    (__VLS_ctx.searchQuery);
}
for (const [item, index] of __VLS_vFor((__VLS_ctx.filteredItems))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.selectItem(item);
                // @ts-ignore
                [onKeydown, searchQuery, searchQuery, filteredItems, filteredItems, selectItem,];
            } },
        ...{ onMouseenter: (...[$event]) => {
                __VLS_ctx.selectedIndex = index;
                // @ts-ignore
                [selectedIndex,];
            } },
        key: (item.id),
        role: "option",
        'aria-selected': (index === __VLS_ctx.selectedIndex),
        ...{ class: "flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors" },
        ...{ class: (index === __VLS_ctx.selectedIndex
                ? 'bg-[color:var(--brand-color)] text-white'
                : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-900 dark:text-white') },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-base flex-shrink-0" },
    });
    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    (item.icon);
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex-1 min-w-0" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm font-medium truncate" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
    (item.label);
    if (item.description) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-xs truncate" },
            ...{ class: (index === __VLS_ctx.selectedIndex ? 'text-white/70' : 'text-gray-500 dark:text-gray-400') },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
        (item.description);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-xs flex-shrink-0" },
        ...{ class: (index === __VLS_ctx.selectedIndex ? 'text-white/60' : 'text-gray-400') },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    (item.category === 'navigation' ? 'Page' :
        item.category === 'lead' ? 'Lead' :
            item.category === 'customer' ? 'Customer' : 'Recent');
    // @ts-ignore
    [selectedIndex, selectedIndex, selectedIndex, selectedIndex,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "px-4 py-2 border-t border-gray-200 dark:border-gray-700 flex items-center gap-4 text-xs text-gray-400" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.kbd, __VLS_intrinsics.kbd)({
    ...{ class: "font-mono" },
});
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.kbd, __VLS_intrinsics.kbd)({
    ...{ class: "font-mono" },
});
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.kbd, __VLS_intrinsics.kbd)({
    ...{ class: "font-mono" },
});
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({
    __typeEmits: {},
});
export default {};

/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useLeadsStore, LEAD_STATUSES, getStatusMeta } from '@/stores/leads';
import { useSavedViewsStore } from '@/stores/savedViews';
import { useToast } from '@/composables/useToast';
import { api } from '@/api';
import ContextMenu from '@/components/ContextMenu.vue';
import LeadScoreBadge from '@/components/LeadScoreBadge.vue';
const route = useRoute();
const router = useRouter();
const store = useLeadsStore();
const savedViewsStore = useSavedViewsStore();
const toast = useToast();
const viewMode = ref('table');
const filterStatus = ref(route.query.status ?? '');
const filterSource = ref('');
const showModal = ref(false);
const editingLead = ref(null);
const confirmDeleteId = ref(null);
const statusPopupId = ref(null);
// Saved view UI
const showSaveViewDialog = ref(false);
const saveViewName = ref('');
const savingView = ref(false);
// Form
const formTitle = ref('');
const formDescription = ref('');
const formStatus = ref('new');
const formSource = ref('web');
const formValue = ref('');
const formCurrency = ref('CZK');
const formError = ref('');
const formLoading = ref(false);
// Context menu
const contextMenuRef = ref(null);
const contextLead = ref(null);
const LEAD_CONTEXT_ITEMS = [
    { id: 'view', label: 'View detail', icon: '↗' },
    { id: 'edit', label: 'Edit', icon: '✎' },
    { id: 'change_status', label: 'Change status', icon: '🔄' },
    { id: 'divider1', label: '', divider: true },
    { id: 'delete', label: 'Delete', icon: '🗑', danger: true },
];
function onRowContextMenu(e, lead) {
    e.preventDefault();
    contextLead.value = lead;
    contextMenuRef.value?.open(e.clientX, e.clientY);
}
function onRowLongPress(lead, e) {
    e.preventDefault();
    const touch = e.touches[0];
    if (!touch)
        return;
    contextLead.value = lead;
    contextMenuRef.value?.open(touch.clientX, touch.clientY);
}
function onContextAction(id) {
    const lead = contextLead.value;
    if (!lead)
        return;
    if (id === 'view')
        goToDetail(lead.id);
    else if (id === 'edit')
        openEdit(lead);
    else if (id === 'change_status')
        statusPopupId.value = lead.id;
    else if (id === 'delete')
        confirmDeleteId.value = lead.id;
}
watch(filterStatus, () => { store.fetchLeads({ status: filterStatus.value, source: filterSource.value }); });
watch(filterSource, () => { store.fetchLeads({ status: filterStatus.value, source: filterSource.value }); });
// Apply saved view from ?view= query param
watch(() => route.query.view, async (viewId) => {
    if (!viewId)
        return;
    await savedViewsStore.fetchViews();
    const v = savedViewsStore.views.find((sv) => sv.id === viewId);
    if (v) {
        filterStatus.value = v.filters.status ?? '';
        filterSource.value = v.filters.source ?? '';
    }
}, { immediate: true });
onMounted(async () => {
    store.fetchLeads({ status: filterStatus.value });
    savedViewsStore.fetchViews();
});
const leadsByStatus = computed(() => {
    const map = {};
    for (const s of LEAD_STATUSES)
        map[s.value] = [];
    for (const l of store.leads) {
        if (map[l.status])
            map[l.status].push(l);
        else
            map[l.status] = [l];
    }
    return map;
});
function openCreate() {
    editingLead.value = null;
    formTitle.value = '';
    formDescription.value = '';
    formStatus.value = 'new';
    formSource.value = 'web';
    formValue.value = '';
    formCurrency.value = 'CZK';
    formError.value = '';
    showModal.value = true;
}
function openEdit(lead) {
    editingLead.value = lead;
    formTitle.value = lead.title;
    formDescription.value = lead.description;
    formStatus.value = lead.status;
    formSource.value = lead.source;
    formValue.value = lead.value != null ? String(lead.value) : '';
    formCurrency.value = lead.currency;
    formError.value = '';
    showModal.value = true;
}
async function submitForm() {
    if (!formTitle.value.trim()) {
        formError.value = 'Title is required.';
        return;
    }
    formLoading.value = true;
    formError.value = '';
    const payload = {
        title: formTitle.value.trim(),
        description: formDescription.value,
        status: formStatus.value,
        source: formSource.value,
        value: formValue.value ? parseFloat(formValue.value) : null,
        currency: formCurrency.value,
    };
    let result;
    if (editingLead.value) {
        result = await store.updateLead(editingLead.value.id, payload);
    }
    else {
        result = await store.createLead(payload);
    }
    formLoading.value = false;
    if (result.ok) {
        showModal.value = false;
        toast.success(editingLead.value ? 'Lead updated.' : 'Lead created.');
    }
    else {
        formError.value = result.error ?? 'An error occurred.';
    }
}
async function confirmDelete(id) {
    const result = await store.deleteLead(id);
    confirmDeleteId.value = null;
    if (result.ok)
        toast.success('Lead deleted.');
    else
        toast.error(result.error ?? 'Failed to delete lead.');
}
async function changeStatus(leadId, newStatus) {
    statusPopupId.value = null;
    const result = await store.patchStatus(leadId, newStatus);
    if (!result.ok)
        toast.error(result.error ?? 'Failed to update status.');
}
function goToDetail(id) {
    router.push(`/app/leads/${id}`);
}
// Kanban drag state
const draggingLead = ref(null);
const dragOverStatus = ref(null);
function onDragStart(lead) {
    draggingLead.value = lead;
}
function onDragOver(e, status) {
    e.preventDefault();
    dragOverStatus.value = status;
}
function onDragLeave() {
    dragOverStatus.value = null;
}
async function onDrop(status) {
    dragOverStatus.value = null;
    if (!draggingLead.value || draggingLead.value.status === status) {
        draggingLead.value = null;
        return;
    }
    const lead = draggingLead.value;
    draggingLead.value = null;
    await changeStatus(lead.id, status);
}
function fmtValue(lead) {
    if (lead.value == null)
        return '';
    return new Intl.NumberFormat(undefined, { style: 'decimal', maximumFractionDigits: 0 }).format(lead.value) + ' ' + lead.currency;
}
// Fetch lead tasks to check overdue
const overdueTasks = ref(new Set());
async function checkOverdueTasks() {
    const res = await api.get('/api/v1/crm/tasks?completed=false&page_size=100');
    if (res.ok) {
        const now = Date.now();
        const set = new Set();
        for (const t of res.data) {
            if (t.due_date && new Date(t.due_date).getTime() < now) {
                set.add(t.lead_id);
            }
        }
        overdueTasks.value = set;
    }
}
onMounted(checkOverdueTasks);
// Saved views
async function saveCurrentView() {
    if (!saveViewName.value.trim())
        return;
    savingView.value = true;
    const result = await savedViewsStore.createView({
        name: saveViewName.value.trim(),
        entity: 'leads',
        filters: {
            ...(filterStatus.value ? { status: filterStatus.value } : {}),
            ...(filterSource.value ? { source: filterSource.value } : {}),
        },
    });
    savingView.value = false;
    if (result) {
        toast.success('View saved.');
        showSaveViewDialog.value = false;
        saveViewName.value = '';
    }
    else {
        toast.error('Failed to save view.');
    }
}
async function deleteSavedView(id) {
    await savedViewsStore.deleteView(id);
    toast.success('View deleted.');
}
const __VLS_ctx = ({ ...{} });
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'p-6 max-w-7xl mx-auto' }));
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-3 mb-5 flex-wrap' }));
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)(({ class: 'text-lg font-semibold text-gray-900 dark:text-gray-100 flex-1' }));
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
if (__VLS_ctx.savedViewsStore.viewsForEntity('leads').length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-1 flex-wrap' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    for (const [view] of __VLS_vFor((__VLS_ctx.savedViewsStore.viewsForEntity('leads')))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!(__VLS_ctx.savedViewsStore.viewsForEntity('leads').length > 0)) return;
		__VLS_ctx.router.push(`/app/leads?view=${view.id}`);
		[
			savedViewsStore,
			savedViewsStore,
			router
		];
	},
	key: view.id,
	...{ class: 'flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-xl border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors' },
	title: view.name
}));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        (view.name);
        // @ts-ignore
        [];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex rounded-xl border border-gray-200 dark:border-gray-600 overflow-hidden text-sm' }));
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		__VLS_ctx.viewMode = 'table';
		[viewMode];
	},
	...{ class: 'px-3 py-1.5 transition-colors' },
	...{ class: __VLS_ctx.viewMode === 'table' ? 'bg-red-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700' }
}));
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		__VLS_ctx.viewMode = 'kanban';
		[viewMode, viewMode];
	},
	...{ class: 'px-3 py-1.5 transition-colors' },
	...{ class: __VLS_ctx.viewMode === 'kanban' ? 'bg-red-600 text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700' }
}));
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
if (__VLS_ctx.viewMode === 'table') {
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)(({
	value: __VLS_ctx.filterStatus,
	class: 'rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "",
    });
    for (const [s] of __VLS_vFor((__VLS_ctx.LEAD_STATUSES))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (s.value),
            value: (s.value),
        });
        (s.label);
        // @ts-ignore
        [viewMode, viewMode, filterStatus, LEAD_STATUSES,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)(({
	value: __VLS_ctx.filterSource,
	class: 'rounded-xl border border-gray-200 dark:border-gray-600 text-sm px-3 py-1.5 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "web",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "email",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "referral",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "cold_call",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "social",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "other",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.showSaveViewDialog = true;
		[filterSource, showSaveViewDialog];
	},
	...{ class: 'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors' },
	title: 'Save current filters as a view'
}));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.openCreate,
	...{ class: 'bg-red-600 text-white rounded-xl px-4 py-1.5 text-sm font-medium hover:bg-red-700 transition-colors' }
}));
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
if (__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-2' }));
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    for (const [i] of __VLS_vFor((5))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	key: i,
	class: 'h-14 bg-gray-100 dark:bg-gray-700 rounded-xl'
}));
        /** @type {__VLS_StyleScopedClasses['h-14']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        // @ts-ignore
        [openCreate, store, store,];
    }
}
else if (__VLS_ctx.viewMode === 'table') {
    if (__VLS_ctx.store.leads.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex flex-col items-center justify-center py-20 text-center' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-20']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-4' }));
        /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-16']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'w-8 h-8 text-gray-400',
	fill: 'none',
	stroke: 'currentColor',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
        /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.path)({
            'stroke-linecap': "round",
            'stroke-linejoin': "round",
            'stroke-width': "1.5",
            d: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2",
        });
        __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-base font-semibold text-gray-900 dark:text-gray-100 mb-1' }));
        /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm text-gray-500 dark:text-gray-400 mb-6 max-w-xs' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
        /** @type {__VLS_StyleScopedClasses['max-w-xs']} */ ;
        if (__VLS_ctx.filterStatus || __VLS_ctx.filterSource) {
        }
        else {
        }
        if (!__VLS_ctx.filterStatus && !__VLS_ctx.filterSource) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.openCreate,
	...{ class: 'px-5 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors' }
}));
            /** @type {__VLS_StyleScopedClasses['px-5']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden' }));
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)(({ class: 'w-full text-sm' }));
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)(({ class: 'border-b border-gray-100 dark:border-gray-700 text-left' }));
        /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)(({ class: 'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)(({ class: 'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)(({ class: 'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden md:table-cell' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
        /** @type {__VLS_StyleScopedClasses['md:table-cell']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)(({ class: 'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden lg:table-cell' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
        /** @type {__VLS_StyleScopedClasses['lg:table-cell']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)(({ class: 'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden xl:table-cell' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
        /** @type {__VLS_StyleScopedClasses['xl:table-cell']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)(({ class: 'px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide hidden lg:table-cell' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
        /** @type {__VLS_StyleScopedClasses['lg:table-cell']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th)(({ class: 'px-4 py-3' }));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
        for (const [lead] of __VLS_vFor((__VLS_ctx.store.leads))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.goToDetail(lead.id);
		[
			viewMode,
			filterStatus,
			filterStatus,
			filterSource,
			filterSource,
			openCreate,
			store,
			store,
			goToDetail
		];
	},
	...{ onContextmenu: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.onRowContextMenu($event, lead);
		[onRowContextMenu];
	} },
	key: lead.id,
	...{ class: 'border-b border-gray-50 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors cursor-pointer group' }
}));
            /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700/50']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
            /** @type {__VLS_StyleScopedClasses['group']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.goToDetail(lead.id);
		[goToDetail];
	},
	...{ class: 'px-4 py-3 font-medium text-gray-900 dark:text-gray-100 max-w-xs' }
}));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['max-w-xs']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-1.5' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'truncate' }));
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (lead.title);
            if (__VLS_ctx.overdueTasks.has(lead.id)) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	title: 'Overdue task',
	class: 'text-red-500 text-xs flex-shrink-0',
	'aria-label': 'Overdue task'
}));
                /** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({ class: 'px-4 py-3' }));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'relative' }));
            /** @type {__VLS_StyleScopedClasses['relative']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.statusPopupId = __VLS_ctx.statusPopupId === lead.id ? null : lead.id;
		[
			overdueTasks,
			statusPopupId,
			statusPopupId
		];
	},
	...{ class: 'inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors hover:opacity-80' },
	...{ class: __VLS_ctx.getStatusMeta(lead.status).color },
	'aria-label': `Status: ${__VLS_ctx.getStatusMeta(lead.status).label}. Click to change.`
}));
            /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:opacity-80']} */ ;
            (__VLS_ctx.getStatusMeta(lead.status).label);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-xs opacity-60',
	'aria-hidden': 'true'
}));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['opacity-60']} */ ;
            if (__VLS_ctx.statusPopupId === lead.id) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: () => {},
	...{ class: 'absolute z-10 top-8 left-0 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-600 shadow-lg py-1 min-w-36' },
	role: 'listbox',
	'aria-label': `Change status for ${lead.title}`
}));
                /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
                /** @type {__VLS_StyleScopedClasses['z-10']} */ ;
                /** @type {__VLS_StyleScopedClasses['top-8']} */ ;
                /** @type {__VLS_StyleScopedClasses['left-0']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
                /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['min-w-36']} */ ;
                for (const [s] of __VLS_vFor((__VLS_ctx.LEAD_STATUSES))) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.statusPopupId === lead.id)) return;
		__VLS_ctx.changeStatus(lead.id, s.value);
		[
			LEAD_STATUSES,
			statusPopupId,
			getStatusMeta,
			getStatusMeta,
			getStatusMeta,
			changeStatus
		];
	},
	key: s.value,
	...{ class: 'w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2 text-gray-700 dark:text-gray-300' },
	...{ class: s.value === lead.status ? 'font-semibold' : '' },
	role: 'option',
	'aria-selected': s.value === lead.status
}));
                    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
                    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span)(({
	class: 'w-2 h-2 rounded-full flex-shrink-0',
	...{ class: s.color.split(' ')[0] },
	'aria-hidden': 'true'
}));
                    /** @type {__VLS_StyleScopedClasses['w-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['h-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                    (s.label);
                    // @ts-ignore
                    [];
                }
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.goToDetail(lead.id);
		[goToDetail];
	},
	...{ class: 'px-4 py-3 text-gray-500 dark:text-gray-400 hidden md:table-cell capitalize' }
}));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
            /** @type {__VLS_StyleScopedClasses['md:table-cell']} */ ;
            /** @type {__VLS_StyleScopedClasses['capitalize']} */ ;
            (lead.source.replace('_', ' '));
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.goToDetail(lead.id);
		[goToDetail];
	},
	...{ class: 'px-4 py-3 text-gray-700 dark:text-gray-300 hidden lg:table-cell' }
}));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
            /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
            /** @type {__VLS_StyleScopedClasses['lg:table-cell']} */ ;
            (__VLS_ctx.fmtValue(lead));
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.goToDetail(lead.id);
		[goToDetail, fmtValue];
	},
	...{ class: 'px-4 py-3 hidden xl:table-cell' }
}));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
            /** @type {__VLS_StyleScopedClasses['xl:table-cell']} */ ;
            const __VLS_0 = LeadScoreBadge;
            // @ts-ignore
            const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
                score: (lead.score),
            }));
            const __VLS_2 = __VLS_1({
                score: (lead.score),
            }, ...__VLS_functionalComponentArgsRest(__VLS_1));
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.goToDetail(lead.id);
		[goToDetail];
	},
	...{ class: 'px-4 py-3 text-gray-400 dark:text-gray-500 text-xs hidden lg:table-cell' }
}));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
            /** @type {__VLS_StyleScopedClasses['lg:table-cell']} */ ;
            (new Date(lead.created_at).toLocaleDateString());
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)(({ class: 'px-4 py-3' }));
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['opacity-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['group-hover:opacity-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-opacity']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.openEdit(lead);
		[openEdit];
	},
	...{ class: 'p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400' },
	'aria-label': 'Edit lead'
}));
            /** @type {__VLS_StyleScopedClasses['p-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		__VLS_ctx.confirmDeleteId = lead.id;
		[confirmDeleteId];
	},
	...{ class: 'p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500' },
	'aria-label': 'Delete lead'
}));
            /** @type {__VLS_StyleScopedClasses['p-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-red-900/30']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
            // @ts-ignore
            [];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex justify-between items-center px-4 py-3 border-t border-gray-100 dark:border-gray-700' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs text-gray-400 dark:text-gray-500' }));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        (__VLS_ctx.store.page);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-2' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        if (__VLS_ctx.store.page > 1) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.store.page > 1)) return;
		__VLS_ctx.store.fetchLeads({
			status: __VLS_ctx.filterStatus,
			source: __VLS_ctx.filterSource,
			page: __VLS_ctx.store.page - 1
		});
		[
			filterStatus,
			filterSource,
			store,
			store,
			store,
			store
		];
	},
	...{ class: 'px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300' }
}));
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        }
        if (__VLS_ctx.store.hasMore) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!(__VLS_ctx.viewMode === 'table')) return;
		if (!!(__VLS_ctx.store.leads.length === 0)) return;
		if (!__VLS_ctx.store.hasMore) return;
		__VLS_ctx.store.fetchLeads({
			status: __VLS_ctx.filterStatus,
			source: __VLS_ctx.filterSource,
			page: __VLS_ctx.store.page + 1
		});
		[
			filterStatus,
			filterSource,
			store,
			store,
			store
		];
	},
	...{ class: 'px-3 py-1 text-xs rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300' }
}));
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        }
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-4 overflow-x-auto pb-4 min-h-96' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
    /** @type {__VLS_StyleScopedClasses['pb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-h-96']} */ ;
    for (const [s] of __VLS_vFor((__VLS_ctx.LEAD_STATUSES))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onDragover: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.onDragOver($event, s.value);
		[LEAD_STATUSES, onDragOver];
	},
	...{ onDragleave: __VLS_ctx.onDragLeave },
	...{ onDrop: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.onDrop(s.value);
		[onDragLeave, onDrop];
	} },
	key: s.value,
	...{ class: 'flex-shrink-0 w-64 flex flex-col' }
}));
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-64']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'flex items-center gap-2 px-3 py-2 rounded-xl mb-2 text-xs font-semibold transition-colors',
	...{ class: [s.color, __VLS_ctx.dragOverStatus === s.value ? 'ring-2 ring-offset-1 ring-red-400' : ''] }
}));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        (s.label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'ml-auto bg-white/60 dark:bg-black/30 rounded px-1.5 py-0.5' }));
        /** @type {__VLS_StyleScopedClasses['ml-auto']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white/60']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-black/30']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        (__VLS_ctx.leadsByStatus[s.value]?.length ?? 0);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'flex-1 space-y-2 min-h-16 rounded-xl transition-colors p-1',
	...{ class: __VLS_ctx.dragOverStatus === s.value ? 'bg-red-50 dark:bg-red-900/20' : 'bg-gray-50 dark:bg-gray-700/30' }
}));
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-h-16']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
        for (const [lead] of __VLS_vFor((__VLS_ctx.leadsByStatus[s.value]))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onDragstart: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.onDragStart(lead);
		[
			dragOverStatus,
			dragOverStatus,
			leadsByStatus,
			leadsByStatus,
			onDragStart
		];
	},
	...{ onContextmenu: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.onRowContextMenu($event, lead);
		[onRowContextMenu];
	} },
	key: lead.id,
	...{ class: 'bg-white dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 p-3 cursor-grab shadow-sm hover:shadow transition-shadow group' },
	draggable: 'true'
}));
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-grab']} */ ;
            /** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:shadow']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-shadow']} */ ;
            /** @type {__VLS_StyleScopedClasses['group']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-start justify-between gap-2' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.goToDetail(lead.id);
		[goToDetail];
	},
	...{ class: 'text-xs font-medium text-gray-900 dark:text-gray-100 text-left hover:text-red-600 transition-colors leading-snug' }
}));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['leading-snug']} */ ;
            (lead.title);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-0.5 opacity-0 group-hover:opacity-100' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-0.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['opacity-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['group-hover:opacity-100']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!(__VLS_ctx.store.loading && __VLS_ctx.store.leads.length === 0)) return;
		if (!!(__VLS_ctx.viewMode === 'table')) return;
		__VLS_ctx.openEdit(lead);
		[openEdit];
	},
	...{ class: 'p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 text-xs' },
	'aria-label': 'Edit lead'
}));
            /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-2 mt-2 flex-wrap' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
            if (__VLS_ctx.fmtValue(lead)) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs text-gray-500 dark:text-gray-400' }));
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
                (__VLS_ctx.fmtValue(lead));
            }
            const __VLS_5 = LeadScoreBadge;
            // @ts-ignore
            const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
                score: (lead.score),
            }));
            const __VLS_7 = __VLS_6({
                score: (lead.score),
            }, ...__VLS_functionalComponentArgsRest(__VLS_6));
            if (__VLS_ctx.overdueTasks.has(lead.id)) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-xs text-red-500',
	title: 'Overdue task'
}));
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
            }
            // @ts-ignore
            [overdueTasks, fmtValue, fmtValue,];
        }
        if ((__VLS_ctx.leadsByStatus[s.value]?.length ?? 0) === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-center text-xs text-gray-300 dark:text-gray-600 py-4' }));
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-4']} */ ;
        }
        // @ts-ignore
        [leadsByStatus,];
    }
}
const __VLS_10 = ContextMenu;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10(({
	'onAction': {},
	ref: 'contextMenuRef',
	items: __VLS_ctx.LEAD_CONTEXT_ITEMS
})));
const __VLS_12 = __VLS_11(({
	'onAction': {},
	ref: 'contextMenuRef',
	items: __VLS_ctx.LEAD_CONTEXT_ITEMS
}), ...__VLS_functionalComponentArgsRest(__VLS_11));
let __VLS_15;
const __VLS_16 = ({ action: {} },
    { onAction: (__VLS_ctx.onContextAction) });
var __VLS_17 = {};
var __VLS_13;
var __VLS_14;
let __VLS_19;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
    to: "body",
}));
const __VLS_21 = __VLS_20({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_20));
const { default: __VLS_24 } = __VLS_22.slots;
if (__VLS_ctx.showSaveViewDialog) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.showSaveViewDialog) return;
		__VLS_ctx.showSaveViewDialog = false;
		[
			showSaveViewDialog,
			showSaveViewDialog,
			LEAD_CONTEXT_ITEMS,
			onContextAction
		];
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
	'aria-label': 'Save view'
}));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-base font-semibold text-gray-900 dark:text-gray-100 mb-4' }));
    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'space-y-3' }));
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	value: __VLS_ctx.saveViewName,
	type: 'text',
	placeholder: 'e.g. New Web Leads',
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-xs text-gray-500 dark:text-gray-400' }));
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    (__VLS_ctx.filterStatus || 'any');
    (__VLS_ctx.filterSource || 'any');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-3 pt-4' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.showSaveViewDialog) return;
		__VLS_ctx.showSaveViewDialog = false;
		[
			filterStatus,
			filterSource,
			showSaveViewDialog,
			saveViewName
		];
	},
	type: 'button',
	...{ class: 'flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700' }
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.saveCurrentView,
	type: 'button',
	disabled: __VLS_ctx.savingView || !__VLS_ctx.saveViewName.trim(),
	...{ class: 'flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60' }
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
    (__VLS_ctx.savingView ? 'Saving…' : 'Save view');
}
// @ts-ignore
[saveViewName, saveCurrentView, savingView, savingView,];
var __VLS_22;
let __VLS_25;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
    to: "body",
}));
const __VLS_27 = __VLS_26({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
const { default: __VLS_30 } = __VLS_28.slots;
if (__VLS_ctx.showModal) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.showModal) return;
		__VLS_ctx.showModal = false;
		[showModal, showModal];
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
	class: 'bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-md p-6',
	role: 'dialog',
	'aria-modal': 'true',
	'aria-label': __VLS_ctx.editingLead ? 'Edit Lead' : 'New Lead'
}));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-md']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4' }));
    /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    (__VLS_ctx.editingLead ? 'Edit Lead' : 'New Lead');
    if (__VLS_ctx.formError) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400',
	role: 'alert'
}));
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-red-900/30']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-red-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-red-400']} */ ;
        (__VLS_ctx.formError);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)(({
	onSubmit: __VLS_ctx.submitForm,
	...{ class: 'space-y-3' }
}));
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	value: __VLS_ctx.formTitle,
	type: 'text',
	required: true,
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.textarea)(({
	value: __VLS_ctx.formDescription,
	rows: '2',
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'grid grid-cols-2 gap-3' }));
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)(({
	value: __VLS_ctx.formStatus,
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    for (const [s] of __VLS_vFor((__VLS_ctx.LEAD_STATUSES))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (s.value),
            value: (s.value),
        });
        (s.label);
        // @ts-ignore
        [LEAD_STATUSES, editingLead, editingLead, formError, formError, submitForm, formTitle, formDescription, formStatus,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)(({
	value: __VLS_ctx.formSource,
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "web",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "email",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "referral",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "cold_call",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "social",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "other",
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'grid grid-cols-2 gap-3' }));
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	type: 'number',
	min: '0',
	step: '0.01',
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400',
	placeholder: '0'
}));
    (__VLS_ctx.formValue);
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)(({ class: 'block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1' }));
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	value: __VLS_ctx.formCurrency,
	type: 'text',
	maxlength: '3',
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400',
	placeholder: 'CZK'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-3 pt-2' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.showModal) return;
		__VLS_ctx.showModal = false;
		[
			showModal,
			formSource,
			formValue,
			formCurrency
		];
	},
	type: 'button',
	...{ class: 'flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700' }
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	type: 'submit',
	disabled: __VLS_ctx.formLoading,
	class: 'flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60'
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
    (__VLS_ctx.formLoading ? 'Saving…' : (__VLS_ctx.editingLead ? 'Save' : 'Create'));
}
// @ts-ignore
[editingLead, formLoading, formLoading,];
var __VLS_28;
let __VLS_31;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent1(__VLS_31, new __VLS_31({
    to: "body",
}));
const __VLS_33 = __VLS_32({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
const { default: __VLS_36 } = __VLS_34.slots;
if (__VLS_ctx.confirmDeleteId) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.confirmDeleteId) return;
		__VLS_ctx.confirmDeleteId = null;
		[confirmDeleteId, confirmDeleteId];
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
	class: 'bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6 text-center',
	role: 'dialog',
	'aria-modal': 'true',
	'aria-label': 'Delete lead confirmation'
}));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	class: 'text-3xl mb-3',
	'aria-hidden': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-base font-semibold text-gray-900 dark:text-gray-100 mb-2' }));
    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm text-gray-500 dark:text-gray-400 mb-4' }));
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-3' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.confirmDeleteId) return;
		__VLS_ctx.confirmDeleteId = null;
		[confirmDeleteId];
	},
	...{ class: 'flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-700 dark:text-gray-300' }
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.confirmDeleteId) return;
		__VLS_ctx.confirmDelete(__VLS_ctx.confirmDeleteId);
		[confirmDeleteId, confirmDelete];
	},
	...{ class: 'flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700' }
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
}
// @ts-ignore
[];
var __VLS_34;
if (__VLS_ctx.statusPopupId) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.statusPopupId) return;
		__VLS_ctx.statusPopupId = null;
		[statusPopupId, statusPopupId];
	},
	...{ class: 'fixed inset-0 z-5' }
}));
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-5']} */ ;
}
// @ts-ignore
var __VLS_18 = __VLS_17;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

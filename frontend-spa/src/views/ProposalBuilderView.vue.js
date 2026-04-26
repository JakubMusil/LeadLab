/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useToast } from '@/composables/useToast';
import { useFirmStore } from '@/stores/firm';
import { api } from '@/api';
const route = useRoute();
const router = useRouter();
const toast = useToast();
const firmStore = useFirmStore();
const leadId = computed(() => route.params.id);
const proposalId = computed(() => route.params.pid);
// -----------------------------------------------------------------------
// State
// -----------------------------------------------------------------------
const proposals = ref([]);
const currentProposal = ref(null);
const loading = ref(false);
const saving = ref(false);
// Editor state
const editTitle = ref('');
const editStatus = ref('draft');
const editExpiry = ref('');
const editCurrency = ref('CZK');
const editNotes = ref('');
const editIntro = ref('');
const editClosing = ref('');
// Items
const items = ref([]);
const newItemDesc = ref('');
const newItemQty = ref(1);
const newItemPrice = ref(0);
const newItemDiscount = ref(0);
const newItemVat = ref(0);
const addingItem = ref(false);
const editingItemId = ref(null);
// Templates
const templates = ref([]);
const showApplyTemplate = ref(false);
const applyingTemplate = ref(false);
// Public link
const publicLinkCopied = ref(false);
const sendingProposal = ref(false);
// Preview panel
const showPreview = ref(false);
const CURRENCIES = ['CZK', 'EUR', 'USD', 'GBP', 'PLN'];
const STATUSES = [
    { value: 'draft', label: 'Draft', color: 'bg-gray-100 text-gray-700' },
    { value: 'sent', label: 'Sent', color: 'bg-blue-100 text-blue-700' },
    { value: 'viewed', label: 'Viewed', color: 'bg-yellow-100 text-yellow-700' },
    { value: 'accepted', label: 'Accepted', color: 'bg-green-100 text-green-700' },
    { value: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-700' },
    { value: 'expired', label: 'Expired', color: 'bg-orange-100 text-orange-700' },
];
function statusMeta(status) {
    return STATUSES.find((s) => s.value === status) ?? { value: status, label: status, color: 'bg-gray-100 text-gray-700' };
}
// -----------------------------------------------------------------------
// Computed totals for preview
// -----------------------------------------------------------------------
const previewSubtotal = computed(() => items.value.reduce((acc, i) => acc + Number(i.subtotal), 0));
const previewDiscount = computed(() => items.value.reduce((acc, i) => acc + Number(i.discount_amount), 0));
const previewTax = computed(() => items.value.reduce((acc, i) => acc + Number(i.tax), 0));
const previewTotal = computed(() => items.value.reduce((acc, i) => acc + Number(i.total), 0));
// -----------------------------------------------------------------------
// Load data
// -----------------------------------------------------------------------
async function loadProposals() {
    loading.value = true;
    try {
        const res = await api.get(`/api/v1/crm/leads/${leadId.value}/proposals`);
        if (res.ok)
            proposals.value = res.data;
    }
    finally {
        loading.value = false;
    }
}
async function loadProposal(id) {
    loading.value = true;
    try {
        const res = await api.get(`/api/v1/crm/proposals/${id}`);
        if (res.ok) {
            currentProposal.value = res.data;
            populateForm(res.data);
            items.value = [...res.data.items].sort((a, b) => a.position - b.position);
        }
        else {
            toast.error('Failed to load proposal.');
        }
    }
    finally {
        loading.value = false;
    }
}
async function loadTemplates() {
    const res = await api.get('/api/v1/crm/proposal-templates');
    if (res.ok)
        templates.value = res.data;
}
function populateForm(p) {
    editTitle.value = p.title;
    editStatus.value = p.status;
    editExpiry.value = p.expiry_date ?? '';
    editCurrency.value = p.currency;
    editNotes.value = p.notes;
    editIntro.value = p.intro_text;
    editClosing.value = p.closing_text;
}
// -----------------------------------------------------------------------
// Create / Save
// -----------------------------------------------------------------------
async function createProposal() {
    saving.value = true;
    const res = await api.post(`/api/v1/crm/leads/${leadId.value}/proposals`, {
        title: editTitle.value || 'New Proposal',
        currency: editCurrency.value,
    });
    saving.value = false;
    if (res.ok) {
        proposals.value.unshift(res.data);
        currentProposal.value = res.data;
        populateForm(res.data);
        items.value = [];
        router.replace(`/app/leads/${leadId.value}/proposals/${res.data.id}`);
        toast.success('Proposal created.');
    }
    else {
        toast.error('Failed to create proposal.');
    }
}
async function saveProposal() {
    if (!currentProposal.value)
        return;
    saving.value = true;
    const res = await api.put(`/api/v1/crm/proposals/${currentProposal.value.id}`, {
        title: editTitle.value,
        status: editStatus.value,
        expiry_date: editExpiry.value || null,
        currency: editCurrency.value,
        notes: editNotes.value,
        intro_text: editIntro.value,
        closing_text: editClosing.value,
    });
    saving.value = false;
    if (res.ok) {
        currentProposal.value = res.data;
        const idx = proposals.value.findIndex((p) => p.id === res.data.id);
        if (idx !== -1)
            proposals.value[idx] = res.data;
        toast.success('Proposal saved.');
    }
    else {
        toast.error('Failed to save proposal.');
    }
}
async function deleteProposal(id) {
    if (!confirm('Delete this proposal?'))
        return;
    const res = await api.delete(`/api/v1/crm/proposals/${id}`);
    if (res.ok || res.status === 204) {
        proposals.value = proposals.value.filter((p) => p.id !== id);
        if (currentProposal.value?.id === id) {
            currentProposal.value = null;
            router.replace(`/app/leads/${leadId.value}/proposals`);
        }
        toast.success('Proposal deleted.');
    }
    else {
        toast.error('Failed to delete proposal.');
    }
}
function selectProposal(p) {
    router.push(`/app/leads/${leadId.value}/proposals/${p.id}`);
}
// -----------------------------------------------------------------------
// Items
// -----------------------------------------------------------------------
async function addItem() {
    if (!currentProposal.value || !newItemDesc.value.trim())
        return;
    addingItem.value = true;
    const res = await api.post(`/api/v1/crm/proposals/${currentProposal.value.id}/items`, {
        description: newItemDesc.value.trim(),
        quantity: newItemQty.value,
        unit_price: newItemPrice.value,
        discount: newItemDiscount.value,
        vat_rate: newItemVat.value,
        position: items.value.length,
    });
    addingItem.value = false;
    if (res.ok) {
        items.value.push(res.data);
        newItemDesc.value = '';
        newItemQty.value = 1;
        newItemPrice.value = 0;
        newItemDiscount.value = 0;
        newItemVat.value = 0;
    }
    else {
        toast.error('Failed to add item.');
    }
}
async function updateItem(item) {
    if (!currentProposal.value)
        return;
    const res = await api.put(`/api/v1/crm/proposals/${currentProposal.value.id}/items/${item.id}`, {
        description: item.description,
        quantity: item.quantity,
        unit_price: item.unit_price,
        discount: item.discount,
        vat_rate: item.vat_rate,
        position: item.position,
    });
    if (res.ok) {
        const idx = items.value.findIndex((i) => i.id === item.id);
        if (idx !== -1)
            items.value[idx] = res.data;
        editingItemId.value = null;
    }
    else {
        toast.error('Failed to update item.');
    }
}
async function deleteItem(itemId) {
    if (!currentProposal.value)
        return;
    const res = await api.delete(`/api/v1/crm/proposals/${currentProposal.value.id}/items/${itemId}`);
    if (res.ok || res.status === 204) {
        items.value = items.value.filter((i) => i.id !== itemId);
    }
    else {
        toast.error('Failed to delete item.');
    }
}
// Drag-and-drop reorder
const dragIndex = ref(null);
function onDragStart(index) {
    dragIndex.value = index;
}
function onDragOver(e, index) {
    e.preventDefault();
    if (dragIndex.value === null || dragIndex.value === index)
        return;
    const removed = items.value.splice(dragIndex.value, 1);
    const moved = removed[0];
    if (!moved)
        return;
    items.value.splice(index, 0, moved);
    dragIndex.value = index;
}
async function onDragEnd() {
    dragIndex.value = null;
    if (!currentProposal.value)
        return;
    // Persist new order
    const reordered = items.value.map((item, idx) => ({ id: item.id, position: idx }));
    const res = await api.post(`/api/v1/crm/proposals/${currentProposal.value.id}/items/reorder`, { items: reordered });
    if (res.ok) {
        items.value = res.data;
    }
}
// -----------------------------------------------------------------------
// Apply template
// -----------------------------------------------------------------------
async function applyTemplate(templateId) {
    if (!currentProposal.value)
        return;
    applyingTemplate.value = true;
    const res = await api.post(`/api/v1/crm/proposals/${currentProposal.value.id}/apply-template`, { template_id: templateId });
    applyingTemplate.value = false;
    if (res.ok) {
        currentProposal.value = res.data;
        populateForm(res.data);
        items.value = [...res.data.items].sort((a, b) => a.position - b.position);
        showApplyTemplate.value = false;
        toast.success('Template applied.');
    }
    else {
        toast.error('Failed to apply template.');
    }
}
// -----------------------------------------------------------------------
// Send & public link
// -----------------------------------------------------------------------
async function sendProposal() {
    if (!currentProposal.value)
        return;
    if (!confirm('Mark this proposal as Sent and generate a public link?'))
        return;
    sendingProposal.value = true;
    const res = await api.post(`/api/v1/crm/proposals/${currentProposal.value.id}/send`);
    sendingProposal.value = false;
    if (res.ok) {
        currentProposal.value = res.data;
        editStatus.value = res.data.status;
        const idx = proposals.value.findIndex((p) => p.id === res.data.id);
        if (idx !== -1)
            proposals.value[idx] = res.data;
        toast.success('Proposal marked as Sent. Copy the public link to share it.');
    }
    else {
        toast.error('Failed to send proposal.');
    }
}
function publicLink(proposal) {
    return `${window.location.origin}/proposals/public/${proposal.public_token}`;
}
async function copyPublicLink() {
    if (!currentProposal.value)
        return;
    await navigator.clipboard.writeText(publicLink(currentProposal.value));
    publicLinkCopied.value = true;
    setTimeout(() => (publicLinkCopied.value = false), 2000);
}
function downloadPdf() {
    if (!currentProposal.value)
        return;
    window.open(`/api/v1/crm/proposals/${currentProposal.value.id}/pdf`, '_blank');
}
// -----------------------------------------------------------------------
// Formatting helpers
// -----------------------------------------------------------------------
function fmt(n) {
    return Number(n).toFixed(2);
}
function formatDate(d) {
    return new Date(d).toLocaleDateString();
}
// -----------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------
onMounted(async () => {
    await loadProposals();
    await loadTemplates();
    const pid = proposalId.value;
    if (pid) {
        await loadProposal(pid);
    }
    else if (proposals.value.length > 0) {
        const first = proposals.value[0];
        if (first) {
            await loadProposal(first.id);
            router.replace(`/app/leads/${leadId.value}/proposals/${first.id}`);
        }
    }
    else {
        // Pre-populate create form
        editTitle.value = 'New Proposal';
        editCurrency.value = 'CZK';
    }
});
watch(() => route.params.pid, async (pid) => {
    if (pid && pid !== currentProposal.value?.id) {
        await loadProposal(pid);
    }
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "p-6 max-w-7xl mx-auto" },
});
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
let __VLS_0;
/** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    to: (`/app/leads/${__VLS_ctx.leadId}`),
    ...{ class: "inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4" },
}));
const __VLS_2 = __VLS_1({
    to: (`/app/leads/${__VLS_ctx.leadId}`),
    ...{ class: "inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
const { default: __VLS_5 } = __VLS_3.slots;
// @ts-ignore
[leadId,];
var __VLS_3;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex gap-6" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.aside, __VLS_intrinsics.aside)({
    ...{ class: "w-64 flex-shrink-0" },
});
/** @type {__VLS_StyleScopedClasses['w-64']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-3" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between mb-2 px-1" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['px-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.createProposal) },
    ...{ class: "text-xs px-2 py-1 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
if (__VLS_ctx.loading && __VLS_ctx.proposals.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "animate-pulse space-y-2 py-2" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    for (const [i] of __VLS_vFor((3))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            key: (i),
            ...{ class: "h-12 bg-gray-100 rounded-xl" },
        });
        /** @type {__VLS_StyleScopedClasses['h-12']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        // @ts-ignore
        [createProposal, loading, proposals,];
    }
}
else if (__VLS_ctx.proposals.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "py-6 text-center text-xs text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['py-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.br)({});
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-1" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
    for (const [p] of __VLS_vFor((__VLS_ctx.proposals))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.loading && __VLS_ctx.proposals.length === 0))
                        return;
                    if (!!(__VLS_ctx.proposals.length === 0))
                        return;
                    __VLS_ctx.selectProposal(p);
                    // @ts-ignore
                    [proposals, proposals, selectProposal,];
                } },
            key: (p.id),
            ...{ class: "w-full text-left px-3 py-2.5 rounded-xl transition-colors" },
            ...{ class: (__VLS_ctx.currentProposal?.id === p.id
                    ? 'bg-red-50 text-red-700'
                    : 'hover:bg-gray-50 text-gray-700') },
        });
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-sm font-medium truncate" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
        (p.title);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-1.5 mt-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "inline-block px-1.5 py-0.5 rounded text-[10px] font-medium" },
            ...{ class: (__VLS_ctx.statusMeta(p.status).color) },
        });
        /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (__VLS_ctx.statusMeta(p.status).label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-[10px] text-gray-400" },
        });
        /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        (__VLS_ctx.fmt(p.total_value));
        (p.currency);
        // @ts-ignore
        [currentProposal, statusMeta, statusMeta, fmt,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex-1 min-w-0 space-y-4" },
});
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
if (!__VLS_ctx.currentProposal && !__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-10 text-center text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-10']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-sm mb-3" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.createProposal) },
        ...{ class: "px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
}
else if (__VLS_ctx.currentProposal) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-4 flex flex-wrap items-center gap-3" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex-1 min-w-0" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        value: (__VLS_ctx.editTitle),
        type: "text",
        ...{ class: "w-full text-lg font-semibold bg-transparent border-b border-transparent focus:border-gray-300 focus:outline-none text-gray-900 pb-0.5" },
        placeholder: "Proposal title…",
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-transparent']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-transparent']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['pb-0.5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
        value: (__VLS_ctx.editStatus),
        ...{ class: "rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    for (const [s] of __VLS_vFor((__VLS_ctx.STATUSES))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (s.value),
            value: (s.value),
        });
        (s.label);
        // @ts-ignore
        [createProposal, loading, currentProposal, currentProposal, editTitle, editStatus, STATUSES,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.saveProposal) },
        ...{ class: "px-3 py-1.5 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50" },
        disabled: (__VLS_ctx.saving),
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.saving ? 'Saving…' : 'Save');
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.sendProposal) },
        ...{ class: "px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50" },
        disabled: (__VLS_ctx.sendingProposal),
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    (__VLS_ctx.sendingProposal ? '…' : '📤 Send');
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.downloadPdf) },
        ...{ class: "px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.copyPublicLink) },
        ...{ class: "px-3 py-1.5 rounded-xl border border-gray-200 text-sm hover:bg-gray-50" },
        ...{ class: (__VLS_ctx.publicLinkCopied ? 'text-green-600' : 'text-gray-600') },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    (__VLS_ctx.publicLinkCopied ? '✓ Copied!' : '🔗 Copy Link');
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                    return;
                if (!(__VLS_ctx.currentProposal))
                    return;
                __VLS_ctx.showPreview = !__VLS_ctx.showPreview;
                // @ts-ignore
                [saveProposal, saving, saving, sendProposal, sendingProposal, sendingProposal, downloadPdf, copyPublicLink, publicLinkCopied, publicLinkCopied, showPreview, showPreview,];
            } },
        ...{ class: "px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    (__VLS_ctx.showPreview ? 'Hide Preview' : 'Preview');
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                    return;
                if (!(__VLS_ctx.currentProposal))
                    return;
                __VLS_ctx.deleteProposal(__VLS_ctx.currentProposal.id);
                // @ts-ignore
                [currentProposal, showPreview, deleteProposal,];
            } },
        ...{ class: "px-3 py-1.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-4" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex-1 min-w-0 space-y-4" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "grid grid-cols-2 gap-3" },
    });
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs text-gray-500 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
        value: (__VLS_ctx.editCurrency),
        ...{ class: "w-full rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    for (const [c] of __VLS_vFor((__VLS_ctx.CURRENCIES))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (c),
            value: (c),
        });
        (c);
        // @ts-ignore
        [editCurrency, CURRENCIES,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs text-gray-500 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "date",
        ...{ class: "w-full rounded-xl border border-gray-200 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400" },
    });
    (__VLS_ctx.editExpiry);
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    if (__VLS_ctx.currentProposal.view_count > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mt-3 flex gap-4 text-xs text-gray-400" },
        });
        /** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (__VLS_ctx.currentProposal.view_count);
        (__VLS_ctx.currentProposal.view_count !== 1 ? 's' : '');
        if (__VLS_ctx.currentProposal.first_viewed_at) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_ctx.formatDate(__VLS_ctx.currentProposal.first_viewed_at));
        }
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.textarea)({
        value: (__VLS_ctx.editIntro),
        rows: "3",
        ...{ class: "w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none" },
        placeholder: "Write an introduction for your proposal…",
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-between mb-3" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                    return;
                if (!(__VLS_ctx.currentProposal))
                    return;
                __VLS_ctx.showApplyTemplate = !__VLS_ctx.showApplyTemplate;
                // @ts-ignore
                [currentProposal, currentProposal, currentProposal, currentProposal, currentProposal, editExpiry, formatDate, editIntro, showApplyTemplate, showApplyTemplate,];
            } },
        ...{ class: "text-xs px-2 py-1 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    if (__VLS_ctx.showApplyTemplate) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mb-3 p-3 bg-gray-50 rounded-xl" },
        });
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-500 mb-2" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
        if (__VLS_ctx.templates.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-400" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "space-y-1" },
            });
            /** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
            for (const [tmpl] of __VLS_vFor((__VLS_ctx.templates))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                                return;
                            if (!(__VLS_ctx.currentProposal))
                                return;
                            if (!(__VLS_ctx.showApplyTemplate))
                                return;
                            if (!!(__VLS_ctx.templates.length === 0))
                                return;
                            __VLS_ctx.applyTemplate(tmpl.id);
                            // @ts-ignore
                            [showApplyTemplate, templates, templates, applyTemplate,];
                        } },
                    key: (tmpl.id),
                    ...{ class: "w-full text-left px-3 py-2 rounded-lg text-sm hover:bg-white border border-transparent hover:border-gray-200 transition-colors" },
                    disabled: (__VLS_ctx.applyingTemplate),
                });
                /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:bg-white']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-transparent']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:border-gray-200']} */ ;
                /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "font-medium" },
                });
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                (tmpl.name);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "text-xs text-gray-400 ml-2" },
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
                (tmpl.items.length);
                // @ts-ignore
                [applyingTemplate,];
            }
        }
    }
    if (__VLS_ctx.items.length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mb-3 overflow-x-auto" },
        });
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
            ...{ class: "w-full text-sm" },
        });
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
            ...{ class: "border-b border-gray-100" },
        });
        /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-left py-1.5 pr-2 text-xs font-medium text-gray-500 w-6" },
        });
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['pr-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-left py-1.5 pr-2 text-xs font-medium text-gray-500" },
        });
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['pr-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16" },
        });
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-24" },
        });
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-24']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16" },
        });
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-right py-1.5 px-2 text-xs font-medium text-gray-500 w-16" },
        });
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "text-right py-1.5 pl-2 text-xs font-medium text-gray-500 w-24" },
        });
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['pl-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-24']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
            ...{ class: "w-8" },
        });
        /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
        for (const [item, index] of __VLS_vFor((__VLS_ctx.items))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                ...{ onDragstart: (...[$event]) => {
                        if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                            return;
                        if (!(__VLS_ctx.currentProposal))
                            return;
                        if (!(__VLS_ctx.items.length > 0))
                            return;
                        __VLS_ctx.onDragStart(index);
                        // @ts-ignore
                        [items, items, onDragStart,];
                    } },
                ...{ onDragover: (...[$event]) => {
                        if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                            return;
                        if (!(__VLS_ctx.currentProposal))
                            return;
                        if (!(__VLS_ctx.items.length > 0))
                            return;
                        __VLS_ctx.onDragOver($event, index);
                        // @ts-ignore
                        [onDragOver,];
                    } },
                ...{ onDragend: (__VLS_ctx.onDragEnd) },
                key: (item.id),
                draggable: "true",
                ...{ class: "border-b border-gray-50 hover:bg-gray-50 cursor-grab" },
            });
            /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-grab']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                ...{ class: "py-1.5 pr-2 text-gray-300 cursor-grab select-none" },
            });
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['pr-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-grab']} */ ;
            /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
            if (__VLS_ctx.editingItemId === item.id) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 pr-2" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['pr-2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                    value: (item.description),
                    type: "text",
                    ...{ class: "w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:border-red-400" },
                });
                /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 px-2" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                    type: "number",
                    min: "0.001",
                    step: "0.001",
                    ...{ class: "w-16 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" },
                });
                (item.quantity);
                /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 px-2" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                    type: "number",
                    min: "0",
                    step: "0.01",
                    ...{ class: "w-24 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" },
                });
                (item.unit_price);
                /** @type {__VLS_StyleScopedClasses['w-24']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 px-2" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                    type: "number",
                    min: "0",
                    max: "100",
                    step: "0.01",
                    ...{ class: "w-16 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" },
                });
                (item.discount);
                /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 px-2" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                    type: "number",
                    min: "0",
                    max: "100",
                    step: "0.01",
                    ...{ class: "w-16 rounded border border-gray-300 px-2 py-1 text-sm text-right focus:outline-none focus:border-red-400" },
                });
                (item.vat_rate);
                /** @type {__VLS_StyleScopedClasses['w-16']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 pl-2 text-right text-xs font-medium text-gray-700" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['pl-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                (__VLS_ctx.fmt(item.total));
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 pl-1" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['pl-1']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                                return;
                            if (!(__VLS_ctx.currentProposal))
                                return;
                            if (!(__VLS_ctx.items.length > 0))
                                return;
                            if (!(__VLS_ctx.editingItemId === item.id))
                                return;
                            __VLS_ctx.updateItem(item);
                            // @ts-ignore
                            [fmt, onDragEnd, editingItemId, updateItem,];
                        } },
                    ...{ class: "text-xs text-green-600 hover:text-green-700 px-1" },
                    title: "Save",
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:text-green-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-1']} */ ;
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 pr-2 text-sm text-gray-700" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['pr-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                (item.description);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 px-2 text-right text-xs text-gray-500" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                (item.quantity);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 px-2 text-right text-xs text-gray-500" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                (__VLS_ctx.fmt(item.unit_price));
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 px-2 text-right text-xs text-gray-500" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                (item.discount);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 px-2 text-right text-xs text-gray-500" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                (item.vat_rate);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 pl-2 text-right text-xs font-medium text-gray-700" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['pl-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                (__VLS_ctx.fmt(item.total));
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1.5 pl-1 flex items-center gap-0.5" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['pl-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['gap-0.5']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                                return;
                            if (!(__VLS_ctx.currentProposal))
                                return;
                            if (!(__VLS_ctx.items.length > 0))
                                return;
                            if (!!(__VLS_ctx.editingItemId === item.id))
                                return;
                            __VLS_ctx.editingItemId = item.id;
                            // @ts-ignore
                            [fmt, fmt, editingItemId,];
                        } },
                    ...{ class: "text-xs text-gray-400 hover:text-blue-500 px-1" },
                    title: "Edit",
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:text-blue-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-1']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                    ...{ onClick: (...[$event]) => {
                            if (!!(!__VLS_ctx.currentProposal && !__VLS_ctx.loading))
                                return;
                            if (!(__VLS_ctx.currentProposal))
                                return;
                            if (!(__VLS_ctx.items.length > 0))
                                return;
                            if (!!(__VLS_ctx.editingItemId === item.id))
                                return;
                            __VLS_ctx.deleteItem(item.id);
                            // @ts-ignore
                            [deleteItem,];
                        } },
                    ...{ class: "text-xs text-gray-400 hover:text-red-500 px-1" },
                    title: "Delete",
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:text-red-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-1']} */ ;
            }
            // @ts-ignore
            [];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.tfoot, __VLS_intrinsics.tfoot)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
            colspan: "6",
            ...{ class: "py-2 text-right text-xs font-semibold text-gray-700 pr-2" },
        });
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['pr-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
            ...{ class: "py-2 pl-2 text-right text-sm font-bold text-gray-900" },
        });
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['pl-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        (__VLS_ctx.fmt(__VLS_ctx.previewTotal));
        (__VLS_ctx.editCurrency);
        __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({});
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "border border-dashed border-gray-200 rounded-xl p-3" },
    });
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-xs text-gray-400 mb-2 font-medium" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex flex-wrap gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        value: (__VLS_ctx.newItemDesc),
        type: "text",
        placeholder: "Description *",
        ...{ class: "flex-1 min-w-40 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-40']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "number",
        min: "0.001",
        step: "0.001",
        placeholder: "Qty",
        ...{ class: "w-20 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" },
    });
    (__VLS_ctx.newItemQty);
    /** @type {__VLS_StyleScopedClasses['w-20']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "number",
        min: "0",
        step: "0.01",
        placeholder: "Unit price",
        ...{ class: "w-28 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" },
    });
    (__VLS_ctx.newItemPrice);
    /** @type {__VLS_StyleScopedClasses['w-28']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "number",
        min: "0",
        max: "100",
        step: "0.01",
        placeholder: "Disc%",
        ...{ class: "w-20 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" },
    });
    (__VLS_ctx.newItemDiscount);
    /** @type {__VLS_StyleScopedClasses['w-20']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "number",
        min: "0",
        max: "100",
        step: "0.01",
        placeholder: "VAT%",
        ...{ class: "w-20 rounded-xl border border-gray-200 px-3 py-1.5 text-sm text-right focus:outline-none focus:border-red-400" },
    });
    (__VLS_ctx.newItemVat);
    /** @type {__VLS_StyleScopedClasses['w-20']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.addItem) },
        disabled: (__VLS_ctx.addingItem || !__VLS_ctx.newItemDesc.trim()),
        ...{ class: "px-4 py-1.5 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.addingItem ? '…' : '+ Add');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.textarea)({
        value: (__VLS_ctx.editNotes),
        rows: "2",
        ...{ class: "w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none" },
        placeholder: "Internal notes (not shown to recipient)…",
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white rounded-2xl border border-gray-100 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.textarea)({
        value: (__VLS_ctx.editClosing),
        rows: "3",
        ...{ class: "w-full rounded-xl border border-gray-200 text-sm px-3 py-2 focus:outline-none focus:border-red-400 resize-none" },
        placeholder: "Write a closing message (e.g. terms, next steps)…",
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
    if (__VLS_ctx.showPreview) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "w-96 flex-shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['w-96']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "bg-white rounded-2xl border border-gray-100 p-5 sticky top-4" },
        });
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
        /** @type {__VLS_StyleScopedClasses['sticky']} */ ;
        /** @type {__VLS_StyleScopedClasses['top-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
            ...{ class: "text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
        /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "border-b-4 pb-3 mb-4" },
            ...{ style: ({ borderColor: __VLS_ctx.firmStore.activeFirm?.primary_color || '#dc2626' }) },
        });
        /** @type {__VLS_StyleScopedClasses['border-b-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['pb-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-base font-bold" },
            ...{ style: ({ color: __VLS_ctx.firmStore.activeFirm?.primary_color || '#dc2626' }) },
        });
        /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
        (__VLS_ctx.firmStore.activeFirm?.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-lg font-semibold text-gray-900 mt-1" },
        });
        /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
        (__VLS_ctx.editTitle || 'Proposal Title');
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium" },
            ...{ class: (__VLS_ctx.statusMeta(__VLS_ctx.editStatus).color) },
        });
        /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (__VLS_ctx.statusMeta(__VLS_ctx.editStatus).label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex gap-4 text-xs text-gray-400 mb-4" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        if (__VLS_ctx.editExpiry) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_ctx.editExpiry);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (__VLS_ctx.editCurrency);
        if (__VLS_ctx.editIntro) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-600 mb-4 leading-relaxed whitespace-pre-wrap" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
            /** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
            (__VLS_ctx.editIntro);
        }
        if (__VLS_ctx.items.length > 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
                ...{ class: "w-full text-xs mb-4" },
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                ...{ class: "text-gray-500 border-b border-gray-100" },
            });
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ class: "text-left pb-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['pb-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ class: "text-right pb-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
            /** @type {__VLS_StyleScopedClasses['pb-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
            for (const [item] of __VLS_vFor((__VLS_ctx.items))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                    key: (item.id),
                    ...{ class: "border-b border-gray-50" },
                });
                /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-50']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 text-gray-700" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                (item.description);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-1 text-right text-gray-700" },
                });
                /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                (__VLS_ctx.fmt(item.total));
                // @ts-ignore
                [statusMeta, statusMeta, fmt, fmt, editTitle, editStatus, editStatus, showPreview, editCurrency, editCurrency, editExpiry, editExpiry, editIntro, editIntro, items, items, previewTotal, newItemDesc, newItemDesc, newItemQty, newItemPrice, newItemDiscount, newItemVat, addItem, addingItem, addingItem, editNotes, editClosing, firmStore, firmStore, firmStore,];
            }
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "border-t border-gray-100 pt-2 text-xs space-y-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['pt-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['space-y-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex justify-between text-gray-500" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (__VLS_ctx.fmt(__VLS_ctx.previewSubtotal));
        if (__VLS_ctx.previewDiscount > 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex justify-between text-gray-500" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_ctx.fmt(__VLS_ctx.previewDiscount));
        }
        if (__VLS_ctx.previewTax > 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex justify-between text-gray-500" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_ctx.fmt(__VLS_ctx.previewTax));
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex justify-between font-bold text-sm text-gray-900 pt-1" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['pt-1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (__VLS_ctx.fmt(__VLS_ctx.previewTotal));
        (__VLS_ctx.editCurrency);
        if (__VLS_ctx.editClosing) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "mt-4 text-xs text-gray-500 leading-relaxed whitespace-pre-wrap" },
            });
            /** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
            /** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
            (__VLS_ctx.editClosing);
        }
    }
}
// @ts-ignore
[fmt, fmt, fmt, fmt, editCurrency, previewTotal, editClosing, editClosing, previewSubtotal, previewDiscount, previewDiscount, previewTax, previewTax,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

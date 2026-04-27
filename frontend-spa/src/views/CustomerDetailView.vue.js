/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useCustomersStore } from '@/stores/customers';
import { useToast } from '@/composables/useToast';
import { api } from '@/api';
const route = useRoute();
const router = useRouter();
const store = useCustomersStore();
const toast = useToast();
const customerId = computed(() => route.params.id);
// Edit mode
const editing = ref(false);
const editFirstName = ref('');
const editLastName = ref('');
const editEmail = ref('');
const editPhone = ref('');
const editCompany = ref('');
const editLoading = ref(false);
const editError = ref('');
// Tags
const newTag = ref('');
const tagsLoading = ref(false);
// Metadata
const newMetaKey = ref('');
const newMetaValue = ref('');
const metaLoading = ref(false);
const linkedLeads = ref([]);
const leadsLoading = ref(false);
function startEdit() {
    const c = store.currentCustomer;
    if (!c)
        return;
    editFirstName.value = c.first_name;
    editLastName.value = c.last_name;
    editEmail.value = c.email;
    editPhone.value = c.phone;
    editCompany.value = c.company_name;
    editError.value = '';
    editing.value = true;
}
function cancelEdit() {
    editing.value = false;
}
async function saveEdit() {
    if (!editFirstName.value.trim()) {
        editError.value = 'First name required.';
        return;
    }
    editLoading.value = true;
    const c = store.currentCustomer;
    const result = await store.updateCustomer(customerId.value, {
        first_name: editFirstName.value.trim(),
        last_name: editLastName.value.trim(),
        email: editEmail.value.trim(),
        phone: editPhone.value.trim(),
        company_name: editCompany.value.trim(),
        tags: c.tags,
        metadata: c.metadata,
    });
    editLoading.value = false;
    if (result.ok) {
        editing.value = false;
        toast.success('Customer updated.');
    }
    else {
        editError.value = result.error ?? 'Failed to update.';
    }
}
async function addTag() {
    const tag = newTag.value.trim();
    if (!tag)
        return;
    const c = store.currentCustomer;
    if (c.tags.includes(tag)) {
        newTag.value = '';
        return;
    }
    tagsLoading.value = true;
    const result = await store.updateCustomer(customerId.value, {
        first_name: c.first_name, last_name: c.last_name,
        email: c.email, phone: c.phone, company_name: c.company_name,
        tags: [...c.tags, tag],
        metadata: c.metadata,
    });
    tagsLoading.value = false;
    if (result.ok)
        newTag.value = '';
    else
        toast.error('Failed to add tag.');
}
async function removeTag(tag) {
    const c = store.currentCustomer;
    tagsLoading.value = true;
    await store.updateCustomer(customerId.value, {
        first_name: c.first_name, last_name: c.last_name,
        email: c.email, phone: c.phone, company_name: c.company_name,
        tags: c.tags.filter((t) => t !== tag),
        metadata: c.metadata,
    });
    tagsLoading.value = false;
}
async function addMetadata() {
    const key = newMetaKey.value.trim();
    const value = newMetaValue.value.trim();
    if (!key)
        return;
    const c = store.currentCustomer;
    metaLoading.value = true;
    const result = await store.updateCustomer(customerId.value, {
        first_name: c.first_name, last_name: c.last_name,
        email: c.email, phone: c.phone, company_name: c.company_name,
        tags: c.tags,
        metadata: { ...c.metadata, [key]: value },
    });
    metaLoading.value = false;
    if (result.ok) {
        newMetaKey.value = '';
        newMetaValue.value = '';
    }
    else
        toast.error('Failed to save metadata.');
}
async function removeMetadata(key) {
    const c = store.currentCustomer;
    const meta = { ...c.metadata };
    delete meta[key];
    metaLoading.value = true;
    await store.updateCustomer(customerId.value, {
        first_name: c.first_name, last_name: c.last_name,
        email: c.email, phone: c.phone, company_name: c.company_name,
        tags: c.tags,
        metadata: meta,
    });
    metaLoading.value = false;
}
async function loadLinkedLeads() {
    leadsLoading.value = true;
    try {
        const res = await api.get(`/api/v1/crm/leads?page_size=50`);
        if (res.ok) {
            linkedLeads.value = res.data.filter((l) => {
                // Filter by customer_id if available from leads endpoint
                return true;
            });
            // For simplicity fetch all and filter client-side (leads don't include customer_id check here)
            // Actually leads have customer_id field, let's re-fetch properly
            const allLeads = await api.get('/api/v1/crm/leads?page_size=100');
            if (allLeads.ok) {
                linkedLeads.value = allLeads.data.filter((l) => l.customer_id === customerId.value);
            }
        }
    }
    finally {
        leadsLoading.value = false;
    }
}
function statusColor(status) {
    const map = {
        new: 'bg-gray-100 text-gray-700', contacted: 'bg-blue-100 text-blue-700',
        proposal: 'bg-yellow-100 text-yellow-700', negotiation: 'bg-orange-100 text-orange-700',
        won: 'bg-green-100 text-green-700', lost: 'bg-red-100 text-red-700', canceled: 'bg-gray-100 text-gray-500',
    };
    return map[status] ?? 'bg-gray-100 text-gray-700';
}
onMounted(async () => {
    await store.fetchCustomer(customerId.value);
    await loadLinkedLeads();
});
const __VLS_ctx = ({ ...{} });
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'p-6 max-w-4xl mx-auto space-y-5' }));
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-5']} */ ;
let __VLS_0;
/** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0(({
	to: '/app/customers',
	class: 'inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600'
})));
const __VLS_2 = __VLS_1(({
	to: '/app/customers',
	class: 'inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600'
}), ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
const { default: __VLS_5 } = __VLS_3.slots;
var __VLS_3;
if (__VLS_ctx.store.loadingDetail) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-4' }));
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({ class: 'h-32 bg-gray-100 rounded-2xl' }));
    /** @type {__VLS_StyleScopedClasses['h-32']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
}
else if (__VLS_ctx.store.currentCustomer) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 p-5' }));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-start justify-between gap-4 flex-wrap' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-4' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'w-14 h-14 rounded-2xl bg-red-100 flex items-center justify-center text-red-600 text-xl font-semibold flex-shrink-0' }));
    /** @type {__VLS_StyleScopedClasses['w-14']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-14']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    (__VLS_ctx.store.currentCustomer.first_name[0]?.toUpperCase() ?? '?');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    if (!__VLS_ctx.editing) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)(({ class: 'text-xl font-semibold text-gray-900' }));
        /** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        ([__VLS_ctx.store.currentCustomer.first_name, __VLS_ctx.store.currentCustomer.last_name].filter(Boolean).join(' '));
        if (__VLS_ctx.store.currentCustomer.company_name) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm text-gray-500' }));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            (__VLS_ctx.store.currentCustomer.company_name);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-3 mt-2 flex-wrap' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        if (__VLS_ctx.store.currentCustomer.email) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)(({
	href: `mailto:${__VLS_ctx.store.currentCustomer.email}`,
	class: 'text-sm text-blue-600 hover:underline flex items-center gap-1'
}));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
            (__VLS_ctx.store.currentCustomer.email);
        }
        if (__VLS_ctx.store.currentCustomer.phone) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)(({
	href: `tel:${__VLS_ctx.store.currentCustomer.phone}`,
	class: 'text-sm text-green-600 hover:underline flex items-center gap-1'
}));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
            (__VLS_ctx.store.currentCustomer.phone);
        }
    }
    else {
        if (__VLS_ctx.editError) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'mb-2 text-sm text-red-600' }));
            /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
            (__VLS_ctx.editError);
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'grid grid-cols-2 gap-2' }));
        /** @type {__VLS_StyleScopedClasses['grid']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	placeholder: 'First name',
	class: 'rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
        (__VLS_ctx.editFirstName);
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	placeholder: 'Last name',
	class: 'rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
        (__VLS_ctx.editLastName);
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	type: 'email',
	placeholder: 'Email',
	class: 'rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
        (__VLS_ctx.editEmail);
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	type: 'tel',
	placeholder: 'Phone',
	class: 'rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
        (__VLS_ctx.editPhone);
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	placeholder: 'Company',
	class: 'col-span-2 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
        (__VLS_ctx.editCompany);
        /** @type {__VLS_StyleScopedClasses['col-span-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-2 mt-2' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.saveEdit,
	disabled: __VLS_ctx.editLoading,
	...{ class: 'px-3 py-1.5 bg-red-600 text-white rounded-xl text-sm hover:bg-red-700 disabled:opacity-50' }
}));
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
        (__VLS_ctx.editLoading ? 'Saving…' : 'Save');
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.cancelEdit,
	...{ class: 'px-3 py-1.5 border border-gray-200 rounded-xl text-sm' }
}));
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    }
    if (!__VLS_ctx.editing) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.startEdit,
	...{ class: 'px-3 py-1.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50' }
}));
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 p-5' }));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-sm font-semibold text-gray-900 mb-3' }));
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex flex-wrap gap-2 mb-3' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    for (const [tag] of __VLS_vFor((__VLS_ctx.store.currentCustomer.tags))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	key: tag,
	class: 'inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 text-sm text-gray-700'
}));
        /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        (tag);
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentCustomer) return;
		__VLS_ctx.removeTag(tag);
		[
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			store,
			editing,
			editing,
			editError,
			editError,
			editFirstName,
			editLastName,
			editEmail,
			editPhone,
			editCompany,
			saveEdit,
			editLoading,
			editLoading,
			cancelEdit,
			startEdit,
			removeTag
		];
	},
	...{ class: 'text-gray-400 hover:text-red-500 ml-1 text-xs' },
	disabled: __VLS_ctx.tagsLoading
}));
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-red-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        // @ts-ignore
        [tagsLoading,];
    }
    if (__VLS_ctx.store.currentCustomer.tags.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-sm text-gray-400' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-2' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	onKeydown: __VLS_ctx.addTag,
	value: __VLS_ctx.newTag,
	type: 'text',
	placeholder: 'Add tag…',
	...{ class: 'flex-1 max-w-48 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400' }
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-48']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.addTag,
	disabled: __VLS_ctx.tagsLoading || !__VLS_ctx.newTag.trim(),
	...{ class: 'px-3 py-1.5 bg-gray-100 rounded-xl text-sm text-gray-700 hover:bg-gray-200 disabled:opacity-50' }
}));
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 p-5' }));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-sm font-semibold text-gray-900 mb-3' }));
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    if (Object.keys(__VLS_ctx.store.currentCustomer.metadata).length > 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'divide-y divide-gray-50 mb-3' }));
        /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
        /** @type {__VLS_StyleScopedClasses['divide-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        for (const [val, key] of __VLS_vFor((__VLS_ctx.store.currentCustomer.metadata))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	key,
	class: 'flex items-center gap-3 py-2 group'
}));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['group']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-sm font-medium text-gray-700 w-32 flex-shrink-0 truncate' }));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['w-32']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (key);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-sm text-gray-500 flex-1 truncate' }));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (val);
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentCustomer) return;
		if (!(Object.keys(__VLS_ctx.store.currentCustomer.metadata).length > 0)) return;
		__VLS_ctx.removeMetadata(key);
		[
			store,
			store,
			store,
			tagsLoading,
			addTag,
			addTag,
			newTag,
			newTag,
			removeMetadata
		];
	},
	...{ class: 'opacity-0 group-hover:opacity-100 text-xs text-red-500 hover:text-red-700' },
	disabled: __VLS_ctx.metaLoading
}));
            /** @type {__VLS_StyleScopedClasses['opacity-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['group-hover:opacity-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-red-700']} */ ;
            // @ts-ignore
            [metaLoading,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-sm text-gray-400 mb-3' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-2 flex-wrap' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	value: __VLS_ctx.newMetaKey,
	type: 'text',
	placeholder: 'Key',
	class: 'w-36 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['w-36']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	value: __VLS_ctx.newMetaValue,
	type: 'text',
	placeholder: 'Value',
	class: 'flex-1 min-w-36 rounded-xl border border-gray-200 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400'
}));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-36']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.addMetadata,
	disabled: __VLS_ctx.metaLoading || !__VLS_ctx.newMetaKey.trim(),
	...{ class: 'px-3 py-1.5 bg-gray-100 rounded-xl text-sm text-gray-700 hover:bg-gray-200 disabled:opacity-50' }
}));
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 p-5' }));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({ class: 'text-sm font-semibold text-gray-900 mb-3' }));
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    if (__VLS_ctx.leadsLoading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-2' }));
        /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
        /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
        for (const [i] of __VLS_vFor((2))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	key: i,
	class: 'h-10 bg-gray-100 rounded-xl'
}));
            /** @type {__VLS_StyleScopedClasses['h-10']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            // @ts-ignore
            [metaLoading, newMetaKey, newMetaKey, newMetaValue, addMetadata, leadsLoading,];
        }
    }
    else if (__VLS_ctx.linkedLeads.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-sm text-gray-400' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'space-y-2' }));
        /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
        for (const [lead] of __VLS_vFor((__VLS_ctx.linkedLeads))) {
            let __VLS_6;
            /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
            RouterLink;
            // @ts-ignore
            const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6(({
	key: lead.id,
	to: `/app/leads/${lead.id}`,
	class: 'flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors'
})));
            const __VLS_8 = __VLS_7(({
	key: lead.id,
	to: `/app/leads/${lead.id}`,
	class: 'flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors'
}), ...__VLS_functionalComponentArgsRest(__VLS_7));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            const { default: __VLS_11 } = __VLS_9.slots;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'flex-1 text-sm font-medium text-gray-900 truncate' }));
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
            (lead.title);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-xs px-2 py-0.5 rounded-full font-medium',
	...{ class: __VLS_ctx.statusColor(lead.status) }
}));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            (lead.status);
            if (lead.value != null) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs text-gray-500' }));
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                (lead.value);
                (lead.currency);
            }
            // @ts-ignore
            [linkedLeads, linkedLeads, statusColor,];
            var __VLS_9;
            // @ts-ignore
            [];
        }
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-center py-12 text-gray-400' }));
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-12']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

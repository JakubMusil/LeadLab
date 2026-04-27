/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useLeadsStore, LEAD_STATUSES, getStatusMeta } from '@/stores/leads';
import { useToast } from '@/composables/useToast';
import { useWebSocket } from '@/composables/useWebSocket';
import { useFirmStore } from '@/stores/firm';
import { api } from '@/api';
import RichTextEditor from '@/components/RichTextEditor.vue';
import DOMPurify from 'dompurify';
function sanitizeHtml(html) {
    return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}
function hasPlainText(html) {
    return Boolean(html.replace(/<[^>]*>/g, '').trim());
}
const route = useRoute();
const router = useRouter();
const store = useLeadsStore();
const toast = useToast();
const firmStore = useFirmStore();
const { on, off } = useWebSocket();
const leadId = computed(() => route.params.id);
const activeTab = ref('overview');
// Team members (for @mention in activity composer)
const teamMembers = ref([]);
const richTextEditorRef = ref(null);
async function loadTeamMembers() {
    const firmId = firmStore.activeFirm ? String(firmStore.activeFirm.id) : '';
    if (!firmId)
        return;
    const res = await api.get(`/api/v1/firms/${firmId}/members`);
    if (res.ok) {
        teamMembers.value = res.data.map((m) => ({ id: m.user_id, label: m.user_full_name || m.user_id }));
    }
}
const activities = ref([]);
const activitiesLoading = ref(false);
const activitiesPage = ref(1);
const activitiesHasMore = ref(true);
const newActivityType = ref('comment');
const newActivityText = ref('');
const activitySubmitting = ref(false);
const tasks = ref([]);
const tasksLoading = ref(false);
const newTaskTitle = ref('');
const newTaskDueDate = ref('');
const taskSubmitting = ref(false);
const files = ref([]);
const filesLoading = ref(false);
const fileInput = ref(null);
const uploadingFile = ref(false);
const uploadProgress = ref(0);
const isDraggingOver = ref(false);
// Edit form
const showEditModal = ref(false);
const editTitle = ref('');
const editDescription = ref('');
const editStatus = ref('');
const editSource = ref('');
const editValue = ref('');
const editCurrency = ref('');
const editError = ref('');
const editLoading = ref(false);
const statusPopupOpen = ref(false);
const activityIcons = {
    comment: '💬', email_out: '📧', email_in: '📥', call: '📞',
    meeting: '🤝', status_change: '🔄', file_upload: '📎',
    task_assigned: '📋', task_completed: '✅',
};
const activityTypes = [
    { value: 'comment', label: 'Comment' },
    { value: 'call', label: 'Call' },
    { value: 'meeting', label: 'Meeting' },
    { value: 'email_out', label: 'Email (Out)' },
    { value: 'email_in', label: 'Email (In)' },
];
function formatTime(ts) {
    return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function fmtBytes(b) {
    if (b < 1024)
        return `${b} B`;
    if (b < 1024 * 1024)
        return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}
async function loadActivities(page = 1) {
    activitiesLoading.value = true;
    try {
        const res = await api.get(`/api/v1/crm/leads/${leadId.value}/activities?page=${page}&page_size=20`);
        if (res.ok) {
            if (page === 1)
                activities.value = res.data;
            else
                activities.value = [...activities.value, ...res.data];
            activitiesPage.value = page;
            activitiesHasMore.value = res.data.length === 20;
        }
    }
    finally {
        activitiesLoading.value = false;
    }
}
async function loadTasks() {
    tasksLoading.value = true;
    try {
        const res = await api.get(`/api/v1/crm/tasks?page_size=100`);
        if (res.ok) {
            tasks.value = res.data.filter((t) => t.lead_id === leadId.value);
        }
    }
    finally {
        tasksLoading.value = false;
    }
}
async function loadFiles() {
    filesLoading.value = true;
    try {
        const res = await api.get(`/api/v1/crm/leads/${leadId.value}/attachments?page_size=50`);
        if (res.ok)
            files.value = res.data;
    }
    finally {
        filesLoading.value = false;
    }
}
async function addActivity() {
    if (!hasPlainText(newActivityText.value) && newActivityType.value === 'comment')
        return;
    activitySubmitting.value = true;
    const mentionedIds = newActivityType.value === 'comment'
        ? (richTextEditorRef.value?.getMentionedIds() ?? [])
        : [];
    const metadata = mentionedIds.length ? { mentions: mentionedIds } : {};
    const res = await api.post('/api/v1/crm/activities', {
        lead_id: leadId.value,
        type: newActivityType.value,
        content_text: newActivityText.value,
        metadata,
    });
    activitySubmitting.value = false;
    if (res.ok) {
        activities.value.unshift(res.data);
        newActivityText.value = '';
        toast.success('Activity added.');
    }
    else {
        toast.error('Failed to add activity.');
    }
}
async function addTask() {
    if (!newTaskTitle.value.trim())
        return;
    taskSubmitting.value = true;
    const payload = { lead_id: leadId.value, title: newTaskTitle.value.trim() };
    if (newTaskDueDate.value)
        payload.due_date = new Date(newTaskDueDate.value).toISOString();
    const res = await api.post('/api/v1/crm/tasks', payload);
    taskSubmitting.value = false;
    if (res.ok) {
        tasks.value.push(res.data);
        newTaskTitle.value = '';
        newTaskDueDate.value = '';
        toast.success('Task created.');
    }
    else {
        toast.error('Failed to create task.');
    }
}
async function completeTask(id) {
    const res = await api.post(`/api/v1/crm/tasks/${id}/complete`);
    if (res.ok) {
        const idx = tasks.value.findIndex((t) => t.id === id);
        if (idx !== -1)
            tasks.value[idx] = res.data;
        toast.success('Task completed.');
    }
    else {
        toast.error('Failed to complete task.');
    }
}
async function uploadFile(e) {
    const input = e.target;
    if (!input.files?.length)
        return;
    await doUpload(input.files[0]);
    if (fileInput.value)
        fileInput.value.value = '';
}
async function onFileDrop(e) {
    isDraggingOver.value = false;
    const file = e.dataTransfer?.files?.[0];
    if (!file)
        return;
    await doUpload(file);
}
async function doUpload(file) {
    uploadingFile.value = true;
    uploadProgress.value = 0;
    const fd = new FormData();
    fd.append('file', file);
    await new Promise((resolve) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/v1/crm/leads/${leadId.value}/attachments`);
        // Forward cookies / CSRF via credentials
        xhr.withCredentials = true;
        xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable)
                uploadProgress.value = Math.round((ev.loaded / ev.total) * 100);
        };
        xhr.onload = () => {
            uploadingFile.value = false;
            uploadProgress.value = 0;
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const item = JSON.parse(xhr.responseText);
                    files.value.unshift(item);
                    toast.success('File uploaded.');
                }
                catch {
                    toast.error('Upload response parse error.');
                }
            }
            else {
                toast.error('Failed to upload file.');
            }
            resolve();
        };
        xhr.onerror = () => {
            uploadingFile.value = false;
            uploadProgress.value = 0;
            toast.error('Failed to upload file.');
            resolve();
        };
        xhr.send(fd);
    });
}
async function deleteFile(id) {
    const res = await api.delete(`/api/v1/crm/leads/${leadId.value}/attachments/${id}`);
    if (res.ok || res.status === 204) {
        files.value = files.value.filter((f) => f.id !== id);
        toast.success('File deleted.');
    }
    else {
        toast.error('Failed to delete file.');
    }
}
async function changeStatus(newStatus) {
    statusPopupOpen.value = false;
    const result = await store.patchStatus(leadId.value, newStatus);
    if (!result.ok)
        toast.error(result.error ?? 'Failed to update status.');
    else
        await loadActivities(1);
}
function openEdit() {
    const lead = store.currentLead;
    if (!lead)
        return;
    editTitle.value = lead.title;
    editDescription.value = lead.description;
    editStatus.value = lead.status;
    editSource.value = lead.source;
    editValue.value = lead.value != null ? String(lead.value) : '';
    editCurrency.value = lead.currency;
    editError.value = '';
    showEditModal.value = true;
}
async function submitEdit() {
    if (!editTitle.value.trim()) {
        editError.value = 'Title is required.';
        return;
    }
    editLoading.value = true;
    const result = await store.updateLead(leadId.value, {
        title: editTitle.value.trim(),
        description: editDescription.value,
        status: editStatus.value,
        source: editSource.value,
        value: editValue.value ? parseFloat(editValue.value) : null,
        currency: editCurrency.value,
    });
    editLoading.value = false;
    if (result.ok) {
        showEditModal.value = false;
        toast.success('Lead updated.');
    }
    else {
        editError.value = result.error ?? 'Failed to update.';
    }
}
async function deleteLead() {
    const result = await store.deleteLead(leadId.value);
    if (result.ok) {
        toast.success('Lead deleted.');
        router.push('/app/leads');
    }
    else {
        toast.error(result.error ?? 'Failed to delete.');
    }
}
onMounted(async () => {
    await store.fetchLead(leadId.value);
    loadTeamMembers();
    if (activeTab.value === 'activities')
        await loadActivities();
    else if (activeTab.value === 'tasks')
        await loadTasks();
    else if (activeTab.value === 'files')
        await loadFiles();
    on('activity.created', onWsActivityCreated);
    on('lead.updated', onWsLeadUpdated);
});
onUnmounted(() => {
    off('activity.created', onWsActivityCreated);
    off('lead.updated', onWsLeadUpdated);
});
function onWsActivityCreated(payload) {
    const act = payload;
    // Only react if this activity belongs to the lead currently open
    if (act.lead_id !== leadId.value)
        return;
    if (activities.value.find((a) => a.id === act.id))
        return;
    activities.value.unshift(act);
}
function onWsLeadUpdated(_payload) {
    // The leads store is already updated by AppShell's WS handler; currentLead
    // is a shared Pinia ref so the UI re-renders automatically.
}
async function switchTab(tab) {
    activeTab.value = tab;
    if (tab === 'activities' && activities.value.length === 0)
        await loadActivities();
    else if (tab === 'tasks' && tasks.value.length === 0)
        await loadTasks();
    else if (tab === 'files' && files.value.length === 0)
        await loadFiles();
    else if (tab === 'proposals')
        router.push(`/app/leads/${leadId.value}/proposals`);
}
const __VLS_ctx = ({ ...{} });
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'p-6 max-w-5xl mx-auto' }));
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-5xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
let __VLS_0;
/** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0(({
	to: '/app/leads',
	class: 'inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4'
})));
const __VLS_2 = __VLS_1(({
	to: '/app/leads',
	class: 'inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-600 mb-4'
}), ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
const { default: __VLS_5 } = __VLS_3.slots;
var __VLS_3;
if (__VLS_ctx.store.loadingDetail) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-4' }));
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({ class: 'h-8 bg-gray-200 rounded w-64' }));
    /** @type {__VLS_StyleScopedClasses['h-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-64']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({ class: 'h-24 bg-gray-100 rounded-2xl' }));
    /** @type {__VLS_StyleScopedClasses['h-24']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
}
else if (__VLS_ctx.store.currentLead) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 p-5 mb-5' }));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-start gap-4 flex-wrap' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex-1 min-w-0' }));
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)(({ class: 'text-xl font-semibold text-gray-900' }));
    /** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    (__VLS_ctx.store.currentLead.title);
    if (__VLS_ctx.store.currentLead.description) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm text-gray-500 mt-1' }));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
        (__VLS_ctx.store.currentLead.description);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-2 flex-shrink-0' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'relative' }));
    /** @type {__VLS_StyleScopedClasses['relative']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		__VLS_ctx.statusPopupOpen = !__VLS_ctx.statusPopupOpen;
		[
			store,
			store,
			store,
			store,
			store,
			statusPopupOpen,
			statusPopupOpen
		];
	},
	...{ class: 'inline-flex items-center gap-1 px-3 py-1.5 rounded-xl text-sm font-medium transition-colors' },
	...{ class: __VLS_ctx.getStatusMeta(__VLS_ctx.store.currentLead.status).color }
}));
    /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    (__VLS_ctx.getStatusMeta(__VLS_ctx.store.currentLead.status).label);
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs opacity-60' }));
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['opacity-60']} */ ;
    if (__VLS_ctx.statusPopupOpen) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'absolute right-0 top-9 z-10 w-40 bg-white rounded-xl border border-gray-200 shadow-lg py-1' }));
        /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
        /** @type {__VLS_StyleScopedClasses['right-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['top-9']} */ ;
        /** @type {__VLS_StyleScopedClasses['z-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-40']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        for (const [s] of __VLS_vFor((__VLS_ctx.LEAD_STATUSES))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!__VLS_ctx.statusPopupOpen) return;
		__VLS_ctx.changeStatus(s.value);
		[
			store,
			store,
			statusPopupOpen,
			getStatusMeta,
			getStatusMeta,
			LEAD_STATUSES,
			changeStatus
		];
	},
	key: s.value,
	...{ class: 'w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 flex items-center gap-2' },
	...{ class: s.value === __VLS_ctx.store.currentLead.status ? 'font-semibold' : '' }
}));
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span)(({
	class: 'w-2 h-2 rounded-full',
	...{ class: s.color.split(' ')[0] }
}));
            /** @type {__VLS_StyleScopedClasses['w-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
            (s.label);
            // @ts-ignore
            [store,];
        }
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.openEdit,
	...{ class: 'px-3 py-1.5 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50' }
}));
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.deleteLead,
	...{ class: 'px-3 py-1.5 rounded-xl border border-red-200 text-sm text-red-600 hover:bg-red-50' }
}));
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex flex-wrap gap-4 mt-4 text-xs text-gray-500' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'font-medium text-gray-700' }));
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    (__VLS_ctx.store.currentLead.source.replace('_', ' '));
    if (__VLS_ctx.store.currentLead.value != null) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'font-medium text-gray-700' }));
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        (__VLS_ctx.store.currentLead.value);
        (__VLS_ctx.store.currentLead.currency);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'font-medium text-gray-700' }));
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    (new Date(__VLS_ctx.store.currentLead.created_at).toLocaleDateString());
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-1 mb-4 bg-gray-100 rounded-xl p-1 w-fit' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-fit']} */ ;
    for (const [tab] of __VLS_vFor(['overview', 'activities', 'tasks', 'files', 'proposals'])) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		__VLS_ctx.switchTab(tab);
		[
			store,
			store,
			store,
			store,
			store,
			openEdit,
			deleteLead,
			switchTab
		];
	},
	key: tab,
	...{ class: 'px-4 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize' },
	...{ class: __VLS_ctx.activeTab === tab ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700' }
}));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        /** @type {__VLS_StyleScopedClasses['capitalize']} */ ;
        (tab);
        // @ts-ignore
        [activeTab,];
    }
    if (__VLS_ctx.activeTab === 'overview') {
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
        __VLS_asFunctionalElement1(__VLS_intrinsics.dl, __VLS_intrinsics.dl)(({ class: 'grid grid-cols-2 gap-4 text-sm' }));
        /** @type {__VLS_StyleScopedClasses['grid']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)(({ class: 'text-xs text-gray-500 mb-0.5' }));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)(({ class: 'font-medium' }));
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (__VLS_ctx.getStatusMeta(__VLS_ctx.store.currentLead.status).label);
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)(({ class: 'text-xs text-gray-500 mb-0.5' }));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)(({ class: 'font-medium capitalize' }));
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['capitalize']} */ ;
        (__VLS_ctx.store.currentLead.source.replace('_', ' '));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)(({ class: 'text-xs text-gray-500 mb-0.5' }));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)(({ class: 'font-medium' }));
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (__VLS_ctx.store.currentLead.value != null ? `${__VLS_ctx.store.currentLead.value} ${__VLS_ctx.store.currentLead.currency}` : '—');
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)(({ class: 'text-xs text-gray-500 mb-0.5' }));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)(({ class: 'font-medium' }));
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (new Date(__VLS_ctx.store.currentLead.created_at).toLocaleDateString());
        if (__VLS_ctx.store.currentLead.description) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'col-span-2' }));
            /** @type {__VLS_StyleScopedClasses['col-span-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.dt, __VLS_intrinsics.dt)(({ class: 'text-xs text-gray-500 mb-0.5' }));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-0.5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.dd, __VLS_intrinsics.dd)({});
            (__VLS_ctx.store.currentLead.description);
        }
    }
    else if (__VLS_ctx.activeTab === 'activities') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'space-y-4' }));
        /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4' }));
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-2 mb-2' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)(({
	value: __VLS_ctx.newActivityType,
	class: 'rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400'
}));
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        for (const [t] of __VLS_vFor((__VLS_ctx.activityTypes))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                key: (t.value),
                value: (t.value),
            });
            (t.label);
            // @ts-ignore
            [store, store, store, store, store, store, store, store, getStatusMeta, activeTab, activeTab, newActivityType, activityTypes,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex flex-col gap-2' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        const __VLS_6 = RichTextEditor;
        // @ts-ignore
        const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
            ref: "richTextEditorRef",
            modelValue: (__VLS_ctx.newActivityText),
            placeholder: (__VLS_ctx.newActivityType === 'comment' ? 'Write a comment… (type @ to mention a team member)' : 'Add a note, call log, or email…'),
            disabled: (__VLS_ctx.activitySubmitting),
            members: (__VLS_ctx.newActivityType === 'comment' ? __VLS_ctx.teamMembers : []),
        }));
        const __VLS_8 = __VLS_7({
            ref: "richTextEditorRef",
            modelValue: (__VLS_ctx.newActivityText),
            placeholder: (__VLS_ctx.newActivityType === 'comment' ? 'Write a comment… (type @ to mention a team member)' : 'Add a note, call log, or email…'),
            disabled: (__VLS_ctx.activitySubmitting),
            members: (__VLS_ctx.newActivityType === 'comment' ? __VLS_ctx.teamMembers : []),
        }, ...__VLS_functionalComponentArgsRest(__VLS_7));
        var __VLS_11 = {};
        var __VLS_9;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex justify-end' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.addActivity,
	disabled: __VLS_ctx.activitySubmitting || !__VLS_ctx.hasPlainText(__VLS_ctx.newActivityText),
	...{ class: 'px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50' }
}));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
        (__VLS_ctx.activitySubmitting ? '…' : 'Add');
        if (__VLS_ctx.activitiesLoading) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-2' }));
            /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
            /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
            for (const [i] of __VLS_vFor((3))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	key: i,
	class: 'h-16 bg-gray-100 rounded-xl'
}));
                /** @type {__VLS_StyleScopedClasses['h-16']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                // @ts-ignore
                [newActivityType, newActivityType, newActivityText, newActivityText, activitySubmitting, activitySubmitting, activitySubmitting, teamMembers, addActivity, hasPlainText, activitiesLoading,];
            }
        }
        else if (__VLS_ctx.activities.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-center py-10 text-gray-400 text-sm' }));
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-10']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50' }));
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-gray-50']} */ ;
            for (const [act] of __VLS_vFor((__VLS_ctx.activities))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	key: act.id,
	class: 'flex items-start gap-3 p-4'
}));
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
                /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-lg mt-0.5 flex-shrink-0' }));
                /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
                /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                (__VLS_ctx.activityIcons[act.type] ?? '📌');
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'min-w-0 flex-1' }));
                /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center gap-2 flex-wrap' }));
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs font-semibold text-gray-700 capitalize' }));
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['capitalize']} */ ;
                (act.type.replace(/_/g, ' '));
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs text-gray-400' }));
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                (__VLS_ctx.formatTime(act.created_at));
                if (act.content_text) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p)(({ class: 'text-sm text-gray-700 dark:text-gray-300 mt-0.5 prose prose-sm dark:prose-invert max-w-none' }));
                    __VLS_asFunctionalDirective(__VLS_directives.vHtml, {})(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.sanitizeHtml(act.content_text)) }, null, null);
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['prose']} */ ;
                    /** @type {__VLS_StyleScopedClasses['prose-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:prose-invert']} */ ;
                    /** @type {__VLS_StyleScopedClasses['max-w-none']} */ ;
                }
                if (act.type === 'status_change') {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm text-gray-500 mt-0.5' }));
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
                    (act.metadata.old_status);
                    (act.metadata.new_status);
                }
                // @ts-ignore
                [activities, activities, activityIcons, formatTime, sanitizeHtml,];
            }
        }
        if (__VLS_ctx.activitiesHasMore) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!(__VLS_ctx.activeTab === 'activities')) return;
		if (!__VLS_ctx.activitiesHasMore) return;
		__VLS_ctx.loadActivities(__VLS_ctx.activitiesPage + 1);
		[
			activitiesHasMore,
			loadActivities,
			activitiesPage
		];
	},
	...{ class: 'w-full py-2 text-sm text-gray-500 hover:text-red-600 border border-gray-200 rounded-xl' }
}));
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        }
    }
    else if (__VLS_ctx.activeTab === 'tasks') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'space-y-4' }));
        /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 p-4' }));
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-2 flex-wrap' }));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	value: __VLS_ctx.newTaskTitle,
	type: 'text',
	placeholder: 'Task title…',
	class: 'flex-1 min-w-40 rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-w-40']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	type: 'date',
	class: 'rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
        (__VLS_ctx.newTaskDueDate);
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: __VLS_ctx.addTask,
	disabled: __VLS_ctx.taskSubmitting || !__VLS_ctx.newTaskTitle.trim(),
	...{ class: 'px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50' }
}));
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
        (__VLS_ctx.taskSubmitting ? '…' : 'Add Task');
        if (__VLS_ctx.tasksLoading) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-2' }));
            /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
            /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
            for (const [i] of __VLS_vFor((3))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	key: i,
	class: 'h-12 bg-gray-100 rounded-xl'
}));
                /** @type {__VLS_StyleScopedClasses['h-12']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                // @ts-ignore
                [activeTab, newTaskTitle, newTaskTitle, newTaskDueDate, addTask, taskSubmitting, taskSubmitting, tasksLoading,];
            }
        }
        else if (__VLS_ctx.tasks.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-center py-10 text-gray-400 text-sm' }));
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-10']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white rounded-2xl border border-gray-100 divide-y divide-gray-50' }));
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-gray-50']} */ ;
            for (const [task] of __VLS_vFor((__VLS_ctx.tasks))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	key: task.id,
	class: 'flex items-center gap-3 p-4'
}));
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!!(__VLS_ctx.activeTab === 'activities')) return;
		if (!(__VLS_ctx.activeTab === 'tasks')) return;
		if (!!__VLS_ctx.tasksLoading) return;
		if (!!(__VLS_ctx.tasks.length === 0)) return;
		__VLS_ctx.completeTask(task.id);
		[
			tasks,
			tasks,
			completeTask
		];
	},
	...{ class: 'w-5 h-5 rounded border flex-shrink-0 flex items-center justify-center transition-colors' },
	...{ class: task.is_completed ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300 hover:border-green-400' },
	disabled: task.is_completed
}));
                /** @type {__VLS_StyleScopedClasses['w-5']} */ ;
                /** @type {__VLS_StyleScopedClasses['h-5']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
                if (task.is_completed) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs' }));
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                }
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex-1 min-w-0' }));
                /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({
	class: 'text-sm text-gray-900',
	...{ class: task.is_completed ? 'line-through text-gray-400' : '' }
}));
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                (task.title);
                if (task.due_date) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({
	class: 'text-xs mt-0.5',
	...{ class: !task.is_completed && new Date(task.due_date) < new Date() ? 'text-red-500' : 'text-gray-400' }
}));
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
                    (new Date(task.due_date).toLocaleDateString());
                }
                // @ts-ignore
                [];
            }
        }
    }
    else if (__VLS_ctx.activeTab === 'files') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'space-y-4' }));
        /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4' }));
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!!(__VLS_ctx.activeTab === 'activities')) return;
		if (!!(__VLS_ctx.activeTab === 'tasks')) return;
		if (!(__VLS_ctx.activeTab === 'files')) return;
		__VLS_ctx.fileInput?.click();
		[activeTab, fileInput];
	},
	...{ onKeydown: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!!(__VLS_ctx.activeTab === 'activities')) return;
		if (!!(__VLS_ctx.activeTab === 'tasks')) return;
		if (!(__VLS_ctx.activeTab === 'files')) return;
		__VLS_ctx.fileInput?.click();
		[fileInput];
	} },
	...{ onDragover: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!!(__VLS_ctx.activeTab === 'activities')) return;
		if (!!(__VLS_ctx.activeTab === 'tasks')) return;
		if (!(__VLS_ctx.activeTab === 'files')) return;
		__VLS_ctx.isDraggingOver = true;
		[isDraggingOver];
	} },
	...{ onDragleave: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!!(__VLS_ctx.activeTab === 'activities')) return;
		if (!!(__VLS_ctx.activeTab === 'tasks')) return;
		if (!(__VLS_ctx.activeTab === 'files')) return;
		__VLS_ctx.isDraggingOver = false;
		[isDraggingOver];
	} },
	...{ onDrop: __VLS_ctx.onFileDrop },
	...{ class: 'flex flex-col items-center justify-center border-2 border-dashed rounded-xl py-8 cursor-pointer transition-colors' },
	...{ class: __VLS_ctx.isDraggingOver ? 'border-red-400 bg-red-50 dark:bg-red-900/20' : 'border-gray-200 dark:border-gray-600 hover:border-red-300 dark:hover:border-red-500' },
	role: 'button',
	'aria-label': 'File upload drop zone. Click or drag and drop files here.',
	tabindex: '0'
}));
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'w-10 h-10 mb-3',
	...{ class: __VLS_ctx.isDraggingOver ? 'text-red-400' : 'text-gray-300 dark:text-gray-600' },
	fill: 'none',
	stroke: 'currentColor',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
        /** @type {__VLS_StyleScopedClasses['w-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.path)({
            'stroke-linecap': "round",
            'stroke-linejoin': "round",
            'stroke-width': "1.5",
            d: "M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12",
        });
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-sm font-medium',
	...{ class: __VLS_ctx.isDraggingOver ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400' }
}));
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (__VLS_ctx.isDraggingOver ? 'Drop to upload' : 'Click or drag & drop a file');
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({ class: 'text-xs text-gray-400 dark:text-gray-500 mt-1' }));
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)(({
	onChange: __VLS_ctx.uploadFile,
	ref: 'fileInput',
	type: 'file',
	...{ class: 'hidden' },
	'aria-hidden': 'true'
}));
        /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
        if (__VLS_ctx.uploadingFile) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'mt-3' }));
            /** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex items-center justify-between text-xs text-gray-500 dark:text-gray-400 mb-1' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (__VLS_ctx.uploadProgress);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'w-full h-1.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden' }));
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	class: 'h-full bg-red-500 rounded-full transition-all duration-200',
	...{ style: { width: `${__VLS_ctx.uploadProgress}%` } },
	role: 'progressbar',
	'aria-valuenow': __VLS_ctx.uploadProgress,
	'aria-valuemin': '0',
	'aria-valuemax': '100'
}));
            /** @type {__VLS_StyleScopedClasses['h-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-red-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
            /** @type {__VLS_StyleScopedClasses['duration-200']} */ ;
        }
        if (__VLS_ctx.filesLoading) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'animate-pulse space-y-2' }));
            /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
            /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
            for (const [i] of __VLS_vFor((3))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	key: i,
	class: 'h-12 bg-gray-100 dark:bg-gray-700 rounded-xl'
}));
                /** @type {__VLS_StyleScopedClasses['h-12']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                // @ts-ignore
                [isDraggingOver, isDraggingOver, isDraggingOver, isDraggingOver, onFileDrop, uploadFile, uploadingFile, uploadProgress, uploadProgress, uploadProgress, filesLoading,];
            }
        }
        else if (__VLS_ctx.files.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex flex-col items-center justify-center py-12 text-center' }));
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-12']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'w-12 h-12 rounded-2xl bg-gray-100 dark:bg-gray-700 flex items-center justify-center mb-3' }));
            /** @type {__VLS_StyleScopedClasses['w-12']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-12']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'w-6 h-6 text-gray-400',
	fill: 'none',
	stroke: 'currentColor',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
            /** @type {__VLS_StyleScopedClasses['w-6']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.path)({
                'stroke-linecap': "round",
                'stroke-linejoin': "round",
                'stroke-width': "1.5",
                d: "M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-sm font-medium text-gray-900 dark:text-gray-100 mb-1' }));
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-xs text-gray-400 dark:text-gray-500' }));
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 divide-y divide-gray-50 dark:divide-gray-700' }));
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:divide-gray-700']} */ ;
            for (const [file] of __VLS_vFor((__VLS_ctx.files))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	key: file.id,
	class: 'flex items-center gap-3 p-4 group'
}));
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
                /** @type {__VLS_StyleScopedClasses['group']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'w-10 h-10 rounded-xl flex-shrink-0 overflow-hidden bg-gray-100 dark:bg-gray-700 flex items-center justify-center' }));
                /** @type {__VLS_StyleScopedClasses['w-10']} */ ;
                /** @type {__VLS_StyleScopedClasses['h-10']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
                if (file.content_type.startsWith('image/')) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.img)(({
	src: file.url,
	alt: file.original_filename,
	class: 'w-full h-full object-cover'
}));
                    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['h-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
                }
                else {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'text-xl',
	'aria-hidden': 'true'
}));
                    /** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
                }
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex-1 min-w-0' }));
                /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
                /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)(({
	href: file.url,
	target: '_blank',
	rel: 'noopener noreferrer',
	class: 'text-sm font-medium text-gray-900 dark:text-gray-100 hover:text-red-600 truncate block'
}));
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
                /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
                /** @type {__VLS_StyleScopedClasses['block']} */ ;
                (file.original_filename);
                __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)(({ class: 'text-xs text-gray-400 dark:text-gray-500' }));
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                (__VLS_ctx.fmtBytes(file.size_bytes));
                (new Date(file.created_at).toLocaleDateString());
                __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!!__VLS_ctx.store.loadingDetail) return;
		if (!__VLS_ctx.store.currentLead) return;
		if (!!(__VLS_ctx.activeTab === 'overview')) return;
		if (!!(__VLS_ctx.activeTab === 'activities')) return;
		if (!!(__VLS_ctx.activeTab === 'tasks')) return;
		if (!(__VLS_ctx.activeTab === 'files')) return;
		if (!!__VLS_ctx.filesLoading) return;
		if (!!(__VLS_ctx.files.length === 0)) return;
		__VLS_ctx.deleteFile(file.id);
		[
			files,
			files,
			fmtBytes,
			deleteFile
		];
	},
	...{ class: 'opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 transition-opacity' },
	'aria-label': `Delete ${file.original_filename}`
}));
                /** @type {__VLS_StyleScopedClasses['opacity-0']} */ ;
                /** @type {__VLS_StyleScopedClasses['group-hover:opacity-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:hover:bg-red-900/30']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['transition-opacity']} */ ;
                // @ts-ignore
                [];
            }
        }
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'text-center py-12 text-gray-400' }));
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-12']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
let __VLS_13;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent1(__VLS_13, new __VLS_13({
    to: "body",
}));
const __VLS_15 = __VLS_14({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
const { default: __VLS_18 } = __VLS_16.slots;
if (__VLS_ctx.showEditModal) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.showEditModal) return;
		__VLS_ctx.showEditModal = false;
		[showEditModal, showEditModal];
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
	'aria-labelledby': 'edit-lead-title'
}));
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-md']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)(({
	id: 'edit-lead-title',
	class: 'text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4'
}));
    /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    if (__VLS_ctx.editError) {
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
        (__VLS_ctx.editError);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)(({
	onSubmit: __VLS_ctx.submitEdit,
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
	value: __VLS_ctx.editTitle,
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
	value: __VLS_ctx.editDescription,
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
	value: __VLS_ctx.editStatus,
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
        [LEAD_STATUSES, editError, editError, submitEdit, editTitle, editDescription, editStatus,];
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
	value: __VLS_ctx.editSource,
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
	class: 'w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400'
}));
    (__VLS_ctx.editValue);
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
	value: __VLS_ctx.editCurrency,
	type: 'text',
	maxlength: '3',
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
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({ class: 'flex gap-3 pt-2' }));
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.showEditModal) return;
		__VLS_ctx.showEditModal = false;
		[
			showEditModal,
			editSource,
			editValue,
			editCurrency
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
	disabled: __VLS_ctx.editLoading,
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
    (__VLS_ctx.editLoading ? 'Saving…' : 'Save');
}
// @ts-ignore
[editLoading, editLoading,];
var __VLS_16;
if (__VLS_ctx.statusPopupOpen) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)(({
	onClick: (...[$event]) => {
		if (!__VLS_ctx.statusPopupOpen) return;
		__VLS_ctx.statusPopupOpen = false;
		[statusPopupOpen, statusPopupOpen];
	},
	...{ class: 'fixed inset-0 z-5' }
}));
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-5']} */ ;
}
// @ts-ignore
var __VLS_12 = __VLS_11;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

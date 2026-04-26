/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useFirmStore } from '@/stores/firm';
import { api } from '@/api';
const router = useRouter();
const firmStore = useFirmStore();
const currentStep = ref(1);
const totalSteps = 5;
// Step 1 — Create workspace
const workspaceName = ref('');
const workspaceError = ref('');
const workspaceLoading = ref(false);
const workspaceCreated = ref(false);
// Step 2 — Invite team
const inviteEmail = ref('');
const inviteLoading = ref(false);
const inviteError = ref('');
const inviteSent = ref(false);
// Step 3 — Import leads
const importFile = ref(null);
const importLoading = ref(false);
const importDone = ref(false);
// Step 4 — Pipeline info
// Step 5 — Complete
const steps = [
    { label: 'Create workspace' },
    { label: 'Invite team' },
    { label: 'Import leads' },
    { label: 'Configure pipeline' },
    { label: 'Complete' },
];
const completedSteps = computed(() => ({
    workspace: workspaceCreated.value,
    team: inviteSent.value,
    leads: importDone.value,
    pipeline: currentStep.value >= 5,
}));
async function handleCreateWorkspace() {
    workspaceError.value = '';
    if (!workspaceName.value.trim()) {
        workspaceError.value = 'Workspace name is required.';
        return;
    }
    workspaceLoading.value = true;
    const result = await firmStore.createFirm(workspaceName.value.trim());
    workspaceLoading.value = false;
    if (result.ok) {
        workspaceCreated.value = true;
        currentStep.value = 2;
    }
    else {
        workspaceError.value = result.error ?? 'Failed to create workspace.';
    }
}
async function handleInvite() {
    if (!inviteEmail.value.trim() || !firmStore.activeFirm)
        return;
    inviteLoading.value = true;
    inviteError.value = '';
    const res = await api.post(`/api/v1/firms/${firmStore.activeFirm.id}/invitations/`, {
        email: inviteEmail.value.trim(),
        role: 'worker',
    });
    inviteLoading.value = false;
    if (res.ok) {
        inviteSent.value = true;
        inviteEmail.value = '';
    }
    else {
        inviteError.value = 'Failed to send invite.';
    }
}
function skipStep() {
    if (currentStep.value < totalSteps)
        currentStep.value++;
}
function nextStep() {
    if (currentStep.value < totalSteps)
        currentStep.value++;
}
function prevStep() {
    if (currentStep.value > 1)
        currentStep.value--;
}
function handleFileChange(e) {
    const input = e.target;
    if (input.files?.[0]) {
        importFile.value = input.files[0];
        importDone.value = true;
    }
}
function finish() {
    if (firmStore.activeFirm) {
        localStorage.setItem('onboarding_complete_' + firmStore.activeFirm.id, '1');
    }
    router.push('/app/dashboard');
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "min-h-screen flex flex-col justify-center items-center bg-gray-50 dark:bg-gray-900 p-8" },
});
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "w-full max-w-lg" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-lg']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-center mb-8" },
});
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text-3xl font-bold text-red-600" },
});
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-gray-500 dark:text-gray-400 mt-1 text-sm" },
});
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-center mb-8" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
for (const [step, idx] of __VLS_vFor((__VLS_ctx.steps))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (step.label),
        ...{ class: "flex items-center" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex flex-col items-center" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors" },
        ...{ class: ({
                'bg-green-600 border-green-600 text-white': idx + 1 < __VLS_ctx.currentStep,
                'bg-red-600 border-red-600 text-white': idx + 1 === __VLS_ctx.currentStep,
                'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-400': idx + 1 > __VLS_ctx.currentStep,
            }) },
    });
    /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-green-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    if (idx + 1 < __VLS_ctx.currentStep) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
        (idx + 1);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "mt-1 text-xs font-medium hidden sm:block" },
        ...{ class: ({
                'text-green-600': idx + 1 < __VLS_ctx.currentStep,
                'text-red-600': idx + 1 === __VLS_ctx.currentStep,
                'text-gray-400': idx + 1 > __VLS_ctx.currentStep,
            }) },
    });
    /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
    /** @type {__VLS_StyleScopedClasses['sm:block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    (step.label);
    if (idx < __VLS_ctx.steps.length - 1) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            ...{ class: "w-8 sm:w-12 h-0.5 mx-1 mb-5" },
            ...{ class: (idx + 1 < __VLS_ctx.currentStep ? 'bg-green-400' : 'bg-gray-200 dark:bg-gray-600') },
        });
        /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['sm:w-12']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['mx-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
    }
    // @ts-ignore
    [steps, steps, currentStep, currentStep, currentStep, currentStep, currentStep, currentStep, currentStep, currentStep,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-8" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
if (__VLS_ctx.currentStep === 1) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-gray-500 dark:text-gray-400 mb-6 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    if (__VLS_ctx.workspaceError) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700" },
        });
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
        (__VLS_ctx.workspaceError);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
        ...{ onSubmit: (__VLS_ctx.handleCreateWorkspace) },
        ...{ class: "space-y-4" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "workspaceName",
        ...{ class: "block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        id: "workspaceName",
        value: (__VLS_ctx.workspaceName),
        type: "text",
        required: true,
        ...{ class: "w-full rounded-xl border border-gray-300 dark:border-gray-600 px-4 py-2.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500" },
        placeholder: "Acme Inc.",
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-red-500']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        type: "submit",
        disabled: (__VLS_ctx.workspaceLoading),
        ...{ class: "w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:cursor-not-allowed']} */ ;
    (__VLS_ctx.workspaceLoading ? 'Creating…' : 'Create workspace');
}
else if (__VLS_ctx.currentStep === 2) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-gray-500 dark:text-gray-400 mb-6 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    if (__VLS_ctx.inviteError) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700" },
        });
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
        (__VLS_ctx.inviteError);
    }
    if (__VLS_ctx.inviteSent) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mb-4 rounded-xl bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700" },
        });
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-green-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-green-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-3 mb-6" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "email",
        placeholder: "colleague@example.com",
        ...{ class: "w-full rounded-xl border border-gray-300 dark:border-gray-600 px-4 py-2.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500" },
    });
    (__VLS_ctx.inviteEmail);
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-red-500']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.handleInvite) },
        disabled: (__VLS_ctx.inviteLoading || !__VLS_ctx.inviteEmail),
        ...{ class: "w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
    (__VLS_ctx.inviteLoading ? 'Sending…' : 'Send invite');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-3" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.prevStep) },
        ...{ class: "flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.skipStep) },
        ...{ class: "flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.nextStep) },
        ...{ class: "flex-1 bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
}
else if (__VLS_ctx.currentStep === 3) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-gray-500 dark:text-gray-400 mb-6 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center mb-6" },
    });
    /** @type {__VLS_StyleScopedClasses['border-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-8']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-3xl mb-3" },
        'aria-hidden': "true",
    });
    /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-sm text-gray-500 dark:text-gray-400 mb-3" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "cursor-pointer inline-block px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600" },
    });
    /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
    /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-600']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        ...{ onChange: (__VLS_ctx.handleFileChange) },
        type: "file",
        accept: ".csv",
        ...{ class: "hidden" },
    });
    /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
    if (__VLS_ctx.importFile) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "mt-2 text-xs text-green-600" },
        });
        /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
        (__VLS_ctx.importFile.name);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-3" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.prevStep) },
        ...{ class: "flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.skipStep) },
        ...{ class: "flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.nextStep) },
        ...{ class: "flex-1 bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
}
else if (__VLS_ctx.currentStep === 4) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-gray-500 dark:text-gray-400 mb-6 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-gray-50 dark:bg-gray-700 rounded-xl p-4 mb-6" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex flex-wrap gap-2 justify-center" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    for (const [stage, i] of __VLS_vFor((['New', 'Contacted', 'Qualified', 'Proposal', 'Won', 'Lost']))) {
        (stage);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "px-3 py-1.5 rounded-full text-xs font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 shadow-sm" },
        });
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
        (stage);
        if (i < 5) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "text-gray-300 dark:text-gray-600 self-center text-xs" },
            });
            /** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['self-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        }
        // @ts-ignore
        [currentStep, currentStep, currentStep, currentStep, workspaceError, workspaceError, handleCreateWorkspace, workspaceName, workspaceLoading, workspaceLoading, inviteError, inviteError, inviteSent, inviteEmail, inviteEmail, handleInvite, inviteLoading, inviteLoading, prevStep, prevStep, skipStep, skipStep, nextStep, nextStep, handleFileChange, importFile, importFile,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-xs text-gray-500 dark:text-gray-400 text-center mt-3" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-3" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.prevStep) },
        ...{ class: "flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.nextStep) },
        ...{ class: "flex-1 bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
}
else if (__VLS_ctx.currentStep === 5) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-center mb-6" },
    });
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-5xl mb-3" },
        'aria-hidden': "true",
    });
    /** @type {__VLS_StyleScopedClasses['text-5xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-gray-500 dark:text-gray-400 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "space-y-2 mb-6" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "flex items-center gap-3 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.completedSteps.workspace ? 'text-green-600' : 'text-gray-400') },
        'aria-hidden': "true",
    });
    (__VLS_ctx.completedSteps.workspace ? '✓' : '○');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.completedSteps.workspace ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400') },
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "flex items-center gap-3 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.completedSteps.team ? 'text-green-600' : 'text-gray-400') },
        'aria-hidden': "true",
    });
    (__VLS_ctx.completedSteps.team ? '✓' : '○');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.completedSteps.team ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400') },
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "flex items-center gap-3 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.completedSteps.leads ? 'text-green-600' : 'text-gray-400') },
        'aria-hidden': "true",
    });
    (__VLS_ctx.completedSteps.leads ? '✓' : '○');
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.completedSteps.leads ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400') },
    });
    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
        ...{ class: "flex items-center gap-3 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-green-600" },
        'aria-hidden': "true",
    });
    /** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-gray-900 dark:text-gray-100" },
    });
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.finish) },
        ...{ class: "w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
}
// @ts-ignore
[currentStep, prevStep, nextStep, completedSteps, completedSteps, completedSteps, completedSteps, completedSteps, completedSteps, completedSteps, completedSteps, completedSteps, finish,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

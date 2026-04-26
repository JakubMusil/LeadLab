/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api } from '@/api';
import { extractErrorMessage } from '@/api/errors';
const route = useRoute();
const router = useRouter();
const newPassword = ref('');
const confirmPassword = ref('');
const errorMsg = ref('');
const successMsg = ref('');
const isLoading = ref(false);
async function handleSubmit() {
    errorMsg.value = '';
    if (newPassword.value.length < 8) {
        errorMsg.value = 'Password must be at least 8 characters.';
        return;
    }
    if (newPassword.value !== confirmPassword.value) {
        errorMsg.value = 'Passwords do not match.';
        return;
    }
    isLoading.value = true;
    const res = await api.post('/api/v1/users/password-reset/confirm', {
        uid: route.params.uidb64,
        token: route.params.token,
        new_password: newPassword.value,
    });
    isLoading.value = false;
    if (res.ok) {
        successMsg.value = 'Password reset successfully! Redirecting to login…';
        setTimeout(() => router.push('/app/login'), 2000);
    }
    else {
        errorMsg.value = extractErrorMessage(res.data, 'Reset failed. The link may have expired.');
    }
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "min-h-screen flex flex-col justify-center items-center bg-gray-50 p-8" },
});
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "w-full max-w-md" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-md']} */ ;
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
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl shadow-sm border border-gray-100 p-8" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
    ...{ class: "text-2xl font-semibold text-gray-900 mb-2" },
});
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-gray-500 mb-6 text-sm" },
});
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
if (__VLS_ctx.successMsg) {
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
    (__VLS_ctx.successMsg);
}
if (__VLS_ctx.errorMsg) {
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
    (__VLS_ctx.errorMsg);
}
if (!__VLS_ctx.successMsg) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
        ...{ onSubmit: (__VLS_ctx.handleSubmit) },
        ...{ class: "space-y-4" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "newPassword",
        ...{ class: "block text-sm font-medium text-gray-700 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        id: "newPassword",
        type: "password",
        required: true,
        autocomplete: "new-password",
        ...{ class: "w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500" },
        placeholder: "Min. 8 characters",
    });
    (__VLS_ctx.newPassword);
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-red-500']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        for: "confirmPassword",
        ...{ class: "block text-sm font-medium text-gray-700 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        id: "confirmPassword",
        type: "password",
        required: true,
        autocomplete: "new-password",
        ...{ class: "w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500" },
        placeholder: "Repeat password",
    });
    (__VLS_ctx.confirmPassword);
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:ring-red-500']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        type: "submit",
        disabled: (__VLS_ctx.isLoading),
        ...{ class: "w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2" },
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
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    if (__VLS_ctx.isLoading) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)({
            ...{ class: "animate-spin h-4 w-4" },
            fill: "none",
            viewBox: "0 0 24 24",
        });
        /** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.circle)({
            ...{ class: "opacity-25" },
            cx: "12",
            cy: "12",
            r: "10",
            stroke: "currentColor",
            'stroke-width': "4",
        });
        /** @type {__VLS_StyleScopedClasses['opacity-25']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.path)({
            ...{ class: "opacity-75" },
            fill: "currentColor",
            d: "M4 12a8 8 0 018-8v8z",
        });
        /** @type {__VLS_StyleScopedClasses['opacity-75']} */ ;
    }
    (__VLS_ctx.isLoading ? 'Resetting…' : 'Reset password');
}
// @ts-ignore
[successMsg, successMsg, successMsg, errorMsg, errorMsg, handleSubmit, newPassword, confirmPassword, isLoading, isLoading, isLoading,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { Button as UiButton, Input as UiInput } from '@/components/ui';
const router = useRouter();
const authStore = useAuthStore();
const email = ref('');
const password = ref('');
const errorMsg = ref('');
const isLoading = ref(false);
async function handleSubmit() {
    errorMsg.value = '';
    isLoading.value = true;
    const result = await authStore.login(email.value, password.value);
    isLoading.value = false;
    if (result.ok) {
        await router.push('/app/dashboard');
    }
    else {
        errorMsg.value = result.error ?? 'Login failed.';
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
    ...{ class: "min-h-screen flex" },
});
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "hidden lg:flex lg:w-1/2 bg-red-600 flex-col justify-center items-center p-12 text-white" },
});
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:flex']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:w-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-12']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "max-w-md text-center" },
});
/** @type {__VLS_StyleScopedClasses['max-w-md']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-5xl font-bold mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-5xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xl text-red-100" },
});
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-100']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "mt-4 text-red-200 text-sm" },
});
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex-1 flex flex-col justify-center items-center p-8 bg-gray-50 dark:bg-gray-900" },
});
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "w-full max-w-md" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-md']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "lg:hidden text-center mb-8" },
});
/** @type {__VLS_StyleScopedClasses['lg:hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text-3xl font-bold text-red-600" },
});
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
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
if (__VLS_ctx.errorMsg) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-4 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-700 dark:text-red-400" },
        role: "alert",
    });
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-red-900/30']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-red-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-red-400']} */ ;
    (__VLS_ctx.errorMsg);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
    ...{ onSubmit: (__VLS_ctx.handleSubmit) },
    ...{ class: "space-y-4" },
});
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
let __VLS_0;
/** @ts-ignore @type {typeof __VLS_components.UiInput} */
UiInput;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    id: "email",
    modelValue: (__VLS_ctx.email),
    type: "email",
    label: "Email",
    placeholder: "you@example.com",
    autocomplete: "email",
    required: true,
}));
const __VLS_2 = __VLS_1({
    id: "email",
    modelValue: (__VLS_ctx.email),
    type: "email",
    label: "Email",
    placeholder: "you@example.com",
    autocomplete: "email",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_5;
/** @ts-ignore @type {typeof __VLS_components.UiInput} */
UiInput;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    id: "password",
    modelValue: (__VLS_ctx.password),
    type: "password",
    label: "Password",
    placeholder: "••••••••",
    autocomplete: "current-password",
    required: true,
}));
const __VLS_7 = __VLS_6({
    id: "password",
    modelValue: (__VLS_ctx.password),
    type: "password",
    label: "Password",
    placeholder: "••••••••",
    autocomplete: "current-password",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex justify-end" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
let __VLS_10;
/** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent1(__VLS_10, new __VLS_10({
    to: "/app/forgot-password",
    ...{ class: "text-sm text-red-600 hover:text-red-700" },
}));
const __VLS_12 = __VLS_11({
    to: "/app/forgot-password",
    ...{ class: "text-sm text-red-600 hover:text-red-700" },
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-700']} */ ;
const { default: __VLS_15 } = __VLS_13.slots;
// @ts-ignore
[errorMsg, errorMsg, handleSubmit, email, password,];
var __VLS_13;
let __VLS_16;
/** @ts-ignore @type {typeof __VLS_components.UiButton | typeof __VLS_components.UiButton} */
UiButton;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
    type: "submit",
    loading: (__VLS_ctx.isLoading),
    disabled: (__VLS_ctx.isLoading),
    ...{ class: "w-full" },
}));
const __VLS_18 = __VLS_17({
    type: "submit",
    loading: (__VLS_ctx.isLoading),
    disabled: (__VLS_ctx.isLoading),
    ...{ class: "w-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
const { default: __VLS_21 } = __VLS_19.slots;
(__VLS_ctx.isLoading ? 'Signing in…' : 'Sign in');
// @ts-ignore
[isLoading, isLoading, isLoading,];
var __VLS_19;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-center mt-6 text-sm text-gray-600 dark:text-gray-400" },
});
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
let __VLS_22;
/** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
RouterLink;
// @ts-ignore
const __VLS_23 = __VLS_asFunctionalComponent1(__VLS_22, new __VLS_22({
    to: "/app/register",
    ...{ class: "text-red-600 font-medium hover:text-red-700" },
}));
const __VLS_24 = __VLS_23({
    to: "/app/register",
    ...{ class: "text-red-600 font-medium hover:text-red-700" },
}, ...__VLS_functionalComponentArgsRest(__VLS_23));
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-700']} */ ;
const { default: __VLS_27 } = __VLS_25.slots;
// @ts-ignore
[];
var __VLS_25;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

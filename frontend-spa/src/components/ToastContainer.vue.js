import { useToast } from '@/composables/useToast';
const { toasts } = useToast();
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['toast-enter-active']} */ ;
/** @type {__VLS_StyleScopedClasses['toast-leave-active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80" },
});
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['bottom-4']} */ ;
/** @type {__VLS_StyleScopedClasses['right-4']} */ ;
/** @type {__VLS_StyleScopedClasses['z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-80']} */ ;
let __VLS_0;
/** @ts-ignore @type {typeof __VLS_components.TransitionGroup | typeof __VLS_components.TransitionGroup} */
TransitionGroup;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
    name: "toast",
}));
const __VLS_2 = __VLS_1({
    name: "toast",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const { default: __VLS_5 } = __VLS_3.slots;
for (const [toast] of __VLS_vFor((__VLS_ctx.toasts))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        key: (toast.id),
        ...{ class: "flex items-start gap-3 rounded-xl px-4 py-3 shadow-lg text-sm font-medium" },
        ...{ class: ({
                'bg-green-600 dark:bg-green-700 text-white': toast.type === 'success',
                'bg-red-600 dark:bg-red-700 text-white': toast.type === 'error',
                'bg-gray-800 dark:bg-gray-700 text-white': toast.type === 'info',
            }) },
        role: "alert",
        'aria-live': "assertive",
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-green-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    if (toast.type === 'success') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    else if (toast.type === 'error') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
    (toast.message);
    // @ts-ignore
    [toasts,];
}
// @ts-ignore
[];
var __VLS_3;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

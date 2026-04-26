/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, onMounted, onUnmounted } from 'vue';
const __VLS_props = withDefaults(defineProps(), { placement: 'right' });
const open = ref(false);
const rootRef = ref(null);
function handleClickOutside(e) {
    if (rootRef.value && !rootRef.value.contains(e.target)) {
        open.value = false;
    }
}
onMounted(() => document.addEventListener('click', handleClickOutside));
onUnmounted(() => document.removeEventListener('click', handleClickOutside));
function selectItem(item) {
    open.value = false;
    item.onClick();
}
const __VLS_defaults = { placement: 'right' };
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['dropdown-enter-active']} */ ;
/** @type {__VLS_StyleScopedClasses['dropdown-leave-active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ref: "rootRef",
    ...{ class: "relative inline-block" },
});
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.open = !__VLS_ctx.open;
            // @ts-ignore
            [open, open,];
        } },
});
var __VLS_0 = {};
let __VLS_2;
/** @ts-ignore @type {typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
    name: "dropdown",
}));
const __VLS_4 = __VLS_3({
    name: "dropdown",
}, ...__VLS_functionalComponentArgsRest(__VLS_3));
const { default: __VLS_7 } = __VLS_5.slots;
if (__VLS_ctx.open) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: () => { } },
        ...{ class: "absolute z-40 mt-1 py-1 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-lg min-w-36" },
        ...{ class: (__VLS_ctx.placement === 'left' ? 'right-0' : 'left-0') },
        role: "menu",
    });
    /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-40']} */ ;
    /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-36']} */ ;
    for (const [item] of __VLS_vFor((__VLS_ctx.items))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.open))
                        return;
                    __VLS_ctx.selectItem(item);
                    // @ts-ignore
                    [open, placement, items, selectItem,];
                } },
            key: (item.label),
            ...{ class: "w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors" },
            ...{ class: (item.danger
                    ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                    : 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700') },
            role: "menuitem",
        });
        /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        if (item.icon) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
            (item.icon);
        }
        (item.label);
        // @ts-ignore
        [];
    }
}
// @ts-ignore
[];
var __VLS_5;
// @ts-ignore
var __VLS_1 = __VLS_0;
// @ts-ignore
[];
const __VLS_base = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
const __VLS_export = {};
export default {};

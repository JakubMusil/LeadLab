/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
/**
 * ContextMenu — right-click / long-press context menu.
 *
 * Usage:
 *   <ContextMenu :items="menuItems" @action="handleAction">
 *     <tr @contextmenu.prevent="openMenu">...</tr>
 *   </ContextMenu>
 *
 * Or trigger programmatically via the exposed `open(x, y)` method.
 */
import { ref, onMounted, onUnmounted } from 'vue';
const __VLS_props = defineProps();
const emit = defineEmits();
const visible = ref(false);
const x = ref(0);
const y = ref(0);
function open(clientX, clientY) {
    x.value = clientX;
    y.value = clientY;
    visible.value = true;
}
function close() {
    visible.value = false;
}
function handleAction(id) {
    emit('action', id);
    close();
}
function onClickOutside() {
    if (visible.value)
        close();
}
function onScroll() {
    if (visible.value)
        close();
}
onMounted(() => {
    document.addEventListener('click', onClickOutside);
    document.addEventListener('scroll', onScroll, true);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape')
            close();
    });
});
onUnmounted(() => {
    document.removeEventListener('click', onClickOutside);
    document.removeEventListener('scroll', onScroll, true);
});
const __VLS_exposed = { open, close };
defineExpose(__VLS_exposed);
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
var __VLS_0 = {};
let __VLS_2;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
    to: "body",
}));
const __VLS_4 = __VLS_3({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_3));
const { default: __VLS_7 } = __VLS_5.slots;
let __VLS_8;
/** @ts-ignore @type {typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent1(__VLS_8, new __VLS_8({
    enterActiveClass: "transition-all duration-100 ease-out",
    enterFromClass: "opacity-0 scale-95",
    enterToClass: "opacity-100 scale-100",
    leaveActiveClass: "transition-all duration-75 ease-in",
    leaveFromClass: "opacity-100 scale-100",
    leaveToClass: "opacity-0 scale-95",
}));
const __VLS_10 = __VLS_9({
    enterActiveClass: "transition-all duration-100 ease-out",
    enterFromClass: "opacity-0 scale-95",
    enterToClass: "opacity-100 scale-100",
    leaveActiveClass: "transition-all duration-75 ease-in",
    leaveFromClass: "opacity-100 scale-100",
    leaveToClass: "opacity-0 scale-95",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const { default: __VLS_13 } = __VLS_11.slots;
if (__VLS_ctx.visible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: () => { } },
        ...{ class: "fixed z-[200] min-w-[160px] bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-200 dark:border-gray-700 py-1 overflow-hidden" },
        ...{ style: ({ top: `${__VLS_ctx.y}px`, left: `${__VLS_ctx.x}px` }) },
        role: "menu",
        'aria-label': "Context menu",
    });
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-[200]']} */ ;
    /** @type {__VLS_StyleScopedClasses['min-w-[160px]']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
    for (const [item] of __VLS_vFor((__VLS_ctx.items))) {
        (item.id);
        if (item.divider) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
                ...{ class: "h-px mx-2 my-1 bg-gray-200 dark:bg-gray-700" },
                role: "separator",
            });
            /** @type {__VLS_StyleScopedClasses['h-px']} */ ;
            /** @type {__VLS_StyleScopedClasses['mx-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['my-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.visible))
                            return;
                        if (!!(item.divider))
                            return;
                        __VLS_ctx.handleAction(item.id);
                        // @ts-ignore
                        [visible, y, x, items, handleAction,];
                    } },
                type: "button",
                ...{ class: "w-full flex items-center gap-2.5 px-3 py-1.5 text-sm text-left transition-colors disabled:opacity-40 disabled:cursor-not-allowed" },
                ...{ class: (item.danger
                        ? 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20'
                        : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700') },
                disabled: (item.disabled),
                role: "menuitem",
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
            /** @type {__VLS_StyleScopedClasses['disabled:opacity-40']} */ ;
            /** @type {__VLS_StyleScopedClasses['disabled:cursor-not-allowed']} */ ;
            if (item.icon) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "w-4 text-center flex-shrink-0" },
                });
                /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                (item.icon);
            }
            (item.label);
        }
        // @ts-ignore
        [];
    }
}
// @ts-ignore
[];
var __VLS_11;
// @ts-ignore
[];
var __VLS_5;
// @ts-ignore
var __VLS_1 = __VLS_0;
// @ts-ignore
[];
const __VLS_base = (await import('vue')).defineComponent({
    setup: () => (__VLS_exposed),
    __typeEmits: {},
    __typeProps: {},
});
const __VLS_export = {};
export default {};

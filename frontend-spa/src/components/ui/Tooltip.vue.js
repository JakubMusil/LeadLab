/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref } from 'vue';
const __VLS_props = withDefaults(defineProps(), { placement: 'top' });
const visible = ref(false);
const __VLS_defaults = { placement: 'top' };
const __VLS_ctx = ({
	...{},
	...{},
	...{}
});
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['tooltip-enter-active']} */ ;
/** @type {__VLS_StyleScopedClasses['tooltip-leave-active']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	onMouseenter: (...[$event]) => {
		__VLS_ctx.visible = true;
		[visible];
	},
	...{ onMouseleave: (...[$event]) => {
		__VLS_ctx.visible = false;
		[visible];
	} },
	...{ onFocusin: (...[$event]) => {
		__VLS_ctx.visible = true;
		[visible];
	} },
	...{ onFocusout: (...[$event]) => {
		__VLS_ctx.visible = false;
		[visible];
	} },
	...{ class: 'relative inline-flex' }
}));
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
var __VLS_0 = {};
let __VLS_2;
/** @ts-ignore @type {typeof __VLS_components.Transition | typeof __VLS_components.Transition} */
Transition;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent1(__VLS_2, new __VLS_2({
    name: "tooltip",
}));
const __VLS_4 = __VLS_3({
    name: "tooltip",
}, ...__VLS_functionalComponentArgsRest(__VLS_3));
const { default: __VLS_7 } = __VLS_5.slots;
if (__VLS_ctx.visible) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)(({
	role: 'tooltip',
	class: 'absolute z-50 whitespace-nowrap bg-gray-900 dark:bg-gray-700 text-white text-xs px-2 py-1 rounded-lg pointer-events-none',
	...{ class: [
		__VLS_ctx.placement === 'top' && 'bottom-full left-1/2 -translate-x-1/2 mb-1',
		__VLS_ctx.placement === 'bottom' && 'top-full left-1/2 -translate-x-1/2 mt-1',
		__VLS_ctx.placement === 'left' && 'right-full top-1/2 -translate-y-1/2 mr-1',
		__VLS_ctx.placement === 'right' && 'left-full top-1/2 -translate-y-1/2 ml-1'
	] }
}));
    /** @type {__VLS_StyleScopedClasses['absolute']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['whitespace-nowrap']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['pointer-events-none']} */ ;
    (__VLS_ctx.content);
}
// @ts-ignore
[visible, placement, placement, placement, placement, content,];
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

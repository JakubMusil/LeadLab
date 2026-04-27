/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
defineOptions({ inheritAttrs: false });
const __VLS_props = withDefaults(defineProps(), {
    variant: 'primary',
    size: 'md',
    type: 'button',
});
const __VLS_emit = defineEmits();
const __VLS_defaults = {
    variant: 'primary',
    size: 'md',
    type: 'button',
};
const __VLS_ctx = ({
	...{},
	...{},
	...{}
});
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)(({
	onClick: (...[$event]) => {
		__VLS_ctx.$emit('click', $event);
		[$emit];
	},
	type: __VLS_ctx.type,
	disabled: __VLS_ctx.disabled || __VLS_ctx.loading,
	...{ class: 'inline-flex items-center justify-center gap-2 font-medium rounded-xl transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed' },
	...{ class: [
		__VLS_ctx.variant === 'primary' && 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
		__VLS_ctx.variant === 'secondary' && 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-700 focus:ring-gray-400',
		__VLS_ctx.variant === 'ghost' && 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700 focus:ring-gray-400',
		__VLS_ctx.variant === 'danger' && 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800 focus:ring-red-500',
		__VLS_ctx.size === 'sm' && 'px-3 py-1.5 text-xs',
		__VLS_ctx.size === 'md' && 'px-4 py-2 text-sm',
		__VLS_ctx.size === 'lg' && 'px-5 py-2.5 text-base'
	] }
}));
(__VLS_ctx.$attrs);
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-offset-2']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:cursor-not-allowed']} */ ;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.svg, __VLS_intrinsics.svg)(({
	class: 'animate-spin h-4 w-4 flex-shrink-0',
	fill: 'none',
	viewBox: '0 0 24 24',
	'aria-hidden': 'true'
}));
    /** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.circle)(({
	class: 'opacity-25',
	cx: '12',
	cy: '12',
	r: '10',
	stroke: 'currentColor',
	'stroke-width': '4'
}));
    /** @type {__VLS_StyleScopedClasses['opacity-25']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.path)(({
	class: 'opacity-75',
	fill: 'currentColor',
	d: 'M4 12a8 8 0 018-8v8z'
}));
    /** @type {__VLS_StyleScopedClasses['opacity-75']} */ ;
}
var __VLS_0 = {};
// @ts-ignore
var __VLS_1 = __VLS_0;
// @ts-ignore
[type, disabled, loading, loading, variant, variant, variant, variant, size, size, size, $attrs,];
const __VLS_base = (await import('vue')).defineComponent({
    __typeEmits: {},
    __defaults: __VLS_defaults,
    __typeProps: {},
});
const __VLS_export = {};
export default {};

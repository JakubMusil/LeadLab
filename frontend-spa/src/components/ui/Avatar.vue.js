/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { computed } from 'vue';
const props = withDefaults(defineProps(), { size: 'md' });
const initials = computed(() => {
    if (!props.name)
        return '?';
    const words = props.name.trim().split(/\s+/);
    return ((words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')).toUpperCase() || '?';
});
const __VLS_defaults = { size: 'md' };
const __VLS_ctx = ({
	...{},
	...{},
	...{}
});
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)(({
	class: 'inline-flex items-center justify-center rounded-full bg-red-600 text-white font-medium flex-shrink-0 overflow-hidden',
	...{ class: [
		__VLS_ctx.size === 'xs' && 'w-6 h-6 text-xs',
		__VLS_ctx.size === 'sm' && 'w-8 h-8 text-sm',
		__VLS_ctx.size === 'md' && 'w-10 h-10 text-sm',
		__VLS_ctx.size === 'lg' && 'w-12 h-12 text-base'
	] },
	title: __VLS_ctx.name
}));
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
if (__VLS_ctx.src) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.img)(({
	src: __VLS_ctx.src,
	alt: __VLS_ctx.name,
	class: 'w-full h-full object-cover'
}));
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        'aria-hidden': "true",
    });
    (__VLS_ctx.initials);
}
// @ts-ignore
[size, size, size, size, name, name, src, src, initials,];
const __VLS_export = (await import('vue')).defineComponent({
    __defaults: __VLS_defaults,
    __typeProps: {},
});
export default {};

/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
const props = defineProps();
function badgeClass(score) {
    if (score >= 80)
        return 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300';
    if (score >= 60)
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300';
    if (score >= 30)
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300';
    return 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300';
}
function label(score) {
    if (score >= 80)
        return 'High';
    if (score >= 60)
        return 'Good';
    if (score >= 30)
        return 'Medium';
    return 'Low';
}
const __VLS_ctx = {
    ...{},
    ...{},
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (__VLS_ctx.score != null) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold" },
        ...{ class: (__VLS_ctx.badgeClass(__VLS_ctx.score)) },
        title: (`Lead score: ${__VLS_ctx.score}/100 (${__VLS_ctx.label(__VLS_ctx.score)})`),
        'aria-label': (`Score ${__VLS_ctx.score} out of 100`),
    });
    /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "tabular-nums" },
    });
    /** @type {__VLS_StyleScopedClasses['tabular-nums']} */ ;
    (__VLS_ctx.score);
}
// @ts-ignore
[score, score, score, score, score, score, badgeClass, label,];
const __VLS_export = (await import('vue')).defineComponent({
    __typeProps: {},
});
export default {};

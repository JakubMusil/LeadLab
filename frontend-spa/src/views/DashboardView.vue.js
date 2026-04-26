/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useFirmStore } from '@/stores/firm';
import { api } from '@/api';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { VueDraggable } from 'vue-draggable-plus';
use([CanvasRenderer, BarChart, GridComponent, TooltipComponent]);
const DEFAULT_WIDGETS = [
    { id: 'stat_cards', visible: true, order: 0 },
    { id: 'pipeline_chart', visible: true, order: 1 },
    { id: 'recent_activity', visible: true, order: 2 },
    { id: 'status_breakdown', visible: true, order: 3 },
];
const WIDGET_LABELS = {
    stat_cards: 'Stat Cards',
    pipeline_chart: 'Pipeline Chart',
    recent_activity: 'Recent Activity',
    status_breakdown: 'Status Breakdown',
};
const firmStore = useFirmStore();
const stats = ref(null);
const loading = ref(false);
const widgets = ref([...DEFAULT_WIDGETS]);
const showLayoutEditor = ref(false);
const savingLayout = ref(false);
let refreshTimer = null;
const STATUS_LABELS = {
    new: 'New', contacted: 'Contacted', proposal: 'Proposal',
    negotiation: 'Negotiation', won: 'Won', lost: 'Lost', canceled: 'Canceled',
};
const STATUS_COLORS = {
    new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
    negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
};
const chartOption = computed(() => {
    if (!stats.value)
        return {};
    const entries = Object.entries(stats.value.leads_by_status);
    return {
        tooltip: { trigger: 'axis' },
        grid: { left: 8, right: 8, top: 8, bottom: 0, containLabel: true },
        xAxis: {
            type: 'category',
            data: entries.map(([k]) => STATUS_LABELS[k] ?? k),
            axisLabel: { fontSize: 11 },
        },
        yAxis: { type: 'value', minInterval: 1 },
        series: [{
                type: 'bar',
                data: entries.map(([k, v]) => ({ value: v, itemStyle: { color: STATUS_COLORS[k] ?? '#6b7280' } })),
                barMaxWidth: 40,
            }],
    };
});
const visibleWidgets = computed(() => widgets.value
    .filter((w) => w.visible)
    .sort((a, b) => a.order - b.order));
const activityIcons = {
    comment: '💬', email_out: '📧', email_in: '📥', call: '📞',
    meeting: '🤝', status_change: '🔄', file_upload: '📎',
    task_assigned: '📋', task_completed: '✅',
};
function activityIcon(type) {
    return activityIcons[type] ?? '📌';
}
function formatTime(ts) {
    return new Date(ts).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function fmtCurrency(val) {
    return new Intl.NumberFormat(undefined, { style: 'decimal', maximumFractionDigits: 0 }).format(val);
}
async function loadStats() {
    if (!firmStore.activeFirm)
        return;
    loading.value = true;
    try {
        const res = await api.get('/api/v1/crm/stats');
        if (res.ok)
            stats.value = res.data;
    }
    finally {
        loading.value = false;
    }
}
async function loadLayout() {
    const res = await api.get('/api/v1/crm/dashboard-layout');
    if (res.ok && res.data.layout && res.data.layout.length > 0) {
        // Merge saved layout with defaults (handle new widgets added after save)
        const saved = res.data.layout;
        const savedIds = new Set(saved.map((w) => w.id));
        const merged = [
            ...saved,
            ...DEFAULT_WIDGETS.filter((d) => !savedIds.has(d.id)),
        ];
        widgets.value = merged;
    }
}
async function saveLayout() {
    savingLayout.value = true;
    try {
        // Update order from current array position
        const layout = widgets.value.map((w, i) => ({ ...w, order: i }));
        widgets.value = layout;
        await api.put('/api/v1/crm/dashboard-layout', { layout });
    }
    finally {
        savingLayout.value = false;
        showLayoutEditor.value = false;
    }
}
function onDragEnd() {
    // Re-index order after drag
    widgets.value = widgets.value.map((w, i) => ({ ...w, order: i }));
    saveLayout();
}
function toggleWidget(id) {
    const w = widgets.value.find((w) => w.id === id);
    if (w)
        w.visible = !w.visible;
}
onMounted(async () => {
    await loadLayout();
    await loadStats();
    refreshTimer = setInterval(loadStats, 60_000);
});
onUnmounted(() => {
    if (refreshTimer)
        clearInterval(refreshTimer);
});
const showSetupBanner = computed(() => {
    if (!firmStore.activeFirm)
        return false;
    return !localStorage.getItem('onboarding_complete_' + firmStore.activeFirm.id);
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "p-6 max-w-7xl mx-auto space-y-6" },
});
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
if (__VLS_ctx.showSetupBanner) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-5 flex items-center justify-between gap-4" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-red-900/20']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-red-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm font-semibold text-red-900 dark:text-red-100" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-red-100']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-xs text-red-700 dark:text-red-300 mt-0.5" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-red-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
    let __VLS_0;
    /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
    RouterLink;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        to: "/app/onboarding",
        ...{ class: "flex-shrink-0 px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors" },
    }));
    const __VLS_2 = __VLS_1({
        to: "/app/onboarding",
        ...{ class: "flex-shrink-0 px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    const { default: __VLS_5 } = __VLS_3.slots;
    // @ts-ignore
    [showSetupBanner,];
    var __VLS_3;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-lg font-semibold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.showLayoutEditor = !__VLS_ctx.showLayoutEditor;
            // @ts-ignore
            [showLayoutEditor, showLayoutEditor,];
        } },
    ...{ class: "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors" },
    'aria-expanded': (__VLS_ctx.showLayoutEditor),
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    'aria-hidden': "true",
});
if (__VLS_ctx.showLayoutEditor) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 p-5" },
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-between mb-4" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-xs text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.saveLayout) },
        ...{ class: "px-3 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50" },
        disabled: (__VLS_ctx.savingLayout),
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-[color:var(--brand-color)]']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:opacity-90']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-opacity']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.savingLayout ? 'Saving…' : 'Save');
    let __VLS_6;
    /** @ts-ignore @type {typeof __VLS_components.VueDraggable | typeof __VLS_components.VueDraggable} */
    VueDraggable;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
        ...{ 'onEnd': {} },
        modelValue: (__VLS_ctx.widgets),
        handle: ".drag-handle",
        ...{ class: "space-y-2" },
    }));
    const __VLS_8 = __VLS_7({
        ...{ 'onEnd': {} },
        modelValue: (__VLS_ctx.widgets),
        handle: ".drag-handle",
        ...{ class: "space-y-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_7));
    let __VLS_11;
    const __VLS_12 = ({ end: {} },
        { onEnd: (__VLS_ctx.onDragEnd) });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    const { default: __VLS_13 } = __VLS_9.slots;
    for (const [widget] of __VLS_vFor((__VLS_ctx.widgets))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (widget.id),
            ...{ class: "flex items-center gap-3 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 cursor-default" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['cursor-default']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "drag-handle cursor-grab text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-sm" },
            title: "Drag to reorder",
            'aria-hidden': "true",
        });
        /** @type {__VLS_StyleScopedClasses['drag-handle']} */ ;
        /** @type {__VLS_StyleScopedClasses['cursor-grab']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "flex-1 text-sm text-gray-700 dark:text-gray-300" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        (__VLS_ctx.WIDGET_LABELS[widget.id] ?? widget.id);
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showLayoutEditor))
                        return;
                    __VLS_ctx.toggleWidget(widget.id);
                    // @ts-ignore
                    [showLayoutEditor, showLayoutEditor, saveLayout, savingLayout, savingLayout, widgets, widgets, onDragEnd, WIDGET_LABELS, toggleWidget,];
                } },
            type: "button",
            ...{ class: "relative inline-flex h-5 w-9 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[color:var(--brand-color)] focus:ring-offset-2" },
            ...{ class: (widget.visible ? 'bg-[color:var(--brand-color)]' : 'bg-gray-300 dark:bg-gray-600') },
            'aria-label': (`${widget.visible ? 'Hide' : 'Show'} ${__VLS_ctx.WIDGET_LABELS[widget.id] ?? widget.id}`),
            'aria-checked': (widget.visible),
            role: "switch",
        });
        /** @type {__VLS_StyleScopedClasses['relative']} */ ;
        /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-5']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-9']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:ring-[color:var(--brand-color)]']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:ring-offset-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ class: "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform mt-0.5" },
            ...{ class: (widget.visible ? 'translate-x-4' : 'translate-x-0.5') },
        });
        /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['transform']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        // @ts-ignore
        [WIDGET_LABELS,];
    }
    // @ts-ignore
    [];
    var __VLS_9;
    var __VLS_10;
}
if (__VLS_ctx.loading && !__VLS_ctx.stats) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "animate-pulse space-y-4" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "grid grid-cols-2 lg:grid-cols-4 gap-4" },
    });
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['lg:grid-cols-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    for (const [i] of __VLS_vFor((4))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            key: (i),
            ...{ class: "h-24 bg-gray-200 dark:bg-gray-700 rounded-2xl" },
        });
        /** @type {__VLS_StyleScopedClasses['h-24']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
        // @ts-ignore
        [loading, stats,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "grid lg:grid-cols-3 gap-4" },
    });
    /** @type {__VLS_StyleScopedClasses['grid']} */ ;
    /** @type {__VLS_StyleScopedClasses['lg:grid-cols-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "lg:col-span-2 h-64 bg-gray-200 dark:bg-gray-700 rounded-2xl" },
    });
    /** @type {__VLS_StyleScopedClasses['lg:col-span-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-64']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "h-64 bg-gray-200 dark:bg-gray-700 rounded-2xl" },
    });
    /** @type {__VLS_StyleScopedClasses['h-64']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
}
else if (__VLS_ctx.stats) {
    for (const [widget] of __VLS_vFor((__VLS_ctx.visibleWidgets))) {
        (widget.id);
        if (widget.id === 'stat_cards') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "grid grid-cols-2 lg:grid-cols-4 gap-4" },
            });
            /** @type {__VLS_StyleScopedClasses['grid']} */ ;
            /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['lg:grid-cols-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
            });
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.stats.total_leads);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-400 dark:text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            ((__VLS_ctx.stats.conversion_rate * 100).toFixed(1));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
            });
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-3xl font-bold text-gray-900 dark:text-gray-100 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.stats.total_customers);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-400 dark:text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
            });
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-2xl font-bold text-gray-900 dark:text-gray-100 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.fmtCurrency(__VLS_ctx.stats.pipeline_value));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-400 dark:text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.fmtCurrency(__VLS_ctx.stats.won_value));
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
            });
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-3xl font-bold mt-1" },
                ...{ class: (__VLS_ctx.stats.total_tasks_overdue > 0 ? 'text-red-600' : 'text-gray-900 dark:text-gray-100') },
            });
            /** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.stats.total_tasks_pending);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs mt-1" },
                ...{ class: (__VLS_ctx.stats.total_tasks_overdue > 0 ? 'text-red-500' : 'text-gray-400 dark:text-gray-500') },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.stats.total_tasks_overdue);
        }
        else if (widget.id === 'pipeline_chart' || widget.id === 'recent_activity') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "grid lg:grid-cols-3 gap-4" },
            });
            /** @type {__VLS_StyleScopedClasses['grid']} */ ;
            /** @type {__VLS_StyleScopedClasses['lg:grid-cols-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
            if (__VLS_ctx.visibleWidgets.some((w) => w.id === 'pipeline_chart') && __VLS_ctx.visibleWidgets.some((w) => w.id === 'recent_activity') && widget.id === 'pipeline_chart') {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg:col-span-2 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
                });
                /** @type {__VLS_StyleScopedClasses['lg:col-span-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
                    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
                });
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
                let __VLS_14;
                /** @ts-ignore @type {typeof __VLS_components.VChart} */
                VChart;
                // @ts-ignore
                const __VLS_15 = __VLS_asFunctionalComponent1(__VLS_14, new __VLS_14({
                    option: (__VLS_ctx.chartOption),
                    ...{ style: {} },
                    autoresize: true,
                }));
                const __VLS_16 = __VLS_15({
                    option: (__VLS_ctx.chartOption),
                    ...{ style: {} },
                    autoresize: true,
                }, ...__VLS_functionalComponentArgsRest(__VLS_15));
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
                });
                /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
                    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
                });
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
                if (__VLS_ctx.stats.recent_activities.length === 0) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "text-sm text-gray-400 text-center py-8" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-8']} */ ;
                }
                __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
                    ...{ class: "space-y-3 overflow-y-auto max-h-56" },
                });
                /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
                /** @type {__VLS_StyleScopedClasses['max-h-56']} */ ;
                for (const [act] of __VLS_vFor((__VLS_ctx.stats.recent_activities))) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                        key: (act.id),
                        ...{ class: "flex items-start gap-2.5" },
                    });
                    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                    /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
                    /** @type {__VLS_StyleScopedClasses['gap-2.5']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                        ...{ class: "text-base mt-0.5 flex-shrink-0" },
                        'aria-hidden': "true",
                    });
                    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                    (__VLS_ctx.activityIcon(act.type));
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "min-w-0" },
                    });
                    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                        ...{ class: "text-xs text-gray-700 dark:text-gray-300 truncate" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
                    if (act.lead_id) {
                        let __VLS_19;
                        /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
                        RouterLink;
                        // @ts-ignore
                        const __VLS_20 = __VLS_asFunctionalComponent1(__VLS_19, new __VLS_19({
                            to: (`/app/leads/${act.lead_id}`),
                            ...{ class: "font-medium hover:text-red-600" },
                        }));
                        const __VLS_21 = __VLS_20({
                            to: (`/app/leads/${act.lead_id}`),
                            ...{ class: "font-medium hover:text-red-600" },
                        }, ...__VLS_functionalComponentArgsRest(__VLS_20));
                        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                        /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
                        const { default: __VLS_24 } = __VLS_22.slots;
                        (act.lead_title ?? 'Lead');
                        // @ts-ignore
                        [stats, stats, stats, stats, stats, stats, stats, stats, stats, stats, stats, stats, visibleWidgets, visibleWidgets, visibleWidgets, fmtCurrency, fmtCurrency, chartOption, activityIcon,];
                        var __VLS_22;
                    }
                    if (act.content_text) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
                        (act.content_text);
                    }
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                        ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                    (__VLS_ctx.formatTime(act.created_at));
                    // @ts-ignore
                    [formatTime,];
                }
            }
            else if (widget.id === 'pipeline_chart' && !__VLS_ctx.visibleWidgets.some((w) => w.id === 'recent_activity')) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg:col-span-3 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
                });
                /** @type {__VLS_StyleScopedClasses['lg:col-span-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
                    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
                });
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
                let __VLS_25;
                /** @ts-ignore @type {typeof __VLS_components.VChart} */
                VChart;
                // @ts-ignore
                const __VLS_26 = __VLS_asFunctionalComponent1(__VLS_25, new __VLS_25({
                    option: (__VLS_ctx.chartOption),
                    ...{ style: {} },
                    autoresize: true,
                }));
                const __VLS_27 = __VLS_26({
                    option: (__VLS_ctx.chartOption),
                    ...{ style: {} },
                    autoresize: true,
                }, ...__VLS_functionalComponentArgsRest(__VLS_26));
            }
            else if (widget.id === 'recent_activity' && !__VLS_ctx.visibleWidgets.some((w) => w.id === 'pipeline_chart')) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "lg:col-span-3 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
                });
                /** @type {__VLS_StyleScopedClasses['lg:col-span-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['border']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
                    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
                });
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
                if (__VLS_ctx.stats.recent_activities.length === 0) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "text-sm text-gray-400 text-center py-8" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-8']} */ ;
                }
                __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
                    ...{ class: "space-y-3" },
                });
                /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
                for (const [act] of __VLS_vFor((__VLS_ctx.stats.recent_activities))) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                        key: (act.id),
                        ...{ class: "flex items-start gap-2.5" },
                    });
                    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                    /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
                    /** @type {__VLS_StyleScopedClasses['gap-2.5']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                        ...{ class: "text-base mt-0.5 flex-shrink-0" },
                        'aria-hidden': "true",
                    });
                    /** @type {__VLS_StyleScopedClasses['text-base']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                    (__VLS_ctx.activityIcon(act.type));
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "min-w-0" },
                    });
                    /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                        ...{ class: "text-xs text-gray-700 dark:text-gray-300 truncate" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
                    if (act.lead_id) {
                        let __VLS_30;
                        /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
                        RouterLink;
                        // @ts-ignore
                        const __VLS_31 = __VLS_asFunctionalComponent1(__VLS_30, new __VLS_30({
                            to: (`/app/leads/${act.lead_id}`),
                            ...{ class: "font-medium hover:text-red-600" },
                        }));
                        const __VLS_32 = __VLS_31({
                            to: (`/app/leads/${act.lead_id}`),
                            ...{ class: "font-medium hover:text-red-600" },
                        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
                        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                        /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
                        const { default: __VLS_35 } = __VLS_33.slots;
                        (act.lead_title ?? 'Lead');
                        // @ts-ignore
                        [stats, stats, visibleWidgets, visibleWidgets, chartOption, activityIcon,];
                        var __VLS_33;
                    }
                    if (act.content_text) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({});
                        (act.content_text);
                    }
                    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                        ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                    (__VLS_ctx.formatTime(act.created_at));
                    // @ts-ignore
                    [formatTime,];
                }
            }
        }
        else if (widget.id === 'status_breakdown') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
            });
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
                ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
            });
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex flex-wrap gap-3" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
            for (const [[status, count]] of __VLS_vFor((Object.entries(__VLS_ctx.stats.leads_by_status)))) {
                let __VLS_36;
                /** @ts-ignore @type {typeof __VLS_components.RouterLink | typeof __VLS_components.RouterLink} */
                RouterLink;
                // @ts-ignore
                const __VLS_37 = __VLS_asFunctionalComponent1(__VLS_36, new __VLS_36({
                    key: (status),
                    to: (`/app/leads?status=${status}`),
                    ...{ class: "flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors" },
                }));
                const __VLS_38 = __VLS_37({
                    key: (status),
                    to: (`/app/leads?status=${status}`),
                    ...{ class: "flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_37));
                /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-600']} */ ;
                /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
                const { default: __VLS_41 } = __VLS_39.slots;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
                    ...{ class: "w-2.5 h-2.5 rounded-full" },
                    ...{ style: ({ backgroundColor: __VLS_ctx.STATUS_COLORS[status] ?? '#6b7280' }) },
                });
                /** @type {__VLS_StyleScopedClasses['w-2.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['h-2.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "text-sm text-gray-700 dark:text-gray-300" },
                });
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                (__VLS_ctx.STATUS_LABELS[status] ?? status);
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
                });
                /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                (count);
                // @ts-ignore
                [stats, STATUS_COLORS, STATUS_LABELS,];
                var __VLS_39;
                // @ts-ignore
                [];
            }
        }
        // @ts-ignore
        [];
    }
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-center py-12 text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-12']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

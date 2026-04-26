/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, watch, onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useFirmStore } from '@/stores/firm';
import { api } from '@/api';
import DateRangePicker from '@/components/DateRangePicker.vue';
import UpgradePrompt from '@/components/UpgradePrompt.vue';
import VChart from 'vue-echarts';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, FunnelChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent, } from 'echarts/components';
use([CanvasRenderer, BarChart, LineChart, FunnelChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent]);
const firmStore = useFirmStore();
const { isPro } = storeToRefs(firmStore);
const loading = ref(false);
const velocity = ref([]);
const wonLost = ref([]);
const dateFrom = ref('');
const dateTo = ref('');
const team = ref([]);
const sortKey = ref('leads_owned');
const sortDir = ref('desc');
const trends = ref(null);
// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------
async function loadVelocity() {
    const res = await api.get('/api/v1/crm/reports/pipeline-velocity');
    if (res.ok && Array.isArray(res.data))
        velocity.value = res.data;
}
async function loadWonLost() {
    const params = new URLSearchParams();
    if (dateFrom.value)
        params.set('date_from', new Date(dateFrom.value).toISOString());
    if (dateTo.value)
        params.set('date_to', new Date(dateTo.value + 'T23:59:59').toISOString());
    const url = `/api/v1/crm/reports/won-lost-by-source${params.toString() ? '?' + params.toString() : ''}`;
    const res = await api.get(url);
    if (res.ok && Array.isArray(res.data))
        wonLost.value = res.data;
}
async function loadTeam() {
    const res = await api.get('/api/v1/crm/reports/team-performance');
    if (res.ok && Array.isArray(res.data))
        team.value = res.data;
}
async function loadTrends() {
    const res = await api.get('/api/v1/crm/reports/trends');
    if (res.ok && res.data)
        trends.value = res.data;
}
const proposalAnalytics = ref(null);
async function loadProposalAnalytics() {
    const res = await api.get('/api/v1/crm/reports/proposal-analytics');
    if (res.ok && res.data)
        proposalAnalytics.value = res.data;
}
async function loadAll() {
    if (!firmStore.activeFirm)
        return;
    loading.value = true;
    try {
        await Promise.all([loadVelocity(), loadWonLost(), loadTeam(), loadTrends(), loadProposalAnalytics()]);
    }
    finally {
        loading.value = false;
    }
}
watch([dateFrom, dateTo], () => loadWonLost());
onMounted(loadAll);
// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------
function toggleSort(key) {
    if (sortKey.value === key) {
        sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc';
    }
    else {
        sortKey.value = key;
        sortDir.value = 'desc';
    }
}
const sortedTeam = computed(() => {
    return [...team.value].sort((a, b) => {
        const av = a[sortKey.value];
        const bv = b[sortKey.value];
        if (typeof av === 'string' && typeof bv === 'string') {
            return sortDir.value === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
        }
        return sortDir.value === 'asc' ? av - bv : bv - av;
    });
});
function sortIcon(key) {
    if (sortKey.value !== key)
        return '↕';
    return sortDir.value === 'asc' ? '↑' : '↓';
}
// ---------------------------------------------------------------------------
// Chart options
// ---------------------------------------------------------------------------
const STATUS_ORDER = ['new', 'contacted', 'proposal', 'negotiation', 'won', 'lost', 'canceled'];
const STATUS_LABELS = {
    new: 'New', contacted: 'Contacted', proposal: 'Proposal',
    negotiation: 'Negotiation', won: 'Won', lost: 'Lost', canceled: 'Canceled',
};
const STATUS_COLORS = {
    new: '#6b7280', contacted: '#3b82f6', proposal: '#eab308',
    negotiation: '#f97316', won: '#22c55e', lost: '#ef4444', canceled: '#9ca3af',
};
const velocityChartOption = computed(() => {
    const sorted = [...velocity.value].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));
    const maxHours = Math.max(...sorted.map((r) => r.avg_hours), 1);
    return {
        tooltip: {
            trigger: 'item',
            formatter: (p) => `${STATUS_LABELS[p['name']] ?? p['name']}: ${Number(p['value']).toFixed(1)} h avg (${sorted.find((r) => r.status === p['name'])?.sample_count ?? 0} transitions)`,
        },
        series: [
            {
                type: 'funnel',
                sort: 'none',
                left: '5%',
                width: '90%',
                min: 0,
                max: maxHours,
                minSize: '10%',
                maxSize: '100%',
                gap: 4,
                label: {
                    show: true,
                    formatter: (p) => `${STATUS_LABELS[p['name']] ?? p['name']}: ${Number(p['value']).toFixed(1)} h`,
                },
                data: sorted.map((r) => ({
                    name: r.status,
                    value: r.avg_hours,
                    itemStyle: { color: STATUS_COLORS[r.status] ?? '#6b7280' },
                })),
            },
        ],
    };
});
const SOURCE_LABELS = {
    web: 'Web', email: 'Email', referral: 'Referral',
    cold_call: 'Cold Call', social: 'Social', other: 'Other',
};
const wonLostChartOption = computed(() => {
    const sources = wonLost.value.map((r) => SOURCE_LABELS[r.source] ?? r.source);
    return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { bottom: 0, textStyle: { fontSize: 11 } },
        grid: { left: 8, right: 8, top: 8, bottom: 32, containLabel: true },
        xAxis: { type: 'category', data: sources, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', minInterval: 1 },
        series: [
            {
                name: 'Won',
                type: 'bar',
                stack: 'total',
                data: wonLost.value.map((r) => r.won),
                itemStyle: { color: '#22c55e' },
                barMaxWidth: 48,
            },
            {
                name: 'Lost',
                type: 'bar',
                stack: 'total',
                data: wonLost.value.map((r) => r.lost),
                itemStyle: { color: '#ef4444' },
                barMaxWidth: 48,
            },
        ],
    };
});
const trendsChartOption = computed(() => {
    if (!trends.value)
        return {};
    const weeks = trends.value.weekly.map((r) => {
        const d = new Date(r.week_start);
        return `${d.getMonth() + 1}/${d.getDate()}`;
    });
    return {
        tooltip: { trigger: 'axis' },
        legend: { bottom: 0, textStyle: { fontSize: 11 } },
        grid: { left: 8, right: 8, top: 8, bottom: 32, containLabel: true },
        xAxis: { type: 'category', data: weeks, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', minInterval: 1 },
        series: [
            {
                name: 'Created',
                type: 'line',
                data: trends.value.weekly.map((r) => r.created),
                itemStyle: { color: '#3b82f6' },
                smooth: true,
            },
            {
                name: 'Closed',
                type: 'line',
                data: trends.value.weekly.map((r) => r.closed),
                itemStyle: { color: '#9ca3af' },
                smooth: true,
            },
        ],
    };
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
if (!__VLS_ctx.isPro) {
    const __VLS_0 = UpgradePrompt;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        description: "Advanced analytics are available on the Pro plan.",
    }));
    const __VLS_2 = __VLS_1({
        description: "Advanced analytics are available on the Pro plan.",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    var __VLS_5 = {};
    var __VLS_3;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "p-6 max-w-7xl mx-auto space-y-6" },
    });
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-between" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h1, __VLS_intrinsics.h1)({
        ...{ class: "text-xl font-bold text-gray-900 dark:text-gray-100" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.loadAll) },
        ...{ class: "text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors" },
        disabled: (__VLS_ctx.loading),
        'aria-label': "Refresh analytics",
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    (__VLS_ctx.loading ? 'Loading…' : '↻ Refresh');
    if (__VLS_ctx.loading && __VLS_ctx.velocity.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "animate-pulse grid grid-cols-1 lg:grid-cols-2 gap-4" },
        });
        /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['lg:grid-cols-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
        for (const [i] of __VLS_vFor((4))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
                key: (i),
                ...{ class: "h-64 bg-gray-200 dark:bg-gray-700 rounded-2xl" },
            });
            /** @type {__VLS_StyleScopedClasses['h-64']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
            // @ts-ignore
            [isPro, loadAll, loading, loading, loading, velocity,];
        }
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "grid grid-cols-1 lg:grid-cols-2 gap-4" },
        });
        /** @type {__VLS_StyleScopedClasses['grid']} */ ;
        /** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['lg:grid-cols-2']} */ ;
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
        __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
            ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500 mb-4" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        if (__VLS_ctx.velocity.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex items-center justify-center h-48 text-sm text-gray-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-48']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        }
        else {
            let __VLS_6;
            /** @ts-ignore @type {typeof __VLS_components.VChart} */
            VChart;
            // @ts-ignore
            const __VLS_7 = __VLS_asFunctionalComponent1(__VLS_6, new __VLS_6({
                option: (__VLS_ctx.velocityChartOption),
                ...{ style: {} },
                autoresize: true,
            }));
            const __VLS_8 = __VLS_7({
                option: (__VLS_ctx.velocityChartOption),
                ...{ style: {} },
                autoresize: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_7));
        }
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
            ...{ class: "flex flex-wrap items-start justify-between gap-2 mb-4" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
            ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        const __VLS_11 = DateRangePicker;
        // @ts-ignore
        const __VLS_12 = __VLS_asFunctionalComponent1(__VLS_11, new __VLS_11({
            modelValueFrom: (__VLS_ctx.dateFrom),
            modelValueTo: (__VLS_ctx.dateTo),
            label: "",
        }));
        const __VLS_13 = __VLS_12({
            modelValueFrom: (__VLS_ctx.dateFrom),
            modelValueTo: (__VLS_ctx.dateTo),
            label: "",
        }, ...__VLS_functionalComponentArgsRest(__VLS_12));
        if (__VLS_ctx.wonLost.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex items-center justify-center h-48 text-sm text-gray-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-48']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        }
        else {
            let __VLS_16;
            /** @ts-ignore @type {typeof __VLS_components.VChart} */
            VChart;
            // @ts-ignore
            const __VLS_17 = __VLS_asFunctionalComponent1(__VLS_16, new __VLS_16({
                option: (__VLS_ctx.wonLostChartOption),
                ...{ style: {} },
                autoresize: true,
            }));
            const __VLS_18 = __VLS_17({
                option: (__VLS_ctx.wonLostChartOption),
                ...{ style: {} },
                autoresize: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        }
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
            ...{ class: "flex flex-wrap items-start justify-between gap-2 mb-4" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
        __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
            ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        if (__VLS_ctx.trends) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex items-center gap-2 px-3 py-1.5 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-green-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-green-900/20']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-green-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "text-xs font-medium" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "text-sm font-bold" },
            });
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            (__VLS_ctx.trends.conversion_rate_30d.toFixed(1));
        }
        if (!__VLS_ctx.trends || __VLS_ctx.trends.weekly.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex items-center justify-center h-48 text-sm text-gray-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-48']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        }
        else {
            let __VLS_21;
            /** @ts-ignore @type {typeof __VLS_components.VChart} */
            VChart;
            // @ts-ignore
            const __VLS_22 = __VLS_asFunctionalComponent1(__VLS_21, new __VLS_21({
                option: (__VLS_ctx.trendsChartOption),
                ...{ style: {} },
                autoresize: true,
            }));
            const __VLS_23 = __VLS_22({
                option: (__VLS_ctx.trendsChartOption),
                ...{ style: {} },
                autoresize: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_22));
        }
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
        __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
            ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
        if (__VLS_ctx.team.length === 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-sm text-gray-400 text-center py-8" },
            });
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-8']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "overflow-x-auto" },
            });
            /** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
                ...{ class: "w-full text-sm" },
                role: "grid",
                'aria-label': "Team performance table",
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
            __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                ...{ class: "border-b border-gray-100 dark:border-gray-700" },
            });
            /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.isPro))
                            return;
                        if (!!(__VLS_ctx.loading && __VLS_ctx.velocity.length === 0))
                            return;
                        if (!!(__VLS_ctx.team.length === 0))
                            return;
                        __VLS_ctx.toggleSort('full_name');
                        // @ts-ignore
                        [velocity, velocityChartOption, dateFrom, dateTo, wonLost, wonLostChartOption, trends, trends, trends, trends, trendsChartOption, team, toggleSort,];
                    } },
                ...{ class: "text-left py-2 pr-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200" },
                scope: "col",
                'aria-sort': (__VLS_ctx.sortKey === 'full_name' ? (__VLS_ctx.sortDir === 'asc' ? 'ascending' : 'descending') : 'none'),
            });
            /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['pr-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
            /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-200']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                'aria-hidden': "true",
            });
            (__VLS_ctx.sortIcon('full_name'));
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.isPro))
                            return;
                        if (!!(__VLS_ctx.loading && __VLS_ctx.velocity.length === 0))
                            return;
                        if (!!(__VLS_ctx.team.length === 0))
                            return;
                        __VLS_ctx.toggleSort('leads_owned');
                        // @ts-ignore
                        [toggleSort, sortKey, sortDir, sortIcon,];
                    } },
                ...{ class: "text-right py-2 px-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200" },
                scope: "col",
                'aria-sort': (__VLS_ctx.sortKey === 'leads_owned' ? (__VLS_ctx.sortDir === 'asc' ? 'ascending' : 'descending') : 'none'),
            });
            /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
            /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-200']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                'aria-hidden': "true",
            });
            (__VLS_ctx.sortIcon('leads_owned'));
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.isPro))
                            return;
                        if (!!(__VLS_ctx.loading && __VLS_ctx.velocity.length === 0))
                            return;
                        if (!!(__VLS_ctx.team.length === 0))
                            return;
                        __VLS_ctx.toggleSort('tasks_completed');
                        // @ts-ignore
                        [toggleSort, sortKey, sortDir, sortIcon,];
                    } },
                ...{ class: "text-right py-2 px-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200" },
                scope: "col",
                'aria-sort': (__VLS_ctx.sortKey === 'tasks_completed' ? (__VLS_ctx.sortDir === 'asc' ? 'ascending' : 'descending') : 'none'),
            });
            /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
            /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-200']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                'aria-hidden': "true",
            });
            (__VLS_ctx.sortIcon('tasks_completed'));
            __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.isPro))
                            return;
                        if (!!(__VLS_ctx.loading && __VLS_ctx.velocity.length === 0))
                            return;
                        if (!!(__VLS_ctx.team.length === 0))
                            return;
                        __VLS_ctx.toggleSort('activities_logged');
                        // @ts-ignore
                        [toggleSort, sortKey, sortDir, sortIcon,];
                    } },
                ...{ class: "text-right py-2 pl-4 text-xs font-medium text-gray-500 dark:text-gray-400 cursor-pointer select-none hover:text-gray-800 dark:hover:text-gray-200" },
                scope: "col",
                'aria-sort': (__VLS_ctx.sortKey === 'activities_logged' ? (__VLS_ctx.sortDir === 'asc' ? 'ascending' : 'descending') : 'none'),
            });
            /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['pl-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
            /** @type {__VLS_StyleScopedClasses['select-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-800']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-200']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                'aria-hidden': "true",
            });
            (__VLS_ctx.sortIcon('activities_logged'));
            __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({
                ...{ class: "divide-y divide-gray-50 dark:divide-gray-700/50" },
            });
            /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
            /** @type {__VLS_StyleScopedClasses['divide-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:divide-gray-700/50']} */ ;
            for (const [row] of __VLS_vFor((__VLS_ctx.sortedTeam))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                    key: (row.user_id),
                    ...{ class: "hover:bg-gray-50 dark:hover:bg-gray-700/30 transition-colors" },
                });
                /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700/30']} */ ;
                /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-3 pr-4" },
                });
                /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['pr-4']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "font-medium text-gray-900 dark:text-gray-100 truncate max-w-[180px]" },
                });
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
                /** @type {__VLS_StyleScopedClasses['max-w-[180px]']} */ ;
                (row.full_name || row.email);
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "text-xs text-gray-400 dark:text-gray-500 truncate max-w-[180px]" },
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
                /** @type {__VLS_StyleScopedClasses['max-w-[180px]']} */ ;
                (row.email);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-3 px-4 text-right font-medium text-gray-700 dark:text-gray-300" },
                });
                /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                (row.leads_owned);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-3 px-4 text-right font-medium text-gray-700 dark:text-gray-300" },
                });
                /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                (row.tasks_completed);
                __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                    ...{ class: "py-3 pl-4 text-right font-medium text-gray-700 dark:text-gray-300" },
                });
                /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
                /** @type {__VLS_StyleScopedClasses['pl-4']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                (row.activities_logged);
                // @ts-ignore
                [sortKey, sortDir, sortIcon, sortedTeam,];
            }
        }
        if (__VLS_ctx.proposalAnalytics) {
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
            __VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
                ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-4" },
            });
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4" },
            });
            /** @type {__VLS_StyleScopedClasses['grid']} */ ;
            /** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['sm:grid-cols-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-center p-3 bg-gray-50 dark:bg-gray-700/30 rounded-xl" },
            });
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700/30']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-2xl font-bold text-gray-900 dark:text-gray-100" },
            });
            /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            (__VLS_ctx.proposalAnalytics.total);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-xl" },
            });
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-green-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-green-900/20']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-2xl font-bold text-green-700 dark:text-green-400" },
            });
            /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-green-400']} */ ;
            (__VLS_ctx.proposalAnalytics.accepted);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.proposalAnalytics.acceptance_rate);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-xl" },
            });
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-red-900/20']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-2xl font-bold text-red-700 dark:text-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-red-400']} */ ;
            (__VLS_ctx.proposalAnalytics.rejected);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            (__VLS_ctx.proposalAnalytics.rejection_rate);
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-xl" },
            });
            /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-blue-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-blue-900/20']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-2xl font-bold text-blue-700 dark:text-blue-400" },
            });
            /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-blue-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-blue-400']} */ ;
            (__VLS_ctx.proposalAnalytics.avg_time_to_open_hours != null ? __VLS_ctx.proposalAnalytics.avg_time_to_open_hours.toFixed(1) + 'h' : '—');
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "text-xs text-gray-500 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex flex-wrap gap-3" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "px-2.5 py-1 rounded-lg text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300" },
            });
            /** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
            (__VLS_ctx.proposalAnalytics.draft);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "px-2.5 py-1 rounded-lg text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400" },
            });
            /** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-blue-900/30']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-blue-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-blue-400']} */ ;
            (__VLS_ctx.proposalAnalytics.sent);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "px-2.5 py-1 rounded-lg text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400" },
            });
            /** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-yellow-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-yellow-900/30']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-yellow-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-yellow-400']} */ ;
            (__VLS_ctx.proposalAnalytics.viewed);
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "px-2.5 py-1 rounded-lg text-xs bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400" },
            });
            /** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-orange-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-orange-900/30']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-orange-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-orange-400']} */ ;
            (__VLS_ctx.proposalAnalytics.expired);
        }
    }
}
// @ts-ignore
[proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics, proposalAnalytics,];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

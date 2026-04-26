/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, computed, onMounted } from 'vue';
import FullCalendar from '@fullcalendar/vue3';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import interactionPlugin from '@fullcalendar/interaction';
import { useTasksStore } from '@/stores/tasks';
import { useLeadsStore } from '@/stores/leads';
import { api } from '@/api';
import { useToast } from '@/composables/useToast';
const tasksStore = useTasksStore();
const leadsStore = useLeadsStore();
const toast = useToast();
// New task form (triggered by clicking a date)
const showNewTaskModal = ref(false);
const newTaskTitle = ref('');
const newTaskDueDate = ref('');
const newTaskLeadId = ref('');
const taskFormLoading = ref(false);
const taskFormError = ref('');
const leadOptions = ref([]);
const events = computed(() => {
    return tasksStore.tasks
        .filter((t) => t.due_date)
        .map((t) => ({
        id: t.id,
        title: t.title,
        start: t.due_date,
        allDay: true,
        backgroundColor: t.is_completed ? '#22c55e' : (new Date(t.due_date) < new Date() ? '#ef4444' : '#3b82f6'),
        borderColor: 'transparent',
        textColor: '#fff',
        extendedProps: { task: t },
    }));
});
const calendarOptions = computed(() => ({
    plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
    initialView: 'dayGridMonth',
    headerToolbar: {
        left: 'prev,next today',
        center: 'title',
        right: 'dayGridMonth,timeGridWeek,listWeek',
    },
    events: events.value,
    selectable: true,
    select: handleDateSelect,
    eventClick: handleEventClick,
    height: 'auto',
}));
function handleDateSelect(info) {
    newTaskDueDate.value = info.startStr;
    newTaskTitle.value = '';
    newTaskLeadId.value = '';
    taskFormError.value = '';
    showNewTaskModal.value = true;
}
function handleEventClick(info) {
    const task = info.event.extendedProps['task'];
    if (task && !task.is_completed) {
        tasksStore.completeTask(info.event.id).then((r) => {
            if (!r.ok)
                toast.error(r.error ?? 'Failed to complete task.');
            else
                toast.success('Task marked complete!');
        });
    }
}
async function submitNewTask() {
    if (!newTaskTitle.value.trim()) {
        taskFormError.value = 'Title is required.';
        return;
    }
    if (!newTaskLeadId.value) {
        taskFormError.value = 'Please select a lead.';
        return;
    }
    taskFormLoading.value = true;
    taskFormError.value = '';
    const result = await tasksStore.createTask({
        lead_id: newTaskLeadId.value,
        title: newTaskTitle.value.trim(),
        due_date: newTaskDueDate.value ? new Date(newTaskDueDate.value).toISOString() : null,
    });
    taskFormLoading.value = false;
    if (result.ok) {
        showNewTaskModal.value = false;
        toast.success('Task created.');
    }
    else {
        taskFormError.value = result.error ?? 'Failed to create task.';
    }
}
const overdueCount = computed(() => tasksStore.tasks.filter((t) => !t.is_completed && t.due_date && new Date(t.due_date) < new Date()).length);
const upcomingTasks = computed(() => {
    const now = new Date();
    const next7 = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    return tasksStore.tasks.filter((t) => !t.is_completed && t.due_date && new Date(t.due_date) >= now && new Date(t.due_date) <= next7);
});
onMounted(async () => {
    await tasksStore.fetchTasks({ completed: false });
    // Load leads for the task creation form
    const res = await api.get('/api/v1/crm/leads?page_size=100');
    if (res.ok)
        leadOptions.value = res.data;
});
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "p-6 max-w-7xl mx-auto" },
});
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "grid grid-cols-2 lg:grid-cols-3 gap-4 mb-5" },
});
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-2xl font-bold" },
    ...{ class: (__VLS_ctx.overdueCount > 0 ? 'text-red-600' : 'text-gray-400 dark:text-gray-500') },
});
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
(__VLS_ctx.overdueCount);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-2xl font-bold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
(__VLS_ctx.upcomingTasks.length);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4 col-span-2 lg:col-span-1" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['col-span-2']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:col-span-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-2xl font-bold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
(__VLS_ctx.tasksStore.tasks.filter(t => !t.is_completed).length);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
if (__VLS_ctx.tasksStore.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
        ...{ class: "animate-pulse h-64 bg-gray-100 dark:bg-gray-700 rounded-xl" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-64']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
}
else {
    let __VLS_0;
    /** @ts-ignore @type {typeof __VLS_components.FullCalendar} */
    FullCalendar;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent1(__VLS_0, new __VLS_0({
        options: (__VLS_ctx.calendarOptions),
    }));
    const __VLS_2 = __VLS_1({
        options: (__VLS_ctx.calendarOptions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
if (__VLS_ctx.upcomingTasks.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mt-4 bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-2" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    for (const [task] of __VLS_vFor((__VLS_ctx.upcomingTasks))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (task.id),
            ...{ class: "flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700/50" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700/50']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.upcomingTasks.length > 0))
                        return;
                    __VLS_ctx.tasksStore.completeTask(task.id);
                    // @ts-ignore
                    [overdueCount, overdueCount, upcomingTasks, upcomingTasks, upcomingTasks, tasksStore, tasksStore, tasksStore, calendarOptions,];
                } },
            ...{ class: "w-5 h-5 rounded border border-gray-300 dark:border-gray-600 hover:border-green-400 flex-shrink-0 flex items-center justify-center" },
            'aria-label': (`Complete task: ${task.title}`),
        });
        /** @type {__VLS_StyleScopedClasses['w-5']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:border-green-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-xs text-transparent hover:text-green-500" },
            'aria-hidden': "true",
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-transparent']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-green-500']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-sm text-gray-800 dark:text-gray-200 flex-1" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        (task.title);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        (task.due_date ? new Date(task.due_date).toLocaleDateString() : '');
        // @ts-ignore
        [];
    }
}
let __VLS_5;
/** @ts-ignore @type {typeof __VLS_components.Teleport | typeof __VLS_components.Teleport} */
Teleport;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent1(__VLS_5, new __VLS_5({
    to: "body",
}));
const __VLS_7 = __VLS_6({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
const { default: __VLS_10 } = __VLS_8.slots;
if (__VLS_ctx.showNewTaskModal) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showNewTaskModal))
                    return;
                __VLS_ctx.showNewTaskModal = false;
                // @ts-ignore
                [showNewTaskModal, showNewTaskModal,];
            } },
        ...{ class: "fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" },
    });
    /** @type {__VLS_StyleScopedClasses['fixed']} */ ;
    /** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
    /** @type {__VLS_StyleScopedClasses['z-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-black/40']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "bg-white dark:bg-gray-800 rounded-2xl shadow-xl w-full max-w-sm p-6" },
        role: "dialog",
        'aria-modal': "true",
        'aria-labelledby': "new-task-title",
    });
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['max-w-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-6']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
        id: "new-task-title",
        ...{ class: "text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4" },
    });
    /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    if (__VLS_ctx.taskFormError) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "mb-3 rounded-xl bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 px-4 py-2 text-sm text-red-700 dark:text-red-400" },
            role: "alert",
        });
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-red-900/30']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-red-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-red-400']} */ ;
        (__VLS_ctx.taskFormError);
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
        ...{ onSubmit: (__VLS_ctx.submitNewTask) },
        ...{ class: "space-y-3" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        value: (__VLS_ctx.newTaskTitle),
        type: "text",
        required: true,
        autofocus: true,
        ...{ class: "w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
        value: (__VLS_ctx.newTaskLeadId),
        ...{ class: "w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        value: "",
    });
    for (const [l] of __VLS_vFor((__VLS_ctx.leadOptions))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (l.id),
            value: (l.id),
        });
        (l.title);
        // @ts-ignore
        [taskFormError, taskFormError, submitNewTask, newTaskTitle, newTaskLeadId, leadOptions,];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "date",
        ...{ class: "w-full rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    });
    (__VLS_ctx.newTaskDueDate);
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-3 pt-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.showNewTaskModal))
                    return;
                __VLS_ctx.showNewTaskModal = false;
                // @ts-ignore
                [showNewTaskModal, newTaskDueDate,];
            } },
        type: "button",
        ...{ class: "flex-1 rounded-xl border border-gray-200 dark:border-gray-600 py-2 text-sm text-gray-600 dark:text-gray-300" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        type: "submit",
        disabled: (__VLS_ctx.taskFormLoading),
        ...{ class: "flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-60" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
    (__VLS_ctx.taskFormLoading ? 'Creating…' : 'Create');
}
// @ts-ignore
[taskFormLoading, taskFormLoading,];
var __VLS_8;
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from '@/api';
import { extractErrorMessage } from '@/api/errors';
export const useTasksStore = defineStore('tasks', () => {
    const tasks = ref([]);
    const loading = ref(false);
    async function fetchTasks(opts = {}) {
        loading.value = true;
        try {
            const params = new URLSearchParams();
            if (opts.completed !== undefined)
                params.set('completed', String(opts.completed));
            params.set('page', String(opts.page ?? 1));
            params.set('page_size', String(opts.page_size ?? 100));
            const res = await api.get(`/api/v1/crm/tasks?${params}`);
            if (res.ok) {
                tasks.value = res.data;
                return { ok: true };
            }
            return { ok: false, error: extractErrorMessage(res.data, 'Failed to load tasks.') };
        }
        finally {
            loading.value = false;
        }
    }
    async function createTask(payload) {
        const res = await api.post('/api/v1/crm/tasks', payload);
        if (res.ok) {
            tasks.value.push(res.data);
            return { ok: true, data: res.data };
        }
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to create task.') };
    }
    async function completeTask(id) {
        const res = await api.post(`/api/v1/crm/tasks/${id}/complete`);
        if (res.ok) {
            const idx = tasks.value.findIndex((t) => t.id === id);
            if (idx !== -1)
                tasks.value[idx] = res.data;
            return { ok: true };
        }
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to complete task.') };
    }
    return { tasks, loading, fetchTasks, createTask, completeTask };
});

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
    async function fetchTasksForView(opts = {}) {
        loading.value = true;
        try {
            const params = new URLSearchParams();
            if (opts.assignedToId !== undefined)
                params.set('assigned_to_id', opts.assignedToId);
            if (opts.completed !== undefined)
                params.set('completed', String(opts.completed));
            params.set('page', String(opts.page ?? 1));
            params.set('page_size', String(opts.page_size ?? 100));
            const res = await api.get(`/api/v1/crm/tasks?${params}`);
            if (res.ok) {
                tasks.value = res.data;
                return { ok: true, data: res.data };
            }
            return { ok: false, error: extractErrorMessage(res.data, 'Failed to load tasks.') };
        }
        finally {
            loading.value = false;
        }
    }
    async function fetchTask(id) {
        const res = await api.get(`/api/v1/crm/tasks/${id}`);
        if (res.ok) return { ok: true, data: res.data };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to load task.') };
    }
    async function createTask(payload) {
        const res = await api.post('/api/v1/crm/tasks', payload);
        if (res.ok) {
            tasks.value.push(res.data);
            return { ok: true, data: res.data };
        }
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to create task.') };
    }
    async function updateTask(id, payload) {
        const res = await api.patch(`/api/v1/crm/tasks/${id}`, payload);
        if (res.ok) {
            const idx = tasks.value.findIndex((t) => t.id === id);
            if (idx !== -1)
                tasks.value[idx] = res.data;
            return { ok: true, data: res.data };
        }
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to update task.') };
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
    async function completeTaskWithFollowUp(id, followUp) {
        const body = {};
        if (followUp) body.follow_up = followUp;
        const res = await api.post(`/api/v1/crm/tasks/${id}/complete`, body);
        if (res.ok) {
            const idx = tasks.value.findIndex((t) => t.id === id);
            if (idx !== -1)
                tasks.value[idx] = res.data;
            return { ok: true };
        }
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to complete task.') };
    }
    async function fetchTaskComments(taskId) {
        const res = await api.get(`/api/v1/crm/tasks/${taskId}/comments`);
        if (res.ok) return { ok: true, data: res.data };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to load comments.') };
    }
    async function createTaskComment(taskId, contentHtml) {
        const res = await api.post(`/api/v1/crm/tasks/${taskId}/comments`, { content_html: contentHtml });
        if (res.ok) return { ok: true, data: res.data };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to post comment.') };
    }
    async function updateTaskComment(taskId, commentId, contentHtml) {
        const res = await api.patch(`/api/v1/crm/tasks/${taskId}/comments/${commentId}`, { content_html: contentHtml });
        if (res.ok) return { ok: true, data: res.data };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to update comment.') };
    }
    async function deleteTaskComment(taskId, commentId) {
        const res = await api.delete(`/api/v1/crm/tasks/${taskId}/comments/${commentId}`);
        if (res.ok) return { ok: true };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete comment.') };
    }
    async function fetchTaskAttachments(taskId) {
        const res = await api.get(`/api/v1/crm/tasks/${taskId}/attachments`);
        if (res.ok) return { ok: true, data: res.data };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to load attachments.') };
    }
    async function uploadTaskAttachment(taskId, file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await api.postForm(`/api/v1/crm/tasks/${taskId}/attachments`, formData);
        if (res.ok) return { ok: true, data: res.data };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to upload file.') };
    }
    async function deleteTaskAttachment(taskId, attachmentId) {
        const res = await api.delete(`/api/v1/crm/tasks/${taskId}/attachments/${attachmentId}`);
        if (res.ok) return { ok: true };
        return { ok: false, error: extractErrorMessage(res.data, 'Failed to delete attachment.') };
    }
    return {
        tasks,
        loading,
        fetchTasks,
        fetchTasksForView,
        fetchTask,
        createTask,
        updateTask,
        completeTask,
        completeTaskWithFollowUp,
        fetchTaskComments,
        createTaskComment,
        updateTaskComment,
        deleteTaskComment,
        fetchTaskAttachments,
        uploadTaskAttachment,
        deleteTaskAttachment,
    };
});

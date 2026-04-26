import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from '@/api';
import { useFirmStore } from '@/stores/firm';
export const useSavedViewsStore = defineStore('savedViews', () => {
    const views = ref([]);
    const loading = ref(false);
    async function fetchViews() {
        const firmStore = useFirmStore();
        if (!firmStore.activeFirm)
            return;
        loading.value = true;
        try {
            const res = await api.get('/api/v1/crm/saved-views');
            if (res.ok)
                views.value = res.data;
        }
        finally {
            loading.value = false;
        }
    }
    async function createView(payload) {
        const res = await api.post('/api/v1/crm/saved-views', payload);
        if (res.ok) {
            views.value.push(res.data);
            return res.data;
        }
        return null;
    }
    async function deleteView(id) {
        const res = await api.delete(`/api/v1/crm/saved-views/${id}`);
        if (res.ok) {
            views.value = views.value.filter((v) => v.id !== id);
            return true;
        }
        return false;
    }
    function viewsForEntity(entity) {
        return views.value.filter((v) => v.entity === entity);
    }
    return { views, loading, fetchViews, createView, deleteView, viewsForEntity };
});

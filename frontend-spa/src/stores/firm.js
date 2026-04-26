import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { api } from '@/api';
import { extractErrorMessage } from '@/api/errors';
const FIRM_ID_KEY = 'firmId';
export const useFirmStore = defineStore('firm', () => {
    const firms = ref([]);
    const activeFirm = ref(null);
    const loading = ref(false);
    async function fetchFirms() {
        loading.value = true;
        try {
            const res = await api.get('/api/v1/firms/');
            if (res.ok) {
                firms.value = res.data;
                const persistedId = localStorage.getItem(FIRM_ID_KEY);
                const first = firms.value[0] ?? null;
                if (persistedId) {
                    const found = firms.value.find((f) => String(f.id) === persistedId);
                    if (found) {
                        activeFirm.value = found;
                    }
                    else if (first) {
                        activeFirm.value = first;
                        localStorage.setItem(FIRM_ID_KEY, String(first.id));
                    }
                }
                else if (first) {
                    activeFirm.value = first;
                    localStorage.setItem(FIRM_ID_KEY, String(first.id));
                }
            }
        }
        finally {
            loading.value = false;
        }
    }
    function setActiveFirm(firmId) {
        const found = firms.value.find((f) => String(f.id) === firmId);
        if (found) {
            activeFirm.value = found;
            localStorage.setItem(FIRM_ID_KEY, firmId);
        }
    }
    async function createFirm(name) {
        loading.value = true;
        try {
            const res = await api.post('/api/v1/firms/', { name });
            if (res.ok) {
                firms.value.push(res.data);
                activeFirm.value = res.data;
                localStorage.setItem(FIRM_ID_KEY, String(res.data.id));
                return { ok: true };
            }
            return { ok: false, error: extractErrorMessage(res.data, 'Failed to create workspace.') };
        }
        finally {
            loading.value = false;
        }
    }
    const isPro = computed(() => activeFirm.value?.subscription_tier === 'pro' &&
        activeFirm.value?.subscription_active === true);
    return { firms, activeFirm, loading, fetchFirms, setActiveFirm, createFirm, isPro };
});

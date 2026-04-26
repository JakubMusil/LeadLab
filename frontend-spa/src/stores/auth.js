import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from '@/api';
import { extractErrorMessage } from '@/api/errors';
import router from '@/router';
export const useAuthStore = defineStore('auth', () => {
    const user = ref(null);
    const loading = ref(false);
    const initialized = ref(false);
    async function fetchMe() {
        const res = await api.get('/api/v1/users/me');
        if (res.ok) {
            user.value = res.data;
        }
        else {
            user.value = null;
        }
    }
    async function init() {
        if (initialized.value)
            return;
        initialized.value = true;
        await fetchMe();
    }
    async function login(email, password) {
        loading.value = true;
        try {
            const res = await api.post('/api/v1/users/login', { email, password });
            if (res.ok) {
                user.value = res.data;
                return { ok: true };
            }
            return { ok: false, error: extractErrorMessage(res.data, 'Invalid credentials. Please try again.') };
        }
        finally {
            loading.value = false;
        }
    }
    async function register(email, password, firstName, lastName) {
        loading.value = true;
        try {
            const res = await api.post('/api/v1/users/register', {
                email,
                password,
                first_name: firstName,
                last_name: lastName,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            });
            if (res.ok) {
                // Login explicitly after successful registration
                const loginRes = await api.post('/api/v1/users/login', { email, password });
                if (loginRes.ok) {
                    user.value = loginRes.data;
                }
                return { ok: true };
            }
            return { ok: false, error: extractErrorMessage(res.data, 'Registration failed. Please try again.') };
        }
        finally {
            loading.value = false;
        }
    }
    async function logout() {
        await api.post('/api/v1/users/logout');
        user.value = null;
        await router.push('/app/login');
    }
    return { user, loading, initialized, fetchMe, init, login, register, logout };
});

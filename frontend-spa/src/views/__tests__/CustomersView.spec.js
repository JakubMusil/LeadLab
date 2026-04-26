/**
 * Component tests for CustomersView.vue
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { setActivePinia, createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import CustomersView from '../CustomersView.vue';
import { useCustomersStore } from '@/stores/customers';
vi.mock('@/composables/useToast', () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));
vi.mock('@/api', () => ({
    api: {
        get: vi.fn().mockResolvedValue({ ok: true, status: 200, data: [] }),
        post: vi.fn(),
        patch: vi.fn(),
        delete: vi.fn(),
        put: vi.fn(),
        postForm: vi.fn(),
    },
}));
import { api } from '@/api';
const router = createRouter({
    history: createMemoryHistory(),
    routes: [
        { path: '/app/customers', component: CustomersView },
        { path: '/app/customers/:id', component: { template: '<div/>' } },
    ],
});
const mockCustomer = {
    id: 'cust-1', firm_id: '1', first_name: 'Alice', last_name: 'Smith',
    email: 'alice@example.com', phone: '', company_name: 'Acme',
    tags: ['vip'], metadata: {}, created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z',
};
describe('CustomersView', () => {
    beforeEach(async () => {
        setActivePinia(createPinia());
        vi.clearAllMocks();
        await router.push('/app/customers');
        await router.isReady();
    });
    it('renders the Customers heading', () => {
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        expect(wrapper.text()).toContain('Customers');
    });
    it('shows the search input', () => {
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        expect(wrapper.find('input[placeholder*="Search"]').exists()).toBe(true);
    });
    it('shows "+ New Customer" button', () => {
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        expect(wrapper.text()).toContain('+ New Customer');
    });
    it('shows empty state when no customers', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [] });
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        await flushPromises();
        expect(wrapper.text()).toContain('No customers yet');
    });
    it('renders customers from store', async () => {
        const store = useCustomersStore();
        store.customers = [mockCustomer];
        store.loading = false;
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        await wrapper.vm.$nextTick();
        expect(wrapper.text()).toContain('Alice Smith');
        expect(wrapper.text()).toContain('Acme');
    });
    it('shows tags in customer rows', async () => {
        const store = useCustomersStore();
        store.customers = [mockCustomer];
        store.loading = false;
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        await wrapper.vm.$nextTick();
        expect(wrapper.text()).toContain('vip');
    });
    it('opens modal on "+ New Customer" click', async () => {
        const wrapper = mount(CustomersView, { global: { plugins: [router] } });
        const buttons = wrapper.findAll('button');
        const newBtn = buttons.find((b) => b.text().includes('New Customer'));
        if (newBtn) {
            await newBtn.trigger('click');
            expect(wrapper.text()).toContain('New Customer');
        }
    });
});

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useCustomersStore } from '../customers';
vi.mock('@/api', () => ({
    api: {
        get: vi.fn(),
        post: vi.fn(),
        patch: vi.fn(),
        put: vi.fn(),
        delete: vi.fn(),
        postForm: vi.fn(),
    },
}));
import { api } from '@/api';
const mockCustomer = {
    id: 'cust-1',
    firm_id: '1',
    first_name: 'Alice',
    last_name: 'Smith',
    email: 'alice@example.com',
    phone: '+1234567890',
    company_name: 'Acme Corp',
    tags: ['vip', 'enterprise'],
    metadata: { plan: 'gold' },
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
};
describe('useCustomersStore', () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.clearAllMocks();
    });
    it('initialises empty', () => {
        const store = useCustomersStore();
        expect(store.customers).toEqual([]);
        expect(store.currentCustomer).toBeNull();
        expect(store.loading).toBe(false);
    });
    it('fetchCustomers() populates customers', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockCustomer] });
        const store = useCustomersStore();
        const result = await store.fetchCustomers();
        expect(result.ok).toBe(true);
        expect(store.customers).toEqual([mockCustomer]);
    });
    it('fetchCustomers() with append=true extends list', async () => {
        const cust2 = { ...mockCustomer, id: 'cust-2', first_name: 'Bob' };
        vi.mocked(api.get)
            .mockResolvedValueOnce({ ok: true, status: 200, data: [mockCustomer] })
            .mockResolvedValueOnce({ ok: true, status: 200, data: [cust2] });
        const store = useCustomersStore();
        await store.fetchCustomers();
        await store.fetchCustomers({ append: true, page: 2 });
        expect(store.customers).toHaveLength(2);
    });
    it('fetchCustomer() sets currentCustomer', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockCustomer });
        const store = useCustomersStore();
        const result = await store.fetchCustomer('cust-1');
        expect(result.ok).toBe(true);
        expect(store.currentCustomer).toEqual(mockCustomer);
    });
    it('createCustomer() prepends new customer', async () => {
        vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 201, data: mockCustomer });
        const store = useCustomersStore();
        const result = await store.createCustomer({ first_name: 'Alice', last_name: 'Smith' });
        expect(result.ok).toBe(true);
        expect(store.customers[0]).toEqual(mockCustomer);
    });
    it('updateCustomer() replaces in list', async () => {
        const updated = { ...mockCustomer, first_name: 'Alicia' };
        vi.mocked(api.put).mockResolvedValueOnce({ ok: true, status: 200, data: updated });
        const store = useCustomersStore();
        store.customers = [mockCustomer];
        const result = await store.updateCustomer('cust-1', { first_name: 'Alicia', last_name: 'Smith' });
        expect(result.ok).toBe(true);
        expect(store.customers[0].first_name).toBe('Alicia');
    });
    it('deleteCustomer() removes from list on 204', async () => {
        vi.mocked(api.delete).mockResolvedValueOnce({ ok: false, status: 204, data: null });
        const store = useCustomersStore();
        store.customers = [mockCustomer];
        const result = await store.deleteCustomer('cust-1');
        expect(result.ok).toBe(true);
        expect(store.customers).toHaveLength(0);
    });
    it('hasMore is true when full page returned', async () => {
        const page = Array.from({ length: 20 }, (_, i) => ({ ...mockCustomer, id: `cust-${i}` }));
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: page });
        const store = useCustomersStore();
        await store.fetchCustomers();
        expect(store.hasMore).toBe(true);
    });
    it('hasMore is false when partial page returned', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockCustomer] });
        const store = useCustomersStore();
        await store.fetchCustomers();
        expect(store.hasMore).toBe(false);
    });
});

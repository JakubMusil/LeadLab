import { describe, it, expect, beforeEach, vi } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useFirmStore } from '../firm';
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
const FIRM_ID_KEY = 'firmId';
const mockFirm = { id: '1', name: 'Test Firm', slug: 'test-firm', subscription_tier: 'free', subscription_active: true, is_active: true };
const mockFirm2 = { id: '2', name: 'Second Firm', slug: 'second-firm', subscription_tier: 'pro', subscription_active: true, is_active: true };
describe('useFirmStore', () => {
    beforeEach(() => {
        setActivePinia(createPinia());
        vi.clearAllMocks();
        localStorage.clear();
    });
    it('initialises empty', () => {
        const store = useFirmStore();
        expect(store.firms).toEqual([]);
        expect(store.activeFirm).toBeNull();
        expect(store.loading).toBe(false);
    });
    it('fetchFirms() populates firms and sets activeFirm', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockFirm] });
        const store = useFirmStore();
        await store.fetchFirms();
        expect(store.firms).toHaveLength(1);
        expect(store.activeFirm).toEqual(mockFirm);
        expect(localStorage.getItem(FIRM_ID_KEY)).toBe('1');
    });
    it('fetchFirms() restores persisted firmId from localStorage', async () => {
        localStorage.setItem(FIRM_ID_KEY, '2');
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockFirm, mockFirm2] });
        const store = useFirmStore();
        await store.fetchFirms();
        expect(store.activeFirm?.id).toBe('2');
    });
    it('fetchFirms() falls back to first firm if persisted id not found', async () => {
        localStorage.setItem(FIRM_ID_KEY, '999');
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockFirm] });
        const store = useFirmStore();
        await store.fetchFirms();
        expect(store.activeFirm?.id).toBe('1');
    });
    it('setActiveFirm() switches active firm and persists', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockFirm, mockFirm2] });
        const store = useFirmStore();
        await store.fetchFirms();
        store.setActiveFirm('2');
        expect(store.activeFirm?.id).toBe('2');
        expect(localStorage.getItem(FIRM_ID_KEY)).toBe('2');
    });
    it('setActiveFirm() with unknown id does nothing', async () => {
        vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockFirm] });
        const store = useFirmStore();
        await store.fetchFirms();
        store.setActiveFirm('999');
        expect(store.activeFirm?.id).toBe('1');
    });
    it('createFirm() adds new firm and sets as active', async () => {
        const newFirm = { id: '3', name: 'New Firm', slug: 'new-firm', subscription_tier: 'free', subscription_active: true, is_active: true };
        vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 201, data: newFirm });
        const store = useFirmStore();
        const result = await store.createFirm('New Firm');
        expect(result.ok).toBe(true);
        expect(store.firms).toContainEqual(newFirm);
        expect(store.activeFirm).toEqual(newFirm);
    });
    it('createFirm() returns error on failure', async () => {
        vi.mocked(api.post).mockResolvedValueOnce({ ok: false, status: 400, data: { detail: 'Firm name taken.' } });
        const store = useFirmStore();
        const result = await store.createFirm('Bad Firm');
        expect(result.ok).toBe(false);
        expect(result.error).toBe('Firm name taken.');
    });
});

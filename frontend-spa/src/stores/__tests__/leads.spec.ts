import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useLeadsStore } from '../leads'

vi.mock('@/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    postForm: vi.fn(),
  },
}))

// Mock firm store
vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({ activeFirm: { id: '1', name: 'Test' } }),
}))

import { api } from '@/api'

const mockLead = {
  id: 'lead-1',
  firm_id: '1',
  customer_id: null,
  title: 'Deal with Acme',
  description: '',
  status: 'new',
  source: 'web',
  assigned_to_id: null,
  value: 5000,
  currency: 'CZK',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('useLeadsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('initialises empty', () => {
    const store = useLeadsStore()
    expect(store.leads).toEqual([])
    expect(store.currentLead).toBeNull()
    expect(store.loading).toBe(false)
  })

  it('fetchLeads() populates leads', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: [mockLead] })

    const store = useLeadsStore()
    const result = await store.fetchLeads()

    expect(result.ok).toBe(true)
    expect(store.leads).toEqual([mockLead])
  })

  it('fetchLeads() with page > 1 appends to existing list', async () => {
    const lead2 = { ...mockLead, id: 'lead-2' }
    vi.mocked(api.get)
      .mockResolvedValueOnce({ ok: true, status: 200, data: [mockLead] })
      .mockResolvedValueOnce({ ok: true, status: 200, data: [lead2] })

    const store = useLeadsStore()
    await store.fetchLeads({ page: 1 })
    await store.fetchLeads({ page: 2 })

    expect(store.leads).toHaveLength(2)
  })

  it('fetchLead() sets currentLead', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: true, status: 200, data: mockLead })

    const store = useLeadsStore()
    const result = await store.fetchLead('lead-1')

    expect(result.ok).toBe(true)
    expect(store.currentLead).toEqual(mockLead)
  })

  it('fetchLead() returns error on 404', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ ok: false, status: 404, data: { detail: 'Lead not found.' } })

    const store = useLeadsStore()
    const result = await store.fetchLead('nonexistent')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Lead not found.')
    expect(store.currentLead).toBeNull()
  })

  it('createLead() prepends new lead', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({ ok: true, status: 201, data: mockLead })

    const store = useLeadsStore()
    const result = await store.createLead({ title: 'Deal with Acme' })

    expect(result.ok).toBe(true)
    expect(store.leads[0]).toEqual(mockLead)
  })

  it('updateLead() replaces lead in list', async () => {
    const updatedLead = { ...mockLead, title: 'Updated Deal' }
    vi.mocked(api.patch).mockResolvedValueOnce({ ok: true, status: 200, data: updatedLead })

    const store = useLeadsStore()
    store.leads = [mockLead]
    const result = await store.updateLead('lead-1', { title: 'Updated Deal' })

    expect(result.ok).toBe(true)
    expect((store.leads[0] as typeof store.leads[0]).title).toBe('Updated Deal')
  })

  it('patchStatus() does optimistic update and rolls back on error', async () => {
    vi.mocked(api.patch).mockResolvedValueOnce({ ok: false, status: 403, data: { detail: 'Forbidden' } })

    const store = useLeadsStore()
    store.leads = [mockLead]

    await store.patchStatus('lead-1', 'won')

    // Should have rolled back to original status
    const lead = store.leads[0]
    expect(lead).toBeDefined()
    expect(lead!.status).toBe('new')
  })

  it('patchStatus() keeps new status on success', async () => {
    const wonLead = { ...mockLead, status: 'won' }
    vi.mocked(api.patch).mockResolvedValueOnce({ ok: true, status: 200, data: wonLead })

    const store = useLeadsStore()
    store.leads = [mockLead]

    const result = await store.patchStatus('lead-1', 'won')

    expect(result.ok).toBe(true)
    expect(store.leads[0]!.status).toBe('won')
  })

  it('deleteLead() removes from list on 204', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({ ok: false, status: 204, data: null })

    const store = useLeadsStore()
    store.leads = [mockLead]
    const result = await store.deleteLead('lead-1')

    expect(result.ok).toBe(true)
    expect(store.leads).toHaveLength(0)
  })

  it('deleteLead() returns error on failure', async () => {
    vi.mocked(api.delete).mockResolvedValueOnce({ ok: false, status: 403, data: { detail: 'Forbidden' } })

    const store = useLeadsStore()
    store.leads = [mockLead]
    const result = await store.deleteLead('lead-1')

    expect(result.ok).toBe(false)
    expect(store.leads).toHaveLength(1)
  })
})

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import FileUploadComposer from '../FileUploadComposer.vue'

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }),
}))

vi.mock('@/stores/firm', () => ({
  useFirmStore: () => ({
    activeFirm: { id: '1', subscription_tier: 'free' },
  }),
}))

const fetchMock = vi.fn()

beforeEach(() => {
  setActivePinia(createPinia())
  fetchMock.mockReset()
  // @ts-expect-error — JSDOM does not provide fetch by default.
  global.fetch = fetchMock
})

function _mount() {
  return mount(FileUploadComposer, {
    props: { uploadUrl: '/api/v1/crm/file-uploads/upload?lead_id=L1' },
  })
}

describe('FileUploadComposer', () => {
  it('defaults to upload mode and disables Save until a file + title are provided', async () => {
    const wrapper = _mount()
    expect(wrapper.attributes('data-source-kind')).toBe('upload')
    const submit = wrapper.find('[data-testid="file-upload-submit"]')
    expect(submit.attributes('disabled')).toBeDefined()

    await wrapper.find('[data-testid="file-upload-title"]').setValue('Q4 brief')
    expect(submit.attributes('disabled')).toBeDefined()

    // Simulate a file being selected (we bypass the click → input
    // round-trip by dispatching a `change` event on the hidden input).
    const input = wrapper.find<HTMLInputElement>('[data-testid="file-upload-input"]')
    const file = new File(['hello'], 'a.pdf', { type: 'application/pdf' })
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')

    const items = wrapper.findAll('[data-testid="file-upload-selected-item"]')
    expect(items).toHaveLength(1)
    expect(items[0].text()).toContain('a.pdf')
    expect(submit.attributes('disabled')).toBeUndefined()
  })

  it('uploads selected files and emits one submit event per returned entry', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        files: [
          { url: '/m/a.pdf', filename: 'a.pdf', content_type: 'application/pdf', size_bytes: 5, document_id: 'D1' },
          { url: '/m/b.png', filename: 'b.png', content_type: 'image/png', size_bytes: 7, document_id: 'D2' },
        ],
      }),
    })

    const wrapper = _mount()
    await wrapper.find('[data-testid="file-upload-title"]').setValue('Batch')
    const input = wrapper.find<HTMLInputElement>('[data-testid="file-upload-input"]')
    const f1 = new File(['hello'], 'a.pdf', { type: 'application/pdf' })
    const f2 = new File(['world1!'], 'b.png', { type: 'image/png' })
    Object.defineProperty(input.element, 'files', { value: [f1, f2], configurable: true })
    await input.trigger('change')
    await wrapper.find('[data-testid="file-upload-submit"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledOnce()
    const submits = wrapper.emitted('submit') ?? []
    expect(submits).toHaveLength(2)
    const [firstPayload] = submits[0] as [unknown]
    expect(firstPayload).toMatchObject({
      title: 'Batch',
      url: '/m/a.pdf',
      filename: 'a.pdf',
      mime_type: 'application/pdf',
      source_kind: 'upload',
    })
  })

  it('skips files that exceed the per-plan size cap (15 MB on free plan)', async () => {
    const wrapper = _mount()
    const input = wrapper.find<HTMLInputElement>('[data-testid="file-upload-input"]')
    const huge = new File([new Uint8Array(16 * 1024 * 1024)], 'huge.bin', { type: 'application/octet-stream' })
    Object.defineProperty(input.element, 'files', { value: [huge], configurable: true })
    await input.trigger('change')
    expect(wrapper.findAll('[data-testid="file-upload-selected-item"]')).toHaveLength(0)
  })

  it('switches to URL mode and emits a single payload without uploading', async () => {
    const wrapper = _mount()
    await wrapper.find('[data-testid="file-upload-source-url"]').trigger('click')
    expect(wrapper.attributes('data-source-kind')).toBe('url')

    await wrapper.find('[data-testid="file-upload-title"]').setValue('Doc link')
    await wrapper.find('[data-testid="file-upload-url"]').setValue('https://example.org/x.pdf')
    await wrapper.find('[data-testid="file-upload-submit"]').trigger('click')
    await flushPromises()

    expect(fetchMock).not.toHaveBeenCalled()
    const submits = wrapper.emitted('submit') ?? []
    expect(submits).toHaveLength(1)
    expect(submits[0][0]).toMatchObject({
      source_kind: 'url',
      url: 'https://example.org/x.pdf',
      store_locally: true,
    })
  })

  it('respects the unchecked "Store locally" toggle for URL mode', async () => {
    const wrapper = _mount()
    await wrapper.find('[data-testid="file-upload-source-url"]').trigger('click')
    await wrapper.find('[data-testid="file-upload-title"]').setValue('External')
    await wrapper.find('[data-testid="file-upload-url"]').setValue('https://example.org/y.pdf')
    const checkbox = wrapper.find('[data-testid="file-upload-store-locally"] input[type="checkbox"]')
    await checkbox.setValue(false)
    await wrapper.find('[data-testid="file-upload-submit"]').trigger('click')
    await flushPromises()
    const payload = (wrapper.emitted('submit') ?? [])[0][0] as { store_locally: boolean }
    expect(payload.store_locally).toBe(false)
  })
})

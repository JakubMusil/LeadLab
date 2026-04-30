import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import EntitySidebarActionPicker from '../EntitySidebarActionPicker.vue'

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

// RichTextEditor is heavyweight and renders a tiptap editor we don't need
// here — replace it with a lightweight stub that exposes the same v-model
// surface and the `getMentionedIds` method the picker calls on submit.
vi.mock('@/components/RichTextEditor.vue', () => ({
  default: {
    name: 'RichTextEditorStub',
    props: ['modelValue', 'placeholder', 'disabled', 'members', 'uploadUrl'],
    emits: ['update:modelValue', 'file-uploaded'],
    template: '<textarea data-testid="stub-rich-text" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    methods: { getMentionedIds: () => [] },
  },
}))

import { api } from '@/api'

// A realistic toolbar for a Lead, matching the new backend behaviour:
// every channel-specific messaging tool carries `channel` + `direction`
// metadata.
const TOOLBAR = [
  { activity_type: 'comment', label: 'Comment', icon: 'ChatBubbleLeftIcon', channel: 'none', direction: 'none', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Body' } }, required: ['content_text'] } },
  { activity_type: 'call', label: 'Call', icon: 'PhoneIcon', channel: 'none', direction: 'none', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Notes' } } } },
  { activity_type: 'email_out', label: 'Email (Outbound)', icon: 'PaperAirplaneIcon', channel: 'email', direction: 'out', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Body' }, subject: { type: 'string', title: 'Subject' }, to: { type: 'string', title: 'To', format: 'email' } }, required: ['content_text', 'subject', 'to'] } },
  { activity_type: 'email_in', label: 'Email (Inbound)', icon: 'InboxArrowDownIcon', channel: 'email', direction: 'in', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Body' }, subject: { type: 'string', title: 'Subject' }, from_address: { type: 'string', title: 'From', format: 'email' } }, required: ['content_text', 'from_address'] } },
  { activity_type: 'sms_out', label: 'SMS (Outbound)', icon: 'DevicePhoneMobileIcon', channel: 'sms', direction: 'out', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Message' }, to: { type: 'string', title: 'To' } }, required: ['content_text', 'to'] } },
  { activity_type: 'sms_in', label: 'SMS (Inbound)', icon: 'DevicePhoneMobileIcon', channel: 'sms', direction: 'in', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Message' }, from_number: { type: 'string', title: 'From' } }, required: ['content_text', 'from_number'] } },
  { activity_type: 'whatsapp_out', label: 'WhatsApp (Outbound)', icon: 'ChatBubbleOvalLeftEllipsisIcon', channel: 'whatsapp', direction: 'out', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Message' }, to: { type: 'string', title: 'To' } }, required: ['content_text', 'to'] } },
  { activity_type: 'whatsapp_in', label: 'WhatsApp (Inbound)', icon: 'ChatBubbleOvalLeftEllipsisIcon', channel: 'whatsapp', direction: 'in', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Message' }, from_number: { type: 'string', title: 'From' } }, required: ['content_text', 'from_number'] } },
  { activity_type: 'chat', label: 'Chat Message', icon: 'ChatBubbleLeftRightIcon', channel: 'chat', direction: 'none', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Message' } }, required: ['content_text'] } },
  { activity_type: 'task', label: 'Task', icon: 'ClipboardDocumentListIcon', channel: 'none', direction: 'none', form_schema: { type: 'object', properties: {} } },
  { activity_type: 'system_note', label: 'System Note', icon: 'InformationCircleIcon', channel: 'none', direction: 'none', form_schema: { type: 'object', properties: { content_text: { type: 'string', title: 'Note' } }, required: ['content_text'] } },
]

async function mountPicker() {
  vi.mocked(api.get).mockResolvedValue({ ok: true, status: 200, data: TOOLBAR })
  const wrapper = mount(EntitySidebarActionPicker, {
    props: { entityType: 'lead', entityId: 'lead-1' },
  })
  await flushPromises()
  return wrapper
}

describe('EntitySidebarActionPicker — unified message composer', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('hides per-channel messaging buttons in the action grid', async () => {
    const wrapper = await mountPicker()
    const options = wrapper.findAll('[data-testid="entity-sidebar-action-option"]')
    const visibleTypes = options.map((o) => o.attributes('data-action'))
    for (const messagingType of ['email_out', 'email_in', 'sms_out', 'sms_in', 'whatsapp_out', 'whatsapp_in', 'chat']) {
      expect(visibleTypes).not.toContain(messagingType)
    }
    // Non-messaging tools and the unified entry are still present.
    expect(visibleTypes).toContain('comment')
    expect(visibleTypes).toContain('call')
    expect(visibleTypes).toContain('message')
  })

  it('does not render the unified "message" entry when no messaging tools are available', async () => {
    vi.mocked(api.get).mockResolvedValue({
      ok: true,
      status: 200,
      data: TOOLBAR.filter((t) => !t.channel || t.channel === 'none'),
    })
    const wrapper = mount(EntitySidebarActionPicker, {
      props: { entityType: 'lead', entityId: 'lead-1' },
    })
    await flushPromises()
    const options = wrapper.findAll('[data-testid="entity-sidebar-action-option"]')
    const visibleTypes = options.map((o) => o.attributes('data-action'))
    expect(visibleTypes).not.toContain('message')
  })

  it('shows channel + direction picker when "Message" is selected', async () => {
    const wrapper = await mountPicker()
    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="message"]').trigger('click')
    expect(wrapper.find('[data-testid="message-composer-channel-picker"]').exists()).toBe(true)
    const channels = wrapper.findAll('[data-testid="message-composer-channel-option"]').map((c) => c.attributes('data-channel'))
    expect(channels).toEqual(['email', 'sms', 'whatsapp', 'chat'])
    // Direction toggle isn't rendered until a channel with direction options is picked.
    expect(wrapper.findAll('[data-testid="message-composer-direction-option"]').length).toBe(0)
  })

  it('exposes both directions for email and resolves to email_out schema', async () => {
    const wrapper = await mountPicker()
    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="message"]').trigger('click')
    await wrapper.find('[data-testid="message-composer-channel-option"][data-channel="email"]').trigger('click')
    const dirs = wrapper.findAll('[data-testid="message-composer-direction-option"]').map((d) => d.attributes('data-direction'))
    expect(dirs).toEqual(['out', 'in'])

    await wrapper.find('[data-testid="message-composer-direction-option"][data-direction="out"]').trigger('click')
    // The resolved tool's "Subject" / "To" header fields appear above the body.
    const fieldKeys = wrapper.findAll('[data-field]').map((d) => d.attributes('data-field'))
    expect(fieldKeys).toContain('subject')
    expect(fieldKeys).toContain('to')
  })

  it('skips the direction toggle for the chat channel', async () => {
    const wrapper = await mountPicker()
    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="message"]').trigger('click')
    await wrapper.find('[data-testid="message-composer-channel-option"][data-channel="chat"]').trigger('click')
    expect(wrapper.findAll('[data-testid="message-composer-direction-option"]').length).toBe(0)
    // Chat schema (single content_text) still renders.
    expect(wrapper.find('[data-testid="stub-rich-text"]').exists()).toBe(true)
  })

  it('submits the resolved activity_type, not "message"', async () => {
    const wrapper = await mountPicker()
    vi.mocked(api.post).mockResolvedValue({ ok: true, status: 201, data: {} })

    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="message"]').trigger('click')
    await wrapper.find('[data-testid="message-composer-channel-option"][data-channel="sms"]').trigger('click')
    await wrapper.find('[data-testid="message-composer-direction-option"][data-direction="out"]').trigger('click')

    // Fill required fields directly via the v-model surface.
    const toInput = wrapper.find('input[data-field-input], [data-field="to"] input')
    expect(toInput.exists()).toBe(true)
    await toInput.setValue('+420123456789')
    const body = wrapper.find('[data-testid="stub-rich-text"]')
    await body.setValue('Hello SMS')

    // Find the submit button (last red button in the form).
    const buttons = wrapper.findAll('button')
    const submit = buttons.find((b) => /add|odeslat|absenden|dodaj|hotovo|ulo|save/i.test(b.text())) ?? buttons[buttons.length - 1]
    expect(submit).toBeTruthy()
    await submit!.trigger('click')
    await flushPromises()

    expect(api.post).toHaveBeenCalledTimes(1)
    const [, payload] = vi.mocked(api.post).mock.calls[0]!
    expect((payload as Record<string, unknown>).type).toBe('sms_out')
  })
})

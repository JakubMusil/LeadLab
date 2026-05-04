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

import { api } from '@/api'

// A realistic toolbar for a Record, matching the new backend behaviour:
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
    props: { entityType: 'record', entityId: 'record-1' },
  })
  await flushPromises()
  return wrapper
}

describe('EntitySidebarActionPicker — action grid', () => {
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
      props: { entityType: 'record', entityId: 'record-1' },
    })
    await flushPromises()
    const options = wrapper.findAll('[data-testid="entity-sidebar-action-option"]')
    const visibleTypes = options.map((o) => o.attributes('data-action'))
    expect(visibleTypes).not.toContain('message')
  })

  it('emits tool-selected with the action type when a non-message tool is clicked', async () => {
    const wrapper = await mountPicker()
    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="comment"]').trigger('click')
    expect(wrapper.emitted('tool-selected')).toEqual([['comment']])
  })

  it('emits tool-selected with "message" when the unified message entry is clicked', async () => {
    const wrapper = await mountPicker()
    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="message"]').trigger('click')
    expect(wrapper.emitted('tool-selected')).toEqual([['message']])
  })

  it('emits tool-selected with "call" when the call tool is clicked', async () => {
    const wrapper = await mountPicker()
    await wrapper.find('[data-testid="entity-sidebar-action-option"][data-action="call"]').trigger('click')
    expect(wrapper.emitted('tool-selected')).toEqual([['call']])
  })
})


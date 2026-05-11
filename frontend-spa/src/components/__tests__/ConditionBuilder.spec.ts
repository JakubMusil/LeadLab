import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConditionBuilder from '../ConditionBuilder.vue'

type ConditionNode = Record<string, unknown>

function lastModelValue(wrapper: ReturnType<typeof mount>): ConditionNode {
  const events = wrapper.emitted('update:modelValue')
  const last = events?.[events.length - 1]?.[0]
  return (last ?? {}) as ConditionNode
}

describe('ConditionBuilder', () => {
  it('keeps operator disabled for category field until a field is selected', async () => {
    const wrapper = mount(ConditionBuilder, {
      props: {
        modelValue: {
          type: 'condition',
          source_type: 'category_field',
          category_field_key: '',
          operator: '',
          value: '',
        },
        categoryFields: [{ field_key: 'budget', label: 'Budget', value_type: 'number' }],
      },
    })

    const selects = wrapper.findAll('select')
    const operatorSelect = selects[3]
    expect((operatorSelect.element as HTMLSelectElement).disabled).toBe(true)

    await selects[2]!.setValue('budget')
    const updated = lastModelValue(wrapper)
    expect(updated.category_field_key).toBe('budget')
    expect(updated.operator).toBe('')
    expect(updated.value).toBe('')
  })

  it('updates standard field selection', async () => {
    const wrapper = mount(ConditionBuilder, {
      props: {
        modelValue: {
          type: 'condition',
          source_type: 'standard_field',
          field: '',
          operator: '',
          value: '',
        },
        categoryFields: [],
      },
    })

    const selects = wrapper.findAll('select')
    await selects[2]!.setValue('title')
    const updated = lastModelValue(wrapper)
    expect(updated.field).toBe('title')
  })

  it('resets operator and value when category field changes', async () => {
    const wrapper = mount(ConditionBuilder, {
      props: {
        modelValue: {
          type: 'condition',
          source_type: 'category_field',
          category_field_key: 'budget',
          operator: 'gt',
          value: 100,
        },
        categoryFields: [
          { field_key: 'budget', label: 'Budget', value_type: 'number' },
          { field_key: 'region', label: 'Region', value_type: 'text' },
        ],
      },
    })

    const selects = wrapper.findAll('select')
    await selects[2]!.setValue('region')
    const updated = lastModelValue(wrapper)
    expect(updated.category_field_key).toBe('region')
    expect(updated.operator).toBe('')
    expect(updated.value).toBe('')
  })

  it('updates streamline tool value input', async () => {
    const wrapper = mount(ConditionBuilder, {
      props: {
        modelValue: {
          type: 'condition',
          source_type: 'streamline_tool',
          tool_type: '',
          operator: '',
          value: '',
        },
        categoryFields: [],
      },
    })

    const textInput = wrapper.find('input[type="text"]')
    await textInput.setValue('email_out')
    const updated = lastModelValue(wrapper)
    expect(updated.tool_type).toBe('email_out')
  })
})

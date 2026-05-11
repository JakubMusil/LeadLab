import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConditionTreeViewer from '../ConditionTreeViewer.vue'

describe('ConditionTreeViewer', () => {
  it('renders empty state for empty tree', () => {
    const wrapper = mount(ConditionTreeViewer, {
      props: {
        conditionTree: {},
        categoryFields: [],
      },
    })

    expect(wrapper.text()).toContain('No conditions')
  })

  it('renders loading state', () => {
    const wrapper = mount(ConditionTreeViewer, {
      props: {
        conditionTree: {},
        categoryFields: [],
        loading: true,
      },
    })

    expect(wrapper.text()).toContain('Loading condition tree')
  })

  it('renders explicit error', () => {
    const wrapper = mount(ConditionTreeViewer, {
      props: {
        conditionTree: {},
        categoryFields: [],
        error: 'Custom error',
      },
    })

    expect(wrapper.text()).toContain('Custom error')
  })

  it('renders a simple condition node', () => {
    const wrapper = mount(ConditionTreeViewer, {
      props: {
        conditionTree: {
          type: 'condition',
          source_type: 'standard_field',
          field: 'title',
          operator: 'contains',
          value: 'Lead',
        },
        categoryFields: [],
      },
    })

    expect(wrapper.text()).toContain('title')
    expect(wrapper.text()).toContain('contains')
  })

  it('supports collapse and expand on group nodes', async () => {
    const wrapper = mount(ConditionTreeViewer, {
      props: {
        conditionTree: {
          type: 'group',
          op: 'and',
          conditions: [
            {
              type: 'condition',
              source_type: 'standard_field',
              field: 'title',
              operator: 'contains',
              value: 'Lead',
            },
          ],
        },
        categoryFields: [],
      },
    })

    expect(wrapper.findAll('.tree-node').length).toBe(2)

    const toggle = wrapper.find('.tree-collapse-btn')
    expect(toggle.exists()).toBe(true)
    await toggle.trigger('click')
    expect(wrapper.findAll('.tree-node').length).toBe(1)
    await toggle.trigger('click')
    expect(wrapper.findAll('.tree-node').length).toBe(2)
  })
})

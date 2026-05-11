import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PipelineFlowDiagram from '../PipelineFlowDiagram.vue'

const categories = [{ id: 'cat-1', name: 'Sales' }]
const stages = [
  { id: 'stage-1', name: 'Qualification' },
  { id: 'stage-2', name: 'Done' },
]

const rules = [
  {
    id: 'rule-1',
    name: 'Activate scenario',
    description: '',
    is_active: true,
    category_id: 'cat-1',
    stage_id: 'stage-1',
    source_stage_id: null,
    target_stage_id: null,
    trigger_type: 'record.field_changed',
    effect: 'activate_scenario',
    severity: 'info',
    priority: 10,
    effect_config: { scenario_id: 'scenario-1' },
  },
]

const scenarios = [
  {
    id: 'scenario-1',
    category_id: 'cat-1',
    stage_id: 'stage-1',
    name: 'Scenario A',
    description: '',
    recommended_next_stage_id: 'stage-2',
    priority: 1,
    is_active: true,
  },
]

const requirements = [
  {
    id: 'req-1',
    scenario_id: 'scenario-1',
    name: 'Upload file',
    description: '',
    requirement_type: 'attachment',
    blocking: true,
    visible_to_user: true,
    sort_order: 1,
    next_step_on_met_id: 'req-2',
    next_step_on_unmet_id: null,
  },
  {
    id: 'req-2',
    scenario_id: 'scenario-1',
    name: 'Finish checklist',
    description: '',
    requirement_type: 'checklist',
    blocking: false,
    visible_to_user: true,
    sort_order: 2,
    next_step_on_met_id: null,
    next_step_on_unmet_id: null,
  },
]

describe('PipelineFlowDiagram', () => {
  it('renders empty state', () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules: [],
        scenarios: [],
        requirements: [],
        categories,
        stages,
      },
    })

    expect(wrapper.text()).toContain('No pipeline flow')
  })

  it('renders rules, scenarios, requirements and directed edges', () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
        initialCategoryId: 'cat-1',
        initialStageId: 'stage-1',
      },
    })

    expect(wrapper.text()).toContain('Activate scenario')
    expect(wrapper.text()).toContain('Scenario A')
    expect(wrapper.text()).toContain('Upload file')
    expect(wrapper.text()).toContain('Finish checklist')
    expect(wrapper.text()).toContain('→')
    expect(wrapper.text()).toContain('Next step if met')
  })

  it('filters nodes by type', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
      },
    })

    const selects = wrapper.findAll('select')
    await selects[3]!.setValue('requirement')

    expect(wrapper.text()).not.toContain('Activate scenario')
    expect(wrapper.text()).not.toContain('Scenario A')
    expect(wrapper.text()).toContain('Upload file')
  })

  it('collapses and expands scenario requirements', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
      },
    })

    const button = wrapper.find('article button')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    expect(wrapper.text()).not.toContain('Upload file')
    await button.trigger('click')
    expect(wrapper.text()).toContain('Upload file')
  })
})

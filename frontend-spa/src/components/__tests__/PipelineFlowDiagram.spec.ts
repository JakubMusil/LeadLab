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
    expect(wrapper.text()).not.toContain('requirementType: attachment')
    await button.trigger('click')
    expect(wrapper.text()).toContain('requirementType: attachment')
  })

  it('shows node detail after selecting a node', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
      },
    })

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('click')

    expect(wrapper.text()).toContain('Node detail')
    expect(wrapper.text()).toContain('Scenario A')
    expect(wrapper.text()).toContain('Children (')
  })

  it('clears selection when clear action is used', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
      },
    })

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('click')

    const clearButton = wrapper.findAll('button').find((button) => button.text().includes('Clear selection'))
    expect(clearButton).toBeTruthy()
    await clearButton!.trigger('click')

    expect(wrapper.text()).toContain('Select a node in the diagram to show detail context.')
  })

  it('supports keyboard selection via enter key', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
      },
    })

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('keydown.enter')

    expect(wrapper.text()).toContain('Node detail')
    expect(wrapper.text()).toContain('Scenario A')
  })

  it('shows requirement link diagnostics with invalid link reason', () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements: [{ ...requirements[0], next_step_on_met_id: 'missing' }],
        categories,
        stages,
      },
    })

    expect(wrapper.text()).toContain('Requirement chained links')
    expect(wrapper.text()).toContain('Some chained requirement links point to requirements outside the current filtered diagram.')
  })

  it('clears selected node detail when filters hide the selected node', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
      },
    })

    const scenarioNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(scenarioNode).toBeTruthy()
    await scenarioNode!.trigger('click')
    expect(wrapper.text()).toContain('Parent: Activate scenario')

    const selects = wrapper.findAll('select')
    await selects[3]!.setValue('requirement')

    expect(wrapper.text()).toContain('Select a node in the diagram to show detail context.')
  })
})

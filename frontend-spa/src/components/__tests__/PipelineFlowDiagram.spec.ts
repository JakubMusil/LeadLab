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
  function mountDiagram(customRequirements = requirements) {
    return mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements: customRequirements,
        categories,
        stages,
      },
    })
  }

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
    const wrapper = mountDiagram()

    const selects = wrapper.findAll('select')
    await selects[4]!.setValue('requirement')

    expect(wrapper.text()).not.toContain('Activate scenario')
    expect(wrapper.text()).not.toContain('Scenario A')
    expect(wrapper.text()).toContain('Upload file')
  })

  it('collapses and expands scenario requirements', async () => {
    const wrapper = mountDiagram()

    const button = wrapper.find('article button')
    expect(button.exists()).toBe(true)
    expect(wrapper.findAll('article')).toHaveLength(4)
    await button.trigger('click')
    expect(wrapper.findAll('article')).toHaveLength(2)
    await button.trigger('click')
    expect(wrapper.findAll('article')).toHaveLength(4)
  })

  it('shows node detail after selecting a node', async () => {
    const wrapper = mountDiagram()

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('click')

    expect(wrapper.text()).toContain('Node detail')
    expect(wrapper.text()).toContain('Scenario A')
    expect(wrapper.text()).toContain('Children (')
  })

  it('clears selection when clear action is used', async () => {
    const wrapper = mountDiagram()

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('click')

    const clearButton = wrapper.findAll('button').find((button) => button.text().includes('Clear selection'))
    expect(clearButton).toBeTruthy()
    await clearButton!.trigger('click')

    expect(wrapper.text()).toContain('Select a node in the diagram to show detail context.')
  })

  it('supports keyboard selection via enter key', async () => {
    const wrapper = mountDiagram()

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
    const wrapper = mountDiagram()

    const scenarioNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(scenarioNode).toBeTruthy()
    await scenarioNode!.trigger('click')
    expect(wrapper.text()).toContain('Parent: Activate scenario')

    const selects = wrapper.findAll('select')
    await selects[4]!.setValue('requirement')

    expect(wrapper.text()).toContain('Select a node in the diagram to show detail context.')
  })

  it('shows localized trigger labels in filter and node badge', () => {
    const wrapper = mountDiagram()
    expect(wrapper.text()).toContain('Record field changed')
    expect(wrapper.text()).not.toContain('record.field_changed')
  })

  it('renders test evaluation and requirement fulfillment badges from inputs', () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules,
        scenarios,
        requirements,
        categories,
        stages,
        testedRuleId: 'rule-1',
        evaluationOutputs: [{ rule_id: 'rule-1' }],
        evaluationLogs: [
          {
            id: 'log-1',
            requirement_id: 'req-1',
            trigger_type: 'requirement.chain_evaluated',
            input_context: { fulfillment_status: 'met', requirement_id: 'req-1' },
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('Matched in test')
    expect(wrapper.text()).toContain('Branch met')
  })

  it('updates zoom level using zoom controls', async () => {
    const wrapper = mountDiagram()
    const zoomLevel = wrapper.get('[data-testid="flow-zoom-level"]')
    expect(zoomLevel.attributes('data-zoom-level')).toBe('100')

    const zoomInButton = wrapper.find('[data-testid="flow-zoom-in"]')
    expect(zoomInButton.exists()).toBe(true)
    await zoomInButton.trigger('click')
    expect(wrapper.get('[data-testid="flow-zoom-level"]').attributes('data-zoom-level')).toBe('110')
  })

  it('updates zoom level from keyboard shortcut on viewport', async () => {
    const wrapper = mountDiagram()
    const viewport = wrapper.find('[role="region"]')
    expect(viewport.exists()).toBe(true)

    await viewport.trigger('keydown', { key: '+' })
    expect(wrapper.get('[data-testid="flow-zoom-level"]').attributes('data-zoom-level')).toBe('110')
  })

  it('enables center selection control after node selection', async () => {
    const wrapper = mountDiagram()
    const centerButton = wrapper.find('[data-testid="flow-center-selection"]')
    expect(centerButton.exists()).toBe(true)
    expect(centerButton.attributes('disabled')).toBeDefined()

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('click')
    expect(centerButton.attributes('disabled')).toBeUndefined()
  })

  it('falls back to limited rendered nodes for large graphs', () => {
    const largeRequirements = Array.from({ length: 90 }, (_, index) => ({
      id: `req-${index + 1}`,
      scenario_id: 'scenario-1',
      name: `Requirement ${index + 1}`,
      description: '',
      requirement_type: 'checklist',
      blocking: false,
      visible_to_user: true,
      sort_order: index + 1,
      next_step_on_met_id: null,
      next_step_on_unmet_id: null,
    }))

    const wrapper = mountDiagram(largeRequirements)

    expect(wrapper.findAll('article')).toHaveLength(80)
    const fallback = wrapper.find('[data-testid="flow-large-graph-fallback"]')
    expect(fallback.exists()).toBe(true)
    expect(fallback.attributes('data-hidden-count')).toBe('12')
  })
})

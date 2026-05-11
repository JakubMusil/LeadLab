import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PipelineFlowDiagram from '../PipelineFlowDiagram.vue'

const categories = [
  { id: 'cat-1', name: 'Sales' },
  { id: 'cat-2', name: 'Support' },
]
const stages = [
  { id: 'stage-1', name: 'Qualification' },
  { id: 'stage-2', name: 'Done' },
  { id: 'stage-3', name: 'Support review' },
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

    const nodeTypeSelect = wrapper.find('select[aria-label="Filter by node type"]')
    expect(nodeTypeSelect.exists()).toBe(true)
    await nodeTypeSelect.setValue('requirement')

    expect(wrapper.text()).not.toContain('Activate scenario')
    expect(wrapper.text()).not.toContain('Scenario A')
    expect(wrapper.text()).toContain('Upload file')
  })

  it('collapses and expands scenario requirements', async () => {
    const wrapper = mountDiagram()

    const button = wrapper.find('article button')
    expect(button.exists()).toBe(true)
    expect(button.attributes('aria-label')).toContain('Collapse scenario')
    expect(wrapper.findAll('article')).toHaveLength(4)
    await button.trigger('click')
    expect(button.attributes('aria-label')).toContain('Expand scenario')
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

  it('supports keyboard selection via space key', async () => {
    const wrapper = mountDiagram()

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('keydown.space')

    expect(wrapper.text()).toContain('Node detail')
    expect(wrapper.text()).toContain('Scenario A')
  })

  it('emits toggle-rule-active from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const ruleNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Activate scenario'))
    expect(ruleNode).toBeTruthy()
    await ruleNode!.trigger('click')

    const toggleButton = wrapper.find('[data-testid="flow-node-action-toggle-rule"]')
    expect(toggleButton.exists()).toBe(true)
    await toggleButton.trigger('click')

    expect(wrapper.emitted('toggle-rule-active')).toBeTruthy()
    expect(wrapper.emitted('toggle-rule-active')?.[0]).toEqual([{ ruleId: 'rule-1', nextActive: false }])
  })

  it('emits update-rule-description from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const ruleNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Activate scenario'))
    expect(ruleNode).toBeTruthy()
    await ruleNode!.trigger('click')

    const input = wrapper.get('[data-testid="flow-node-rule-description"]')
    await input.setValue('Updated description')
    const saveButton = wrapper.get('[data-testid="flow-node-action-save-rule-description"]')
    await saveButton.trigger('click')

    expect(wrapper.emitted('update-rule-description')).toBeTruthy()
    expect(wrapper.emitted('update-rule-description')?.[0]).toEqual([
      { ruleId: 'rule-1', description: 'Updated description' },
    ])
  })

  it('emits toggle-rule-root-operator from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const ruleNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Activate scenario'))
    expect(ruleNode).toBeTruthy()
    await ruleNode!.trigger('click')

    const toggleRootOperatorButton = wrapper.get('[data-testid="flow-node-action-toggle-rule-root-operator"]')
    await toggleRootOperatorButton.trigger('click')

    expect(wrapper.emitted('toggle-rule-root-operator')).toBeTruthy()
    expect(wrapper.emitted('toggle-rule-root-operator')?.[0]).toEqual([{ ruleId: 'rule-1' }])
  })

  it('emits add-rule-root-group from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const ruleNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Activate scenario'))
    expect(ruleNode).toBeTruthy()
    await ruleNode!.trigger('click')

    const addRootGroupButton = wrapper.get('[data-testid="flow-node-action-add-rule-root-group"]')
    await addRootGroupButton.trigger('click')

    expect(wrapper.emitted('add-rule-root-group')).toBeTruthy()
    expect(wrapper.emitted('add-rule-root-group')?.[0]).toEqual([{ ruleId: 'rule-1' }])
  })

  it('emits open-rule-editor from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const ruleNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Activate scenario'))
    expect(ruleNode).toBeTruthy()
    await ruleNode!.trigger('click')

    const openRuleEditorButton = wrapper.get('[data-testid="flow-node-action-open-rule-editor"]')
    await openRuleEditorButton.trigger('click')

    expect(wrapper.emitted('open-rule-editor')).toBeTruthy()
    expect(wrapper.emitted('open-rule-editor')?.[0]).toEqual([{ ruleId: 'rule-1' }])
  })

  it('emits update-scenario-priority from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const scenarioNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(scenarioNode).toBeTruthy()
    await scenarioNode!.trigger('click')

    const priorityInput = wrapper.get('[data-testid="flow-node-scenario-priority"]')
    await priorityInput.setValue('4')
    const saveButton = wrapper.get('[data-testid="flow-node-action-save-scenario-priority"]')
    await saveButton.trigger('click')

    expect(wrapper.emitted('update-scenario-priority')).toBeTruthy()
    expect(wrapper.emitted('update-scenario-priority')?.[0]).toEqual([{ scenarioId: 'scenario-1', priority: 4 }])
  })

  it('emits update-scenario-description from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const scenarioNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(scenarioNode).toBeTruthy()
    await scenarioNode!.trigger('click')

    const descriptionInput = wrapper.get('[data-testid="flow-node-scenario-description"]')
    await descriptionInput.setValue('Updated scenario description')
    const saveButton = wrapper.get('[data-testid="flow-node-action-save-scenario-description"]')
    await saveButton.trigger('click')

    expect(wrapper.emitted('update-scenario-description')).toBeTruthy()
    expect(wrapper.emitted('update-scenario-description')?.[0]).toEqual([
      { scenarioId: 'scenario-1', description: 'Updated scenario description' },
    ])
  })

  it('emits open-requirement-editor from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const requirementNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Upload file'))
    expect(requirementNode).toBeTruthy()
    await requirementNode!.trigger('click')

    const openEditorButton = wrapper.get('[data-testid="flow-node-action-open-requirement-editor"]')
    await openEditorButton.trigger('click')

    expect(wrapper.emitted('open-requirement-editor')).toBeTruthy()
    expect(wrapper.emitted('open-requirement-editor')?.[0]).toEqual([{ requirementId: 'req-1' }])
  })

  it('emits update-requirement-next-step from node detail quick action', async () => {
    const wrapper = mountDiagram()

    const requirementNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Upload file'))
    expect(requirementNode).toBeTruthy()
    await requirementNode!.trigger('click')

    const metSelect = wrapper.get('[data-testid="flow-node-requirement-next-step-met"]')
    const unmetSelect = wrapper.get('[data-testid="flow-node-requirement-next-step-unmet"]')
    await metSelect.setValue('')
    await unmetSelect.setValue('req-2')

    const saveButton = wrapper.get('[data-testid="flow-node-action-save-requirement-next-step"]')
    await saveButton.trigger('click')

    expect(wrapper.emitted('update-requirement-next-step')).toBeTruthy()
    expect(wrapper.emitted('update-requirement-next-step')?.[0]).toEqual([
      { requirementId: 'req-1', nextStepOnMetId: null, nextStepOnUnmetId: 'req-2' },
    ])
  })

  it('shows requirement next-step options only from same scenario', async () => {
    const wrapper = mountDiagram([
      ...requirements,
      {
        ...requirements[0],
        id: 'req-3',
        scenario_id: 'scenario-2',
        name: 'External requirement',
        next_step_on_met_id: null,
        next_step_on_unmet_id: null,
      },
    ])

    const requirementNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Upload file'))
    expect(requirementNode).toBeTruthy()
    await requirementNode!.trigger('click')

    const metSelect = wrapper.get('[data-testid="flow-node-requirement-next-step-met"]')
    const values = metSelect.findAll('option').map((option) => option.attributes('value'))
    expect(values).toContain('req-2')
    expect(values).not.toContain('req-1')
    expect(values).not.toContain('req-3')
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

    const nodeTypeSelect = wrapper.find('select[aria-label="Filter by node type"]')
    expect(nodeTypeSelect.exists()).toBe(true)
    await nodeTypeSelect.setValue('requirement')

    expect(wrapper.text()).toContain('Select a node in the diagram to show detail context.')
  })

  it('syncs category and stage filters when initial props change from form state', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules: [
          ...rules,
          {
            ...rules[0],
            id: 'rule-2',
            name: 'Activate support scenario',
            category_id: 'cat-2',
            stage_id: 'stage-3',
            effect_config: { stage_scenario_id: 'scenario-2' },
          },
        ],
        scenarios: [
          ...scenarios,
          {
            ...scenarios[0],
            id: 'scenario-2',
            name: 'Scenario B',
            category_id: 'cat-2',
            stage_id: 'stage-3',
          },
        ],
        requirements: [
          ...requirements,
          {
            ...requirements[0],
            id: 'req-3',
            scenario_id: 'scenario-2',
            name: 'Prepare support summary',
            next_step_on_met_id: null,
            next_step_on_unmet_id: null,
          },
        ],
        categories,
        stages,
        initialCategoryId: 'cat-1',
        initialStageId: 'stage-1',
      },
    })

    expect(wrapper.text()).toContain('Scenario A')
    expect(wrapper.text()).not.toContain('Scenario B')
    await wrapper.setProps({
      initialCategoryId: 'cat-2',
      initialStageId: 'stage-3',
    })
    expect(wrapper.text()).toContain('Scenario B')
    expect(wrapper.text()).not.toContain('Scenario A')
  })

  it('clears selected node detail when requirements update from form and remove selected node', async () => {
    const wrapper = mountDiagram()

    const selectedNode = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Finish checklist'))
    expect(selectedNode).toBeTruthy()
    await selectedNode!.trigger('click')
    expect(wrapper.text()).toContain('Finish checklist')

    await wrapper.setProps({
      requirements: [{ ...requirements[0], next_step_on_met_id: null }],
    })

    expect(wrapper.text()).toContain('Select a node in the diagram to show detail context.')
    expect(wrapper.text()).not.toContain('Finish checklist')
  })

  it('shows localized trigger labels in filter and node badge', () => {
    const wrapper = mountDiagram()
    expect(wrapper.text()).toContain('Record field changed')
    expect(wrapper.text()).not.toContain('record.field_changed')
  })

  it('toggles in-app help panel', async () => {
    const wrapper = mountDiagram()
    const helpToggle = wrapper.get('[data-testid="flow-help-toggle"]')

    expect(wrapper.find('[data-testid="flow-help-panel"]').exists()).toBe(false)
    await helpToggle.trigger('click')
    expect(wrapper.find('[data-testid="flow-help-panel"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('How to read this diagram')
    await helpToggle.trigger('click')
    expect(wrapper.find('[data-testid="flow-help-panel"]').exists()).toBe(false)
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

  it('highlights related nodes and dims unrelated nodes for selected node', async () => {
    const wrapper = mount(PipelineFlowDiagram, {
      props: {
        rules: [
          ...rules,
          {
            ...rules[0],
            id: 'rule-2',
            name: 'Activate scenario B',
            effect_config: { stage_scenario_id: 'scenario-2' },
          },
        ],
        scenarios: [
          ...scenarios,
          {
            ...scenarios[0],
            id: 'scenario-2',
            name: 'Scenario B',
          },
        ],
        requirements: [
          ...requirements,
          {
            ...requirements[0],
            id: 'req-3',
            scenario_id: 'scenario-2',
            name: 'Upload support file',
            next_step_on_met_id: null,
          },
        ],
        categories,
        stages,
      },
    })

    const scenarioAButton = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(scenarioAButton).toBeTruthy()
    await scenarioAButton!.trigger('click')

    expect(wrapper.get('[data-node-id="scenario-scenario-1"]').classes()).toContain('ring-2')
    expect(wrapper.get('[data-node-id="rule-rule-1"]').classes()).toContain('ring-1')
    expect(wrapper.get('[data-node-id="requirement-req-1"]').classes()).toContain('ring-1')
    expect(wrapper.get('[data-node-id="scenario-scenario-2"]').classes()).toContain('opacity-50')
  })

  it('highlights connected edges when node is selected', async () => {
    const wrapper = mountDiagram()
    const requirementButton = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Upload file'))
    expect(requirementButton).toBeTruthy()
    await requirementButton!.trigger('click')

    const edgeRows = wrapper.findAll('li.transition-colors')
    expect(edgeRows.length).toBeGreaterThan(0)
    expect(edgeRows.some((edge) => edge.classes().includes('text-indigo-700'))).toBe(true)
    expect(edgeRows.some((edge) => edge.classes().includes('opacity-60'))).toBe(true)
  })

  it('clears relation highlighting when selected node is deselected', async () => {
    const wrapper = mountDiagram()
    const scenarioButton = wrapper.findAll('[role="button"]').find((button) => button.text().includes('Scenario A'))
    expect(scenarioButton).toBeTruthy()
    await scenarioButton!.trigger('click')
    await scenarioButton!.trigger('click')

    const ruleNodeClasses = wrapper.get('[data-node-id="rule-rule-1"]').classes()
    expect(ruleNodeClasses).not.toContain('opacity-50')
    expect(ruleNodeClasses).toContain('opacity-100')
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

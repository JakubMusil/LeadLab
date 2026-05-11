import { describe, expect, it } from 'vitest'
import { buildPipelineFlowModel } from '../pipelineFlowVisualization'

const t = (key: string): string => key

const baseRule = {
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
}

const baseScenario = {
  id: 'scenario-1',
  category_id: 'cat-1',
  stage_id: 'stage-1',
  name: 'Scenario A',
  description: '',
  activation_condition: { type: 'condition', source_type: 'standard_field', field: 'lead_source' },
  recommended_next_stage_id: 'stage-2',
  priority: 1,
  is_active: true,
}

const firstRequirement = {
  id: 'req-1',
  scenario_id: 'scenario-1',
  name: 'Upload file',
  description: '',
  requirement_type: 'attachment',
  blocking: true,
  visible_to_user: true,
  sort_order: 1,
  next_step_on_met_id: 'req-2',
  next_step_on_unmet_id: 'req-3',
}

const secondRequirement = {
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
}

const thirdRequirement = {
  id: 'req-3',
  scenario_id: 'scenario-1',
  name: 'Fix missing data',
  description: '',
  requirement_type: 'field',
  blocking: true,
  visible_to_user: true,
  sort_order: 3,
  next_step_on_met_id: null,
  next_step_on_unmet_id: null,
}

describe('pipelineFlowVisualization', () => {
  it('builds empty model with root only', () => {
    const model = buildPipelineFlowModel({ rules: [], scenarios: [], requirements: [] }, { t })

    expect(model.rootId).toBe('root')
    expect(model.nodesByType.all).toEqual([])
    expect(model.edges).toEqual([])
  })

  it('builds rule to scenario to requirement model', () => {
    const model = buildPipelineFlowModel(
      {
        rules: [baseRule],
        scenarios: [baseScenario],
        requirements: [firstRequirement],
      },
      { categoryId: 'cat-1', stageId: 'stage-1', t },
    )

    expect(model.nodesByType.rule).toHaveLength(1)
    expect(model.nodesByType.scenario).toHaveLength(1)
    expect(model.nodesByType.requirement).toHaveLength(1)
    expect(model.edges.some((edge) => edge.type === 'activates_scenario')).toBe(true)
    expect(model.edges.some((edge) => edge.source === 'scenario-scenario-1' && edge.target === 'requirement-req-1')).toBe(true)
    expect(model.nodesByType.scenario[0]?.meta.activationCondition).toBe('pipeline.flowDiagramActivationConfigured')
    expect(model.nodesByType.requirement[0]?.meta.recommendedNextStage).toBe('stage-2')
  })

  it('builds directed requirement chain edges for met and unmet branches', () => {
    const model = buildPipelineFlowModel(
      {
        rules: [baseRule, { ...baseRule, id: 'rule-2', name: 'Second activator', priority: 20 }],
        scenarios: [baseScenario],
        requirements: [firstRequirement, secondRequirement, thirdRequirement],
      },
      { t },
    )

    expect(model.edges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          source: 'requirement-req-1',
          target: 'requirement-req-2',
          type: 'next_step_on_met',
        }),
        expect.objectContaining({
          source: 'requirement-req-1',
          target: 'requirement-req-3',
          type: 'next_step_on_unmet',
        }),
      ]),
    )
    expect(model.edges.filter((edge) => edge.type === 'activates_scenario')).toHaveLength(2)
  })

  it('filters by trigger, active state and node type', () => {
    const model = buildPipelineFlowModel(
      {
        rules: [
          baseRule,
          {
            ...baseRule,
            id: 'rule-2',
            name: 'Inactive stage rule',
            is_active: false,
            trigger_type: 'record.stage_changed',
          },
        ],
        scenarios: [{ ...baseScenario, is_active: false }],
        requirements: [firstRequirement],
      },
      {
        triggerType: 'field',
        activeState: 'enabled',
        nodeType: 'rule',
        t,
      },
    )

    expect(model.nodesByType.rule.map((node) => node.sourceId)).toEqual(['rule-1'])
    expect(model.nodesByType.scenario).toEqual([])
    expect(model.nodesByType.requirement).toEqual([])
  })

  it('warns when a chained requirement target is missing', () => {
    const model = buildPipelineFlowModel(
      {
        rules: [],
        scenarios: [baseScenario],
        requirements: [{ ...firstRequirement, next_step_on_met_id: 'missing' }],
      },
      { t },
    )

    expect(model.warnings).toContain('pipeline.flowDiagramMissingRequirementLink')
  })
})

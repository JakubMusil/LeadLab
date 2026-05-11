import { describe, it, expect } from 'vitest'
import {
  createDefaultConditionTree,
  normalizeConditionTree,
  buildConditionTreeNodeLabel,
  buildConditionTreeVisualizationModel,
} from '../conditionTreeVisualization'

const t = (key: string): string => key

describe('conditionTreeVisualization', () => {
  it('creates default condition tree', () => {
    expect(createDefaultConditionTree()).toEqual({
      type: 'group',
      op: 'and',
      conditions: [],
    })
  })

  it('normalizes invalid input to default group', () => {
    const normalized = normalizeConditionTree({ type: 'invalid' })
    expect(normalized).toEqual(createDefaultConditionTree())
  })

  it('normalizes nested groups and conditions', () => {
    const normalized = normalizeConditionTree({
      type: 'group',
      op: 'or',
      negated: true,
      conditions: [
        {
          type: 'condition',
          source_type: 'standard_field',
          field: 'title',
          operator: 'contains',
          value: 'Deal',
        },
        {
          type: 'group',
          op: 'and',
          conditions: [],
        },
      ],
    })

    expect(normalized.type).toBe('group')
    expect(normalized.op).toBe('or')
    expect(normalized.negated).toBe(true)
    expect(Array.isArray(normalized.conditions)).toBe(true)
    expect((normalized.conditions as unknown[]).length).toBe(2)
  })

  it('builds readable label for condition node', () => {
    const label = buildConditionTreeNodeLabel(
      {
        type: 'condition',
        source_type: 'category_field',
        category_field_key: 'budget',
        operator: 'gte',
        value: 100,
      },
      {
        categoryFieldLabels: { budget: 'Budget' },
        t,
      },
    )
    expect(label).toContain('Budget')
    expect(label).toContain('gte')
  })

  it('builds visualization model with nodes and edges', () => {
    const model = buildConditionTreeVisualizationModel(
      {
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
          {
            type: 'group',
            op: 'or',
            conditions: [
              {
                type: 'condition',
                source_type: 'related_entity',
                entity_type: 'customer',
                operator: 'exists',
              },
            ],
          },
        ],
      },
      { t },
    )

    expect(model.rootId).toBeTruthy()
    expect(model.nodes.length).toBe(4)
    expect(model.edges.length).toBe(3)
    expect(model.nodes.some((node) => node.type === 'group')).toBe(true)
    expect(model.nodes.some((node) => node.type === 'condition')).toBe(true)
  })

  it('normalizes malformed group children to safe defaults', () => {
    const normalized = normalizeConditionTree({
      type: 'group',
      op: 'or',
      conditions: [
        null,
        [],
        'invalid',
        {
          type: 'condition',
          source_type: 'standard_field',
          field: 'title',
          operator: 'contains',
          value: 'Lead',
        },
      ],
    } as unknown as Record<string, unknown>)

    const conditions = normalized.conditions as Record<string, unknown>[]
    expect(conditions).toHaveLength(4)
    expect(conditions[0]).toEqual(createDefaultConditionTree())
    expect(conditions[1]).toEqual(createDefaultConditionTree())
    expect(conditions[2]).toEqual(createDefaultConditionTree())
    expect(conditions[3]).toMatchObject({
      type: 'condition',
      source_type: 'standard_field',
      field: 'title',
    })
  })
})

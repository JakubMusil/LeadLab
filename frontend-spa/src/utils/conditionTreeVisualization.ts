export interface ConditionTreeVisualizationNode {
  id: string
  parentId: string | null
  depth: number
  type: 'group' | 'condition'
  label: string
  negated: boolean
  childIds: string[]
  sourceType?: string
  operator?: string
  raw: Record<string, unknown>
}

export interface ConditionTreeVisualizationEdge {
  id: string
  source: string
  target: string
  type: 'contains'
}

export interface ConditionTreeVisualizationModel {
  rootId: string
  nodes: ConditionTreeVisualizationNode[]
  edges: ConditionTreeVisualizationEdge[]
}

interface BuildVisualizationOptions {
  categoryFieldLabels?: Record<string, string>
  t?: (key: string) => string
}

function translate(
  key: string,
  translator?: (key: string) => string,
): string {
  return translator ? translator(key) : key
}

export function createDefaultConditionTree(): Record<string, unknown> {
  return {
    type: 'group',
    op: 'and',
    conditions: [],
  }
}

export function normalizeConditionTree(tree: Record<string, unknown>): Record<string, unknown> {
  if (!tree || Object.keys(tree).length === 0) {
    return createDefaultConditionTree()
  }
  if (tree.type === 'group') {
    const conditions = Array.isArray(tree.conditions) ? tree.conditions : []
    return {
      type: 'group',
      op: tree.op === 'or' ? 'or' : 'and',
      conditions: conditions.map((child) => (
        child && typeof child === 'object' && !Array.isArray(child)
          ? normalizeConditionTree(child as Record<string, unknown>)
          : createDefaultConditionTree()
      )),
      negated: Boolean(tree.negated),
    }
  }
  if (tree.type === 'condition') {
    return {
      type: 'condition',
      source_type: typeof tree.source_type === 'string' ? tree.source_type : '',
      field: typeof tree.field === 'string' ? tree.field : undefined,
      category_field_key: typeof tree.category_field_key === 'string' ? tree.category_field_key : undefined,
      operator: typeof tree.operator === 'string' ? tree.operator : '',
      value: tree.value ?? '',
      activity_type: typeof tree.activity_type === 'string' ? tree.activity_type : undefined,
      tool_type: typeof tree.tool_type === 'string' ? tree.tool_type : undefined,
      entity_type: typeof tree.entity_type === 'string' ? tree.entity_type : undefined,
      time_window:
        tree.time_window && typeof tree.time_window === 'object' && !Array.isArray(tree.time_window)
          ? tree.time_window as Record<string, unknown>
          : undefined,
      negated: Boolean(tree.negated),
    }
  }
  return createDefaultConditionTree()
}

function sourcePreviewLabel(sourceType: string, t?: (key: string) => string): string {
  if (sourceType === 'standard_field') return translate('pipeline.rulesBuilderSourceStandardField', t)
  if (sourceType === 'category_field') return translate('pipeline.rulesBuilderSourceCategoryField', t)
  if (sourceType === 'streamline_activity') return translate('pipeline.rulesBuilderSourceStreamlineActivity', t)
  if (sourceType === 'streamline_tool') return translate('pipeline.rulesBuilderSourceStreamlineTool', t)
  if (sourceType === 'related_entity') return translate('pipeline.rulesBuilderSourceRelatedEntity', t)
  return sourceType || translate('pipeline.rulesBuilderUnknown', t)
}

function buildTimeWindowLabel(
  rawTimeWindow: unknown,
  t?: (key: string) => string,
): string {
  if (!rawTimeWindow || typeof rawTimeWindow !== 'object' || Array.isArray(rawTimeWindow)) return ''
  const timeWindow = rawTimeWindow as Record<string, unknown>
  if (timeWindow.last_hours !== undefined) {
    return ` (${translate('pipeline.rulesBuilderLastHours', t)}: ${String(timeWindow.last_hours)})`
  }
  if (timeWindow.last_days !== undefined) {
    return ` (${translate('pipeline.rulesBuilderLastDays', t)}: ${String(timeWindow.last_days)})`
  }
  return ''
}

export function buildConditionTreeNodeLabel(
  tree: Record<string, unknown>,
  options?: BuildVisualizationOptions,
): string {
  const t = options?.t
  const nodeType = typeof tree.type === 'string' ? tree.type : ''
  if (nodeType === 'group') {
    const opLabel = tree.op === 'or'
      ? translate('pipeline.rulesBuilderGroupOr', t)
      : translate('pipeline.rulesBuilderGroupAnd', t)
    return tree.negated
      ? `${translate('pipeline.rulesBuilderNegatedPrefix', t)} ${opLabel}`
      : opLabel
  }
  if (nodeType !== 'condition') return translate('pipeline.rulesBuilderPreviewInvalid', t)

  const sourceType = typeof tree.source_type === 'string' ? tree.source_type : ''
  const operator = typeof tree.operator === 'string' ? tree.operator : ''
  const value = tree.value
  let target = ''
  if (sourceType === 'standard_field') target = String(tree.field || translate('pipeline.rulesBuilderMissingField', t))
  if (sourceType === 'category_field') {
    const key = String(tree.category_field_key || '')
    target = key
      ? (options?.categoryFieldLabels?.[key] || key)
      : translate('pipeline.rulesBuilderMissingField', t)
  }
  if (sourceType === 'streamline_activity') target = String(tree.activity_type || translate('pipeline.rulesBuilderMissingActivity', t))
  if (sourceType === 'streamline_tool') target = String(tree.tool_type || translate('pipeline.rulesBuilderMissingTool', t))
  if (sourceType === 'related_entity') target = String(tree.entity_type || translate('pipeline.rulesBuilderMissingEntity', t))

  const valueText = value === undefined || value === null || value === '' ? '' : ` "${String(value)}"`
  const timeWindowText = buildTimeWindowLabel(tree.time_window, t)
  const preview = `${sourcePreviewLabel(sourceType, t)} → ${target} ${operator}${valueText}${timeWindowText}`.trim()
  return tree.negated ? `${translate('pipeline.rulesBuilderNegatedPrefix', t)} ${preview}` : preview
}

export function buildConditionTreeVisualizationModel(
  tree: Record<string, unknown>,
  options?: BuildVisualizationOptions,
): ConditionTreeVisualizationModel {
  const normalized = normalizeConditionTree(tree)
  const nodes: ConditionTreeVisualizationNode[] = []
  const edges: ConditionTreeVisualizationEdge[] = []
  let nodeCounter = 0
  let edgeCounter = 0

  function visit(
    node: Record<string, unknown>,
    parentId: string | null,
    depth: number,
  ): string {
    const id = `node-${nodeCounter++}`
    const nodeType = node.type === 'condition' ? 'condition' : 'group'
    const visualizationNode: ConditionTreeVisualizationNode = {
      id,
      parentId,
      depth,
      type: nodeType,
      label: buildConditionTreeNodeLabel(node, options),
      negated: Boolean(node.negated),
      childIds: [],
      sourceType: typeof node.source_type === 'string' ? node.source_type : undefined,
      operator: typeof node.operator === 'string' ? node.operator : undefined,
      raw: node,
    }
    nodes.push(visualizationNode)
    if (parentId) {
      edges.push({
        id: `edge-${edgeCounter++}`,
        source: parentId,
        target: id,
        type: 'contains',
      })
    }

    if (nodeType === 'group') {
      const children = Array.isArray(node.conditions) ? node.conditions : []
      children.forEach((child) => {
        if (!child || typeof child !== 'object' || Array.isArray(child)) return
        const childId = visit(child as Record<string, unknown>, id, depth + 1)
        visualizationNode.childIds.push(childId)
      })
    }

    return id
  }

  const rootId = visit(normalized, null, 0)
  return { rootId, nodes, edges }
}

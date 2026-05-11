import { getTriggerTypeLabel } from '@/constants/triggerTypes'

export type PipelineFlowNodeType = 'root' | 'rule' | 'scenario' | 'requirement'
export type PipelineFlowEdgeType = 'contains' | 'activates_scenario' | 'next_step_on_met' | 'next_step_on_unmet'
export type PipelineFlowActiveFilter = 'all' | 'enabled' | 'disabled'
export type PipelineFlowNodeTypeFilter = 'all' | 'rule' | 'scenario' | 'requirement'

export interface PipelineFlowRuleInput {
  id: string
  name: string
  description?: string
  is_active: boolean
  category_id?: string | null
  stage_id?: string | null
  source_stage_id?: string | null
  target_stage_id?: string | null
  trigger_type: string
  effect: string
  severity: string
  priority?: number
  effect_config?: Record<string, unknown>
}

export interface PipelineFlowScenarioInput {
  id: string
  category_id: string
  stage_id: string
  name: string
  description?: string
  activation_condition?: Record<string, unknown>
  recommended_next_stage_id?: string | null
  priority: number
  is_active: boolean
}

export interface PipelineFlowRequirementInput {
  id: string
  scenario_id: string
  name: string
  description?: string
  requirement_type: string
  blocking: boolean
  visible_to_user: boolean
  sort_order: number
  next_step_on_met_id?: string | null
  next_step_on_unmet_id?: string | null
}

export interface PipelineFlowBuildInput {
  rules: PipelineFlowRuleInput[]
  scenarios: PipelineFlowScenarioInput[]
  requirements: PipelineFlowRequirementInput[]
}

export interface PipelineFlowBuildOptions {
  categoryId?: string
  stageId?: string
  triggerType?: string
  activeState?: PipelineFlowActiveFilter
  nodeType?: PipelineFlowNodeTypeFilter
  stageLabels?: Record<string, string>
  t?: (key: string) => string
}

export interface PipelineFlowNode {
  id: string
  sourceId: string
  type: PipelineFlowNodeType
  label: string
  description: string
  active: boolean
  depth: number
  childIds: string[]
  parentId: string | null
  badge?: string
  statusLabel?: string
  meta: Record<string, string | number | boolean | null>
}

export interface PipelineFlowEdge {
  id: string
  source: string
  target: string
  type: PipelineFlowEdgeType
  label: string
}

export type PipelineFlowRequirementLinkIssue = 'missing_target' | 'cross_scenario' | 'cycle'
export type PipelineFlowRequirementLinkBranch = 'met' | 'unmet'

export interface PipelineFlowRequirementLinkDiagnostic {
  id: string
  sourceRequirementId: string
  sourceRequirementLabel: string
  targetRequirementId: string | null
  targetRequirementLabel: string | null
  branch: PipelineFlowRequirementLinkBranch
  edgeType: PipelineFlowEdgeType
  valid: boolean
  issue: PipelineFlowRequirementLinkIssue | null
}

export interface PipelineFlowVisualizationModel {
  rootId: string
  nodes: PipelineFlowNode[]
  edges: PipelineFlowEdge[]
  nodesByType: Record<PipelineFlowNodeTypeFilter, PipelineFlowNode[]>
  requirementLinkDiagnostics: PipelineFlowRequirementLinkDiagnostic[]
  warnings: string[]
}

function translate(key: string, t?: (key: string) => string): string {
  return t ? t(key) : key
}

function matchesActiveFilter(isActive: boolean, activeState: PipelineFlowActiveFilter = 'all'): boolean {
  if (activeState === 'enabled') return isActive
  if (activeState === 'disabled') return !isActive
  return true
}

function matchesRuleScope(
  rule: PipelineFlowRuleInput,
  categoryId?: string,
  stageId?: string,
): boolean {
  if (categoryId && rule.category_id && rule.category_id !== categoryId) return false
  if (!stageId) return true
  const scopedStageIds = [rule.stage_id, rule.source_stage_id, rule.target_stage_id].filter(Boolean)
  return scopedStageIds.length === 0 || scopedStageIds.includes(stageId)
}

function extractScenarioIdFromEffectConfig(effectConfig?: Record<string, unknown>): string | null {
  if (!effectConfig || typeof effectConfig !== 'object') return null
  const candidates = [
    effectConfig.scenario_id,
    effectConfig.stage_scenario_id,
    effectConfig.active_stage_scenario_id,
    effectConfig.activate_scenario_id,
  ]
  const match = candidates.find((value) => typeof value === 'string' && value.trim())
  return match ?? null
}

function nodeMatchesTypeFilter(node: PipelineFlowNode, nodeType: PipelineFlowNodeTypeFilter = 'all'): boolean {
  return node.type === 'root' || nodeType === 'all' || node.type === nodeType
}

function createRootNode(t?: (key: string) => string): PipelineFlowNode {
  return {
    id: 'root',
    sourceId: 'root',
    type: 'root',
    label: translate('pipeline.flowDiagramRootLabel', t),
    description: '',
    active: true,
    depth: 0,
    childIds: [],
    parentId: null,
    meta: {},
  }
}

function buildRuleNode(rule: PipelineFlowRuleInput, t?: (key: string) => string): PipelineFlowNode {
  const triggerLabel = getTriggerTypeLabel(rule.trigger_type, (key, params) => (t ? t(key) : key))
  return {
    id: `rule-${rule.id}`,
    sourceId: rule.id,
    type: 'rule',
    label: rule.name || rule.id,
    description: rule.description || '',
    active: rule.is_active,
    depth: 1,
    childIds: [],
    parentId: 'root',
    badge: `${triggerLabel} · ${rule.effect}`,
    statusLabel: rule.is_active
      ? translate('pipeline.flowDiagramNodeActive', t)
      : translate('pipeline.flowDiagramNodeInactive', t),
    meta: {
      trigger: triggerLabel,
      // Internal-only raw trigger code for logic (class styling/filtering); hidden in UI.
      _triggerCode: rule.trigger_type,
      effect: rule.effect,
      severity: rule.severity,
      priority: rule.priority ?? null,
    },
  }
}

function buildScenarioNode(
  scenario: PipelineFlowScenarioInput,
  stageLabels: Record<string, string> = {},
  t?: (key: string) => string,
): PipelineFlowNode {
  return {
    id: `scenario-${scenario.id}`,
    sourceId: scenario.id,
    type: 'scenario',
    label: scenario.name || scenario.id,
    description: scenario.description || '',
    active: scenario.is_active,
    depth: 1,
    childIds: [],
    parentId: 'root',
    badge: `${translate('pipeline.flowDiagramPriorityLabel', t)} ${scenario.priority}`,
    statusLabel: scenario.is_active
      ? translate('pipeline.flowDiagramNodeActive', t)
      : translate('pipeline.flowDiagramNodeInactive', t),
    meta: {
      priority: scenario.priority,
      stage: stageLabels[scenario.stage_id] || scenario.stage_id,
      activationCondition: scenario.activation_condition && Object.keys(scenario.activation_condition).length > 0
        ? translate('pipeline.flowDiagramActivationConfigured', t)
        : translate('pipeline.flowDiagramActivationAlways', t),
      recommendedNextStage: scenario.recommended_next_stage_id
        ? stageLabels[scenario.recommended_next_stage_id] || scenario.recommended_next_stage_id
        : null,
    },
  }
}

function buildRequirementNode(
  requirement: PipelineFlowRequirementInput,
  scenarioById: Map<string, PipelineFlowScenarioInput>,
  stageLabels: Record<string, string> = {},
  t?: (key: string) => string,
): PipelineFlowNode {
  const scenario = scenarioById.get(requirement.scenario_id)
  return {
    id: `requirement-${requirement.id}`,
    sourceId: requirement.id,
    type: 'requirement',
    label: requirement.name || requirement.id,
    description: requirement.description || '',
    active: requirement.visible_to_user,
    depth: 2,
    childIds: [],
    parentId: `scenario-${requirement.scenario_id}`,
    badge: requirement.blocking
      ? translate('pipeline.flowDiagramRequirementBlocking', t)
      : translate('pipeline.flowDiagramRequirementWarning', t),
    statusLabel: requirement.visible_to_user
      ? translate('pipeline.flowDiagramNodeActive', t)
      : translate('pipeline.flowDiagramNodeInactive', t),
    meta: {
      requirementType: requirement.requirement_type,
      sortOrder: requirement.sort_order,
      blocking: requirement.blocking,
      recommendedNextStage: scenario?.recommended_next_stage_id
        ? stageLabels[scenario.recommended_next_stage_id] || scenario.recommended_next_stage_id
        : null,
    },
  }
}

export function buildPipelineFlowModel(
  input: PipelineFlowBuildInput,
  options: PipelineFlowBuildOptions = {},
): PipelineFlowVisualizationModel {
  const t = options.t
  const root = createRootNode(t)
  const warnings: string[] = []
  const triggerFilter = options.triggerType?.trim() || ''

  const filteredRules = input.rules
    .filter((rule) => matchesRuleScope(rule, options.categoryId, options.stageId))
    // Exact match is intentional: trigger filter now comes from predefined dropdown options.
    .filter((rule) => !triggerFilter || rule.trigger_type === triggerFilter)
    .filter((rule) => matchesActiveFilter(rule.is_active, options.activeState))
    .sort((a, b) => (a.priority ?? 100) - (b.priority ?? 100) || a.name.localeCompare(b.name))

  const filteredScenarios = input.scenarios
    .filter((scenario) => !options.categoryId || scenario.category_id === options.categoryId)
    .filter((scenario) => !options.stageId || scenario.stage_id === options.stageId)
    .filter((scenario) => matchesActiveFilter(scenario.is_active, options.activeState))
    .sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name))

  const scenarioIds = new Set(filteredScenarios.map((scenario) => scenario.id))
  const scenarioById = new Map(filteredScenarios.map((scenario) => [scenario.id, scenario]))
  const filteredRequirements = input.requirements
    .filter((requirement) => scenarioIds.has(requirement.scenario_id))
    .filter((requirement) => matchesActiveFilter(requirement.visible_to_user, options.activeState))
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))

  const allNodes = [
    root,
    ...filteredRules.map((rule) => buildRuleNode(rule, t)),
    ...filteredScenarios.map((scenario) => buildScenarioNode(scenario, options.stageLabels, t)),
    ...filteredRequirements.map((requirement) => buildRequirementNode(requirement, scenarioById, options.stageLabels, t)),
  ]
  const nodeMap = new Map(allNodes.map((node) => [node.id, node]))
  const requirementById = new Map(filteredRequirements.map((requirement) => [requirement.id, requirement]))
  const edges: PipelineFlowEdge[] = []
  const requirementLinkDiagnostics: PipelineFlowRequirementLinkDiagnostic[] = []

  function addEdge(
    source: string,
    target: string,
    type: PipelineFlowEdgeType,
    label: string,
    updateHierarchy = true,
  ) {
    if (!nodeMap.has(source) || !nodeMap.has(target)) return
    edges.push({
      id: `${type}-${source}-${target}`,
      source,
      target,
      type,
      label,
    })
    nodeMap.get(source)?.childIds.push(target)
    if (updateHierarchy) {
      const targetNode = nodeMap.get(target)
      if (targetNode) {
        targetNode.parentId = source
        targetNode.depth = source === 'root' ? 1 : (nodeMap.get(source)?.depth ?? 0) + 1
      }
    }
  }

  filteredRules.forEach((rule) => addEdge('root', `rule-${rule.id}`, 'contains', translate('pipeline.flowDiagramEdgeContains', t)))

  const scenarioIdsLinkedFromRules = new Set<string>()
  filteredRules.forEach((rule) => {
    const scenarioId = extractScenarioIdFromEffectConfig(rule.effect_config)
    if (!scenarioId || !scenarioIds.has(scenarioId)) return
    scenarioIdsLinkedFromRules.add(scenarioId)
    addEdge(
      `rule-${rule.id}`,
      `scenario-${scenarioId}`,
      'activates_scenario',
      translate('pipeline.flowDiagramEdgeActivatesScenario', t),
    )
  })

  filteredScenarios.forEach((scenario) => {
    if (!scenarioIdsLinkedFromRules.has(scenario.id)) {
      addEdge('root', `scenario-${scenario.id}`, 'contains', translate('pipeline.flowDiagramEdgeContains', t))
    }
  })

  filteredRequirements.forEach((requirement) => {
    addEdge(
      `scenario-${requirement.scenario_id}`,
      `requirement-${requirement.id}`,
      'contains',
      translate('pipeline.flowDiagramEdgeContains', t),
    )
  })

  const requirementIds = new Set(filteredRequirements.map((requirement) => requirement.id))
  const requirementLinkCandidates: Array<{
    sourceId: string
    targetId: string | null
    branch: PipelineFlowRequirementLinkBranch
    edgeType: PipelineFlowEdgeType
  }> = []
  filteredRequirements.forEach((requirement) => {
    const links: Array<[string | null | undefined, PipelineFlowRequirementLinkBranch, PipelineFlowEdgeType]> = [
      [requirement.next_step_on_met_id, 'met', 'next_step_on_met'],
      [requirement.next_step_on_unmet_id, 'unmet', 'next_step_on_unmet'],
    ]
    links.forEach(([targetId, branch, edgeType]) => {
      if (!targetId) return
      requirementLinkCandidates.push({
        sourceId: requirement.id,
        targetId,
        branch,
        edgeType,
      })
    })
  })

  const validLinkCandidates = requirementLinkCandidates.filter((candidate) => {
    if (!candidate.targetId || !requirementIds.has(candidate.targetId)) return false
    const source = requirementById.get(candidate.sourceId)
    const target = requirementById.get(candidate.targetId)
    return !!source && !!target && source.scenario_id === target.scenario_id
  })
  const adjacency = new Map<string, Set<string>>()
  validLinkCandidates.forEach((candidate) => {
    if (!candidate.targetId) return
    const links = adjacency.get(candidate.sourceId) ?? new Set<string>()
    links.add(candidate.targetId)
    adjacency.set(candidate.sourceId, links)
  })

  const pathCache = new Map<string, boolean>()
  function hasPath(startId: string, targetId: string): boolean {
    const cacheKey = `${startId}->${targetId}`
    const cachedValue = pathCache.get(cacheKey)
    if (cachedValue !== undefined) return cachedValue
    const stack = [startId]
    const visited = new Set<string>()
    while (stack.length > 0) {
      const nodeId = stack.pop()
      if (!nodeId || visited.has(nodeId)) continue
      if (nodeId === targetId) {
        pathCache.set(cacheKey, true)
        return true
      }
      visited.add(nodeId)
      const nextTargets = adjacency.get(nodeId)
      if (!nextTargets) continue
      nextTargets.forEach((nextTarget) => stack.push(nextTarget))
    }
    pathCache.set(cacheKey, false)
    return false
  }

  requirementLinkCandidates.forEach((candidate) => {
    const sourceRequirement = requirementById.get(candidate.sourceId)
    const sourceRequirementLabel = sourceRequirement?.name || candidate.sourceId
    const targetRequirement = candidate.targetId ? requirementById.get(candidate.targetId) : null
    const targetRequirementLabel = targetRequirement?.name || candidate.targetId

    let issue: PipelineFlowRequirementLinkIssue | null = null
    if (!candidate.targetId || !requirementIds.has(candidate.targetId)) {
      issue = 'missing_target'
      warnings.push(translate('pipeline.flowDiagramMissingRequirementLink', t))
    } else if (!sourceRequirement || !targetRequirement || sourceRequirement.scenario_id !== targetRequirement.scenario_id) {
      issue = 'cross_scenario'
      warnings.push(translate('pipeline.flowDiagramInvalidRequirementScenarioLink', t))
    } else if (hasPath(candidate.targetId, candidate.sourceId)) {
      issue = 'cycle'
      warnings.push(translate('pipeline.flowDiagramRequirementCycleLink', t))
    }

    requirementLinkDiagnostics.push({
      id: `${candidate.edgeType}-${candidate.sourceId}-${candidate.targetId ?? 'missing'}`,
      sourceRequirementId: candidate.sourceId,
      sourceRequirementLabel,
      targetRequirementId: candidate.targetId,
      targetRequirementLabel: targetRequirementLabel || null,
      branch: candidate.branch,
      edgeType: candidate.edgeType,
      valid: issue === null,
      issue,
    })

    if (issue === null && candidate.targetId) {
      addEdge(
        `requirement-${candidate.sourceId}`,
        `requirement-${candidate.targetId}`,
        candidate.edgeType,
        candidate.branch === 'met'
          ? translate('pipeline.flowDiagramEdgeNextStepMet', t)
          : translate('pipeline.flowDiagramEdgeNextStepUnmet', t),
        false,
      )
    }
  })

  const visibleNodes = allNodes.filter((node) => nodeMatchesTypeFilter(node, options.nodeType))
  const visibleNodeIds = new Set(visibleNodes.map((node) => node.id))
  const visibleEdges = edges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
  const visibleDiagnostics = requirementLinkDiagnostics.filter((diagnostic) => {
    const sourceVisible = visibleNodeIds.has(`requirement-${diagnostic.sourceRequirementId}`)
    // Invalid links should stay visible even when the target node is filtered out,
    // otherwise the administrator loses direct feedback that the chain is broken.
    const targetVisible = diagnostic.targetRequirementId
      ? !diagnostic.valid || visibleNodeIds.has(`requirement-${diagnostic.targetRequirementId}`)
      : true
    return sourceVisible && targetVisible
  })
  const visibleNodesByType = {
    all: visibleNodes.filter((node) => node.type !== 'root'),
    rule: visibleNodes.filter((node) => node.type === 'rule'),
    scenario: visibleNodes.filter((node) => node.type === 'scenario'),
    requirement: visibleNodes.filter((node) => node.type === 'requirement'),
  }

  return {
    rootId: root.id,
    nodes: visibleNodes,
    edges: visibleEdges,
    nodesByType: visibleNodesByType,
    requirementLinkDiagnostics: visibleDiagnostics,
    warnings: Array.from(new Set(warnings)),
  }
}

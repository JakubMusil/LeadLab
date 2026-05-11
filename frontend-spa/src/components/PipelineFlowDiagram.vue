<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from '@/composables/useI18n'
import {
  buildPipelineFlowModel,
  type PipelineFlowActiveFilter,
  type PipelineFlowNode,
  type PipelineFlowNodeTypeFilter,
  type PipelineFlowRequirementInput,
  type PipelineFlowRuleInput,
  type PipelineFlowScenarioInput,
} from '@/utils/pipelineFlowVisualization'

interface FlowCategoryOption {
  id: string
  name: string
}

interface FlowStageOption {
  id: string
  name: string
}

const props = withDefaults(defineProps<{
  rules: PipelineFlowRuleInput[]
  scenarios: PipelineFlowScenarioInput[]
  requirements: PipelineFlowRequirementInput[]
  categories: FlowCategoryOption[]
  stages: FlowStageOption[]
  loading?: boolean
  error?: string | null
  initialCategoryId?: string
  initialStageId?: string
}>(), {
  loading: false,
  error: null,
  initialCategoryId: '',
  initialStageId: '',
})

const { t } = useI18n()

const selectedCategoryId = ref(props.initialCategoryId)
const selectedStageId = ref(props.initialStageId)
const triggerFilter = ref('')
const activeFilter = ref<PipelineFlowActiveFilter>('all')
const nodeTypeFilter = ref<PipelineFlowNodeTypeFilter>('all')
const collapsedScenarioIds = ref<Record<string, boolean>>({})
const graphViewportRef = ref<HTMLElement | null>(null)
const zoomLevel = ref(1)
const zoomMin = 0.6
const zoomMax = 1.8
const zoomStep = 0.1
const fallbackNodeLimit = 80
const panPosition = ref({ x: 0, y: 0 })

watch(
  () => props.initialCategoryId,
  (value) => {
    selectedCategoryId.value = value
  },
)

watch(
  () => props.initialStageId,
  (value) => {
    selectedStageId.value = value
  },
)

const stageLabelById = computed<Record<string, string>>(() =>
  props.stages.reduce<Record<string, string>>((acc, stage) => {
    acc[stage.id] = stage.name
    return acc
  }, {}),
)

const filteredStages = computed(() => props.stages)

const model = computed(() =>
  buildPipelineFlowModel(
    {
      rules: props.rules,
      scenarios: props.scenarios,
      requirements: props.requirements,
    },
    {
      categoryId: selectedCategoryId.value || undefined,
      stageId: selectedStageId.value || undefined,
      triggerType: triggerFilter.value,
      activeState: activeFilter.value,
      nodeType: nodeTypeFilter.value,
      stageLabels: stageLabelById.value,
      t,
    },
  ),
)

const diagramNodes = computed(() => model.value.nodes.filter((node) => node.type !== 'root'))
const nodeById = computed<Record<string, PipelineFlowNode>>(() =>
  model.value.nodes.reduce<Record<string, PipelineFlowNode>>((acc, node) => {
    acc[node.id] = node
    return acc
  }, {}),
)

const visibleNodeIds = computed<Set<string>>(() => {
  const hidden = new Set<string>()
  Object.entries(collapsedScenarioIds.value).forEach(([scenarioNodeId, collapsed]) => {
    if (!collapsed) return
    const prefix = `requirement-`
    const scenario = nodeById.value[scenarioNodeId]
    if (!scenario) return
    scenario.childIds
      .filter((childId) => childId.startsWith(prefix))
      .forEach((childId) => hidden.add(childId))
  })
  return new Set(diagramNodes.value.filter((node) => !hidden.has(node.id)).map((node) => node.id))
})

const visibleNodes = computed(() => diagramNodes.value.filter((node) => visibleNodeIds.value.has(node.id)))
const visibleEdges = computed(() =>
  model.value.edges.filter((edge) => visibleNodeIds.value.has(edge.source) && visibleNodeIds.value.has(edge.target)),
)
const visibleRequirementLinkDiagnostics = computed(() => model.value.requirementLinkDiagnostics)
const fallbackActive = computed(() => visibleNodes.value.length > fallbackNodeLimit)
const displayedNodes = computed(() =>
  fallbackActive.value ? visibleNodes.value.slice(0, fallbackNodeLimit) : visibleNodes.value,
)
const displayedNodeIds = computed(() => new Set(displayedNodes.value.map((node) => node.id)))
const displayedEdges = computed(() =>
  visibleEdges.value.filter((edge) => displayedNodeIds.value.has(edge.source) && displayedNodeIds.value.has(edge.target)),
)
const displayedRequirementLinkDiagnostics = computed(() =>
  visibleRequirementLinkDiagnostics.value.filter((link) => displayedNodeIds.value.has(`requirement-${link.sourceRequirementId}`)),
)
const hiddenNodesCount = computed(() => Math.max(0, visibleNodes.value.length - displayedNodes.value.length))
const isEmpty = computed(() => !props.loading && !props.error && displayedNodes.value.length === 0)
const nodeGridClass = computed(() => {
  const count = displayedNodes.value.length
  if (count > 36) return 'grid-cols-1 md:grid-cols-2'
  if (count > 18) return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3'
  return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4'
})
const graphCanvasStyle = computed(() => ({
  transform: `scale(${zoomLevel.value})`,
  transformOrigin: 'top left',
}))
const selectedNodeId = ref<string | null>(null)
const selectedNode = computed<PipelineFlowNode | null>(() =>
  selectedNodeId.value ? nodeById.value[selectedNodeId.value] ?? null : null,
)
const selectedNodeParent = computed<PipelineFlowNode | null>(() => {
  const parentId = selectedNode.value?.parentId
  if (!parentId) return null
  return nodeById.value[parentId] ?? null
})
const selectedNodeChildren = computed<PipelineFlowNode[]>(() =>
  (selectedNode.value?.childIds ?? []).map((id) => nodeById.value[id]).filter((node): node is PipelineFlowNode => !!node),
)
const selectedNodeEdges = computed(() =>
  selectedNodeId.value
    ? displayedEdges.value.filter((edge) => edge.source === selectedNodeId.value || edge.target === selectedNodeId.value)
    : [],
)

watch(visibleNodeIds, (visibleIds) => {
  if (selectedNodeId.value && !visibleIds.has(selectedNodeId.value)) {
    selectedNodeId.value = null
  }
})

watch(displayedNodeIds, (visibleIds) => {
  if (selectedNodeId.value && !visibleIds.has(selectedNodeId.value)) {
    selectedNodeId.value = null
  }
})

function toggleScenario(nodeId: string) {
  collapsedScenarioIds.value = {
    ...collapsedScenarioIds.value,
    [nodeId]: !collapsedScenarioIds.value[nodeId],
  }
}

function isScenarioCollapsed(nodeId: string): boolean {
  return collapsedScenarioIds.value[nodeId] === true
}

function selectNode(nodeId: string) {
  selectedNodeId.value = selectedNodeId.value === nodeId ? null : nodeId
}

function nodeTypeLabel(node: PipelineFlowNode): string {
  if (node.type === 'rule') return t('pipeline.flowDiagramNodeTypeRule')
  if (node.type === 'scenario') return t('pipeline.flowDiagramNodeTypeScenario')
  if (node.type === 'requirement') return t('pipeline.flowDiagramNodeTypeRequirement')
  return node.type
}

function nodeClass(node: PipelineFlowNode): string {
  if (node.type === 'rule') {
    const trigger = String(node.meta.trigger || '')
    let triggerClass = 'ring-1 ring-indigo-100 dark:ring-indigo-800/60'
    if (trigger.includes('field')) {
      triggerClass = 'ring-1 ring-purple-100 dark:ring-purple-800/60'
    } else if (trigger.includes('stage')) {
      triggerClass = 'ring-1 ring-sky-100 dark:ring-sky-800/60'
    } else if (trigger.includes('streamline')) {
      triggerClass = 'ring-1 ring-teal-100 dark:ring-teal-800/60'
    }
    if (node.meta.effect === 'block') return `border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30 ${triggerClass}`
    if (node.meta.effect === 'warning') return `border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 ${triggerClass}`
    return `border-indigo-200 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-950/30 ${triggerClass}`
  }
  if (node.type === 'scenario') return 'border-sky-200 bg-sky-50 dark:border-sky-800 dark:bg-sky-950/30'
  if (node.meta.blocking === true) return 'border-red-200 bg-white dark:border-red-800 dark:bg-gray-800'
  return 'border-amber-200 bg-white dark:border-amber-800 dark:bg-gray-800'
}

function edgeEndpointLabel(nodeId: string): string {
  return nodeById.value[nodeId]?.label || nodeId
}

function requirementBranchLabel(branch: 'met' | 'unmet'): string {
  return branch === 'met' ? t('pipeline.flowDiagramEdgeNextStepMet') : t('pipeline.flowDiagramEdgeNextStepUnmet')
}

function requirementLinkIssueLabel(issue: 'missing_target' | 'cross_scenario' | 'cycle' | null): string {
  if (issue === 'missing_target') return t('pipeline.flowDiagramRequirementLinkMissingTarget')
  if (issue === 'cross_scenario') return t('pipeline.flowDiagramInvalidRequirementScenarioLink')
  if (issue === 'cycle') return t('pipeline.flowDiagramRequirementCycleLink')
  return t('pipeline.flowDiagramRequirementLinkValid')
}

function clampZoom(value: number): number {
  return Math.min(zoomMax, Math.max(zoomMin, Number(value.toFixed(2))))
}

function updateZoom(nextZoom: number) {
  zoomLevel.value = clampZoom(nextZoom)
}

function zoomIn() {
  updateZoom(zoomLevel.value + zoomStep)
}

function zoomOut() {
  updateZoom(zoomLevel.value - zoomStep)
}

function resetView() {
  zoomLevel.value = 1
  const viewport = graphViewportRef.value
  if (!viewport) return
  viewport.scrollTo({ left: 0, top: 0, behavior: 'smooth' })
}

function onViewportWheel(event: WheelEvent) {
  if (!event.ctrlKey && !event.metaKey) return
  event.preventDefault()
  if (event.deltaY < 0) {
    zoomIn()
  } else {
    zoomOut()
  }
}

function onViewportScroll() {
  const viewport = graphViewportRef.value
  if (!viewport) return
  panPosition.value = {
    x: viewport.scrollLeft,
    y: viewport.scrollTop,
  }
}

function panBy(dx: number, dy: number) {
  const viewport = graphViewportRef.value
  if (!viewport) return
  viewport.scrollBy({ left: dx, top: dy, behavior: 'smooth' })
}

function centerOnSelectedNode() {
  if (!selectedNodeId.value) return
  const viewport = graphViewportRef.value
  if (!viewport) return
  const nodeElement = viewport.querySelector<HTMLElement>(`[data-node-id="${selectedNodeId.value}"]`)
  if (nodeElement) {
    nodeElement.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' })
  }
}

function onViewportKeydown(event: KeyboardEvent) {
  if (event.key === '+' || event.key === '=') {
    event.preventDefault()
    zoomIn()
    return
  }
  if (event.key === '-') {
    event.preventDefault()
    zoomOut()
    return
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    panBy(-80, 0)
    return
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault()
    panBy(80, 0)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    panBy(0, -80)
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    panBy(0, 80)
  }
}
</script>

<template>
  <section class="rounded-lg border border-gray-100 bg-gray-50 p-3 space-y-3 dark:border-gray-700 dark:bg-gray-800/50">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <div class="text-sm font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.flowDiagramTitle') }}</div>
        <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('pipeline.flowDiagramSubtitle') }}</p>
      </div>
      <div class="flex flex-wrap gap-1 text-[11px] text-gray-600 dark:text-gray-300" :aria-label="t('pipeline.flowDiagramLegend')">
        <span class="rounded bg-red-50 px-2 py-0.5 text-red-700 dark:bg-red-900/30 dark:text-red-300">{{ t('pipeline.flowDiagramLegendBlock') }}</span>
        <span class="rounded bg-amber-50 px-2 py-0.5 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300">{{ t('pipeline.flowDiagramLegendWarning') }}</span>
        <span class="rounded bg-sky-50 px-2 py-0.5 text-sky-700 dark:bg-sky-900/30 dark:text-sky-300">{{ t('pipeline.flowDiagramLegendScenario') }}</span>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-2 md:grid-cols-5">
      <select
        v-model="selectedCategoryId"
        class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
      >
        <option value="">{{ t('pipeline.allCategories') }}</option>
        <option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option>
      </select>
      <select
        v-model="selectedStageId"
        class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
      >
        <option value="">{{ t('pipeline.rulesFilterStageAll') }}</option>
        <option v-for="stage in filteredStages" :key="stage.id" :value="stage.id">{{ stage.name }}</option>
      </select>
      <input
        v-model="triggerFilter"
        type="text"
        :placeholder="t('pipeline.flowDiagramFilterTrigger')"
        class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
      />
      <select
        v-model="activeFilter"
        class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
      >
        <option value="all">{{ t('pipeline.rulesFilterStateAll') }}</option>
        <option value="enabled">{{ t('pipeline.rulesFilterStateEnabled') }}</option>
        <option value="disabled">{{ t('pipeline.rulesFilterStateDisabled') }}</option>
      </select>
      <select
        v-model="nodeTypeFilter"
        class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
      >
        <option value="all">{{ t('pipeline.flowDiagramFilterNodeTypeAll') }}</option>
        <option value="rule">{{ t('pipeline.flowDiagramNodeTypeRule') }}</option>
        <option value="scenario">{{ t('pipeline.flowDiagramNodeTypeScenario') }}</option>
        <option value="requirement">{{ t('pipeline.flowDiagramNodeTypeRequirement') }}</option>
      </select>
    </div>

    <div v-if="loading" class="text-xs text-gray-500 dark:text-gray-400">{{ t('pipeline.flowDiagramLoading') }}</div>
    <div v-else-if="error" class="text-xs text-red-600 dark:text-red-400">{{ error }}</div>
    <div v-else-if="isEmpty" class="text-xs text-gray-500 dark:text-gray-400">{{ t('pipeline.flowDiagramEmpty') }}</div>

    <template v-else>
      <div v-if="model.warnings.length > 0" class="rounded border border-amber-100 bg-amber-50 p-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300">
        <div v-for="warning in model.warnings" :key="warning">{{ warning }}</div>
      </div>

      <div class="rounded border border-gray-100 bg-white p-2 space-y-2 dark:border-gray-700 dark:bg-gray-800">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="text-[11px] text-gray-500 dark:text-gray-400">
            {{ t('pipeline.flowDiagramViewportHint') }}
          </div>
          <div class="flex flex-wrap items-center gap-1">
            <button
              type="button"
              class="rounded border border-gray-200 bg-white px-2 py-1 text-[11px] text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              :aria-label="t('pipeline.flowDiagramZoomOut')"
              @click="zoomOut"
            >
              {{ t('pipeline.flowDiagramZoomOut') }}
            </button>
            <button
              type="button"
              class="rounded border border-gray-200 bg-white px-2 py-1 text-[11px] text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              :aria-label="t('pipeline.flowDiagramZoomIn')"
              @click="zoomIn"
            >
              {{ t('pipeline.flowDiagramZoomIn') }}
            </button>
            <button
              type="button"
              class="rounded border border-gray-200 bg-white px-2 py-1 text-[11px] text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600 disabled:cursor-not-allowed disabled:opacity-60"
              :aria-label="t('pipeline.flowDiagramCenterSelected')"
              :disabled="!selectedNodeId"
              @click="centerOnSelectedNode"
            >
              {{ t('pipeline.flowDiagramCenterSelected') }}
            </button>
            <button
              type="button"
              class="rounded border border-gray-200 bg-white px-2 py-1 text-[11px] text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              :aria-label="t('pipeline.flowDiagramResetView')"
              @click="resetView"
            >
              {{ t('pipeline.flowDiagramResetView') }}
            </button>
            <span class="rounded bg-gray-100 px-2 py-1 text-[11px] text-gray-600 dark:bg-gray-700 dark:text-gray-300">
              {{ t('pipeline.flowDiagramZoomLevel', { value: Math.round(zoomLevel * 100) }) }}
            </span>
          </div>
        </div>
        <div class="text-[11px] text-gray-500 dark:text-gray-400">
          {{ t('pipeline.flowDiagramPanPosition', { x: panPosition.x, y: panPosition.y }) }}
        </div>
        <div
          v-if="fallbackActive"
          class="rounded border border-amber-100 bg-amber-50 p-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
        >
          {{ t('pipeline.flowDiagramLargeGraphFallback', { count: hiddenNodesCount }) }}
        </div>
        <div
          ref="graphViewportRef"
          class="max-h-[36rem] overflow-auto rounded border border-gray-100 bg-gray-50 p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-900/30 dark:focus:ring-indigo-400"
          role="region"
          tabindex="0"
          :aria-label="t('pipeline.flowDiagramNodesLabel')"
          @wheel="onViewportWheel"
          @scroll="onViewportScroll"
          @keydown="onViewportKeydown"
        >
          <div class="min-w-[42rem] space-y-2" :style="graphCanvasStyle">
            <div class="grid gap-2" :class="nodeGridClass" role="list" :aria-label="t('pipeline.flowDiagramNodesLabel')">
              <article
                v-for="node in displayedNodes"
                :key="node.id"
                :data-node-id="node.id"
                role="listitem"
                class="rounded border p-2 shadow-sm transition-colors"
                :class="[
                  nodeClass(node),
                  'ring-offset-1 ring-offset-white dark:ring-offset-gray-800',
                  selectedNodeId === node.id ? 'ring-2 ring-indigo-500 dark:ring-indigo-400' : 'ring-0',
                ]"
              >
                <div class="flex items-start justify-between gap-2">
                  <div
                    class="min-w-0 flex-1 rounded cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                    role="button"
                    tabindex="0"
                    :aria-label="node.label"
                    @click="selectNode(node.id)"
                    @keydown.enter.prevent="selectNode(node.id)"
                    @keydown.space.prevent="selectNode(node.id)"
                  >
                    <div class="flex flex-wrap items-center gap-1">
                      <span class="rounded bg-white/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600 dark:bg-gray-700/80 dark:text-gray-300">
                        {{ nodeTypeLabel(node) }}
                      </span>
                      <span v-if="node.badge" class="rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-700/80 dark:text-gray-300">
                        {{ node.badge }}
                      </span>
                      <span class="rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-700/80 dark:text-gray-300">
                        {{ node.statusLabel }}
                      </span>
                    </div>
                    <div class="mt-1 text-xs font-semibold text-gray-800 break-words dark:text-gray-100">{{ node.label }}</div>
                    <p v-if="node.description" class="mt-0.5 text-[11px] text-gray-500 break-words dark:text-gray-400">{{ node.description }}</p>
                    <div class="mt-1 space-y-0.5 text-[11px] text-gray-500 dark:text-gray-400">
                      <div v-for="(value, key) in node.meta" :key="key">
                        <template v-if="value !== null && value !== ''">{{ key }}: {{ value }}</template>
                      </div>
                    </div>
                  </div>
                  <button
                    v-if="node.type === 'scenario' && node.childIds.length > 0"
                    type="button"
                    class="shrink-0 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[11px] text-gray-600 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                    :aria-expanded="!isScenarioCollapsed(node.id)"
                    @click.stop="toggleScenario(node.id)"
                  >
                    {{ isScenarioCollapsed(node.id) ? '+' : '−' }}
                  </button>
                </div>
              </article>
            </div>
          </div>
        </div>
      </div>

      <div v-if="displayedEdges.length > 0" class="rounded border border-gray-100 bg-white p-2 dark:border-gray-700 dark:bg-gray-800">
        <div class="mb-1 text-xs font-semibold text-gray-700 dark:text-gray-200">{{ t('pipeline.flowDiagramEdgesTitle') }}</div>
        <ul class="space-y-1 text-[11px] text-gray-600 dark:text-gray-300">
          <li v-for="edge in displayedEdges" :key="edge.id" class="break-words">
            <span class="font-medium">{{ edgeEndpointLabel(edge.source) }}</span>
            <span class="mx-1 text-gray-400 dark:text-gray-500" aria-hidden="true">→</span>
            <span class="font-medium">{{ edgeEndpointLabel(edge.target) }}</span>
            <span class="ml-1 text-gray-400 dark:text-gray-500">({{ edge.label }})</span>
          </li>
        </ul>
      </div>

      <div
        v-if="displayedRequirementLinkDiagnostics.length > 0"
        class="rounded border border-gray-100 bg-white p-2 dark:border-gray-700 dark:bg-gray-800"
      >
        <div class="mb-1 text-xs font-semibold text-gray-700 dark:text-gray-200">
          {{ t('pipeline.flowDiagramRequirementLinksTitle') }}
        </div>
        <ul class="space-y-1 text-[11px] text-gray-600 dark:text-gray-300">
          <li
            v-for="link in displayedRequirementLinkDiagnostics"
            :key="link.id"
            class="rounded border px-2 py-1"
            :class="link.valid
              ? 'border-emerald-200 bg-emerald-50/60 text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/20 dark:text-emerald-300'
              : 'border-red-200 bg-red-50/60 text-red-700 dark:border-red-800/60 dark:bg-red-950/20 dark:text-red-300'"
          >
            <div class="font-medium">
              {{ link.sourceRequirementLabel }}
              <span class="mx-1 text-gray-400 dark:text-gray-500" aria-hidden="true">→</span>
              {{ link.targetRequirementLabel || t('pipeline.flowDiagramRequirementLinkMissingTarget') }}
            </div>
            <div class="text-[10px] opacity-90">
              {{ requirementBranchLabel(link.branch) }} · {{ requirementLinkIssueLabel(link.issue) }}
            </div>
          </li>
        </ul>
      </div>

      <div class="rounded border border-gray-100 bg-white p-2 dark:border-gray-700 dark:bg-gray-800">
        <div class="mb-1 flex items-center justify-between gap-2">
          <div class="text-xs font-semibold text-gray-700 dark:text-gray-200">{{ t('pipeline.flowDiagramNodeDetailTitle') }}</div>
          <button
            v-if="selectedNodeId"
            type="button"
            class="text-[11px] text-gray-500 underline-offset-2 hover:underline dark:text-gray-300"
            :aria-label="t('pipeline.flowDiagramNodeDetailClear')"
            @click="selectedNodeId = null"
          >
            {{ t('pipeline.flowDiagramNodeDetailClear') }}
          </button>
        </div>
        <div v-if="!selectedNode" class="text-xs text-gray-500 dark:text-gray-400">
          {{ t('pipeline.flowDiagramNodeDetailEmpty') }}
        </div>
        <div v-else class="space-y-2 text-[11px] text-gray-600 dark:text-gray-300">
          <div class="text-xs font-semibold text-gray-800 dark:text-gray-100">{{ selectedNode.label }}</div>
          <div v-if="selectedNode.description" class="text-gray-500 dark:text-gray-400">{{ selectedNode.description }}</div>
          <div>
            <span class="font-medium text-gray-700 dark:text-gray-200">{{ t('pipeline.flowDiagramNodeDetailType') }}:</span>
            {{ nodeTypeLabel(selectedNode) }}
          </div>
          <div>
            <span class="font-medium text-gray-700 dark:text-gray-200">{{ t('pipeline.flowDiagramNodeDetailId') }}:</span>
            {{ selectedNode.sourceId }}
          </div>
          <div v-if="selectedNodeParent">
            <span class="font-medium text-gray-700 dark:text-gray-200">{{ t('pipeline.flowDiagramNodeDetailParent') }}:</span>
            {{ selectedNodeParent.label }}
          </div>
          <div>
            <div class="font-medium text-gray-700 dark:text-gray-200">
              {{ t('pipeline.flowDiagramNodeDetailChildren') }} ({{ selectedNodeChildren.length }})
            </div>
            <ul v-if="selectedNodeChildren.length > 0" class="mt-0.5 list-inside list-disc space-y-0.5">
              <li v-for="child in selectedNodeChildren" :key="child.id">{{ child.label }}</li>
            </ul>
          </div>
          <div>
            <div class="font-medium text-gray-700 dark:text-gray-200">{{ t('pipeline.flowDiagramNodeDetailConnections') }}</div>
            <ul v-if="selectedNodeEdges.length > 0" class="mt-0.5 space-y-0.5">
              <li v-for="edge in selectedNodeEdges" :key="edge.id">
                <span class="font-medium">{{ edgeEndpointLabel(edge.source) }}</span>
                <span class="mx-1 text-gray-400 dark:text-gray-500" aria-hidden="true">→</span>
                <span class="font-medium">{{ edgeEndpointLabel(edge.target) }}</span>
                <span class="ml-1 text-gray-400 dark:text-gray-500">({{ edge.label }})</span>
              </li>
            </ul>
            <div v-else class="text-gray-500 dark:text-gray-400">{{ t('pipeline.flowDiagramNodeDetailNoConnections') }}</div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

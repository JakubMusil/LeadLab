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
const isEmpty = computed(() => !props.loading && !props.error && visibleNodes.value.length === 0)

function toggleScenario(nodeId: string) {
  collapsedScenarioIds.value = {
    ...collapsedScenarioIds.value,
    [nodeId]: !collapsedScenarioIds.value[nodeId],
  }
}

function isScenarioCollapsed(nodeId: string): boolean {
  return collapsedScenarioIds.value[nodeId] === true
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
    let triggerClass = 'ring-1 ring-indigo-100'
    if (trigger.includes('field')) {
      triggerClass = 'ring-1 ring-purple-100'
    } else if (trigger.includes('stage')) {
      triggerClass = 'ring-1 ring-sky-100'
    } else if (trigger.includes('streamline')) {
      triggerClass = 'ring-1 ring-teal-100'
    }
    if (node.meta.effect === 'block') return `border-red-200 bg-red-50 ${triggerClass}`
    if (node.meta.effect === 'warning') return `border-amber-200 bg-amber-50 ${triggerClass}`
    return `border-indigo-200 bg-indigo-50 ${triggerClass}`
  }
  if (node.type === 'scenario') return 'border-sky-200 bg-sky-50'
  if (node.meta.blocking === true) return 'border-red-200 bg-white'
  return 'border-amber-200 bg-white'
}

function edgeEndpointLabel(nodeId: string): string {
  return nodeById.value[nodeId]?.label || nodeId
}
</script>

<template>
  <section class="rounded-lg border border-gray-100 bg-gray-50 p-3 space-y-3">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <div class="text-sm font-semibold text-gray-700">{{ t('pipeline.flowDiagramTitle') }}</div>
        <p class="text-xs text-gray-500">{{ t('pipeline.flowDiagramSubtitle') }}</p>
      </div>
      <div class="flex flex-wrap gap-1 text-[11px] text-gray-600" :aria-label="t('pipeline.flowDiagramLegend')">
        <span class="rounded bg-red-50 px-2 py-0.5 text-red-700">{{ t('pipeline.flowDiagramLegendBlock') }}</span>
        <span class="rounded bg-amber-50 px-2 py-0.5 text-amber-700">{{ t('pipeline.flowDiagramLegendWarning') }}</span>
        <span class="rounded bg-sky-50 px-2 py-0.5 text-sky-700">{{ t('pipeline.flowDiagramLegendScenario') }}</span>
      </div>
    </div>

    <div class="grid grid-cols-1 gap-2 md:grid-cols-5">
      <select
        v-model="selectedCategoryId"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
      >
        <option value="">{{ t('pipeline.allCategories') }}</option>
        <option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option>
      </select>
      <select
        v-model="selectedStageId"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
      >
        <option value="">{{ t('pipeline.rulesFilterStageAll') }}</option>
        <option v-for="stage in filteredStages" :key="stage.id" :value="stage.id">{{ stage.name }}</option>
      </select>
      <input
        v-model="triggerFilter"
        type="text"
        :placeholder="t('pipeline.flowDiagramFilterTrigger')"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
      />
      <select
        v-model="activeFilter"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
      >
        <option value="all">{{ t('pipeline.rulesFilterStateAll') }}</option>
        <option value="enabled">{{ t('pipeline.rulesFilterStateEnabled') }}</option>
        <option value="disabled">{{ t('pipeline.rulesFilterStateDisabled') }}</option>
      </select>
      <select
        v-model="nodeTypeFilter"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
      >
        <option value="all">{{ t('pipeline.flowDiagramFilterNodeTypeAll') }}</option>
        <option value="rule">{{ t('pipeline.flowDiagramNodeTypeRule') }}</option>
        <option value="scenario">{{ t('pipeline.flowDiagramNodeTypeScenario') }}</option>
        <option value="requirement">{{ t('pipeline.flowDiagramNodeTypeRequirement') }}</option>
      </select>
    </div>

    <div v-if="loading" class="text-xs text-gray-500">{{ t('pipeline.flowDiagramLoading') }}</div>
    <div v-else-if="error" class="text-xs text-red-600">{{ error }}</div>
    <div v-else-if="isEmpty" class="text-xs text-gray-500">{{ t('pipeline.flowDiagramEmpty') }}</div>

    <template v-else>
      <div v-if="model.warnings.length > 0" class="rounded border border-amber-100 bg-amber-50 p-2 text-xs text-amber-700">
        <div v-for="warning in model.warnings" :key="warning">{{ warning }}</div>
      </div>

      <div class="grid grid-cols-1 gap-2 lg:grid-cols-3" role="list" :aria-label="t('pipeline.flowDiagramNodesLabel')">
        <article
          v-for="node in visibleNodes"
          :key="node.id"
          role="listitem"
          class="rounded border p-2 shadow-sm"
          :class="nodeClass(node)"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-1">
                <span class="rounded bg-white/80 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-600">
                  {{ nodeTypeLabel(node) }}
                </span>
                <span v-if="node.badge" class="rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-gray-600">
                  {{ node.badge }}
                </span>
                <span class="rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-gray-600">
                  {{ node.statusLabel }}
                </span>
              </div>
              <div class="mt-1 text-xs font-semibold text-gray-800 break-words">{{ node.label }}</div>
              <p v-if="node.description" class="mt-0.5 text-[11px] text-gray-500 break-words">{{ node.description }}</p>
              <div class="mt-1 space-y-0.5 text-[11px] text-gray-500">
                <div v-for="(value, key) in node.meta" :key="key">
                  <template v-if="value !== null && value !== ''">{{ key }}: {{ value }}</template>
                </div>
              </div>
            </div>
            <button
              v-if="node.type === 'scenario' && node.childIds.length > 0"
              type="button"
              class="shrink-0 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[11px] text-gray-600 hover:bg-gray-100"
              :aria-expanded="!isScenarioCollapsed(node.id)"
              @click="toggleScenario(node.id)"
            >
              {{ isScenarioCollapsed(node.id) ? '+' : '−' }}
            </button>
          </div>
        </article>
      </div>

      <div v-if="visibleEdges.length > 0" class="rounded border border-gray-100 bg-white p-2">
        <div class="mb-1 text-xs font-semibold text-gray-700">{{ t('pipeline.flowDiagramEdgesTitle') }}</div>
        <ul class="space-y-1 text-[11px] text-gray-600">
          <li v-for="edge in visibleEdges" :key="edge.id" class="break-words">
            <span class="font-medium">{{ edgeEndpointLabel(edge.source) }}</span>
            <span class="mx-1 text-gray-400">→</span>
            <span class="font-medium">{{ edgeEndpointLabel(edge.target) }}</span>
            <span class="ml-1 text-gray-400">({{ edge.label }})</span>
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

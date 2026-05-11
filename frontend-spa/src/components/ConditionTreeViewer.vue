<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from '@/composables/useI18n'
import {
  normalizeConditionTree,
  buildConditionTreeVisualizationModel,
  type ConditionTreeVisualizationNode,
} from '@/utils/conditionTreeVisualization'

interface CategoryFieldOption {
  field_key: string
  label: string
  value_type?: string
}

const props = withDefaults(defineProps<{
  conditionTree: Record<string, unknown>
  categoryFields: CategoryFieldOption[]
  loading?: boolean
  error?: string | null
}>(), {
  loading: false,
  error: null,
})

const { t } = useI18n()
const collapsedNodeIds = ref<Record<string, boolean>>({})
const TREE_NODE_INDENT_PX = 14

const categoryFieldLabelByKey = computed<Record<string, string>>(() =>
  props.categoryFields.reduce<Record<string, string>>((acc, field) => {
    acc[field.field_key] = field.label || field.field_key
    return acc
  }, {}),
)

const normalizedTree = computed(() => normalizeConditionTree(props.conditionTree))
const hasRenderableTree = computed(() => {
  if (normalizedTree.value.type !== 'group') return true
  const children = Array.isArray(normalizedTree.value.conditions) ? normalizedTree.value.conditions : []
  return children.length > 0
})

const visualizationError = ref<string | null>(null)
const visualizationModel = computed(() => {
  visualizationError.value = null
  try {
    return buildConditionTreeVisualizationModel(normalizedTree.value, {
      categoryFieldLabels: categoryFieldLabelByKey.value,
      t,
    })
  } catch (error) {
    console.warn('[ConditionTreeViewer] Failed to build visualization model', error)
    visualizationError.value = t('pipeline.rulesTreeViewerParseFailed')
    return {
      rootId: '',
      nodes: [],
      edges: [],
    }
  }
})

const nodeById = computed<Record<string, ConditionTreeVisualizationNode>>(() =>
  visualizationModel.value.nodes.reduce<Record<string, ConditionTreeVisualizationNode>>((acc, node) => {
    acc[node.id] = node
    return acc
  }, {}),
)

const resolvedError = computed(() => props.error || visualizationError.value)

function isCollapsed(nodeId: string): boolean {
  return collapsedNodeIds.value[nodeId] === true
}

function toggleNode(nodeId: string) {
  collapsedNodeIds.value = {
    ...collapsedNodeIds.value,
    [nodeId]: !collapsedNodeIds.value[nodeId],
  }
}

const visibleNodes = computed<ConditionTreeVisualizationNode[]>(() => {
  const result: ConditionTreeVisualizationNode[] = []
  const rootId = visualizationModel.value.rootId
  if (!rootId) return result
  const map = nodeById.value

  function visit(nodeId: string) {
    const node = map[nodeId]
    if (!node) return
    result.push(node)
    if (isCollapsed(nodeId)) return
    node.childIds.forEach((childId) => visit(childId))
  }

  visit(rootId)
  return result
})
</script>

<template>
  <div class="rounded border border-gray-200 bg-white p-2 dark:border-gray-600 dark:bg-gray-800">
    <div v-if="loading" class="text-xs text-gray-500 dark:text-gray-400">
      {{ t('pipeline.rulesTreeViewerLoading') }}
    </div>
    <div v-else-if="resolvedError" class="text-xs text-red-600 dark:text-red-400">
      {{ resolvedError }}
    </div>
    <div v-else-if="!hasRenderableTree" class="text-xs text-gray-500 dark:text-gray-400">
      {{ t('pipeline.rulesTreeViewerEmpty') }}
    </div>
    <ul v-else class="space-y-1" role="tree" :aria-label="t('pipeline.rulesVisualizationTreeTitle')">
      <li
        v-for="node in visibleNodes"
        :key="node.id"
        class="tree-node"
        role="treeitem"
        :aria-level="node.depth + 1"
        :aria-expanded="node.childIds.length > 0 ? !isCollapsed(node.id) : undefined"
      >
        <div class="flex items-start gap-1" :style="{ paddingLeft: `${node.depth * TREE_NODE_INDENT_PX}px` }">
          <button
            v-if="node.childIds.length > 0"
            type="button"
            class="tree-collapse-btn mt-0.5 h-4 w-4 rounded border border-gray-300 text-[10px] leading-none text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
            :aria-label="isCollapsed(node.id) ? t('pipeline.rulesTreeViewerExpandNode') : t('pipeline.rulesTreeViewerCollapseNode')"
            :aria-expanded="!isCollapsed(node.id)"
            :title="isCollapsed(node.id) ? t('pipeline.rulesTreeViewerExpandNode') : t('pipeline.rulesTreeViewerCollapseNode')"
            @click="toggleNode(node.id)"
          >
            {{ isCollapsed(node.id) ? '+' : '−' }}
          </button>
          <span v-else class="inline-block h-4 w-4"></span>
          <div class="min-w-0 rounded border border-gray-200 px-2 py-1 dark:border-gray-600 dark:bg-gray-800/50">
            <div class="flex items-center gap-1.5">
              <span
                class="rounded px-1 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                :class="node.type === 'group' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300'"
              >
                {{ node.type === 'group' ? t('pipeline.rulesBuilderNodeTypeGroup') : t('pipeline.rulesBuilderNodeTypeCondition') }}
              </span>
              <span v-if="node.negated" class="text-[10px] text-red-600 dark:text-red-400">{{ t('pipeline.rulesBuilderNegatedPrefix') }}</span>
            </div>
            <div class="mt-0.5 text-xs text-gray-700 break-words dark:text-gray-200">
              {{ node.label }}
            </div>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

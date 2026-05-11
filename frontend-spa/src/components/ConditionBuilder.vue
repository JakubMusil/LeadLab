<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '@/composables/useI18n'

interface CategoryFieldOption {
  field_key: string
  label: string
  value_type: string
}

interface ConditionTreeNode {
  type: 'group' | 'condition'
  op?: 'and' | 'or'
  conditions?: ConditionTreeNode[]
  source_type?: string
  field?: string
  category_field_key?: string
  operator?: string
  value?: string | number | boolean | null
  activity_type?: string
  tool_type?: string
  entity_type?: string
  time_window?: {
    last_hours?: number
    last_days?: number
  }
  negated?: boolean
}

const props = withDefaults(defineProps<{
  modelValue: ConditionTreeNode
  categoryFields: CategoryFieldOption[]
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: ConditionTreeNode]
}>()

const { t } = useI18n()

const STANDARD_FIELD_OPTIONS = [
  'title',
  'status',
  'source',
  'value',
  'currency',
  'score',
  'customer_id',
  'assigned_to_id',
  'company_id',
  'contact_person_id',
  'category_id',
  'current_stage_id',
  'parent_id',
  'start_date',
  'end_date',
  'expires_at',
  'notes',
]

const RELATED_ENTITY_OPTIONS = [
  'customer',
  'company',
  'contact_person',
  'assigned_to',
  'category',
  'current_stage',
  'parent',
]

const node = computed<ConditionTreeNode>(() => props.modelValue ?? { type: 'group', op: 'and', conditions: [] })
const isGroup = computed(() => node.value.type === 'group')
const groupConditions = computed<ConditionTreeNode[]>(() => node.value.conditions ?? [])

const sourceOptions = computed(() => [
  { value: 'standard_field', label: t('pipeline.rulesBuilderSourceStandardField') },
  { value: 'category_field', label: t('pipeline.rulesBuilderSourceCategoryField') },
  { value: 'streamline_activity', label: t('pipeline.rulesBuilderSourceStreamlineActivity') },
  { value: 'streamline_tool', label: t('pipeline.rulesBuilderSourceStreamlineTool') },
  { value: 'related_entity', label: t('pipeline.rulesBuilderSourceRelatedEntity') },
])

const operatorOptions = computed(() => {
  if (isGroup.value) return []
  const sourceType = node.value.source_type ?? ''
  if (sourceType === 'standard_field') {
    const selectedField = node.value.field ?? ''
    if (['value', 'score'].includes(selectedField)) {
      return ['eq', 'neq', 'gt', 'gte', 'lt', 'lte']
    }
    return ['eq', 'neq', 'contains']
  }
  if (sourceType === 'category_field') {
    const key = node.value.category_field_key ?? ''
    const field = props.categoryFields.find((item) => item.field_key === key)
    if (field?.value_type && ['number', 'currency', 'date', 'datetime'].includes(field.value_type)) {
      return ['eq', 'neq', 'gt', 'gte', 'lt', 'lte']
    }
    if (field?.value_type === 'multiselect') return ['contains']
    return ['eq', 'neq', 'contains']
  }
  if (sourceType === 'streamline_activity' || sourceType === 'streamline_tool') {
    return ['exists', 'not_exists', 'eq', 'neq', 'gt', 'gte', 'lt', 'lte']
  }
  if (sourceType === 'related_entity') return ['exists', 'not_exists', 'eq', 'neq']
  return ['eq', 'neq', 'contains']
})

const needsValue = computed(() => {
  if (isGroup.value) return false
  const operator = node.value.operator ?? ''
  return !['exists', 'not_exists'].includes(operator)
})

const usesBooleanValue = computed(() => {
  if (!needsValue.value) return false
  const sourceType = node.value.source_type ?? ''
  const operator = node.value.operator ?? ''
  return isBooleanOperatorForSource(sourceType, operator)
})

const usesNumericValue = computed(() => {
  if (!needsValue.value || usesBooleanValue.value) return false
  const sourceType = node.value.source_type ?? ''
  const operator = node.value.operator ?? ''
  return ['streamline_activity', 'streamline_tool'].includes(sourceType) && ['gt', 'gte', 'lt', 'lte'].includes(operator)
})

const timeWindowUnit = computed<'hours' | 'days' | ''>(() => {
  if (!node.value.time_window) return ''
  if (node.value.time_window.last_hours !== undefined) return 'hours'
  if (node.value.time_window.last_days !== undefined) return 'days'
  return ''
})

const timeWindowValue = computed<string>(() => {
  if (!node.value.time_window) return ''
  if (node.value.time_window.last_hours !== undefined) return String(node.value.time_window.last_hours)
  if (node.value.time_window.last_days !== undefined) return String(node.value.time_window.last_days)
  return ''
})

function cloneNode(value: ConditionTreeNode): ConditionTreeNode {
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(value) as ConditionTreeNode
    } catch {
      // fallback below
    }
  }
  return JSON.parse(JSON.stringify(value)) as ConditionTreeNode
}

function isBooleanOperatorForSource(sourceType: string, operator: string): boolean {
  if (sourceType === 'related_entity') return true
  return ['streamline_activity', 'streamline_tool'].includes(sourceType) && ['eq', 'neq'].includes(operator)
}

function defaultConditionNode(): ConditionTreeNode {
  return {
    type: 'condition',
    source_type: '',
    operator: '',
    value: '',
    negated: false,
  }
}

function defaultGroupNode(): ConditionTreeNode {
  return {
    type: 'group',
    op: 'and',
    conditions: [],
    negated: false,
  }
}

function updateNode(patch: Partial<ConditionTreeNode>) {
  emit('update:modelValue', {
    ...cloneNode(node.value),
    ...patch,
  })
}

function updateNodeType(nextType: 'group' | 'condition') {
  if (nextType === 'group') {
    emit('update:modelValue', defaultGroupNode())
    return
  }
  emit('update:modelValue', defaultConditionNode())
}

function updateSourceType(sourceType: string) {
  const next = cloneNode(node.value)
  next.source_type = sourceType
  next.field = undefined
  next.category_field_key = undefined
  next.entity_type = undefined
  next.activity_type = undefined
  next.tool_type = undefined
  next.time_window = undefined
  next.operator = ''
  next.value = ''
  emit('update:modelValue', next)
}

function addCondition() {
  if (!isGroup.value) return
  const next = cloneNode(node.value)
  next.conditions = [...(next.conditions ?? []), defaultConditionNode()]
  emit('update:modelValue', next)
}

function addGroup() {
  if (!isGroup.value) return
  const next = cloneNode(node.value)
  next.conditions = [...(next.conditions ?? []), defaultGroupNode()]
  emit('update:modelValue', next)
}

function updateChild(index: number, child: ConditionTreeNode) {
  if (!isGroup.value) return
  const next = cloneNode(node.value)
  const children = [...(next.conditions ?? [])]
  children[index] = child
  next.conditions = children
  emit('update:modelValue', next)
}

function removeChild(index: number) {
  if (!isGroup.value) return
  const next = cloneNode(node.value)
  next.conditions = (next.conditions ?? []).filter((_, childIndex) => childIndex !== index)
  emit('update:modelValue', next)
}

function updateOperator(operator: string) {
  const next = cloneNode(node.value)
  next.operator = operator
  const sourceType = next.source_type ?? ''
  const needsBoolean = isBooleanOperatorForSource(sourceType, operator)
  if (['exists', 'not_exists'].includes(operator)) {
    next.value = undefined
  } else if (needsBoolean) {
    if (typeof next.value !== 'boolean') next.value = true
  } else if (next.value === null || next.value === undefined) {
    next.value = ''
  }
  emit('update:modelValue', next)
}

function updateTimeWindowUnit(unit: string) {
  const next = cloneNode(node.value)
  if (!unit) {
    next.time_window = undefined
    emit('update:modelValue', next)
    return
  }
  const parsed = Number(timeWindowValue.value)
  const safeValue = Number.isFinite(parsed) && parsed > 0 ? parsed : 1
  next.time_window = unit === 'hours'
    ? { last_hours: safeValue }
    : { last_days: safeValue }
  emit('update:modelValue', next)
}

function updateTimeWindowValue(rawValue: string) {
  const next = cloneNode(node.value)
  const parsed = Number(rawValue)
  if (!Number.isFinite(parsed) || parsed <= 0 || !next.time_window) {
    emit('update:modelValue', next)
    return
  }
  if (next.time_window.last_hours !== undefined) {
    next.time_window = { last_hours: parsed }
  } else {
    next.time_window = { last_days: parsed }
  }
  emit('update:modelValue', next)
}
</script>

<template>
  <div class="space-y-2 rounded border border-gray-200 bg-white p-2">
    <div class="grid grid-cols-1 md:grid-cols-4 gap-2">
      <select
        :value="node.type"
        class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
        :disabled="disabled"
        @change="updateNodeType(($event.target as HTMLSelectElement).value as 'group' | 'condition')"
      >
        <option value="group">{{ t('pipeline.rulesBuilderNodeTypeGroup') }}</option>
        <option value="condition">{{ t('pipeline.rulesBuilderNodeTypeCondition') }}</option>
      </select>

      <label class="inline-flex items-center gap-2 text-xs text-gray-600 md:col-span-3">
        <input
          :checked="node.negated === true"
          type="checkbox"
          class="rounded"
          :disabled="disabled"
          @change="updateNode({ negated: ($event.target as HTMLInputElement).checked })"
        />
        {{ t('pipeline.rulesBuilderNegate') }}
      </label>
    </div>

    <template v-if="isGroup">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <select
          :value="node.op ?? 'and'"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
          :disabled="disabled"
          @change="updateNode({ op: ($event.target as HTMLSelectElement).value as 'and' | 'or' })"
        >
          <option value="and">{{ t('pipeline.rulesBuilderGroupAnd') }}</option>
          <option value="or">{{ t('pipeline.rulesBuilderGroupOr') }}</option>
        </select>
        <div class="flex gap-2">
          <button
            class="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
            :disabled="disabled"
            @click="addCondition"
          >
            {{ t('pipeline.rulesBuilderAddCondition') }}
          </button>
          <button
            class="px-2 py-1 text-xs bg-gray-700 text-white rounded hover:bg-gray-800 disabled:opacity-50"
            :disabled="disabled"
            @click="addGroup"
          >
            {{ t('pipeline.rulesBuilderAddGroup') }}
          </button>
        </div>
      </div>

      <div class="space-y-2">
        <div
          v-for="(child, index) in groupConditions"
          :key="index"
          class="border-l-2 border-indigo-100 pl-2"
        >
          <div class="flex justify-end mb-1">
            <button
              class="text-xs text-red-600 hover:text-red-700"
              :disabled="disabled"
              @click="removeChild(index)"
            >
              {{ t('pipeline.rulesBuilderRemoveNode') }}
            </button>
          </div>
          <ConditionBuilder
            :model-value="child"
            :category-fields="categoryFields"
            :disabled="disabled"
            @update:model-value="updateChild(index, $event)"
          />
        </div>
      </div>
    </template>

    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
        <select
          :value="node.source_type ?? ''"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
          :disabled="disabled"
          @change="updateSourceType(($event.target as HTMLSelectElement).value)"
        >
          <option value="">{{ t('pipeline.rulesBuilderSelectSource') }}</option>
          <option v-for="source in sourceOptions" :key="source.value" :value="source.value">
            {{ source.label }}
          </option>
        </select>

        <template v-if="node.source_type === 'standard_field'">
          <select
            :value="node.field ?? ''"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @change="updateNode({ field: ($event.target as HTMLSelectElement).value })"
          >
            <option value="">{{ t('pipeline.rulesBuilderSelectField') }}</option>
            <option v-for="field in STANDARD_FIELD_OPTIONS" :key="field" :value="field">{{ field }}</option>
          </select>
        </template>

        <template v-else-if="node.source_type === 'category_field'">
          <select
            :value="node.category_field_key ?? ''"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @change="updateNode({ category_field_key: ($event.target as HTMLSelectElement).value })"
          >
            <option value="">{{ t('pipeline.rulesBuilderSelectCategoryField') }}</option>
            <option
              v-for="field in categoryFields"
              :key="field.field_key"
              :value="field.field_key"
            >
              {{ field.label || field.field_key }}
            </option>
          </select>
        </template>

        <template v-else-if="node.source_type === 'streamline_activity'">
          <input
            :value="node.activity_type ?? ''"
            type="text"
            :placeholder="t('pipeline.rulesBuilderActivityTypePlaceholder')"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @input="updateNode({ activity_type: ($event.target as HTMLInputElement).value })"
          />
        </template>

        <template v-else-if="node.source_type === 'streamline_tool'">
          <input
            :value="node.tool_type ?? ''"
            type="text"
            :placeholder="t('pipeline.rulesBuilderToolTypePlaceholder')"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @input="updateNode({ tool_type: ($event.target as HTMLInputElement).value })"
          />
        </template>

        <template v-else-if="node.source_type === 'related_entity'">
          <select
            :value="node.entity_type ?? ''"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @change="updateNode({ entity_type: ($event.target as HTMLSelectElement).value })"
          >
            <option value="">{{ t('pipeline.rulesBuilderSelectEntity') }}</option>
            <option v-for="entity in RELATED_ENTITY_OPTIONS" :key="entity" :value="entity">{{ entity }}</option>
          </select>
        </template>

        <select
          :value="node.operator ?? ''"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
          :disabled="disabled"
          @change="updateOperator(($event.target as HTMLSelectElement).value)"
        >
          <option value="">{{ t('pipeline.rulesBuilderSelectOperator') }}</option>
          <option v-for="operator in operatorOptions" :key="operator" :value="operator">{{ operator }}</option>
        </select>

        <template v-if="needsValue && !usesBooleanValue">
          <input
            :value="node.value === null || node.value === undefined ? '' : String(node.value)"
            :type="usesNumericValue ? 'number' : 'text'"
            :placeholder="t('pipeline.rulesBuilderValuePlaceholder')"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @input="updateNode({ value: usesNumericValue ? Number(($event.target as HTMLInputElement).value) : ($event.target as HTMLInputElement).value })"
          />
        </template>

        <template v-else-if="needsValue && usesBooleanValue">
          <select
            :value="String(node.value ?? true)"
            class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
            :disabled="disabled"
            @change="updateNode({ value: ($event.target as HTMLSelectElement).value === 'true' })"
          >
            <option value="true">{{ t('pipeline.rulesBuilderBooleanTrue') }}</option>
            <option value="false">{{ t('pipeline.rulesBuilderBooleanFalse') }}</option>
          </select>
        </template>
      </div>

      <div v-if="['streamline_activity', 'streamline_tool'].includes(node.source_type ?? '')" class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <select
          :value="timeWindowUnit"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
          :disabled="disabled"
          @change="updateTimeWindowUnit(($event.target as HTMLSelectElement).value)"
        >
          <option value="">{{ t('pipeline.rulesBuilderNoTimeWindow') }}</option>
          <option value="hours">{{ t('pipeline.rulesBuilderLastHours') }}</option>
          <option value="days">{{ t('pipeline.rulesBuilderLastDays') }}</option>
        </select>
        <input
          :value="timeWindowValue"
          type="number"
          min="1"
          class="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
          :placeholder="t('pipeline.rulesBuilderTimeWindowValue')"
          :disabled="disabled || !timeWindowUnit"
          @input="updateTimeWindowValue(($event.target as HTMLInputElement).value)"
        />
      </div>
    </template>
  </div>
</template>

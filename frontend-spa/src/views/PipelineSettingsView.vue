<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { usePipelineStore, type CategoryOut, type StageOut, type CategoryFieldOut } from '@/stores/pipeline'
import {
  useConditionRulesStore,
  type ConditionRuleOut,
  type ConditionRuleIn,
  type ConditionRuleTestEvaluationOut,
} from '@/stores/conditionRules'
import {
  useStageScenariosStore,
  type StageScenarioOut,
  type StageRequirementOut,
} from '@/stores/stageScenarios'
import { useRuleEvaluationLogsStore, type RuleEvaluationLogOut } from '@/stores/ruleEvaluationLogs'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { ConfirmDeleteModal } from '@/components/ui'
import { RULE_TEMPLATE_PRESETS, type RuleTemplatePreset } from '@/constants/ruleTemplates'
import {
  RULE_FORM_TRIGGER_TYPE_OPTIONS,
  TRIGGER_TYPE_OPTIONS,
  getTriggerTypeLabel,
} from '@/constants/triggerTypes'
import { useCan } from '@/composables/useCan'
import {
  createDefaultConditionTree,
  normalizeConditionTree,
} from '@/utils/conditionTreeVisualization'
import {
  PlusIcon,
  TrashIcon,
  PencilSquareIcon,
  CheckIcon,
  XMarkIcon,
  Bars3Icon,
  LockOpenIcon,
} from '@heroicons/vue/24/outline'
import PeoplePicker from '@/components/PeoplePicker.vue'
import ConditionBuilder from '@/components/ConditionBuilder.vue'
import ConditionTreeViewer from '@/components/ConditionTreeViewer.vue'
import PipelineFlowDiagram from '@/components/PipelineFlowDiagram.vue'
import { useMembersStore } from '@/stores/members'

const pipelineStore = usePipelineStore()
const conditionRulesStore = useConditionRulesStore()
const stageScenariosStore = useStageScenariosStore()
const ruleEvaluationLogsStore = useRuleEvaluationLogsStore()
const toast = useToast()
const firmStore = useFirmStore()
const { t } = useI18n()
const { can } = useCan()
const membersStore = useMembersStore()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const selectedCategoryId = ref<string | null>(null)
const editingCategoryId = ref<string | null>(null)
const editingCategoryName = ref('')
const editingCategoryIcon = ref('')
const editingCategoryColor = ref('')

const newCategoryName = ref('')
const newCategoryColor = ref('#3B82F6')
const newCategoryIcon = ref('funnel')
const showNewCategoryForm = ref(false)
const savingCategory = ref(false)

// Stages
const editingStageId = ref<string | null>(null)
const editingStage = ref<Partial<StageOut>>({})
const showNewStageForm = ref(false)
const newStageName = ref('')
const newStageColor = ref('#94A3B8')
const newStageIsTerminal = ref(false)
const newStageIsWon = ref(false)
const savingStage = ref(false)

// Fields
const editingFieldKey = ref<string | null>(null)
const editingField = ref<{
  is_visible: boolean
  is_required: boolean
  value_type: string
  widget: string
  validation_rules: Record<string, unknown>
  label_override: string
  help_text_override: string
}>({
  is_visible: true,
  is_required: false,
  value_type: 'text',
  widget: 'auto',
  validation_rules: {},
  label_override: '',
  help_text_override: '',
})
const showNewFieldForm = ref(false)
const newFieldKey = ref('')
const newFieldIsVisible = ref(true)
const newFieldIsRequired = ref(false)
const newFieldValueType = ref('text')
const newFieldWidget = ref('auto')
const newFieldValidationRules = ref<Record<string, unknown>>({})
const newFieldLabelOverride = ref('')
const newFieldHelpText = ref('')
const savingField = ref(false)

// Condition rules
const ruleFilterCategoryId = ref('')
const ruleFilterStageId = ref('')
const ruleFilterTriggerType = ref('')
const ruleFilterEnabled = ref<'all' | 'enabled' | 'disabled'>('all')
const updatingRuleIds = ref<Record<string, boolean>>({})
const DEFAULT_RULE_PRIORITY = 100
const showRuleForm = ref(false)
const editingRuleId = ref<string | null>(null)
const savingRule = ref(false)
const testingRule = ref(false)
const testRuleId = ref<string | null>(null)
const testRecordId = ref('')
const testEvaluationResult = ref<ConditionRuleTestEvaluationOut | null>(null)
const useRuleJsonEditor = ref(false)
const ruleVisualizationMode = ref<'builder' | 'tree'>('builder')
const ruleConditionTree = ref<Record<string, unknown>>({
  type: 'group',
  op: 'and',
  conditions: [],
})
const ruleConditionTreeText = ref('{}')
const ruleEffectConfigText = ref('{}')
const pendingDeactivateRuleId = ref<string | null>(null)
const pendingDeactivateRuleName = ref('')
const ruleLogsFilterTriggerType = ref('')
const ruleLogsFilterResult = ref('')
const ruleLogsFilterRecordId = ref('')
const ruleLogsFilterRuleId = ref('')
const showRuleTemplates = ref(false)
const ruleFormTriggerTypeOptions = RULE_FORM_TRIGGER_TYPE_OPTIONS
const ruleFilterTriggerTypeOptions = RULE_FORM_TRIGGER_TYPE_OPTIONS
const ruleLogTriggerTypeOptions = TRIGGER_TYPE_OPTIONS

// Stage scenarios
const scenarioFilterStageId = ref('')
const showScenarioForm = ref(false)
const editingScenarioId = ref<string | null>(null)
const savingScenario = ref(false)
const deletingScenarioId = ref<string | null>(null)
const loadingScenarioPreview = ref(false)
const scenarioPreviewRecordId = ref('')
const scenarioPreviewResult = ref<{
  activeScenarioId: string | null
  activeScenarioName: string | null
  activeRequirementsCount: number
  unmetRequirementsCount: number
} | null>(null)
const scenarioActivationCondition = ref<Record<string, unknown>>({
  type: 'group',
  op: 'and',
  conditions: [],
})

const showRequirementForm = ref(false)
const editingRequirementId = ref<string | null>(null)
const savingRequirement = ref(false)
const deletingRequirementId = ref<string | null>(null)
const pipelineFlowRequirements = ref<StageRequirementOut[]>([])
const pipelineFlowLoading = ref(false)
const pipelineFlowError = ref<string | null>(null)
const requirementConditionTree = ref<Record<string, unknown>>({
  type: 'group',
  op: 'and',
  conditions: [],
})

interface ScenarioFormState {
  name: string
  description: string
  recommended_next_stage_id: string
  priority: string
  is_active: boolean
}

const scenarioForm = ref<ScenarioFormState>({
  name: '',
  description: '',
  recommended_next_stage_id: '',
  priority: '100',
  is_active: true,
})

interface RequirementFormState {
  name: string
  description: string
  requirement_type: string
  blocking: boolean
  visible_to_user: boolean
  sort_order: string
}

const requirementForm = ref<RequirementFormState>({
  name: '',
  description: '',
  requirement_type: 'custom',
  blocking: true,
  visible_to_user: true,
  sort_order: '0',
})

interface ConditionTreeValidationIssue {
  path: string
  message: string
}

interface RuleFormState {
  name: string
  description: string
  is_active: boolean
  scope_type: string
  category_id: string
  stage_id: string
  source_stage_id: string
  target_stage_id: string
  trigger_type: string
  effect: string
  severity: string
  activity_type: string
  priority: string
}

const ruleForm = ref<RuleFormState>({
  name: '',
  description: '',
  is_active: true,
  scope_type: 'firm',
  category_id: '',
  stage_id: '',
  source_stage_id: '',
  target_stage_id: '',
  trigger_type: 'record.stage_change_requested',
  effect: 'block',
  severity: 'error',
  activity_type: '',
  priority: String(DEFAULT_RULE_PRIORITY),
})

// Delete confirmations
const pendingDeleteCategoryId = ref<string | null>(null)
const pendingDeleteStageId = ref<string | null>(null)
const pendingDeleteFieldKey = ref<string | null>(null)

// ---------------------------------------------------------------------------
// Category Access Grants
// ---------------------------------------------------------------------------

interface GrantOut {
  id: string
  principal_type: string
  principal_id: string
  principal_name: string | null
  level: string
  granted_by_id: string | null
  granted_at: string
  expires_at: string | null
}

const categoryGrants = ref<GrantOut[]>([])
const categoryGrantsLoading = ref(false)
const showGrantForm = ref(false)
const newGrantPrincipalId = ref('')
const newGrantLevel = ref('view')
const savingGrant = ref(false)

function grantDisplayName(grant: GrantOut): string {
  if (grant.principal_name) return grant.principal_name
  if (grant.principal_type === 'user') return membersStore.displayNameById(grant.principal_id)
  return grant.principal_id
}

async function loadCategoryGrants() {
  if (!selectedCategoryId.value) return
  if (!can('category.manage')) return
  categoryGrantsLoading.value = true
  const res = await api.get<GrantOut[]>(`/api/v1/crm/categories/${selectedCategoryId.value}/grants`)
  categoryGrantsLoading.value = false
  if (res.ok) {
    categoryGrants.value = res.data
  } else {
    categoryGrants.value = []
    console.warn('[PipelineSettings] Failed to load category grants:', res)
  }
}

async function addCategoryGrant() {
  if (!selectedCategoryId.value || !newGrantPrincipalId.value.trim()) return
  savingGrant.value = true
  const res = await api.post<GrantOut>(`/api/v1/crm/categories/${selectedCategoryId.value}/grants`, {
    principal_type: 'user',
    principal_id: newGrantPrincipalId.value.trim(),
    level: newGrantLevel.value,
  })
  savingGrant.value = false
  if (res.ok) {
    toast.success(t('permissions.shareGranted'))
    newGrantPrincipalId.value = ''
    newGrantLevel.value = 'view'
    showGrantForm.value = false
    await loadCategoryGrants()
  } else {
    toast.error(t('permissions.failedToShare'))
  }
}

async function removeCategoryGrant(grantId: string) {
  if (!selectedCategoryId.value) return
  const res = await api.delete(`/api/v1/crm/categories/${selectedCategoryId.value}/grants/${grantId}`)
  if (res.ok) {
    toast.success(t('permissions.shareRevoked'))
    categoryGrants.value = categoryGrants.value.filter((g) => g.id !== grantId)
  } else {
    toast.error(t('permissions.failedToRevoke'))
  }
}

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------

const categories = computed(() => pipelineStore.categories)
const selectedCategory = computed<CategoryOut | undefined>(() =>
  selectedCategoryId.value ? pipelineStore.getCategoryById(selectedCategoryId.value) : undefined,
)
const selectedStages = computed<StageOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : [],
)
const selectedFields = computed<CategoryFieldOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getFieldsForCategory(selectedCategoryId.value) : [],
)
const conditionRules = computed<ConditionRuleOut[]>(() => conditionRulesStore.rules)
const conditionRulesError = computed(() => conditionRulesStore.error)
const conditionRulesLoading = computed(() => conditionRulesStore.loading)
const ruleFilterStages = computed<StageOut[]>(() =>
  ruleFilterCategoryId.value ? pipelineStore.getStagesForCategory(ruleFilterCategoryId.value) : pipelineStore.allStages,
)
const ruleFormStages = computed<StageOut[]>(() =>
  ruleForm.value.category_id ? pipelineStore.getStagesForCategory(ruleForm.value.category_id) : pipelineStore.allStages,
)
const stageScenarios = computed<StageScenarioOut[]>(() => stageScenariosStore.scenarios)
const stageRequirements = computed<StageRequirementOut[]>(() => stageScenariosStore.requirements)
const pipelineFlowStageOptions = computed<StageOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : pipelineStore.allStages,
)
const ruleEvaluationLogs = computed<RuleEvaluationLogOut[]>(() => ruleEvaluationLogsStore.logs)
const ruleEvaluationLogsLoading = computed(() => ruleEvaluationLogsStore.loading)
const ruleEvaluationLogsError = computed(() => ruleEvaluationLogsStore.error)
const ruleEvaluationLogsPage = computed(() => ruleEvaluationLogsStore.page)
const ruleEvaluationLogsHasMore = computed(() => ruleEvaluationLogsStore.hasMore)
const scenarioFilterStages = computed<StageOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : [],
)
const scenarioRecommendedStageOptions = computed<StageOut[]>(() =>
  selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : [],
)
const ruleBuilderCategoryFields = computed(() => {
  const categoryId = ruleForm.value.category_id || selectedCategoryId.value
  if (!categoryId) return []
  return pipelineStore.getFieldsForCategory(categoryId).map((field) => ({
    field_key: field.field_key,
    label: field.label_override || t(`pipeline.fieldKey.${field.field_key}`),
    value_type: field.value_type || 'text',
  }))
})
const ruleBuilderCategoryFieldLabelByKey = computed<Record<string, string>>(() =>
  ruleBuilderCategoryFields.value.reduce<Record<string, string>>((acc, field) => {
    acc[field.field_key] = field.label || field.field_key
    return acc
  }, {}),
)
const selectedTemplateDomain = computed<RuleTemplatePreset['domain'] | null>(() => {
  const categorySlug = selectedCategory.value?.slug?.toLowerCase()
  if (!categorySlug) return null
  if (
    categorySlug.includes('call') ||
    categorySlug.includes('lead') ||
    categorySlug.includes('telefon') ||
    categorySlug.includes('kontakt')
  ) {
    return 'call_center'
  }
  if (
    categorySlug.includes('mont') ||
    categorySlug.includes('instal') ||
    categorySlug.includes('realiz')
  ) {
    return 'installation'
  }
  if (
    categorySlug.includes('it') ||
    categorySlug.includes('servis') ||
    categorySlug.includes('incident') ||
    categorySlug.includes('support')
  ) {
    return 'it_service'
  }
  return null
})
const ruleTemplatePresets = computed<RuleTemplatePreset[]>(() => {
  const domain = selectedTemplateDomain.value
  if (!domain) return RULE_TEMPLATE_PRESETS
  return RULE_TEMPLATE_PRESETS.filter((template) => template.domain === 'all' || template.domain === domain)
})

// All valid field keys (must match BE FIELD_KEY_CHOICES)
const ALL_FIELD_KEYS = [
  'value_currency',
  'date_range',
  'expires_at',
  'notes',
  'source',
  'origin_record',
] as const

// Field keys not yet configured for the selected category
const availableFieldKeys = computed(() =>
  ALL_FIELD_KEYS.filter((k) => !selectedFields.value.some((f) => f.field_key === k)),
)

// ---------------------------------------------------------------------------
// Role/permissions
// ---------------------------------------------------------------------------
const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

async function loadMembers() {
  if (!firmId.value) return
  await membersStore.fetchMembers(firmId.value)
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

onMounted(async () => {
  await loadMembers()
  if (pipelineStore.categories.length === 0) {
    await pipelineStore.fetchCategories()
  }
  if (pipelineStore.categories.length > 0 && !selectedCategoryId.value) {
    selectedCategoryId.value = pipelineStore.categories[0]!.id
  }
})

// Reload grants when selected category changes
watch(selectedCategoryId, () => {
  categoryGrants.value = []
  if (selectedCategoryId.value) void loadCategoryGrants()
  ruleFilterCategoryId.value = selectedCategoryId.value ?? ''
  ruleFilterStageId.value = ''
  void loadConditionRules()
  scenarioFilterStageId.value = selectedStages.value[0]?.id ?? ''
  resetScenarioForm()
  resetRequirementForm()
  stageScenariosStore.clearRequirements()
  pipelineFlowRequirements.value = []
  void loadRuleEvaluationLogs(1)
  if (selectedCategoryId.value && scenarioFilterStageId.value) void loadStageScenarios()
})

watch(scenarioFilterStageId, () => {
  resetScenarioForm()
  resetRequirementForm()
  stageScenariosStore.clearRequirements()
  pipelineFlowRequirements.value = []
  if (selectedCategoryId.value && scenarioFilterStageId.value) void loadStageScenarios()
})

// ---------------------------------------------------------------------------
// Category actions
// ---------------------------------------------------------------------------

function selectCategory(id: string) {
  selectedCategoryId.value = id
  cancelEditCategory()
  cancelEditStage()
  showNewStageForm.value = false
  cancelEditField()
  showNewFieldForm.value = false
  showGrantForm.value = false
  resetScenarioForm()
  resetRequirementForm()
}

function stageNameById(stageId: string | null): string {
  if (!stageId) return '—'
  const stage = pipelineStore.allStages.find((item) => item.id === stageId)
  return stage?.name || stageId
}

function startEditCategory(cat: CategoryOut) {
  editingCategoryId.value = cat.id
  editingCategoryName.value = cat.name
  editingCategoryIcon.value = cat.icon
  editingCategoryColor.value = cat.color || '#3B82F6'
}

function cancelEditCategory() {
  editingCategoryId.value = null
  editingCategoryName.value = ''
}

async function saveEditCategory() {
  if (!editingCategoryId.value || !editingCategoryName.value.trim()) return
  savingCategory.value = true
  const result = await pipelineStore.updateCategory(editingCategoryId.value, {
    name: editingCategoryName.value.trim(),
    icon: editingCategoryIcon.value,
    color: editingCategoryColor.value,
  })
  savingCategory.value = false
  if (result.ok) {
    toast.success(t('pipeline.categoryUpdated'))
    cancelEditCategory()
  } else {
    toast.error(result.error ?? t('pipeline.categoryUpdateFailed'))
  }
}

async function createCategory() {
  if (!newCategoryName.value.trim()) return
  savingCategory.value = true
  const result = await pipelineStore.createCategory({
    name: newCategoryName.value.trim(),
    icon: newCategoryIcon.value,
    color: newCategoryColor.value,
  })
  savingCategory.value = false
  if (result.ok && result.data) {
    toast.success(t('pipeline.categoryCreated'))
    newCategoryName.value = ''
    newCategoryColor.value = '#3B82F6'
    newCategoryIcon.value = 'funnel'
    showNewCategoryForm.value = false
    selectedCategoryId.value = result.data.id
  } else {
    toast.error(result.error ?? t('pipeline.categoryCreateFailed'))
  }
}

async function confirmDeleteCategory() {
  if (!pendingDeleteCategoryId.value) return
  const result = await pipelineStore.deleteCategory(pendingDeleteCategoryId.value)
  if (result.ok) {
    toast.success(t('pipeline.categoryDeleted'))
    if (selectedCategoryId.value === pendingDeleteCategoryId.value) {
      selectedCategoryId.value = pipelineStore.categories[0]?.id ?? null
    }
  } else {
    toast.error(result.error ?? t('pipeline.categoryDeleteFailed'))
  }
  pendingDeleteCategoryId.value = null
}

// ---------------------------------------------------------------------------
// Stage actions
// ---------------------------------------------------------------------------

function startEditStage(stage: StageOut) {
  editingStageId.value = stage.id
  editingStage.value = { ...stage }
}

function cancelEditStage() {
  editingStageId.value = null
  editingStage.value = {}
}

async function saveEditStage() {
  if (!selectedCategoryId.value || !editingStageId.value) return
  savingStage.value = true
  const result = await pipelineStore.updateStage(selectedCategoryId.value, editingStageId.value, {
    name: editingStage.value.name,
    label: editingStage.value.label,
    color: editingStage.value.color,
    is_terminal: editingStage.value.is_terminal,
    is_won: editingStage.value.is_won,
  })
  savingStage.value = false
  if (result.ok) {
    toast.success(t('pipeline.stageUpdatedOk'))
    cancelEditStage()
  } else {
    toast.error(result.error ?? t('pipeline.stageUpdateFailed'))
  }
}

async function createStage() {
  if (!selectedCategoryId.value || !newStageName.value.trim()) return
  savingStage.value = true
  const nextOrder = selectedStages.value.length
    ? Math.max(...selectedStages.value.map((s) => s.order)) + 1
    : 0
  const result = await pipelineStore.createStage(selectedCategoryId.value, {
    name: newStageName.value.trim(),
    label: newStageName.value.trim(),
    color: newStageColor.value,
    order: nextOrder,
    is_terminal: newStageIsTerminal.value,
    is_won: newStageIsWon.value,
  })
  savingStage.value = false
  if (result.ok) {
    toast.success(t('pipeline.stageCreated'))
    newStageName.value = ''
    newStageColor.value = '#94A3B8'
    newStageIsTerminal.value = false
    newStageIsWon.value = false
    showNewStageForm.value = false
  } else {
    toast.error(result.error ?? t('pipeline.stageCreateFailed'))
  }
}

async function confirmDeleteStage() {
  if (!pendingDeleteStageId.value || !selectedCategoryId.value) return
  const result = await pipelineStore.deleteStage(selectedCategoryId.value, pendingDeleteStageId.value)
  if (result.ok) {
    toast.success(t('pipeline.stageDeleted'))
  } else {
    toast.error(result.error ?? t('pipeline.stageDeleteFailed'))
  }
  pendingDeleteStageId.value = null
}

// ---------------------------------------------------------------------------
// Drag-and-drop stage reordering
// ---------------------------------------------------------------------------

const draggableStages = computed({
  get: () => selectedCategoryId.value ? pipelineStore.getStagesForCategory(selectedCategoryId.value) : [],
  set: (reordered: StageOut[]) => {
    if (!selectedCategoryId.value) return
    const cat = pipelineStore.getCategoryById(selectedCategoryId.value)
    if (cat) cat.stages = reordered
  },
})

async function onStageDragEnd() {
  if (!selectedCategoryId.value) return
  const stages = pipelineStore.getStagesForCategory(selectedCategoryId.value)
  await Promise.all(
    stages.map((stage, idx) =>
      pipelineStore.updateStage(selectedCategoryId.value!, stage.id, { order: idx }),
    ),
  )
}

// ---------------------------------------------------------------------------
// Field actions
// ---------------------------------------------------------------------------

function startEditField(field: CategoryFieldOut) {
  editingFieldKey.value = field.field_key
  editingField.value = {
    is_visible: field.is_visible,
    is_required: field.is_required,
    value_type: field.value_type || 'text',
    widget: field.widget || 'auto',
    validation_rules: field.validation_rules ? { ...field.validation_rules } : {},
    label_override: field.label_override || '',
    help_text_override: field.help_text_override || '',
  }
}

function cancelEditField() {
  editingFieldKey.value = null
  editingField.value = {
    is_visible: true,
    is_required: false,
    value_type: 'text',
    widget: 'auto',
    validation_rules: {},
    label_override: '',
    help_text_override: '',
  }
}

async function saveEditField() {
  if (!selectedCategoryId.value || !editingFieldKey.value) return
  savingField.value = true
  const result = await pipelineStore.updateField(selectedCategoryId.value, editingFieldKey.value, {
    is_visible: editingField.value.is_visible,
    is_required: editingField.value.is_required,
    value_type: editingField.value.value_type,
    widget: editingField.value.widget,
    validation_rules: editingField.value.validation_rules,
    label_override: editingField.value.label_override,
    help_text_override: editingField.value.help_text_override,
  })
  savingField.value = false
  if (result.ok) {
    toast.success(t('pipeline.fieldUpdated'))
    cancelEditField()
  } else {
    toast.error(result.error ?? t('pipeline.fieldUpdateFailed'))
  }
}

async function createField() {
  if (!selectedCategoryId.value || !newFieldKey.value) return
  savingField.value = true
  const nextOrder = selectedFields.value.length
    ? Math.max(0, ...selectedFields.value.map((f) => f.order)) + 1
    : 0
  const result = await pipelineStore.createField(selectedCategoryId.value, newFieldKey.value, {
    is_visible: newFieldIsVisible.value,
    is_required: newFieldIsRequired.value,
    order: nextOrder,
    value_type: newFieldValueType.value,
    widget: newFieldWidget.value,
    validation_rules: newFieldValidationRules.value,
    label_override: newFieldLabelOverride.value,
    help_text_override: newFieldHelpText.value,
  })
  savingField.value = false
  if (result.ok) {
    toast.success(t('pipeline.fieldCreated'))
    newFieldKey.value = ''
    newFieldIsVisible.value = true
    newFieldIsRequired.value = false
    newFieldValueType.value = 'text'
    newFieldWidget.value = 'auto'
    newFieldValidationRules.value = {}
    newFieldLabelOverride.value = ''
    newFieldHelpText.value = ''
    showNewFieldForm.value = false
  } else {
    toast.error(result.error ?? t('pipeline.fieldCreateFailed'))
  }
}

async function confirmDeleteField() {
  if (!pendingDeleteFieldKey.value || !selectedCategoryId.value) return
  const result = await pipelineStore.deleteField(selectedCategoryId.value, pendingDeleteFieldKey.value)
  if (result.ok) {
    toast.success(t('pipeline.fieldDeleted'))
  } else {
    toast.error(result.error ?? t('pipeline.fieldDeleteFailed'))
  }
  pendingDeleteFieldKey.value = null
}

// ---------------------------------------------------------------------------
// Drag-and-drop field reordering
// ---------------------------------------------------------------------------

const draggableFields = computed({
  get: () => selectedCategoryId.value ? pipelineStore.getFieldsForCategory(selectedCategoryId.value) : [],
  set: (reordered: CategoryFieldOut[]) => {
    if (!selectedCategoryId.value) return
    const cat = pipelineStore.getCategoryById(selectedCategoryId.value)
    if (cat) cat.fields = reordered
  },
})

async function onFieldDragEnd() {
  if (!selectedCategoryId.value) return
  const fields = pipelineStore.getFieldsForCategory(selectedCategoryId.value)
  await Promise.all(
    fields.map((field, idx) =>
      pipelineStore.updateField(selectedCategoryId.value!, field.field_key, { order: idx }),
    ),
  )
}

// ---------------------------------------------------------------------------
// Condition rules actions
// ---------------------------------------------------------------------------

async function loadConditionRules() {
  const isActive =
    ruleFilterEnabled.value === 'all' ? undefined : ruleFilterEnabled.value === 'enabled'
  const categoryIdForFiltering = selectedCategoryId.value || ruleFilterCategoryId.value || undefined
  await conditionRulesStore.fetchRules({
    categoryId: categoryIdForFiltering,
    stageId: ruleFilterStageId.value || undefined,
    triggerType: ruleFilterTriggerType.value || undefined,
    isActive,
  })
}

function resetRuleFilters() {
  ruleFilterCategoryId.value = selectedCategoryId.value ?? ''
  ruleFilterStageId.value = ''
  ruleFilterTriggerType.value = ''
  ruleFilterEnabled.value = 'all'
  void loadConditionRules()
}

function isRuleUpdating(ruleId: string): boolean {
  return updatingRuleIds.value[ruleId] === true
}

function deepCloneObject(value: Record<string, unknown>): Record<string, unknown> {
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(value) as Record<string, unknown>
    } catch {
      // fallback below
    }
  }
  try {
    return JSON.parse(JSON.stringify(value)) as Record<string, unknown>
  } catch {
    return {}
  }
}

function sourcePreviewLabel(sourceType: string): string {
  if (sourceType === 'standard_field') return t('pipeline.rulesBuilderSourceStandardField')
  if (sourceType === 'category_field') return t('pipeline.rulesBuilderSourceCategoryField')
  if (sourceType === 'streamline_activity') return t('pipeline.rulesBuilderSourceStreamlineActivity')
  if (sourceType === 'streamline_tool') return t('pipeline.rulesBuilderSourceStreamlineTool')
  if (sourceType === 'related_entity') return t('pipeline.rulesBuilderSourceRelatedEntity')
  return sourceType || t('pipeline.rulesBuilderUnknown')
}

function buildConditionTreePreview(tree: Record<string, unknown>): string {
  if (!tree || typeof tree !== 'object' || Array.isArray(tree)) {
    return t('pipeline.rulesBuilderPreviewEmpty')
  }
  const nodeType = typeof tree.type === 'string' ? tree.type : ''
  if (nodeType === 'group') {
    const children = Array.isArray(tree.conditions) ? tree.conditions : []
    if (children.length === 0) return t('pipeline.rulesBuilderPreviewEmptyGroup')
    const joinLabel = tree.op === 'or' ? t('pipeline.rulesBuilderGroupOr') : t('pipeline.rulesBuilderGroupAnd')
    const childPreview = children
      .map((child) => (
        child && typeof child === 'object' && !Array.isArray(child)
          ? buildConditionTreePreview(child as Record<string, unknown>)
          : t('pipeline.rulesBuilderPreviewInvalid')
      ))
      .join(` ${joinLabel} `)
    const wrapped = `(${childPreview})`
    return tree.negated ? `${t('pipeline.rulesBuilderNegatedPrefix')} ${wrapped}` : wrapped
  }
  if (nodeType !== 'condition') return t('pipeline.rulesBuilderPreviewInvalid')

  const sourceType = typeof tree.source_type === 'string' ? tree.source_type : ''
  const operator = typeof tree.operator === 'string' ? tree.operator : ''
  const value = tree.value
  let target = ''
  if (sourceType === 'standard_field') target = String(tree.field || t('pipeline.rulesBuilderMissingField'))
  if (sourceType === 'category_field') {
    const key = String(tree.category_field_key || '')
    target = key
      ? (ruleBuilderCategoryFieldLabelByKey.value[key] || key)
      : t('pipeline.rulesBuilderMissingField')
  }
  if (sourceType === 'streamline_activity') target = String(tree.activity_type || t('pipeline.rulesBuilderMissingActivity'))
  if (sourceType === 'streamline_tool') target = String(tree.tool_type || t('pipeline.rulesBuilderMissingTool'))
  if (sourceType === 'related_entity') target = String(tree.entity_type || t('pipeline.rulesBuilderMissingEntity'))
  const valueText = value === undefined || value === null || value === '' ? '' : ` "${String(value)}"`
  const preview = `${sourcePreviewLabel(sourceType)} → ${target} ${operator}${valueText}`.trim()
  return tree.negated ? `${t('pipeline.rulesBuilderNegatedPrefix')} ${preview}` : preview
}

function validateConditionTreeNode(node: Record<string, unknown>, path: string): ConditionTreeValidationIssue[] {
  const issues: ConditionTreeValidationIssue[] = []
  const nodeType = typeof node.type === 'string' ? node.type : ''
  if (nodeType === 'group') {
    const op = node.op
    if (op !== 'and' && op !== 'or') {
      issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingGroupOperator') })
    }
    const children = Array.isArray(node.conditions) ? node.conditions : []
    if (children.length === 0) {
      issues.push({ path, message: t('pipeline.rulesBuilderValidationEmptyGroup') })
      return issues
    }
    children.forEach((child, index) => {
      if (!child || typeof child !== 'object' || Array.isArray(child)) {
        issues.push({
          path: `${path}.${index}`,
          message: t('pipeline.rulesBuilderValidationInvalidNode'),
        })
        return
      }
      issues.push(...validateConditionTreeNode(child as Record<string, unknown>, `${path}.${index}`))
    })
    return issues
  }
  if (nodeType !== 'condition') {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationInvalidNode') })
    return issues
  }

  const sourceType = typeof node.source_type === 'string' ? node.source_type : ''
  const operator = typeof node.operator === 'string' ? node.operator : ''
  const allowedSourceTypes = ['standard_field', 'category_field', 'streamline_activity', 'streamline_tool', 'related_entity']
  if (!sourceType) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingSource') })
  } else if (!allowedSourceTypes.includes(sourceType)) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationInvalidSourceType') })
  }
  if (!operator) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingOperator') })
  }

  if (sourceType === 'standard_field' && !String(node.field ?? '').trim()) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingField') })
  }
  if (sourceType === 'category_field' && !String(node.category_field_key ?? '').trim()) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingCategoryField') })
  }
  if (sourceType === 'streamline_activity' && !String(node.activity_type ?? '').trim()) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingActivity') })
  }
  if (sourceType === 'streamline_tool' && !String(node.tool_type ?? '').trim()) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingTool') })
  }
  if (sourceType === 'related_entity' && !String(node.entity_type ?? '').trim()) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingEntity') })
  }

  const requiresValue = !['exists', 'not_exists'].includes(operator)
  const value = node.value
  if (requiresValue && (value === undefined || value === null || String(value).trim() === '')) {
    issues.push({ path, message: t('pipeline.rulesBuilderValidationMissingValue') })
  }

  const rawTimeWindow = node.time_window
  if (rawTimeWindow !== undefined) {
    if (!rawTimeWindow || typeof rawTimeWindow !== 'object' || Array.isArray(rawTimeWindow)) {
      issues.push({ path, message: t('pipeline.rulesBuilderValidationInvalidTimeWindow') })
    } else {
      const timeWindow = rawTimeWindow as Record<string, unknown>
      const hasHours = timeWindow.last_hours !== undefined
      const hasDays = timeWindow.last_days !== undefined
      if (!hasHours && !hasDays) {
        issues.push({ path, message: t('pipeline.rulesBuilderValidationInvalidTimeWindow') })
      } else if (hasHours && hasDays) {
        issues.push({ path, message: t('pipeline.rulesBuilderValidationInvalidTimeWindow') })
      } else {
        const rawAmount = hasHours ? timeWindow.last_hours : timeWindow.last_days
        const amount = Number(rawAmount)
        if (!Number.isFinite(amount) || amount <= 0) {
          issues.push({ path, message: t('pipeline.rulesBuilderValidationInvalidTimeWindowValue') })
        }
      }
    }
  }

  return issues
}

const ruleConditionTreePreview = computed(() => buildConditionTreePreview(ruleConditionTree.value))
const ruleConditionTreeIssues = computed(() => {
  if (useRuleJsonEditor.value) return []
  return validateConditionTreeNode(ruleConditionTree.value, 'root')
})

function setRuleEditorMode(useJson: boolean) {
  if (useJson) {
    useRuleJsonEditor.value = true
    ruleConditionTreeText.value = JSON.stringify(ruleConditionTree.value, null, 2)
    return
  }
  try {
    const parsed = parseJsonText(ruleConditionTreeText.value, {})
    ruleConditionTree.value = normalizeConditionTree(parsed)
    useRuleJsonEditor.value = false
  } catch {
    toast.error(t('pipeline.rulesInvalidJson'))
    useRuleJsonEditor.value = true
  }
}

async function toggleRuleActive(rule: ConditionRuleOut, enabled: boolean) {
  if (isRuleUpdating(rule.id)) return
  updatingRuleIds.value = { ...updatingRuleIds.value, [rule.id]: true }
  const result = await conditionRulesStore.updateRule(rule.id, { is_active: enabled })
  if (!result.ok) {
    toast.error(result.error ?? t('pipeline.rulesToggleFailed'))
  }
  const next = { ...updatingRuleIds.value }
  delete next[rule.id]
  updatingRuleIds.value = next
}

function resetRuleForm() {
  showRuleForm.value = false
  editingRuleId.value = null
  useRuleJsonEditor.value = false
  ruleVisualizationMode.value = 'builder'
  ruleForm.value = {
    name: '',
    description: '',
    is_active: true,
    scope_type: 'firm',
    category_id: ruleFilterCategoryId.value || selectedCategoryId.value || '',
    stage_id: '',
    source_stage_id: '',
    target_stage_id: '',
    trigger_type: ruleFilterTriggerTypeOptions.some((option) => option.value === ruleFilterTriggerType.value)
      ? ruleFilterTriggerType.value
      : 'record.stage_change_requested',
    effect: 'block',
    severity: 'error',
    activity_type: '',
    priority: String(DEFAULT_RULE_PRIORITY),
  }
  ruleConditionTree.value = createDefaultConditionTree()
  ruleConditionTreeText.value = JSON.stringify(ruleConditionTree.value, null, 2)
  ruleEffectConfigText.value = '{}'
}

function openCreateRuleForm() {
  resetRuleForm()
  showRuleForm.value = true
}

function applyRuleTemplate(templateId: string) {
  const template = RULE_TEMPLATE_PRESETS.find((item) => item.id === templateId)
  if (!template) return
  resetRuleForm()
  ruleForm.value.name = t(template.nameKey)
  ruleForm.value.description = t(template.descriptionKey)
  ruleForm.value.scope_type = template.scopeType
  ruleForm.value.trigger_type = template.triggerType
  ruleForm.value.effect = template.effect
  ruleForm.value.severity = template.severity
  ruleForm.value.activity_type = template.activityType ?? ''
  ruleConditionTree.value = normalizeConditionTree(deepCloneObject(template.conditionTree))
  ruleConditionTreeText.value = JSON.stringify(ruleConditionTree.value, null, 2)
  const effectConfig = deepCloneObject(template.effectConfig ?? {})
  if (template.messageKey) {
    effectConfig.message = t(template.messageKey)
  }
  ruleEffectConfigText.value = JSON.stringify(effectConfig, null, 2)
  showRuleTemplates.value = false
  showRuleForm.value = true
  toast.success(t('pipeline.rulesTemplateApplied'))
}

function openEditRuleForm(rule: ConditionRuleOut) {
  editingRuleId.value = rule.id
  showRuleForm.value = true
  useRuleJsonEditor.value = false
  ruleVisualizationMode.value = 'builder'
  ruleForm.value = {
    name: rule.name,
    description: rule.description,
    is_active: rule.is_active,
    scope_type: rule.scope_type,
    category_id: rule.category_id ?? '',
    stage_id: rule.stage_id ?? '',
    source_stage_id: rule.source_stage_id ?? '',
    target_stage_id: rule.target_stage_id ?? '',
    trigger_type: rule.trigger_type,
    effect: rule.effect,
    severity: rule.severity,
    activity_type: rule.activity_type,
    priority: String(rule.priority ?? DEFAULT_RULE_PRIORITY),
  }
  const normalizedTree = normalizeConditionTree(deepCloneObject(rule.condition_tree ?? {}))
  ruleConditionTree.value = normalizedTree
  ruleConditionTreeText.value = JSON.stringify(normalizedTree, null, 2)
  ruleEffectConfigText.value = JSON.stringify(rule.effect_config ?? {}, null, 2)
}

function parseJsonText(raw: string, fallback: Record<string, unknown>): Record<string, unknown> {
  const text = raw.trim()
  if (!text) return fallback
  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch {
    throw new Error('invalid_json')
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('invalid_json')
  }
  return parsed as Record<string, unknown>
}

function parseRulePriority(value: string): number | null {
  if (!value.trim()) return DEFAULT_RULE_PRIORITY
  const priority = Number(value)
  if (!Number.isInteger(priority) || priority < 0) return null
  return priority
}

function buildRulePayload(priority: number): ConditionRuleIn {
  const conditionTree = useRuleJsonEditor.value
    ? parseJsonText(ruleConditionTreeText.value, {})
    : deepCloneObject(ruleConditionTree.value)
  return {
    name: ruleForm.value.name.trim(),
    description: ruleForm.value.description.trim(),
    is_active: ruleForm.value.is_active,
    scope_type: ruleForm.value.scope_type,
    category_id: ruleForm.value.category_id || null,
    stage_id: ruleForm.value.stage_id || null,
    source_stage_id: ruleForm.value.source_stage_id || null,
    target_stage_id: ruleForm.value.target_stage_id || null,
    trigger_type: ruleForm.value.trigger_type,
    condition_tree: conditionTree,
    effect: ruleForm.value.effect,
    severity: ruleForm.value.severity,
    effect_config: parseJsonText(ruleEffectConfigText.value, {}),
    activity_type: ruleForm.value.activity_type.trim(),
    priority,
  }
}

async function submitRuleForm() {
  if (savingRule.value) return
  if (!ruleForm.value.name.trim()) {
    toast.error(t('pipeline.rulesNameRequired'))
    return
  }
  if (!ruleForm.value.trigger_type.trim()) {
    toast.error(t('pipeline.rulesTriggerRequired'))
    return
  }

  if (!useRuleJsonEditor.value && ruleConditionTreeIssues.value.length > 0) {
    toast.error(t('pipeline.rulesBuilderValidationError'))
    return
  }

  const parsedPriority = parseRulePriority(ruleForm.value.priority)
  if (parsedPriority === null) {
    toast.error(t('pipeline.rulesPriorityInvalid'))
    return
  }

  let payload: ConditionRuleIn
  try {
    payload = buildRulePayload(parsedPriority)
  } catch (error) {
    const message = error instanceof Error && error.message
      ? `${t('pipeline.rulesInvalidJson')} (${error.message})`
      : t('pipeline.rulesInvalidJson')
    toast.error(message)
    return
  }

  savingRule.value = true
  const isEdit = Boolean(editingRuleId.value)
  const result = isEdit && editingRuleId.value
    ? await conditionRulesStore.updateRule(editingRuleId.value, payload)
    : await conditionRulesStore.createRule(payload)
  savingRule.value = false

  if (!result.ok) {
    toast.error(result.error ?? t(isEdit ? 'pipeline.rulesUpdateFailed' : 'pipeline.rulesCreateFailed'))
    return
  }

  toast.success(t(isEdit ? 'pipeline.rulesUpdated' : 'pipeline.rulesCreated'))
  resetRuleForm()
  await loadConditionRules()
}

function requestDeactivateRule(rule: ConditionRuleOut) {
  pendingDeactivateRuleId.value = rule.id
  pendingDeactivateRuleName.value = rule.name
}

async function confirmDeactivateRule() {
  if (!pendingDeactivateRuleId.value) return
  const result = await conditionRulesStore.deactivateRule(pendingDeactivateRuleId.value)
  if (!result.ok) {
    toast.error(result.error ?? t('pipeline.rulesDeactivateFailed'))
    return
  }
  toast.success(t('pipeline.rulesDeactivated'))
  pendingDeactivateRuleId.value = null
  pendingDeactivateRuleName.value = ''
  await loadConditionRules()
}

async function copyRule(rule: ConditionRuleOut) {
  const result = await conditionRulesStore.createRuleFromExisting(rule, {
    name: `${rule.name} (${t('pipeline.rulesCopySuffix')})`,
  })
  if (!result.ok) {
    toast.error(result.error ?? t('pipeline.rulesCopyFailed'))
    return
  }
  toast.success(t('pipeline.rulesCopied'))
  await loadConditionRules()
}

function openRuleTest(rule: ConditionRuleOut) {
  testRuleId.value = rule.id
  testRecordId.value = ''
  testEvaluationResult.value = null
}

function closeRuleTest() {
  testRuleId.value = null
  testRecordId.value = ''
  testEvaluationResult.value = null
}

async function runRuleTestEvaluation() {
  if (!testRuleId.value) return
  if (!testRecordId.value.trim()) {
    toast.error(t('pipeline.rulesTestRecordRequired'))
    return
  }
  testingRule.value = true
  const result = await conditionRulesStore.testEvaluation({
    rule_id: testRuleId.value,
    record_id: testRecordId.value.trim(),
  })
  testingRule.value = false
  if (!result.ok || !result.data) {
    toast.error(result.error ?? t('pipeline.rulesTestFailed'))
    return
  }
  testEvaluationResult.value = result.data
}

async function loadRuleEvaluationLogs(page = 1) {
  const result = await ruleEvaluationLogsStore.fetchLogs({
    triggerType: ruleLogsFilterTriggerType.value || undefined,
    result: ruleLogsFilterResult.value.trim() || undefined,
    recordId: ruleLogsFilterRecordId.value.trim() || undefined,
    ruleId: ruleLogsFilterRuleId.value.trim() || undefined,
    page,
    pageSize: 50,
  })
  if (!result.ok) {
    toast.error(result.error ?? t('pipeline.ruleLogsLoadFailed'))
  }
}

function triggerTypeLabel(triggerType: string): string {
  // Keep a local wrapper so templates stay compact and do not repeat passing `t`.
  return getTriggerTypeLabel(triggerType, t)
}

function resetRuleEvaluationLogFilters() {
  ruleLogsFilterTriggerType.value = ''
  ruleLogsFilterResult.value = ''
  ruleLogsFilterRecordId.value = ''
  ruleLogsFilterRuleId.value = ''
  void loadRuleEvaluationLogs(1)
}

function loadNextRuleEvaluationLogsPage() {
  if (!ruleEvaluationLogsHasMore.value || ruleEvaluationLogsLoading.value) return
  void loadRuleEvaluationLogs(ruleEvaluationLogsPage.value + 1)
}

function loadPreviousRuleEvaluationLogsPage() {
  if (ruleEvaluationLogsPage.value <= 1 || ruleEvaluationLogsLoading.value) return
  void loadRuleEvaluationLogs(ruleEvaluationLogsPage.value - 1)
}

// ---------------------------------------------------------------------------
// Stage scenarios actions
// ---------------------------------------------------------------------------

function parseNonNegativeInteger(value: string, defaultValue: number): number | null {
  if (!value.trim()) return defaultValue
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 0) return null
  return parsed
}

async function loadStageScenarios() {
  if (!selectedCategoryId.value || !scenarioFilterStageId.value) return
  const result = await stageScenariosStore.fetchScenarios(selectedCategoryId.value, scenarioFilterStageId.value)
  if (result.ok) {
    await loadPipelineFlowRequirements()
  } else {
    pipelineFlowRequirements.value = []
    pipelineFlowError.value = result.error ?? t('pipeline.flowDiagramLoadFailed')
  }
}

async function loadPipelineFlowRequirements() {
  pipelineFlowError.value = null
  pipelineFlowRequirements.value = []
  const scenarios = stageScenariosStore.scenarios
  if (scenarios.length === 0) return
  pipelineFlowLoading.value = true
  try {
    const responses = await Promise.all(
      scenarios.map((scenario) =>
        api.get<StageRequirementOut[]>(`/api/v1/crm/scenarios/${scenario.id}/requirements`),
      ),
    )
    const failedIndex = responses.findIndex((response) => !response.ok)
    if (failedIndex !== -1) {
      const failedScenario = scenarios[failedIndex]
      const scenarioName = failedScenario?.name || failedScenario?.id || ''
      pipelineFlowError.value = scenarioName
        ? `${t('pipeline.flowDiagramLoadFailed')} (${scenarioName})`
        : t('pipeline.flowDiagramLoadFailed')
      return
    }
    pipelineFlowRequirements.value = responses.flatMap((response) => response.data)
  } finally {
    pipelineFlowLoading.value = false
  }
}

function resetScenarioForm() {
  showScenarioForm.value = false
  editingScenarioId.value = null
  savingScenario.value = false
  deletingScenarioId.value = null
  scenarioForm.value = {
    name: '',
    description: '',
    recommended_next_stage_id: '',
    priority: '100',
    is_active: true,
  }
  scenarioActivationCondition.value = createDefaultConditionTree()
  scenarioPreviewRecordId.value = ''
  scenarioPreviewResult.value = null
}

function openCreateScenarioForm() {
  resetScenarioForm()
  showScenarioForm.value = true
}

function openEditScenarioForm(scenario: StageScenarioOut) {
  showScenarioForm.value = true
  editingScenarioId.value = scenario.id
  scenarioForm.value = {
    name: scenario.name,
    description: scenario.description || '',
    recommended_next_stage_id: scenario.recommended_next_stage_id || '',
    priority: String(scenario.priority ?? 100),
    is_active: scenario.is_active,
  }
  scenarioActivationCondition.value = normalizeConditionTree(
    deepCloneObject(scenario.activation_condition || {}),
  )
  scenarioPreviewResult.value = null
}

function startEditScenario(scenario: StageScenarioOut) {
  openEditScenarioForm(scenario)
  void loadScenarioRequirements()
}

async function submitScenarioForm() {
  if (!selectedCategoryId.value || !scenarioFilterStageId.value) return
  if (!scenarioForm.value.name.trim()) {
    toast.error(t('pipeline.stageScenariosNameRequired'))
    return
  }
  const priority = parseNonNegativeInteger(scenarioForm.value.priority, 100)
  if (priority === null) {
    toast.error(t('pipeline.stageScenariosPriorityInvalid'))
    return
  }

  savingScenario.value = true
  const payload = {
    name: scenarioForm.value.name.trim(),
    description: scenarioForm.value.description.trim(),
    activation_condition: deepCloneObject(scenarioActivationCondition.value),
    recommended_next_stage_id: scenarioForm.value.recommended_next_stage_id || null,
    priority,
    is_active: scenarioForm.value.is_active,
  }
  const isEdit = Boolean(editingScenarioId.value)
  const result = isEdit && editingScenarioId.value
    ? await stageScenariosStore.updateScenario(
      selectedCategoryId.value,
      scenarioFilterStageId.value,
      editingScenarioId.value,
      payload,
    )
    : await stageScenariosStore.createScenario(
      selectedCategoryId.value,
      scenarioFilterStageId.value,
      payload,
    )
  savingScenario.value = false

  if (!result.ok || !result.data) {
    toast.error(
      result.error ?? t(isEdit ? 'pipeline.stageScenariosUpdateFailed' : 'pipeline.stageScenariosCreateFailed'),
    )
    return
  }

  toast.success(t(isEdit ? 'pipeline.stageScenariosUpdated' : 'pipeline.stageScenariosCreated'))
  await loadStageScenarios()
  openEditScenarioForm(result.data)
  await loadScenarioRequirements()
}

async function requestDeleteScenario(scenarioId: string) {
  if (!selectedCategoryId.value || !scenarioFilterStageId.value) return
  if (deletingScenarioId.value) return
  deletingScenarioId.value = scenarioId
  const result = await stageScenariosStore.deleteScenario(
    selectedCategoryId.value,
    scenarioFilterStageId.value,
    scenarioId,
  )
  deletingScenarioId.value = null
  if (!result.ok) {
    toast.error(result.error ?? t('pipeline.stageScenariosDeleteFailed'))
    return
  }
  toast.success(t('pipeline.stageScenariosDeleted'))
  if (editingScenarioId.value === scenarioId) {
    resetScenarioForm()
    resetRequirementForm()
    stageScenariosStore.clearRequirements()
  }
  await loadStageScenarios()
}

async function loadScenarioRequirements() {
  if (!editingScenarioId.value) {
    stageScenariosStore.clearRequirements()
    return
  }
  await stageScenariosStore.fetchRequirements(editingScenarioId.value)
}

function resetRequirementForm() {
  showRequirementForm.value = false
  editingRequirementId.value = null
  savingRequirement.value = false
  deletingRequirementId.value = null
  requirementForm.value = {
    name: '',
    description: '',
    requirement_type: 'custom',
    blocking: true,
    visible_to_user: true,
    sort_order: '0',
  }
  requirementConditionTree.value = createDefaultConditionTree()
}

function openCreateRequirementForm() {
  resetRequirementForm()
  showRequirementForm.value = true
}

function openEditRequirementForm(requirement: StageRequirementOut) {
  showRequirementForm.value = true
  editingRequirementId.value = requirement.id
  requirementForm.value = {
    name: requirement.name,
    description: requirement.description || '',
    requirement_type: requirement.requirement_type,
    blocking: requirement.blocking,
    visible_to_user: requirement.visible_to_user,
    sort_order: String(requirement.sort_order ?? 0),
  }
  requirementConditionTree.value = normalizeConditionTree(
    deepCloneObject(requirement.condition || {}),
  )
}

async function submitRequirementForm() {
  if (!editingScenarioId.value) return
  if (!requirementForm.value.name.trim()) {
    toast.error(t('pipeline.stageRequirementsNameRequired'))
    return
  }
  const sortOrder = parseNonNegativeInteger(requirementForm.value.sort_order, 0)
  if (sortOrder === null) {
    toast.error(t('pipeline.stageRequirementsSortOrderInvalid'))
    return
  }

  savingRequirement.value = true
  const payload = {
    name: requirementForm.value.name.trim(),
    description: requirementForm.value.description.trim(),
    requirement_type: requirementForm.value.requirement_type.trim() || 'custom',
    condition: deepCloneObject(requirementConditionTree.value),
    blocking: requirementForm.value.blocking,
    visible_to_user: requirementForm.value.visible_to_user,
    sort_order: sortOrder,
  }
  const isEdit = Boolean(editingRequirementId.value)
  const result = isEdit && editingRequirementId.value
    ? await stageScenariosStore.updateRequirement(editingScenarioId.value, editingRequirementId.value, payload)
    : await stageScenariosStore.createRequirement(editingScenarioId.value, payload)
  savingRequirement.value = false

  if (!result.ok) {
    toast.error(
      result.error
      ?? t(isEdit ? 'pipeline.stageRequirementsUpdateFailed' : 'pipeline.stageRequirementsCreateFailed'),
    )
    return
  }

  toast.success(t(isEdit ? 'pipeline.stageRequirementsUpdated' : 'pipeline.stageRequirementsCreated'))
  resetRequirementForm()
  await loadScenarioRequirements()
  await loadPipelineFlowRequirements()
}

async function requestDeleteRequirement(requirementId: string) {
  if (!editingScenarioId.value || deletingRequirementId.value) return
  deletingRequirementId.value = requirementId
  const result = await stageScenariosStore.deleteRequirement(editingScenarioId.value, requirementId)
  deletingRequirementId.value = null
  if (!result.ok) {
    toast.error(result.error ?? t('pipeline.stageRequirementsDeleteFailed'))
    return
  }
  toast.success(t('pipeline.stageRequirementsDeleted'))
  if (editingRequirementId.value === requirementId) {
    resetRequirementForm()
  }
  await loadScenarioRequirements()
  await loadPipelineFlowRequirements()
}

async function runScenarioPreview() {
  if (!editingScenarioId.value) return
  if (!scenarioPreviewRecordId.value.trim()) {
    toast.error(t('pipeline.stageScenariosPreviewRecordRequired'))
    return
  }
  loadingScenarioPreview.value = true
  const result = await stageScenariosStore.previewForRecord(scenarioPreviewRecordId.value.trim())
  loadingScenarioPreview.value = false
  if (!result.ok || !result.data) {
    toast.error(result.error ?? t('pipeline.stageScenariosPreviewFailed'))
    return
  }
  const activeRequirements = Array.isArray(result.data.active_stage_requirements)
    ? result.data.active_stage_requirements
    : []
  scenarioPreviewResult.value = {
    activeScenarioId: result.data.active_stage_scenario_id || null,
    activeScenarioName: result.data.active_stage_scenario_name || null,
    activeRequirementsCount: activeRequirements.length,
    unmetRequirementsCount: activeRequirements.filter((item) => item?.is_met === false).length,
  }
}

// ---------------------------------------------------------------------------
// Value type / widget helpers
// ---------------------------------------------------------------------------

const VALUE_TYPES = [
  { value: 'text', label: () => t('pipeline.valueType.text') },
  { value: 'number', label: () => t('pipeline.valueType.number') },
  { value: 'currency', label: () => t('pipeline.valueType.currency') },
  { value: 'date', label: () => t('pipeline.valueType.date') },
  { value: 'datetime', label: () => t('pipeline.valueType.datetime') },
  { value: 'boolean', label: () => t('pipeline.valueType.boolean') },
  { value: 'select', label: () => t('pipeline.valueType.select') },
  { value: 'multiselect', label: () => t('pipeline.valueType.multiselect') },
  { value: 'url', label: () => t('pipeline.valueType.url') },
  { value: 'email', label: () => t('pipeline.valueType.email') },
]

const ALL_WIDGETS = [
  { value: 'auto', label: () => t('pipeline.widget.auto') },
  { value: 'text_input', label: () => t('pipeline.widget.text_input') },
  { value: 'textarea', label: () => t('pipeline.widget.textarea') },
  { value: 'number_input', label: () => t('pipeline.widget.number_input') },
  { value: 'date_picker', label: () => t('pipeline.widget.date_picker') },
  { value: 'datetime_picker', label: () => t('pipeline.widget.datetime_picker') },
  { value: 'toggle', label: () => t('pipeline.widget.toggle') },
  { value: 'select', label: () => t('pipeline.widget.select') },
  { value: 'multiselect', label: () => t('pipeline.widget.multiselect') },
  { value: 'color_picker', label: () => t('pipeline.widget.color_picker') },
  { value: 'currency_input', label: () => t('pipeline.widget.currency_input') },
  { value: 'rich_text', label: () => t('pipeline.widget.rich_text') },
]

/** Widgets relevant to a given value_type */
function widgetsForType(vt: string) {
  const map: Record<string, string[]> = {
    text: ['auto', 'text_input', 'textarea', 'rich_text'],
    number: ['auto', 'number_input'],
    currency: ['auto', 'currency_input', 'number_input'],
    date: ['auto', 'date_picker'],
    datetime: ['auto', 'datetime_picker'],
    boolean: ['auto', 'toggle'],
    select: ['auto', 'select'],
    multiselect: ['auto', 'multiselect'],
    url: ['auto', 'text_input'],
    email: ['auto', 'text_input'],
  }
  const allowed = map[vt] ?? ['auto']
  return ALL_WIDGETS.filter((w) => allowed.includes(w.value))
}

const editWidgets = computed(() => widgetsForType(editingField.value.value_type))
const newWidgets = computed(() => widgetsForType(newFieldValueType.value))

/** When value_type changes, reset widget to 'auto' if no longer compatible */
function onEditValueTypeChange() {
  const allowed = editWidgets.value.map((w) => w.value)
  if (!allowed.includes(editingField.value.widget)) {
    editingField.value.widget = 'auto'
  }
  // reset options if no longer select/multiselect
  if (!['select', 'multiselect'].includes(editingField.value.value_type)) {
    const rules = { ...editingField.value.validation_rules }
    delete rules.options
    editingField.value.validation_rules = rules
  }
}

function onNewValueTypeChange() {
  const allowed = newWidgets.value.map((w) => w.value)
  if (!allowed.includes(newFieldWidget.value)) {
    newFieldWidget.value = 'auto'
  }
  if (!['select', 'multiselect'].includes(newFieldValueType.value)) {
    const rules = { ...newFieldValidationRules.value }
    delete rules.options
    newFieldValidationRules.value = rules
  }
}

/** Computed string of options (one per line) for select/multiselect */
const editOptionsText = computed({
  get: () => {
    const opts = (editingField.value.validation_rules.options as string[] | undefined) ?? []
    return opts.join('\n')
  },
  set: (val: string) => {
    const opts = val.split('\n').map((s) => s.trim()).filter(Boolean)
    editingField.value.validation_rules = { ...editingField.value.validation_rules, options: opts }
  },
})

const newOptionsText = computed({
  get: () => {
    const opts = (newFieldValidationRules.value.options as string[] | undefined) ?? []
    return opts.join('\n')
  },
  set: (val: string) => {
    const opts = val.split('\n').map((s) => s.trim()).filter(Boolean)
    newFieldValidationRules.value = { ...newFieldValidationRules.value, options: opts }
  },
})

/** min/max helpers */
const editMin = computed({
  get: () => String(editingField.value.validation_rules.min ?? ''),
  set: (v: string) => {
    const rules = { ...editingField.value.validation_rules }
    const n = parseFloat(v)
    if (v === '' || isNaN(n)) delete rules.min
    else rules.min = n
    editingField.value.validation_rules = rules
  },
})
const editMax = computed({
  get: () => String(editingField.value.validation_rules.max ?? ''),
  set: (v: string) => {
    const rules = { ...editingField.value.validation_rules }
    const n = parseFloat(v)
    if (v === '' || isNaN(n)) delete rules.max
    else rules.max = n
    editingField.value.validation_rules = rules
  },
})
const newMin = computed({
  get: () => String(newFieldValidationRules.value.min ?? ''),
  set: (v: string) => {
    const rules = { ...newFieldValidationRules.value }
    const n = parseFloat(v)
    if (v === '' || isNaN(n)) delete rules.min
    else rules.min = n
    newFieldValidationRules.value = rules
  },
})
const newMax = computed({
  get: () => String(newFieldValidationRules.value.max ?? ''),
  set: (v: string) => {
    const rules = { ...newFieldValidationRules.value }
    const n = parseFloat(v)
    if (v === '' || isNaN(n)) delete rules.max
    else rules.max = n
    newFieldValidationRules.value = rules
  },
})
const editPattern = computed({
  get: () => String(editingField.value.validation_rules.pattern ?? ''),
  set: (v: string) => {
    const rules = { ...editingField.value.validation_rules }
    if (v === '') delete rules.pattern
    else rules.pattern = v
    editingField.value.validation_rules = rules
  },
})
const newPattern = computed({
  get: () => String(newFieldValidationRules.value.pattern ?? ''),
  set: (v: string) => {
    const rules = { ...newFieldValidationRules.value }
    if (v === '') delete rules.pattern
    else rules.pattern = v
    newFieldValidationRules.value = rules
  },
})
</script>

<template>
  <div class="p-6 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold text-gray-900">{{ t('pipeline.settingsTitle') }}</h1>
    </div>

    <div v-if="pipelineStore.loading" class="text-gray-500 text-sm">{{ t('pipeline.loadingCategories') }}</div>

    <div v-else class="flex gap-6 min-h-[500px]">
      <!-- Left panel: categories -->
      <div class="w-64 flex-shrink-0 space-y-2">
        <div class="text-xs font-semibold uppercase text-gray-400 tracking-wider mb-1">Kategorie</div>

        <div
          v-for="cat in categories"
          :key="cat.id"
          class="group relative flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors"
          :class="selectedCategoryId === cat.id ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-50 text-gray-700'"
          @click="selectCategory(cat.id)"
        >
          <!-- Color dot -->
          <span
            class="w-3 h-3 rounded-full flex-shrink-0"
            :style="{ backgroundColor: cat.color || '#94A3B8' }"
          ></span>

          <!-- Name or inline edit -->
          <template v-if="editingCategoryId === cat.id">
            <input
              v-model="editingCategoryName"
              class="flex-1 text-sm border border-indigo-300 rounded px-1 py-0.5 outline-none"
              @keyup.enter="saveEditCategory"
              @keyup.escape="cancelEditCategory"
              @click.stop
            />
            <button class="p-0.5 text-green-600 hover:text-green-700" @click.stop="saveEditCategory">
              <CheckIcon class="w-4 h-4" />
            </button>
            <button class="p-0.5 text-gray-400 hover:text-gray-600" @click.stop="cancelEditCategory">
              <XMarkIcon class="w-4 h-4" />
            </button>
          </template>
          <template v-else>
            <span class="flex-1 text-sm font-medium truncate">{{ cat.name }}</span>
            <div class="hidden group-hover:flex items-center gap-1">
              <button class="p-0.5 text-gray-400 hover:text-gray-600" @click.stop="startEditCategory(cat)">
                <PencilSquareIcon class="w-4 h-4" />
              </button>
              <button class="p-0.5 text-gray-400 hover:text-red-500" @click.stop="pendingDeleteCategoryId = cat.id">
                <TrashIcon class="w-4 h-4" />
              </button>
            </div>
          </template>
        </div>

        <!-- Add category -->
        <div v-if="showNewCategoryForm" class="space-y-2 p-2 border border-gray-200 rounded-lg">
          <input
            v-model="newCategoryName"
            placeholder="Název kategorie"
            class="w-full text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
            @keyup.enter="createCategory"
          />
          <div class="flex items-center gap-2">
            <label class="text-xs text-gray-500">Barva</label>
            <input v-model="newCategoryColor" type="color" class="w-8 h-6 rounded cursor-pointer border border-gray-200" />
          </div>
          <div class="flex gap-1">
            <button
              class="flex-1 px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
              :disabled="savingCategory || !newCategoryName.trim()"
              @click="createCategory"
            >Přidat</button>
            <button
              class="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
              @click="showNewCategoryForm = false"
            >Zrušit</button>
          </div>
        </div>
        <button
          v-else
          class="flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700 px-3 py-1"
          @click="showNewCategoryForm = true"
        >
          <PlusIcon class="w-4 h-4" />
          Nová kategorie
        </button>
      </div>

      <!-- Right panel: stages & fields -->
      <div class="flex-1 space-y-6">
        <template v-if="selectedCategory">
          <!-- Category header -->
          <div class="flex items-center gap-3">
            <span
              class="w-4 h-4 rounded-full"
              :style="{ backgroundColor: selectedCategory.color || '#94A3B8' }"
            ></span>
            <h2 class="text-lg font-semibold text-gray-900">{{ selectedCategory.name }}</h2>
            <span class="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">{{ selectedCategory.slug }}</span>
          </div>

          <!-- Stages -->
          <div>
            <div class="text-sm font-semibold text-gray-700 mb-2">Stavy (stages)</div>

            <VueDraggable
              v-model="draggableStages"
              handle=".stage-drag-handle"
              class="space-y-2"
              @end="onStageDragEnd"
            >
              <div
                v-for="stage in draggableStages"
                :key="stage.id"
                class="flex items-center gap-3 p-3 border border-gray-100 rounded-lg bg-white group"
              >
                <!-- Drag handle -->
                <span class="stage-drag-handle cursor-grab text-gray-300 hover:text-gray-500 flex-shrink-0" :title="t('pipeline.stageDragHandle')">
                  <Bars3Icon class="w-4 h-4" />
                </span>

                <!-- Color -->
                <span class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: stage.color || '#94A3B8' }"></span>

                <template v-if="editingStageId === stage.id">
                  <div class="flex-1 grid grid-cols-2 gap-2">
                    <input
                      v-model="editingStage.name"
                      placeholder="Název"
                      class="text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                    />
                    <input
                      v-model="editingStage.color"
                      type="color"
                      class="w-10 h-8 rounded cursor-pointer border border-gray-200"
                    />
                    <label class="flex items-center gap-1 text-xs text-gray-600 col-span-2">
                      <input v-model="editingStage.is_terminal" type="checkbox" class="rounded" />
                      Terminální stav
                    </label>
                    <label v-if="editingStage.is_terminal" class="flex items-center gap-1 text-xs text-gray-600 col-span-2">
                      <input v-model="editingStage.is_won" type="checkbox" class="rounded" />
                      Je to výhra (won)
                    </label>
                  </div>
                  <div class="flex gap-1">
                    <button class="p-1 text-green-600 hover:text-green-700" :disabled="savingStage" @click="saveEditStage">
                      <CheckIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="cancelEditStage">
                      <XMarkIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
                <template v-else>
                  <span class="flex-1 text-sm font-medium text-gray-800">{{ stage.name }}</span>
                  <div class="flex items-center gap-2">
                    <span v-if="stage.is_terminal && stage.is_won" class="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">Výhra</span>
                    <span v-else-if="stage.is_terminal" class="text-xs text-red-500 bg-red-50 px-1.5 py-0.5 rounded">Konec</span>
                  </div>
                  <div class="hidden group-hover:flex items-center gap-1">
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="startEditStage(stage)">
                      <PencilSquareIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-red-500" @click="pendingDeleteStageId = stage.id">
                      <TrashIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
              </div>
            </VueDraggable>

              <!-- Add stage form -->
              <div v-if="showNewStageForm" class="p-3 border border-indigo-100 rounded-lg bg-indigo-50 space-y-2 mt-2">
                <div class="grid grid-cols-2 gap-2">
                  <input
                    v-model="newStageName"
                    placeholder="Název stavu"
                    class="col-span-2 text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                    @keyup.enter="createStage"
                  />
                  <div class="flex items-center gap-2">
                    <label class="text-xs text-gray-500">Barva</label>
                    <input v-model="newStageColor" type="color" class="w-8 h-6 rounded cursor-pointer border border-gray-200" />
                  </div>
                  <label class="flex items-center gap-1 text-xs text-gray-600">
                    <input v-model="newStageIsTerminal" type="checkbox" class="rounded" />
                    Terminální
                  </label>
                  <label v-if="newStageIsTerminal" class="flex items-center gap-1 text-xs text-gray-600 col-span-2">
                    <input v-model="newStageIsWon" type="checkbox" class="rounded" />
                    Je to výhra (won)
                  </label>
                </div>
                <div class="flex gap-2">
                  <button
                    class="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                    :disabled="savingStage || !newStageName.trim()"
                    @click="createStage"
                  >Přidat stav</button>
                  <button
                    class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700"
                    @click="showNewStageForm = false"
                  >Zrušit</button>
                </div>
              </div>

              <button
                v-if="!showNewStageForm"
                class="flex items-center gap-1 mt-2 text-sm text-indigo-600 hover:text-indigo-700"
                @click="showNewStageForm = true"
              >
                <PlusIcon class="w-4 h-4" />
                Přidat stav
              </button>
          </div>

          <!-- Fields management -->
          <div>
            <div class="text-sm font-semibold text-gray-700 mb-2">{{ t('pipeline.fieldsTitle') }}</div>

            <VueDraggable
              v-model="draggableFields"
              handle=".field-drag-handle"
              class="space-y-2"
              @end="onFieldDragEnd"
            >
              <div
                v-for="field in draggableFields"
                :key="field.field_key"
                class="flex items-center gap-3 p-3 border border-gray-100 rounded-lg bg-white group"
              >
                <!-- Drag handle -->
                <span class="field-drag-handle cursor-grab text-gray-300 hover:text-gray-500 flex-shrink-0" :title="t('pipeline.fieldDragHandle')">
                  <Bars3Icon class="w-4 h-4" />
                </span>

                <template v-if="editingFieldKey === field.field_key">
                  <div class="flex-1 space-y-3">
                    <span class="text-sm font-semibold text-gray-800">{{ t(`pipeline.fieldKey.${field.field_key}`) }}</span>

                    <!-- Basic toggles -->
                    <div class="flex gap-4">
                      <label class="flex items-center gap-1.5 text-xs text-gray-600">
                        <input v-model="editingField.is_visible" type="checkbox" class="rounded" />
                        {{ t('pipeline.fieldVisible') }}
                      </label>
                      <label class="flex items-center gap-1.5 text-xs text-gray-600">
                        <input v-model="editingField.is_required" type="checkbox" class="rounded" />
                        {{ t('pipeline.fieldRequired') }}
                      </label>
                    </div>

                    <!-- Label override -->
                    <div class="flex items-center gap-2">
                      <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldLabelOverride') }}</label>
                      <input
                        v-model="editingField.label_override"
                        :placeholder="t('pipeline.fieldLabelOverridePlaceholder')"
                        class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                      />
                    </div>

                    <!-- Help text -->
                    <div class="flex items-center gap-2">
                      <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldHelpText') }}</label>
                      <input
                        v-model="editingField.help_text_override"
                        :placeholder="t('pipeline.fieldHelpTextPlaceholder')"
                        class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                      />
                    </div>

                    <!-- Value type -->
                    <div class="flex items-center gap-2">
                      <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldValueType') }}</label>
                      <select
                        v-model="editingField.value_type"
                        class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
                        @change="onEditValueTypeChange"
                      >
                        <option v-for="vt in VALUE_TYPES" :key="vt.value" :value="vt.value">{{ vt.label() }}</option>
                      </select>
                    </div>

                    <!-- Widget -->
                    <div class="flex items-center gap-2">
                      <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldWidget') }}</label>
                      <select
                        v-model="editingField.widget"
                        class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
                      >
                        <option v-for="w in editWidgets" :key="w.value" :value="w.value">{{ w.label() }}</option>
                      </select>
                    </div>

                    <!-- Validation rules: number/currency → min/max -->
                    <template v-if="['number', 'currency'].includes(editingField.value_type)">
                      <div class="flex gap-3">
                        <div class="flex items-center gap-1">
                          <label class="text-xs text-gray-500">{{ t('pipeline.fieldMin') }}</label>
                          <input v-model="editMin" type="number" class="w-20 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300" />
                        </div>
                        <div class="flex items-center gap-1">
                          <label class="text-xs text-gray-500">{{ t('pipeline.fieldMax') }}</label>
                          <input v-model="editMax" type="number" class="w-20 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300" />
                        </div>
                      </div>
                    </template>

                    <!-- Validation rules: text → pattern -->
                    <template v-if="editingField.value_type === 'text'">
                      <div class="flex items-center gap-2">
                        <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldPattern') }}</label>
                        <input
                          v-model="editPattern"
                          placeholder="^[A-Z].*"
                          class="flex-1 text-xs font-mono border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300"
                        />
                      </div>
                    </template>

                    <!-- Validation rules: select/multiselect → options -->
                    <template v-if="['select', 'multiselect'].includes(editingField.value_type)">
                      <div class="flex flex-col gap-1">
                        <label class="text-xs text-gray-500">{{ t('pipeline.fieldOptions') }}</label>
                        <textarea
                          v-model="editOptionsText"
                          rows="4"
                          :placeholder="t('pipeline.fieldOptionsPlaceholder')"
                          class="text-xs font-mono border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 resize-y"
                        />
                        <span class="text-xs text-gray-400">{{ t('pipeline.fieldOptionsHint') }}</span>
                      </div>
                    </template>
                  </div>
                  <div class="flex gap-1 self-start">
                    <button class="p-1 text-green-600 hover:text-green-700" :disabled="savingField" @click="saveEditField">
                      <CheckIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="cancelEditField">
                      <XMarkIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
                <template v-else>
                  <div class="flex-1 min-w-0">
                    <span class="text-sm font-medium text-gray-800 block truncate">
                      {{ field.label_override || t(`pipeline.fieldKey.${field.field_key}`) }}
                    </span>
                    <span v-if="field.label_override" class="text-xs text-gray-400 truncate">{{ t(`pipeline.fieldKey.${field.field_key}`) }}</span>
                  </div>
                  <div class="flex items-center gap-2 flex-shrink-0">
                    <span class="text-xs text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded font-mono">{{ field.value_type }}</span>
                    <span v-if="!field.is_visible" class="text-xs text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">{{ t('pipeline.fieldHidden') }}</span>
                    <span v-if="field.is_required" class="text-xs text-red-500 bg-red-50 px-1.5 py-0.5 rounded">{{ t('pipeline.fieldRequired') }}</span>
                  </div>
                  <div class="hidden group-hover:flex items-center gap-1">
                    <button class="p-1 text-gray-400 hover:text-gray-600" @click="startEditField(field)">
                      <PencilSquareIcon class="w-4 h-4" />
                    </button>
                    <button class="p-1 text-gray-400 hover:text-red-500" @click="pendingDeleteFieldKey = field.field_key">
                      <TrashIcon class="w-4 h-4" />
                    </button>
                  </div>
                </template>
              </div>
            </VueDraggable>

            <p v-if="selectedFields.length === 0 && !showNewFieldForm" class="text-xs text-gray-400 py-1">
              {{ t('pipeline.noFields') }}
            </p>

            <!-- Add field form -->
            <div v-if="showNewFieldForm" class="p-3 border border-indigo-100 rounded-lg bg-indigo-50 space-y-3 mt-2">
              <!-- Field key selector -->
              <select
                v-model="newFieldKey"
                class="w-full text-sm border border-gray-200 rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
              >
                <option value="" disabled>{{ t('pipeline.fieldKeyPlaceholder') }}</option>
                <option v-for="key in availableFieldKeys" :key="key" :value="key">
                  {{ t(`pipeline.fieldKey.${key}`) }}
                </option>
              </select>

              <!-- Label override -->
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldLabelOverride') }}</label>
                <input
                  v-model="newFieldLabelOverride"
                  :placeholder="t('pipeline.fieldLabelOverridePlaceholder')"
                  class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                />
              </div>

              <!-- Help text -->
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldHelpText') }}</label>
                <input
                  v-model="newFieldHelpText"
                  :placeholder="t('pipeline.fieldHelpTextPlaceholder')"
                  class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                />
              </div>

              <!-- Value type -->
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldValueType') }}</label>
                <select
                  v-model="newFieldValueType"
                  class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
                  @change="onNewValueTypeChange"
                >
                  <option v-for="vt in VALUE_TYPES" :key="vt.value" :value="vt.value">{{ vt.label() }}</option>
                </select>
              </div>

              <!-- Widget -->
              <div class="flex items-center gap-2">
                <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldWidget') }}</label>
                <select
                  v-model="newFieldWidget"
                  class="flex-1 text-xs border border-gray-200 rounded px-2 py-1 bg-white outline-none focus:ring-1 focus:ring-indigo-300"
                >
                  <option v-for="w in newWidgets" :key="w.value" :value="w.value">{{ w.label() }}</option>
                </select>
              </div>

              <!-- number/currency → min/max -->
              <template v-if="['number', 'currency'].includes(newFieldValueType)">
                <div class="flex gap-3">
                  <div class="flex items-center gap-1">
                    <label class="text-xs text-gray-500">{{ t('pipeline.fieldMin') }}</label>
                    <input v-model="newMin" type="number" class="w-20 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white" />
                  </div>
                  <div class="flex items-center gap-1">
                    <label class="text-xs text-gray-500">{{ t('pipeline.fieldMax') }}</label>
                    <input v-model="newMax" type="number" class="w-20 text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white" />
                  </div>
                </div>
              </template>

              <!-- text → pattern -->
              <template v-if="newFieldValueType === 'text'">
                <div class="flex items-center gap-2">
                  <label class="text-xs text-gray-500 w-24 flex-shrink-0">{{ t('pipeline.fieldPattern') }}</label>
                  <input
                    v-model="newPattern"
                    placeholder="^[A-Z].*"
                    class="flex-1 text-xs font-mono border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                  />
                </div>
              </template>

              <!-- select/multiselect → options -->
              <template v-if="['select', 'multiselect'].includes(newFieldValueType)">
                <div class="flex flex-col gap-1">
                  <label class="text-xs text-gray-500">{{ t('pipeline.fieldOptions') }}</label>
                  <textarea
                    v-model="newOptionsText"
                    rows="4"
                    :placeholder="t('pipeline.fieldOptionsPlaceholder')"
                    class="text-xs font-mono border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 resize-y bg-white"
                  />
                  <span class="text-xs text-gray-400">{{ t('pipeline.fieldOptionsHint') }}</span>
                </div>
              </template>

              <!-- Visibility / required -->
              <div class="flex gap-4">
                <label class="flex items-center gap-1.5 text-xs text-gray-600">
                  <input v-model="newFieldIsVisible" type="checkbox" class="rounded" />
                  {{ t('pipeline.fieldVisible') }}
                </label>
                <label class="flex items-center gap-1.5 text-xs text-gray-600">
                  <input v-model="newFieldIsRequired" type="checkbox" class="rounded" />
                  {{ t('pipeline.fieldRequired') }}
                </label>
              </div>

              <div class="flex gap-2">
                <button
                  class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                  :disabled="savingField || !newFieldKey"
                  @click="createField"
                >{{ t('pipeline.addField') }}</button>
                <button
                  class="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                  @click="showNewFieldForm = false"
                >{{ t('pipeline.cancel') }}</button>
              </div>
            </div>

            <button
              v-if="!showNewFieldForm && availableFieldKeys.length > 0"
              class="flex items-center gap-1 mt-2 text-sm text-indigo-600 hover:text-indigo-700"
              @click="showNewFieldForm = true"
            >
              <PlusIcon class="w-4 h-4" />
              {{ t('pipeline.addField') }}
            </button>
          </div>

          <!-- Condition rules -->
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <div class="text-sm font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.rulesTitle') }}</div>
              <div class="flex items-center gap-2">
                <button
                  class="px-3 py-1.5 text-xs border border-indigo-200 text-indigo-700 rounded hover:bg-indigo-50"
                  @click="showRuleTemplates = !showRuleTemplates"
                >
                  {{ showRuleTemplates ? t('pipeline.rulesTemplatesHide') : t('pipeline.rulesTemplatesBrowse') }}
                </button>
                <button
                  class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
                  @click="openCreateRuleForm"
                >{{ t('pipeline.rulesCreate') }}</button>
              </div>
            </div>

            <div v-if="showRuleTemplates" class="mb-3 p-3 border border-indigo-100 rounded-lg bg-indigo-50 dark:border-indigo-800/60 dark:bg-indigo-950/30 space-y-2">
              <div class="text-xs font-semibold text-indigo-700 dark:text-indigo-300">{{ t('pipeline.rulesTemplatesTitle') }}</div>
              <div class="text-xs text-indigo-600 dark:text-indigo-300">{{ t('pipeline.rulesTemplatesHint') }}</div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div
                  v-for="template in ruleTemplatePresets"
                  :key="template.id"
                  class="p-2 border border-indigo-100 rounded bg-white dark:border-indigo-800/60 dark:bg-gray-800"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="text-xs font-semibold text-gray-800 dark:text-gray-100">{{ t(template.nameKey) }}</div>
                    <span class="inline-flex items-center rounded-full bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-200">
                      {{ t(template.domainLabelKey) }}
                    </span>
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{{ t(template.descriptionKey) }}</div>
                  <button
                    class="mt-2 px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
                    @click="applyRuleTemplate(template.id)"
                  >
                    {{ t('pipeline.rulesTemplatesUse') }}
                  </button>
                </div>
              </div>
            </div>

            <div v-if="showRuleForm" class="mb-3 p-3 border border-indigo-100 rounded-lg bg-indigo-50 dark:border-indigo-800/60 dark:bg-indigo-950/30 space-y-2">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div class="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                  {{ editingRuleId ? t('pipeline.rulesEditTitle') : t('pipeline.rulesCreateTitle') }}
                </div>
                <div class="inline-flex rounded border border-indigo-200 overflow-hidden dark:border-indigo-700">
                  <button
                    type="button"
                    class="px-2 py-1 text-xs"
                    :class="ruleVisualizationMode === 'builder' ? 'bg-indigo-600 text-white' : 'bg-white text-indigo-700 hover:bg-indigo-100 dark:bg-gray-700 dark:text-indigo-200 dark:hover:bg-gray-600'"
                    @click="ruleVisualizationMode = 'builder'"
                  >
                    {{ t('pipeline.rulesVisualizationModeBuilder') }}
                  </button>
                  <button
                    type="button"
                    class="px-2 py-1 text-xs border-l border-indigo-200 dark:border-indigo-700"
                    :class="ruleVisualizationMode === 'tree' ? 'bg-indigo-600 text-white' : 'bg-white text-indigo-700 hover:bg-indigo-100 dark:bg-gray-700 dark:text-indigo-200 dark:hover:bg-gray-600'"
                    @click="ruleVisualizationMode = 'tree'"
                  >
                    {{ t('pipeline.rulesVisualizationModeTree') }}
                  </button>
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input
                  v-model="ruleForm.name"
                  type="text"
                  :placeholder="t('pipeline.rulesNamePlaceholder')"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                />
                <select
                  v-model="ruleForm.trigger_type"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="">{{ t('pipeline.rulesTriggerSelect') }}</option>
                  <option
                    v-for="triggerOption in ruleFormTriggerTypeOptions"
                    :key="triggerOption.value"
                    :value="triggerOption.value"
                  >
                    {{ triggerTypeLabel(triggerOption.value) }}
                  </option>
                </select>
                <input
                  v-model="ruleForm.description"
                  type="text"
                  :placeholder="t('pipeline.rulesDescriptionPlaceholder')"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500 md:col-span-2"
                />
                <select
                  v-model="ruleForm.scope_type"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="firm">{{ t('pipeline.rulesScopeFirm') }}</option>
                  <option value="category">{{ t('pipeline.rulesScopeCategory') }}</option>
                  <option value="stage">{{ t('pipeline.rulesScopeStage') }}</option>
                  <option value="stage_transition">{{ t('pipeline.rulesScopeTransition') }}</option>
                </select>
                <input
                  v-model="ruleForm.priority"
                  type="number"
                  min="0"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                />
                <select
                  v-model="ruleForm.category_id"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="">{{ t('pipeline.allCategories') }}</option>
                  <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                </select>
                <select
                  v-model="ruleForm.stage_id"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="">{{ t('pipeline.rulesFilterStageAll') }}</option>
                  <option v-for="stage in ruleFormStages" :key="stage.id" :value="stage.id">{{ stage.name }}</option>
                </select>
                <select
                  v-model="ruleForm.source_stage_id"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="">{{ t('pipeline.rulesSourceStage') }}</option>
                  <option v-for="stage in ruleFormStages" :key="`source-${stage.id}`" :value="stage.id">{{ stage.name }}</option>
                </select>
                <select
                  v-model="ruleForm.target_stage_id"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="">{{ t('pipeline.rulesTargetStage') }}</option>
                  <option v-for="stage in ruleFormStages" :key="`target-${stage.id}`" :value="stage.id">{{ stage.name }}</option>
                </select>
                <select
                  v-model="ruleForm.effect"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="block">{{ t('pipeline.rulesEffectBlock') }}</option>
                  <option value="warning">{{ t('pipeline.rulesEffectWarning') }}</option>
                  <option value="info">{{ t('pipeline.rulesEffectInfo') }}</option>
                  <option value="recommend">{{ t('pipeline.rulesEffectRecommend') }}</option>
                </select>
                <select
                  v-model="ruleForm.severity"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="error">{{ t('pipeline.rulesSeverityError') }}</option>
                  <option value="warning">{{ t('pipeline.rulesSeverityWarning') }}</option>
                  <option value="info">{{ t('pipeline.rulesSeverityInfo') }}</option>
                </select>
                <input
                  v-model="ruleForm.activity_type"
                  type="text"
                  :placeholder="t('pipeline.rulesActivityTypePlaceholder')"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500 md:col-span-2"
                />
                <label class="inline-flex items-center gap-2 text-xs text-gray-700 dark:text-gray-200">
                  <input v-model="ruleForm.is_active" type="checkbox" class="rounded" />
                  {{ t('pipeline.rulesStartEnabled') }}
                </label>
                <div v-if="ruleVisualizationMode === 'builder'" class="md:col-span-2 p-2 border border-indigo-100 rounded bg-white dark:border-indigo-800/60 dark:bg-gray-800 space-y-2">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.rulesBuilderTitle') }}</div>
                    <div class="flex items-center gap-3">
                      <button
                        type="button"
                        class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200"
                        @click="setRuleEditorMode(!useRuleJsonEditor)"
                      >
                        {{ useRuleJsonEditor ? t('pipeline.rulesBuilderSwitchToVisual') : t('pipeline.rulesBuilderSwitchToJson') }}
                      </button>
                      <button
                        type="button"
                        class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200"
                        @click="ruleVisualizationMode = 'tree'"
                      >
                        {{ t('pipeline.rulesVisualizationOpenTree') }}
                      </button>
                    </div>
                  </div>
                  <p class="text-[11px] text-gray-500 dark:text-gray-400">{{ t('pipeline.rulesBuilderHint') }}</p>
                  <template v-if="!useRuleJsonEditor">
                    <ConditionBuilder
                      v-model="ruleConditionTree"
                      :category-fields="ruleBuilderCategoryFields"
                      :disabled="savingRule"
                    />
                    <div class="text-[11px] text-gray-500 break-words">
                      <span class="font-semibold text-gray-600 dark:text-gray-300">{{ t('pipeline.rulesBuilderPreviewLabel') }}:</span>
                      {{ ruleConditionTreePreview }}
                    </div>
                    <ul
                      v-if="ruleConditionTreeIssues.length > 0"
                      role="alert"
                      :aria-label="t('pipeline.rulesBuilderValidationError')"
                      class="text-[11px] text-red-600 list-disc pl-4 space-y-0.5"
                    >
                      <li v-for="issue in ruleConditionTreeIssues" :key="`${issue.path}-${issue.message}`">
                        {{ issue.message }}
                      </li>
                    </ul>
                  </template>
                  <textarea
                    v-else
                    v-model="ruleConditionTreeText"
                    rows="6"
                    class="w-full text-xs font-mono text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                    :placeholder="t('pipeline.rulesConditionTreePlaceholder')"
                  ></textarea>
                </div>
                <div v-else class="md:col-span-2 p-2 border border-indigo-100 rounded bg-white dark:border-indigo-800/60 dark:bg-gray-800 space-y-2">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.rulesVisualizationTreeTitle') }}</div>
                    <button
                      type="button"
                      class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200"
                      @click="ruleVisualizationMode = 'builder'"
                    >
                      {{ t('pipeline.rulesVisualizationBackToBuilder') }}
                    </button>
                  </div>
                  <p class="text-[11px] text-gray-500 dark:text-gray-400">
                    {{ t('pipeline.rulesVisualizationTreeHint') }}
                  </p>
                  <ConditionTreeViewer
                    :condition-tree="ruleConditionTree"
                    :category-fields="ruleBuilderCategoryFields"
                  />
                </div>
                <textarea
                  v-model="ruleEffectConfigText"
                  rows="3"
                  class="md:col-span-2 text-xs font-mono text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                  :placeholder="t('pipeline.rulesEffectConfigPlaceholder')"
                ></textarea>
              </div>
              <div class="flex gap-2">
                <button
                  class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                  :disabled="savingRule"
                  @click="submitRuleForm"
                >{{ editingRuleId ? t('pipeline.rulesUpdate') : t('pipeline.rulesCreate') }}</button>
                <button
                  class="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-100"
                  @click="resetRuleForm"
                >{{ t('pipeline.cancel') }}</button>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
              <select
                v-model="ruleFilterCategoryId"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                :disabled="Boolean(selectedCategoryId)"
              >
                <option value="">{{ t('pipeline.allCategories') }}</option>
                <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
              </select>

              <select
                v-model="ruleFilterStageId"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              >
                <option value="">{{ t('pipeline.rulesFilterStageAll') }}</option>
                <option v-for="stage in ruleFilterStages" :key="stage.id" :value="stage.id">{{ stage.name }}</option>
              </select>

              <select
                v-model="ruleFilterTriggerType"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              >
                <option value="">{{ t('pipeline.rulesFilterTriggerAll') }}</option>
                <option
                  v-for="triggerOption in ruleFilterTriggerTypeOptions"
                  :key="triggerOption.value"
                  :value="triggerOption.value"
                >
                  {{ triggerTypeLabel(triggerOption.value) }}
                </option>
              </select>

              <select
                v-model="ruleFilterEnabled"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              >
                <option value="all">{{ t('pipeline.rulesFilterStateAll') }}</option>
                <option value="enabled">{{ t('pipeline.rulesFilterStateEnabled') }}</option>
                <option value="disabled">{{ t('pipeline.rulesFilterStateDisabled') }}</option>
              </select>
            </div>

            <div class="flex gap-2 mb-3">
              <button
                class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                :disabled="conditionRulesLoading"
                @click="loadConditionRules"
              >{{ t('pipeline.rulesApplyFilters') }}</button>
              <button
                class="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-100"
                @click="resetRuleFilters"
              >{{ t('pipeline.rulesResetFilters') }}</button>
            </div>

            <div v-if="conditionRulesLoading" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.rulesLoading') }}
            </div>
            <div v-else-if="conditionRulesError" class="text-xs text-red-500 dark:text-red-400 py-2">
              {{ conditionRulesError }}
            </div>
            <div v-else-if="conditionRules.length === 0" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.rulesEmpty') }}
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="rule in conditionRules"
                :key="rule.id"
                class="flex items-start justify-between gap-3 p-3 border border-gray-100 rounded-lg bg-white dark:border-gray-700 dark:bg-gray-800"
              >
                <div class="min-w-0">
                  <div class="text-sm font-medium text-gray-800 truncate dark:text-gray-100">{{ rule.name }}</div>
                  <div v-if="rule.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 break-words">
                    {{ rule.description }}
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 break-words">
                    {{ t('pipeline.rulesTrigger') }}: {{ triggerTypeLabel(rule.trigger_type) }}
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">
                    {{ t('pipeline.rulesScope') }}: {{ rule.scope_type }}
                  </div>
                </div>
                <div class="flex flex-col items-end gap-1.5">
                  <label class="inline-flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300 pt-0.5">
                    <input
                      :checked="rule.is_active"
                      type="checkbox"
                      class="rounded"
                      :disabled="isRuleUpdating(rule.id)"
                      @change="toggleRuleActive(rule, ($event.target as HTMLInputElement).checked)"
                    />
                    <span>{{ rule.is_active ? t('pipeline.rulesStateEnabled') : t('pipeline.rulesStateDisabled') }}</span>
                  </label>
                  <div class="flex flex-wrap justify-end gap-1">
                    <button class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200" @click="openEditRuleForm(rule)">
                      {{ t('pipeline.rulesEdit') }}
                    </button>
                    <button class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200" @click="copyRule(rule)">
                      {{ t('pipeline.rulesCopy') }}
                    </button>
                    <button class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200" @click="openRuleTest(rule)">
                      {{ t('pipeline.rulesTest') }}
                    </button>
                    <button
                      v-if="rule.is_active"
                      class="text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
                      @click="requestDeactivateRule(rule)"
                    >
                      {{ t('pipeline.rulesDeactivate') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="testRuleId" class="mt-3 p-3 border border-gray-100 rounded-lg bg-gray-50 dark:border-gray-700 dark:bg-gray-800/50 space-y-2">
              <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.rulesTestTitle') }}</div>
              <div class="flex flex-col md:flex-row gap-2">
                <input
                  v-model="testRecordId"
                  type="text"
                  :placeholder="t('pipeline.rulesTestRecordPlaceholder')"
                  class="flex-1 text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                />
                <button
                  class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                  :disabled="testingRule"
                  @click="runRuleTestEvaluation"
                >{{ t('pipeline.rulesTestRun') }}</button>
                <button
                  class="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-100"
                  @click="closeRuleTest"
                >{{ t('pipeline.cancel') }}</button>
              </div>
              <div v-if="testEvaluationResult" class="text-xs text-gray-600 dark:text-gray-300">
                <div>
                  {{ t('pipeline.rulesTestMatched') }}:
                  <span class="font-semibold">{{ testEvaluationResult.matched ? t('pipeline.rulesTestMatchedYes') : t('pipeline.rulesTestMatchedNo') }}</span>
                </div>
                <div>{{ t('pipeline.rulesTestOutputs') }}: {{ testEvaluationResult.outputs.length }}</div>
                <div>{{ t('pipeline.rulesTestBlocking') }}: {{ testEvaluationResult.blocking.length }}</div>
                <div>{{ t('pipeline.rulesTestWarnings') }}: {{ testEvaluationResult.warnings.length }}</div>
              </div>
            </div>
          </div>

          <!-- Rule evaluation logs -->
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <div class="text-sm font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.ruleLogsTitle') }}</div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-2 mb-3">
              <select
                v-model="ruleLogsFilterTriggerType"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              >
                <option value="">{{ t('pipeline.rulesFilterTriggerAll') }}</option>
                <option
                  v-for="triggerOption in ruleLogTriggerTypeOptions"
                  :key="triggerOption.value"
                  :value="triggerOption.value"
                >
                  {{ triggerTypeLabel(triggerOption.value) }}
                </option>
              </select>
              <input
                v-model="ruleLogsFilterResult"
                type="text"
                :placeholder="t('pipeline.ruleLogsFilterResultPlaceholder')"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              />
              <input
                v-model="ruleLogsFilterRecordId"
                type="text"
                :placeholder="t('pipeline.ruleLogsFilterRecordPlaceholder')"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              />
              <input
                v-model="ruleLogsFilterRuleId"
                type="text"
                :placeholder="t('pipeline.ruleLogsFilterRulePlaceholder')"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              />
            </div>

            <div class="flex gap-2 mb-3">
              <button
                class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                :disabled="ruleEvaluationLogsLoading"
                @click="loadRuleEvaluationLogs(1)"
              >
                {{ t('pipeline.ruleLogsApplyFilters') }}
              </button>
              <button
                class="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-100"
                :disabled="ruleEvaluationLogsLoading"
                @click="resetRuleEvaluationLogFilters"
              >
                {{ t('pipeline.ruleLogsResetFilters') }}
              </button>
            </div>

            <div v-if="ruleEvaluationLogsLoading" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.ruleLogsLoading') }}
            </div>
            <div v-else-if="ruleEvaluationLogsError" class="text-xs text-red-500 dark:text-red-400 py-2">
              {{ ruleEvaluationLogsError }}
            </div>
            <div v-else-if="ruleEvaluationLogs.length === 0" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.ruleLogsEmpty') }}
            </div>
            <div v-else class="space-y-2">
              <div class="overflow-auto border border-gray-100 rounded-lg bg-white dark:border-gray-700 dark:bg-gray-800">
                <table class="min-w-full text-xs">
                  <thead class="bg-gray-50 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                    <tr>
                      <th class="text-left px-3 py-2 font-medium">{{ t('pipeline.ruleLogsColEvaluatedAt') }}</th>
                      <th class="text-left px-3 py-2 font-medium">{{ t('pipeline.ruleLogsColTrigger') }}</th>
                      <th class="text-left px-3 py-2 font-medium">{{ t('pipeline.ruleLogsColResult') }}</th>
                      <th class="text-left px-3 py-2 font-medium">{{ t('pipeline.ruleLogsColRecordId') }}</th>
                      <th class="text-left px-3 py-2 font-medium">{{ t('pipeline.ruleLogsColRuleId') }}</th>
                      <th class="text-left px-3 py-2 font-medium">{{ t('pipeline.ruleLogsColScenarioId') }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="log in ruleEvaluationLogs"
                      :key="log.id"
                      class="border-t border-gray-100 text-gray-700 dark:border-gray-700 dark:text-gray-200"
                    >
                      <td class="px-3 py-2 whitespace-nowrap">{{ log.evaluated_at }}</td>
                      <td class="px-3 py-2 whitespace-nowrap">{{ triggerTypeLabel(log.trigger_type) }}</td>
                      <td class="px-3 py-2 whitespace-nowrap">{{ log.result }}</td>
                      <td class="px-3 py-2 whitespace-nowrap">{{ log.record_id || '—' }}</td>
                      <td class="px-3 py-2 whitespace-nowrap">{{ log.rule_id || '—' }}</td>
                      <td class="px-3 py-2 whitespace-nowrap">{{ log.scenario_id || '—' }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="flex items-center justify-between">
                <button
                  class="px-2 py-1 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-gray-100 disabled:opacity-50"
                  :disabled="ruleEvaluationLogsPage <= 1 || ruleEvaluationLogsLoading"
                  @click="loadPreviousRuleEvaluationLogsPage"
                >
                  {{ t('pipeline.ruleLogsPrevPage') }}
                </button>
                <span class="text-xs text-gray-500 dark:text-gray-400">
                  {{ t('pipeline.ruleLogsPageLabel', { page: ruleEvaluationLogsPage }) }}
                </span>
                <button
                  class="px-2 py-1 text-xs text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-gray-100 disabled:opacity-50"
                  :disabled="!ruleEvaluationLogsHasMore || ruleEvaluationLogsLoading"
                  @click="loadNextRuleEvaluationLogsPage"
                >
                  {{ t('pipeline.ruleLogsNextPage') }}
                </button>
              </div>
            </div>
          </div>

          <!-- Stage scenarios -->
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <div class="text-sm font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.stageScenariosTitle') }}</div>
              <button
                class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                :disabled="!scenarioFilterStageId"
                @click="openCreateScenarioForm"
              >
                {{ t('pipeline.stageScenariosCreate') }}
              </button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
              <select
                v-model="scenarioFilterStageId"
                class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
              >
                <option value="">{{ t('pipeline.stageScenariosSelectStage') }}</option>
                <option v-for="stage in scenarioFilterStages" :key="`scenario-stage-${stage.id}`" :value="stage.id">
                  {{ stage.name }}
                </option>
              </select>
              <button
                class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                :disabled="!scenarioFilterStageId || stageScenariosStore.loadingScenarios"
                @click="loadStageScenarios"
              >
                {{ t('pipeline.stageScenariosReload') }}
              </button>
            </div>

            <div v-if="stageScenariosStore.loadingScenarios" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.stageScenariosLoading') }}
            </div>
            <div v-else-if="stageScenariosStore.error" class="text-xs text-red-500 dark:text-red-400 py-2">
              {{ stageScenariosStore.error }}
            </div>
            <div v-else-if="!scenarioFilterStageId" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.stageScenariosChooseStageHint') }}
            </div>
            <div v-else-if="stageScenarios.length === 0" class="text-xs text-gray-400 dark:text-gray-500 py-2">
              {{ t('pipeline.stageScenariosEmpty') }}
            </div>
            <div v-else class="space-y-2">
              <div
                v-for="scenario in stageScenarios"
                :key="scenario.id"
                class="flex items-start justify-between gap-3 p-3 border border-gray-100 rounded-lg bg-white dark:border-gray-700 dark:bg-gray-800"
              >
                <div class="min-w-0">
                  <div class="text-sm font-medium text-gray-800 truncate dark:text-gray-100">{{ scenario.name }}</div>
                  <div v-if="scenario.description" class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 break-words">
                    {{ scenario.description }}
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    {{ t('pipeline.stageScenariosPriorityLabel') }}: {{ scenario.priority }}
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">
                    {{ t('pipeline.stageScenariosRecommendedNextStageLabel') }}:
                    {{ stageNameById(scenario.recommended_next_stage_id) }}
                  </div>
                </div>
                <div class="flex flex-col items-end gap-1.5">
                  <span
                    class="text-[11px] px-2 py-0.5 rounded-full"
                    :class="scenario.is_active ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'"
                  >
                    {{
                      scenario.is_active
                        ? t('pipeline.stageScenariosStateEnabled')
                        : t('pipeline.stageScenariosStateDisabled')
                    }}
                  </span>
                  <div class="flex flex-wrap justify-end gap-1">
                    <button class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200" @click="startEditScenario(scenario)">
                      {{ t('pipeline.stageScenariosEdit') }}
                    </button>
                    <button
                      class="text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 disabled:opacity-50"
                      :disabled="deletingScenarioId === scenario.id"
                      @click="requestDeleteScenario(scenario.id)"
                    >
                      {{ t('pipeline.stageScenariosDelete') }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="showScenarioForm" class="mt-3 p-3 border border-indigo-100 rounded-lg bg-indigo-50 dark:border-indigo-800/60 dark:bg-indigo-950/30 space-y-2">
              <div class="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                {{ editingScenarioId ? t('pipeline.stageScenariosEditTitle') : t('pipeline.stageScenariosCreateTitle') }}
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input
                  v-model="scenarioForm.name"
                  type="text"
                  :placeholder="t('pipeline.stageScenariosNamePlaceholder')"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                />
                <input
                  v-model="scenarioForm.priority"
                  type="number"
                  min="0"
                  step="1"
                  :placeholder="t('pipeline.stageScenariosPriorityPlaceholder')"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                />
                <select
                  v-model="scenarioForm.recommended_next_stage_id"
                  class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                >
                  <option value="">{{ t('pipeline.stageScenariosRecommendedNextStageNone') }}</option>
                  <option
                    v-for="stage in scenarioRecommendedStageOptions"
                    :key="`scenario-next-stage-${stage.id}`"
                    :value="stage.id"
                  >
                    {{ stage.name }}
                  </option>
                </select>
                <label class="inline-flex items-center gap-2 text-xs text-gray-700 dark:text-gray-200">
                  <input v-model="scenarioForm.is_active" type="checkbox" class="rounded" />
                  {{ t('pipeline.stageScenariosStartEnabled') }}
                </label>
                <textarea
                  v-model="scenarioForm.description"
                  rows="2"
                  :placeholder="t('pipeline.stageScenariosDescriptionPlaceholder')"
                  class="md:col-span-2 text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                ></textarea>
                <div class="md:col-span-2 p-2 border border-indigo-100 rounded bg-white dark:border-indigo-800/60 dark:bg-gray-800 space-y-2">
                  <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.stageScenariosActivationCondition') }}</div>
                  <ConditionBuilder
                    v-model="scenarioActivationCondition"
                    :category-fields="ruleBuilderCategoryFields"
                    :disabled="savingScenario"
                  />
                </div>
              </div>
              <div class="flex gap-2">
                <button
                  class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                  :disabled="savingScenario"
                  @click="submitScenarioForm"
                >
                  {{ editingScenarioId ? t('pipeline.stageScenariosUpdate') : t('pipeline.stageScenariosCreate') }}
                </button>
                <button class="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-100" @click="resetScenarioForm">
                  {{ t('pipeline.cancel') }}
                </button>
              </div>

              <div v-if="editingScenarioId" class="pt-2 border-t border-indigo-100 dark:border-indigo-800/60 space-y-2">
                <div class="flex items-center justify-between gap-2">
                  <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.stageRequirementsTitle') }}</div>
                  <button
                    class="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
                    @click="openCreateRequirementForm"
                  >
                    {{ t('pipeline.stageRequirementsCreate') }}
                  </button>
                </div>
                <div v-if="stageScenariosStore.loadingRequirements" class="text-xs text-gray-400 dark:text-gray-500">
                  {{ t('pipeline.stageRequirementsLoading') }}
                </div>
                <div v-else-if="stageRequirements.length === 0" class="text-xs text-gray-400 dark:text-gray-500">
                  {{ t('pipeline.stageRequirementsEmpty') }}
                </div>
                <div v-else class="space-y-1.5">
                  <div
                    v-for="requirement in stageRequirements"
                    :key="requirement.id"
                    class="p-2 border border-gray-200 rounded bg-white dark:border-gray-600 dark:bg-gray-800 flex items-start justify-between gap-2"
                  >
                    <div class="min-w-0">
                      <div class="text-xs font-semibold text-gray-800 dark:text-gray-100 truncate">{{ requirement.name }}</div>
                      <div class="text-[11px] text-gray-500 dark:text-gray-400">
                        {{ t('pipeline.stageRequirementsTypeLabel') }}: {{ requirement.requirement_type }}
                      </div>
                      <div class="text-[11px] text-gray-500 dark:text-gray-400">
                        {{ t('pipeline.stageRequirementsBlockingLabel') }}:
                        {{ requirement.blocking ? t('pipeline.stageRequirementsBlockingYes') : t('pipeline.stageRequirementsBlockingNo') }}
                      </div>
                    </div>
                    <div class="flex gap-1">
                      <button class="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-700 dark:hover:text-indigo-200" @click="openEditRequirementForm(requirement)">
                        {{ t('pipeline.stageRequirementsEdit') }}
                      </button>
                      <button
                        class="text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 disabled:opacity-50"
                        :disabled="deletingRequirementId === requirement.id"
                        @click="requestDeleteRequirement(requirement.id)"
                      >
                        {{ t('pipeline.stageRequirementsDelete') }}
                      </button>
                    </div>
                  </div>
                </div>

                <div v-if="showRequirementForm" class="p-2 border border-indigo-100 rounded bg-white dark:border-indigo-800/60 dark:bg-gray-800 space-y-2">
                  <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">
                    {{ editingRequirementId ? t('pipeline.stageRequirementsEditTitle') : t('pipeline.stageRequirementsCreateTitle') }}
                  </div>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input
                      v-model="requirementForm.name"
                      type="text"
                      :placeholder="t('pipeline.stageRequirementsNamePlaceholder')"
                      class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                    />
                    <input
                      v-model="requirementForm.sort_order"
                      type="number"
                      min="0"
                      step="1"
                      :placeholder="t('pipeline.stageRequirementsSortOrderPlaceholder')"
                      class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                    />
                    <input
                      v-model="requirementForm.requirement_type"
                      type="text"
                      :placeholder="t('pipeline.stageRequirementsTypePlaceholder')"
                      class="text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                    />
                    <label class="inline-flex items-center gap-2 text-xs text-gray-700 dark:text-gray-200">
                      <input v-model="requirementForm.blocking" type="checkbox" class="rounded" />
                      {{ t('pipeline.stageRequirementsBlockingToggle') }}
                    </label>
                    <label class="inline-flex items-center gap-2 text-xs text-gray-700 dark:text-gray-200">
                      <input v-model="requirementForm.visible_to_user" type="checkbox" class="rounded" />
                      {{ t('pipeline.stageRequirementsVisibleToggle') }}
                    </label>
                    <textarea
                      v-model="requirementForm.description"
                      rows="2"
                      :placeholder="t('pipeline.stageRequirementsDescriptionPlaceholder')"
                      class="md:col-span-2 text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                    ></textarea>
                    <div class="md:col-span-2 p-2 border border-indigo-100 rounded bg-indigo-50 dark:border-indigo-800/60 dark:bg-indigo-950/30 space-y-1">
                      <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.stageRequirementsConditionTitle') }}</div>
                      <ConditionBuilder
                        v-model="requirementConditionTree"
                        :category-fields="ruleBuilderCategoryFields"
                        :disabled="savingRequirement"
                      />
                    </div>
                  </div>
                  <div class="flex gap-2">
                    <button
                      class="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                      :disabled="savingRequirement"
                      @click="submitRequirementForm"
                    >
                      {{ editingRequirementId ? t('pipeline.stageRequirementsUpdate') : t('pipeline.stageRequirementsCreate') }}
                    </button>
                    <button class="px-2 py-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-100" @click="resetRequirementForm">
                      {{ t('pipeline.cancel') }}
                    </button>
                  </div>
                </div>
              </div>

              <div v-if="editingScenarioId" class="pt-2 border-t border-indigo-100 dark:border-indigo-800/60 space-y-2">
                <div class="text-xs font-semibold text-gray-700 dark:text-gray-100">{{ t('pipeline.stageScenariosPreviewTitle') }}</div>
                <div class="flex flex-col md:flex-row gap-2">
                  <input
                    v-model="scenarioPreviewRecordId"
                    type="text"
                    :placeholder="t('pipeline.stageScenariosPreviewRecordPlaceholder')"
                    class="flex-1 text-xs text-gray-900 border border-gray-200 rounded px-2 py-1.5 bg-white outline-none focus:ring-1 focus:ring-indigo-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:focus:ring-blue-500"
                  />
                  <button
                    class="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                    :disabled="loadingScenarioPreview"
                    @click="runScenarioPreview"
                  >
                    {{ t('pipeline.stageScenariosPreviewRun') }}
                  </button>
                </div>
                <div v-if="scenarioPreviewResult" class="text-xs text-gray-600 dark:text-gray-300 space-y-0.5">
                  <div>
                    {{ t('pipeline.stageScenariosPreviewIsActive') }}:
                    <span class="font-semibold">
                      {{
                        scenarioPreviewResult.activeScenarioId === editingScenarioId
                          ? t('pipeline.stageScenariosPreviewYes')
                          : t('pipeline.stageScenariosPreviewNo')
                      }}
                    </span>
                  </div>
                  <div>
                    {{ t('pipeline.stageScenariosPreviewActiveScenario') }}:
                    <span class="font-semibold">{{ scenarioPreviewResult.activeScenarioName || '—' }}</span>
                  </div>
                  <div>
                    {{ t('pipeline.stageScenariosPreviewRequirements') }}:
                    {{ scenarioPreviewResult.activeRequirementsCount }}
                  </div>
                  <div>
                    {{ t('pipeline.stageScenariosPreviewUnmetRequirements') }}:
                    {{ scenarioPreviewResult.unmetRequirementsCount }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Pipeline flow diagram -->
          <PipelineFlowDiagram
            :rules="conditionRules"
            :scenarios="stageScenarios"
            :requirements="pipelineFlowRequirements"
            :categories="categories"
            :stages="pipelineFlowStageOptions"
            :loading="pipelineFlowLoading || stageScenariosStore.loadingScenarios"
            :error="pipelineFlowError"
            :initial-category-id="selectedCategoryId || ''"
            :initial-stage-id="scenarioFilterStageId"
            :evaluation-outputs="testEvaluationResult?.outputs ?? []"
            :evaluation-logs="ruleEvaluationLogs"
            :tested-rule-id="testRuleId"
          />

          <!-- Category Access Grants -->
          <div v-if="can('category.manage')">
            <div class="flex items-center gap-2 mb-3">
              <LockOpenIcon class="w-4 h-4 text-gray-500" />
              <div class="text-sm font-semibold text-gray-700">{{ t('pipeline.categoryAccess') }}</div>
            </div>

            <!-- Loading -->
            <div v-if="categoryGrantsLoading" class="text-xs text-gray-400 py-2">{{ t('pipeline.loadingCategories') }}</div>

            <!-- Grants list -->
            <div v-else class="space-y-2">
              <div
                v-for="grant in categoryGrants"
                :key="grant.id"
                class="flex items-center justify-between p-2 border border-gray-100 rounded-lg bg-white text-sm group"
              >
                <div class="flex items-center gap-2 min-w-0">
                  <span class="text-gray-500 text-xs uppercase tracking-wide flex-shrink-0">{{ grant.principal_type }}</span>
                  <span class="text-sm text-gray-800 truncate">{{ grantDisplayName(grant) }}</span>
                  <span
                    class="text-xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                    :class="{
                      'bg-blue-50 text-blue-700': grant.level === 'view',
                      'bg-amber-50 text-amber-700': grant.level === 'edit',
                      'bg-red-50 text-red-700': grant.level === 'manage',
                    }"
                  >{{ t(`permissions.access${grant.level.charAt(0).toUpperCase() + grant.level.slice(1)}`) }}</span>
                </div>
                <button
                  class="p-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  :title="t('permissions.revokeAccess')"
                  @click="removeCategoryGrant(grant.id)"
                >
                  <TrashIcon class="w-4 h-4" />
                </button>
              </div>

              <div v-if="!categoryGrantsLoading && categoryGrants.length === 0" class="text-xs text-gray-400 py-1">
                {{ t('permissions.noGrants') }}
              </div>

              <!-- Add grant form -->
              <div v-if="showGrantForm" class="p-3 border border-indigo-100 rounded-lg bg-indigo-50 space-y-2 mt-2">
                <div class="grid grid-cols-2 gap-2">
                  <div class="col-span-2">
                    <PeoplePicker
                      v-model="newGrantPrincipalId"
                      :firm-id="firmId"
                      :placeholder="t('peoplePicker.placeholder')"
                    />
                  </div>
                  <select
                    v-model="newGrantLevel"
                    class="col-span-2 text-sm border border-gray-200 rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
                  >
                    <option value="view">{{ t('permissions.accessView') }}</option>
                    <option value="edit">{{ t('permissions.accessEdit') }}</option>
                    <option value="manage">{{ t('permissions.accessManage') }}</option>
                  </select>
                </div>
                <div class="flex gap-2">
                  <button
                    class="px-3 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                    :disabled="savingGrant || !newGrantPrincipalId.trim()"
                    @click="addCategoryGrant"
                  >{{ t('pipeline.categoryGrantAdd') }}</button>
                  <button
                    class="px-3 py-1 text-xs text-gray-500 hover:text-gray-700"
                    @click="showGrantForm = false"
                  >{{ t('pipeline.cancel') }}</button>
                </div>
              </div>

              <button
                v-if="!showGrantForm"
                class="flex items-center gap-1 mt-1 text-sm text-indigo-600 hover:text-indigo-700"
                @click="showGrantForm = true"
              >
                <PlusIcon class="w-4 h-4" />
                {{ t('pipeline.categoryGrantAdd') }}
              </button>
            </div>
          </div>
        </template>

        <div v-else class="flex items-center justify-center h-48 text-gray-400 text-sm">
          Vyberte kategorii vlevo
        </div>
      </div>
    </div>
  </div>

  <!-- Delete category confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeleteCategoryId"
    :message="t('pipeline.confirmDeleteCategory')"
    @confirm="confirmDeleteCategory"
    @cancel="pendingDeleteCategoryId = null"
  />

  <!-- Delete stage confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeleteStageId"
    :message="t('pipeline.confirmDeleteStage')"
    @confirm="confirmDeleteStage"
    @cancel="pendingDeleteStageId = null"
  />

  <!-- Delete field confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeleteFieldKey"
    :message="t('pipeline.confirmDeleteField')"
    @confirm="confirmDeleteField"
    @cancel="pendingDeleteFieldKey = null"
  />

  <!-- Deactivate rule confirm -->
  <ConfirmDeleteModal
    :open="!!pendingDeactivateRuleId"
    :message="t('pipeline.rulesDeactivateConfirm', { name: pendingDeactivateRuleName })"
    @confirm="confirmDeactivateRule"
    @cancel="pendingDeactivateRuleId = null; pendingDeactivateRuleName = ''"
  />
</template>

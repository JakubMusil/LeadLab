export interface TriggerTypeOption {
  value: string
  labelKey: string
  selectableInRuleForm?: boolean
}

export const TRIGGER_TYPE_OPTIONS: TriggerTypeOption[] = [
  { value: 'record.created', labelKey: 'pipeline.triggerTypeRecordCreated' },
  { value: 'record.updated', labelKey: 'pipeline.triggerTypeRecordUpdated' },
  { value: 'record.field_changed', labelKey: 'pipeline.triggerTypeRecordFieldChanged' },
  { value: 'record.category_field_changed', labelKey: 'pipeline.triggerTypeRecordCategoryFieldChanged' },
  { value: 'record.stage_change_requested', labelKey: 'pipeline.triggerTypeRecordStageChangeRequested' },
  { value: 'record.stage_changed', labelKey: 'pipeline.triggerTypeRecordStageChanged' },
  { value: 'stage.entered', labelKey: 'pipeline.triggerTypeStageEntered' },
  { value: 'stage.left', labelKey: 'pipeline.triggerTypeStageLeft' },
  { value: 'streamline.activity_created', labelKey: 'pipeline.triggerTypeStreamlineActivityCreated' },
  { value: 'streamline.activity_updated', labelKey: 'pipeline.triggerTypeStreamlineActivityUpdated' },
  { value: 'streamline.activity_deleted', labelKey: 'pipeline.triggerTypeStreamlineActivityDeleted' },
  { value: 'streamline.checklist_item_completed', labelKey: 'pipeline.triggerTypeStreamlineChecklistItemCompleted' },
  { value: 'streamline.checklist_item_reopened', labelKey: 'pipeline.triggerTypeStreamlineChecklistItemReopened' },
  { value: 'streamline.file_uploaded', labelKey: 'pipeline.triggerTypeStreamlineFileUploaded' },
  { value: 'task.completed', labelKey: 'pipeline.triggerTypeTaskCompleted' },
  { value: 'task.reopened', labelKey: 'pipeline.triggerTypeTaskReopened' },
  { value: 'proposal.signed', labelKey: 'pipeline.triggerTypeProposalSigned' },
  { value: 'proposal.rejected', labelKey: 'pipeline.triggerTypeProposalRejected' },
  { value: 'manual.evaluation_requested', labelKey: 'pipeline.triggerTypeManualEvaluationRequested' },
  {
    value: 'requirement.chain_evaluated',
    labelKey: 'pipeline.triggerTypeRequirementChainEvaluated',
    selectableInRuleForm: false,
  },
]

export const RULE_FORM_TRIGGER_TYPE_OPTIONS = TRIGGER_TYPE_OPTIONS.filter(
  (option) => option.selectableInRuleForm !== false,
)

const TRIGGER_TYPE_LABEL_KEY_BY_VALUE = TRIGGER_TYPE_OPTIONS.reduce<Record<string, string>>((acc, option) => {
  acc[option.value] = option.labelKey
  return acc
}, {})

export function getTriggerTypeLabel(
  triggerType: string,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  const normalized = triggerType.trim()
  if (!normalized) return t('pipeline.rulesFilterTriggerAll')
  const key = TRIGGER_TYPE_LABEL_KEY_BY_VALUE[normalized]
  if (!key) return t('pipeline.triggerTypeUnknown', { trigger: normalized })
  return t(key)
}

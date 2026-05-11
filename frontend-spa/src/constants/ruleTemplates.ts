export interface RuleTemplatePreset {
  id: string
  nameKey: string
  descriptionKey: string
  messageKey?: string
  triggerType: string
  scopeType: string
  effect: string
  severity: string
  activityType?: string
  conditionTree: Record<string, unknown>
  effectConfig?: Record<string, unknown>
}

// Starter threshold for the preset; admins can adjust this value before saving the rule.
const MIN_HIGH_VALUE_TEMPLATE_THRESHOLD = 1000

export const RULE_TEMPLATE_PRESETS: RuleTemplatePreset[] = [
  {
    id: 'block_without_owner',
    nameKey: 'pipeline.rulesTemplateOwnerRequiredName',
    descriptionKey: 'pipeline.rulesTemplateOwnerRequiredDescription',
    triggerType: 'record.stage_change_requested',
    scopeType: 'category',
    effect: 'block',
    severity: 'error',
    conditionTree: {
      type: 'condition',
      source_type: 'standard_field',
      field: 'assigned_to_id',
      operator: 'not_exists',
      value: null,
    },
  },
  {
    id: 'warn_without_contact',
    nameKey: 'pipeline.rulesTemplateContactRecommendedName',
    descriptionKey: 'pipeline.rulesTemplateContactRecommendedDescription',
    triggerType: 'record.stage_change_requested',
    scopeType: 'category',
    effect: 'warning',
    severity: 'warning',
    conditionTree: {
      type: 'condition',
      source_type: 'standard_field',
      field: 'contact_person_id',
      operator: 'not_exists',
      value: null,
    },
  },
  {
    id: 'block_low_value',
    nameKey: 'pipeline.rulesTemplateHighValueName',
    descriptionKey: 'pipeline.rulesTemplateHighValueDescription',
    triggerType: 'record.stage_change_requested',
    scopeType: 'category',
    effect: 'block',
    severity: 'error',
    conditionTree: {
      type: 'condition',
      source_type: 'standard_field',
      field: 'value',
      operator: 'lt',
      value: MIN_HIGH_VALUE_TEMPLATE_THRESHOLD,
    },
  },
  {
    id: 'block_without_recent_activity',
    nameKey: 'pipeline.rulesTemplateRecentActivityName',
    descriptionKey: 'pipeline.rulesTemplateRecentActivityDescription',
    triggerType: 'record.stage_change_requested',
    scopeType: 'category',
    effect: 'block',
    severity: 'error',
    activityType: 'note',
    conditionTree: {
      type: 'condition',
      source_type: 'streamline_activity',
      activity_type: 'note',
      operator: 'not_exists',
      value: null,
      time_window: { last_days: 7 },
    },
  },
  {
    id: 'recommend_review_for_new_record',
    nameKey: 'pipeline.rulesTemplateReviewRecommendationName',
    descriptionKey: 'pipeline.rulesTemplateReviewRecommendationDescription',
    messageKey: 'pipeline.rulesTemplateReviewRecommendationMessage',
    triggerType: 'record.stage_change_requested',
    scopeType: 'category',
    effect: 'recommend',
    severity: 'info',
    conditionTree: {
      type: 'group',
      op: 'and',
      conditions: [
        {
          type: 'condition',
          source_type: 'standard_field',
          field: 'status',
          operator: 'eq',
          value: 'new',
        },
        {
          type: 'condition',
          source_type: 'standard_field',
          field: 'notes',
          operator: 'not_exists',
          value: null,
        },
      ],
    },
    effectConfig: {},
  },
]

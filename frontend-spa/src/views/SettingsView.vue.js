/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/template-helpers.d.ts" />
/// <reference types="../../../../../../.npm/_npx/2db181330ea4b15b/node_modules/@vue/language-core/types/props-fallback.d.ts" />
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useFirmStore } from '@/stores/firm';
import { useToast } from '@/composables/useToast';
import { usePushNotifications } from '@/composables/usePushNotifications';
import { api } from '@/api';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { setLocale, useI18n } from '@/composables/useI18n';
import { useLeadScoringStore, SCORING_FIELDS } from '@/stores/leadScoring';
import { pluginRegistry } from '@/plugins';
const leadScoringStore = useLeadScoringStore();
const authStore = useAuthStore();
const firmStore = useFirmStore();
const toast = useToast();
const router = useRouter();
const { isPro } = storeToRefs(firmStore);
const { locale: currentLocale } = useI18n();
const { isSupported: pushSupported, isSubscribed: pushSubscribed, isLoading: pushLoading, subscribe: subscribePush, unsubscribe: unsubscribePush } = usePushNotifications();
// Branding
const brandColor = ref(firmStore.activeFirm?.primary_color || '#e63946');
const brandLogoPreview = ref(null);
const brandLogoInput = ref(null);
const brandSaving = ref(false);
const brandError = ref('');
const brandSuccess = ref(false);
function onBrandLogoChange(event) {
    const file = event.target.files?.[0];
    if (file) {
        brandLogoPreview.value = URL.createObjectURL(file);
    }
}
async function saveBranding() {
    if (!firmStore.activeFirm)
        return;
    brandSaving.value = true;
    brandError.value = '';
    brandSuccess.value = false;
    try {
        const formData = new FormData();
        formData.append('primary_color', brandColor.value);
        const file = brandLogoInput.value?.files?.[0];
        if (file)
            formData.append('logo', file);
        const res = await fetch(`/api/v1/firms/${firmStore.activeFirm.id}/branding/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData,
        });
        if (res.ok) {
            const data = await res.json();
            firmStore.activeFirm.primary_color = data.primary_color;
            if (data.logo_url)
                firmStore.activeFirm.logo_url = data.logo_url;
            brandSuccess.value = true;
        }
        else {
            brandError.value = 'Failed to save branding.';
        }
    }
    finally {
        brandSaving.value = false;
    }
}
function getCsrfToken() {
    const m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
}
function changeLocale(code) {
    setLocale(code);
}
// Profile
const profileFirstName = ref('');
const profileLastName = ref('');
const profileTimezone = ref('');
const profileLoading = ref(false);
const profileError = ref('');
const profileSuccess = ref(false);
// Avatar
const avatarInput = ref(null);
const avatarPreview = ref(null);
const avatarLoading = ref(false);
// Workspace rename
const workspaceName = ref('');
const workspaceLoading = ref(false);
const workspaceError = ref('');
const workspaceSuccess = ref(false);
// Danger zone
const confirmDeleteWorkspace = ref(false);
const dangerLoading = ref(false);
const confirmDeleteText = ref('');
const tokens = ref([]);
const tokensLoading = ref(false);
const newTokenName = ref('');
const newTokenCreating = ref(false);
const createdTokenValue = ref(null);
const webhooks = ref([]);
const webhooksLoading = ref(false);
const newWebhookUrl = ref('');
const newWebhookEvents = ref('');
const newWebhookCreating = ref(false);
// Weekly digest
const digestEnabled = ref(true);
const digestLoading = ref(false);
async function loadDigestPreference() {
    if (!firmStore.activeFirm)
        return;
    const res = await api.get('/api/v1/crm/digest-preference');
    if (res.ok && res.data) {
        digestEnabled.value = res.data.weekly_digest_enabled;
    }
}
async function toggleDigest() {
    digestLoading.value = true;
    const res = await api.patch('/api/v1/crm/digest-preference', { enabled: !digestEnabled.value });
    digestLoading.value = false;
    if (res.ok && res.data) {
        digestEnabled.value = res.data.weekly_digest_enabled;
        toast.success(res.data.weekly_digest_enabled
            ? 'Weekly digest enabled.'
            : 'Weekly digest disabled.');
    }
    else {
        toast.error('Failed to update digest preference.');
    }
}
// ---- Lead Scoring ----
const newRuleField = ref('status');
const newRuleOperand = ref('');
const newRuleScoreDelta = ref(10);
const ruleError = ref('');
const ruleLoading = ref(false);
async function addScoringRule() {
    if (!newRuleOperand.value.toString().trim()) {
        ruleError.value = 'Operand is required.';
        return;
    }
    ruleError.value = '';
    ruleLoading.value = true;
    let operand = newRuleOperand.value;
    // coerce numeric operands
    if (newRuleField.value === 'value_gte' || newRuleField.value === 'last_activity_days_lte') {
        const n = parseFloat(String(operand));
        if (isNaN(n)) {
            ruleError.value = 'Operand must be a number for this field.';
            ruleLoading.value = false;
            return;
        }
        operand = n;
    }
    const result = await leadScoringStore.createRule({
        field: newRuleField.value,
        operand,
        score_delta: newRuleScoreDelta.value,
    });
    ruleLoading.value = false;
    if (result) {
        toast.success('Scoring rule added.');
        newRuleOperand.value = '';
        newRuleScoreDelta.value = 10;
    }
    else {
        ruleError.value = 'Failed to add rule.';
    }
}
async function removeScoringRule(id) {
    await leadScoringStore.deleteRule(id);
    toast.success('Rule deleted.');
}
onMounted(() => {
    if (authStore.user) {
        profileFirstName.value = authStore.user.first_name;
        profileLastName.value = authStore.user.last_name;
        profileTimezone.value = authStore.user.timezone;
    }
    if (firmStore.activeFirm) {
        workspaceName.value = firmStore.activeFirm.name;
        loadTokens();
        loadWebhooks();
        loadDigestPreference();
        leadScoringStore.fetchRules();
        loadPropTemplates();
        loadPluginConfigs();
        loadAutomations();
        loadAutomationTemplates();
    }
});
// ---- API Tokens ----
async function loadTokens() {
    if (!firmStore.activeFirm)
        return;
    tokensLoading.value = true;
    const res = await api.get(`/api/v1/firms/${firmStore.activeFirm.id}/tokens`);
    tokensLoading.value = false;
    if (res.ok && Array.isArray(res.data)) {
        tokens.value = res.data;
    }
}
async function createToken() {
    if (!firmStore.activeFirm || !newTokenName.value.trim())
        return;
    newTokenCreating.value = true;
    const res = await api.post(`/api/v1/firms/${firmStore.activeFirm.id}/tokens`, { name: newTokenName.value.trim() });
    newTokenCreating.value = false;
    if (res.ok && res.data) {
        createdTokenValue.value = res.data.token;
        newTokenName.value = '';
        tokens.value.unshift(res.data);
        toast.success('API token created. Copy it now — it will not be shown again.');
    }
    else {
        toast.error('Failed to create token.');
    }
}
async function revokeToken(token) {
    if (!firmStore.activeFirm)
        return;
    if (!confirm(`Revoke token "${token.name}"? This cannot be undone.`))
        return;
    const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/tokens/${token.id}`);
    if (res.ok || res.status === 204) {
        tokens.value = tokens.value.map((t) => t.id === token.id ? { ...t, is_active: false, revoked_at: new Date().toISOString() } : t);
        toast.success('Token revoked.');
    }
    else {
        toast.error('Failed to revoke token.');
    }
}
function copyToken() {
    if (!createdTokenValue.value)
        return;
    navigator.clipboard.writeText(createdTokenValue.value).then(() => {
        toast.success('Token copied to clipboard.');
    });
}
// ---- Webhooks ----
async function loadWebhooks() {
    if (!firmStore.activeFirm)
        return;
    webhooksLoading.value = true;
    const res = await api.get(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks`);
    webhooksLoading.value = false;
    if (res.ok && Array.isArray(res.data)) {
        webhooks.value = res.data;
    }
}
async function createWebhook() {
    if (!firmStore.activeFirm || !newWebhookUrl.value.trim())
        return;
    newWebhookCreating.value = true;
    const events = newWebhookEvents.value
        .split(',')
        .map((e) => e.trim())
        .filter(Boolean);
    const res = await api.post(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks`, { url: newWebhookUrl.value.trim(), events });
    newWebhookCreating.value = false;
    if (res.ok && res.data) {
        webhooks.value.unshift(res.data);
        newWebhookUrl.value = '';
        newWebhookEvents.value = '';
        toast.success('Webhook endpoint created.');
    }
    else {
        toast.error('Failed to create webhook.');
    }
}
async function toggleWebhook(wh) {
    if (!firmStore.activeFirm)
        return;
    const res = await api.patch(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks/${wh.id}`, { is_active: !wh.is_active });
    if (res.ok && res.data) {
        const idx = webhooks.value.findIndex((w) => w.id === wh.id);
        if (idx !== -1)
            webhooks.value.splice(idx, 1, res.data);
        toast.success(res.data.is_active ? 'Webhook enabled.' : 'Webhook disabled.');
    }
    else {
        toast.error('Failed to update webhook.');
    }
}
async function deleteWebhook(wh) {
    if (!firmStore.activeFirm)
        return;
    if (!confirm(`Delete webhook for "${wh.url}"?`))
        return;
    const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}/webhooks/${wh.id}`);
    if (res.ok || res.status === 204) {
        webhooks.value = webhooks.value.filter((w) => w.id !== wh.id);
        toast.success('Webhook deleted.');
    }
    else {
        toast.error('Failed to delete webhook.');
    }
}
async function saveProfile() {
    profileLoading.value = true;
    profileError.value = '';
    profileSuccess.value = false;
    const res = await api.patch('/api/v1/users/me', {
        first_name: profileFirstName.value,
        last_name: profileLastName.value,
        timezone: profileTimezone.value,
    });
    profileLoading.value = false;
    if (res.ok && res.data) {
        authStore.user = res.data;
        profileSuccess.value = true;
        toast.success('Profile updated.');
        setTimeout(() => { profileSuccess.value = false; }, 3000);
    }
    else {
        profileError.value = res.data?.detail ?? 'Failed to update profile.';
    }
}
function onAvatarChange(e) {
    const file = e.target.files?.[0];
    if (!file)
        return;
    const reader = new FileReader();
    reader.onload = (ev) => { avatarPreview.value = ev.target?.result; };
    reader.readAsDataURL(file);
}
async function uploadAvatar() {
    const file = avatarInput.value?.files?.[0];
    if (!file)
        return;
    avatarLoading.value = true;
    const fd = new FormData();
    fd.append('avatar', file);
    const res = await api.postForm('/api/v1/users/me/avatar', fd);
    avatarLoading.value = false;
    if (res.ok && res.data) {
        authStore.user = res.data;
        toast.success('Avatar updated.');
    }
    else {
        toast.error('Failed to upload avatar.');
    }
}
async function saveWorkspaceName() {
    if (!firmStore.activeFirm)
        return;
    if (!workspaceName.value.trim()) {
        workspaceError.value = 'Name is required.';
        return;
    }
    workspaceLoading.value = true;
    workspaceError.value = '';
    workspaceSuccess.value = false;
    const res = await api.patch(`/api/v1/firms/${firmStore.activeFirm.id}`, { name: workspaceName.value.trim() });
    workspaceLoading.value = false;
    if (res.ok) {
        // Update firm in store
        const idx = firmStore.firms.findIndex((f) => f.id === firmStore.activeFirm.id);
        if (idx !== -1) {
            const updated = { ...firmStore.firms[idx], name: res.data.name };
            firmStore.firms.splice(idx, 1, updated);
        }
        if (firmStore.activeFirm) {
            // Safe mutation via setActiveFirm — update in-place
            const af = firmStore.activeFirm;
            Object.assign(af, { name: res.data.name });
        }
        workspaceSuccess.value = true;
        toast.success('Workspace renamed.');
        setTimeout(() => { workspaceSuccess.value = false; }, 3000);
    }
    else {
        workspaceError.value = res.data?.detail ?? 'Failed to rename workspace.';
    }
}
async function deleteWorkspace() {
    if (!firmStore.activeFirm)
        return;
    if (confirmDeleteText.value !== firmStore.activeFirm.name) {
        toast.error('Workspace name does not match.');
        return;
    }
    dangerLoading.value = true;
    const res = await api.delete(`/api/v1/firms/${firmStore.activeFirm.id}`);
    dangerLoading.value = false;
    if (res.ok || res.status === 204) {
        firmStore.firms = firmStore.firms.filter((f) => f.id !== firmStore.activeFirm.id);
        firmStore.activeFirm = firmStore.firms[0] ?? null;
        localStorage.removeItem('firmId');
        toast.success('Workspace deleted.');
        if (!firmStore.activeFirm) {
            await router.push('/app/onboarding');
        }
    }
    else {
        toast.error(res.data?.detail ?? 'Failed to delete workspace.');
    }
}
const propTemplates = ref([]);
const propTemplatesLoading = ref(false);
const newTemplateName = ref('');
const newTemplateIntro = ref('');
const newTemplateClosing = ref('');
const newTemplateCreating = ref(false);
const expandedTemplate = ref(null);
const newTmplItemDesc = ref('');
const newTmplItemQty = ref(1);
const newTmplItemPrice = ref(0);
const addingTmplItem = ref(false);
async function loadPropTemplates() {
    propTemplatesLoading.value = true;
    const res = await api.get('/api/v1/crm/proposal-templates');
    propTemplatesLoading.value = false;
    if (res.ok && Array.isArray(res.data))
        propTemplates.value = res.data;
}
async function createPropTemplate() {
    if (!newTemplateName.value.trim())
        return;
    newTemplateCreating.value = true;
    const res = await api.post('/api/v1/crm/proposal-templates', {
        name: newTemplateName.value.trim(),
        intro_text: newTemplateIntro.value,
        closing_text: newTemplateClosing.value,
    });
    newTemplateCreating.value = false;
    if (res.ok && res.data) {
        propTemplates.value.unshift(res.data);
        newTemplateName.value = '';
        newTemplateIntro.value = '';
        newTemplateClosing.value = '';
        toast.success('Template created.');
    }
    else {
        toast.error('Failed to create template.');
    }
}
async function deletePropTemplate(id) {
    if (!confirm('Delete this template?'))
        return;
    const res = await api.delete(`/api/v1/crm/proposal-templates/${id}`);
    if (res.ok || res.status === 204) {
        propTemplates.value = propTemplates.value.filter((t) => t.id !== id);
        if (expandedTemplate.value === id)
            expandedTemplate.value = null;
        toast.success('Template deleted.');
    }
    else {
        toast.error('Failed to delete template.');
    }
}
async function addTmplItem(template) {
    if (!newTmplItemDesc.value.trim())
        return;
    addingTmplItem.value = true;
    const res = await api.post(`/api/v1/crm/proposal-templates/${template.id}/items`, {
        description: newTmplItemDesc.value.trim(),
        quantity: newTmplItemQty.value,
        unit_price: newTmplItemPrice.value,
        discount: 0,
        vat_rate: 0,
        position: template.items.length,
    });
    addingTmplItem.value = false;
    if (res.ok) {
        template.items.push(res.data);
        newTmplItemDesc.value = '';
        newTmplItemQty.value = 1;
        newTmplItemPrice.value = 0;
    }
    else {
        toast.error('Failed to add item.');
    }
}
async function deleteTmplItem(template, itemId) {
    const res = await api.delete(`/api/v1/crm/proposal-templates/${template.id}/items/${itemId}`);
    if (res.ok || res.status === 204) {
        template.items = template.items.filter((i) => i.id !== itemId);
    }
    else {
        toast.error('Failed to delete item.');
    }
}
const pluginConfigs = ref([]);
const pluginsLoading = ref(false);
const expandedPlugin = ref(null);
const pluginSaving = ref({});
const pluginDraftConfigs = ref({});
async function loadPluginConfigs() {
    if (!firmStore.activeFirm)
        return;
    pluginsLoading.value = true;
    const res = await api.get(`/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/`);
    pluginsLoading.value = false;
    if (res.ok && Array.isArray(res.data)) {
        pluginConfigs.value = res.data;
        // Seed draft configs with current values
        for (const pc of res.data) {
            pluginDraftConfigs.value[pc.plugin_name] = { ...pc.config };
        }
    }
}
async function togglePlugin(pc) {
    if (!firmStore.activeFirm)
        return;
    const res = await api.patch(`/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/${pc.plugin_name}/`, { enabled: !pc.enabled });
    if (res.ok && res.data) {
        const idx = pluginConfigs.value.findIndex((p) => p.plugin_name === pc.plugin_name);
        if (idx !== -1)
            pluginConfigs.value.splice(idx, 1, res.data);
        toast.success(res.data.enabled ? `${pc.plugin_name} enabled.` : `${pc.plugin_name} disabled.`);
    }
    else {
        toast.error('Failed to update plugin.');
    }
}
async function savePluginConfig(pc) {
    if (!firmStore.activeFirm)
        return;
    pluginSaving.value[pc.plugin_name] = true;
    const config = pluginDraftConfigs.value[pc.plugin_name] ?? {};
    const res = await api.patch(`/api/v1/plugins/${firmStore.activeFirm.id}/plugin-configs/${pc.plugin_name}/`, { config });
    pluginSaving.value[pc.plugin_name] = false;
    if (res.ok && res.data) {
        const idx = pluginConfigs.value.findIndex((p) => p.plugin_name === pc.plugin_name);
        if (idx !== -1)
            pluginConfigs.value.splice(idx, 1, res.data);
        toast.success('Plugin settings saved.');
        expandedPlugin.value = null;
    }
    else {
        toast.error('Failed to save plugin settings.');
    }
}
function getDraftValue(pluginName, key) {
    return pluginDraftConfigs.value[pluginName]?.[key] ?? '';
}
function setDraftValue(pluginName, key, value) {
    if (!pluginDraftConfigs.value[pluginName]) {
        pluginDraftConfigs.value[pluginName] = {};
    }
    pluginDraftConfigs.value[pluginName][key] = value;
}
// Expose installed plugin count from local registry for quick reference
const localPluginCount = computed(() => pluginRegistry.length);
const TRIGGER_LABELS = {
    lead_created: 'Lead Created',
    lead_status_change: 'Lead Status Changed',
    task_overdue: 'Task Overdue',
    proposal_sent: 'Proposal Sent',
    proposal_accepted: 'Proposal Accepted',
    lead_inactive: 'Lead Inactive (N days)',
    webhook_received: 'Custom Webhook Received',
};
const ACTION_TYPE_LABELS = {
    send_email: 'Send email',
    create_task: 'Create task',
    update_field: 'Update field',
    call_webhook: 'Call webhook',
    run_plugin_action: 'Run plugin action',
};
const OPERATOR_LABELS = {
    eq: '=',
    neq: '≠',
    gt: '>',
    gte: '≥',
    lt: '<',
    lte: '≤',
    contains: 'contains',
};
const automationRules = ref([]);
const automationTemplates = ref([]);
const automationsLoading = ref(false);
const showTemplates = ref(false);
const expandedRuleRuns = ref(null);
const ruleRunsMap = ref({});
const ruleRunsLoading = ref(false);
// New / edit rule form
const showRuleForm = ref(false);
const editingRule = ref(null);
const ruleFormName = ref('');
const ruleFormTrigger = ref('lead_status_change');
const ruleFormTriggerConfig = ref({});
const ruleFormConditions = ref([]);
const ruleFormActions = ref([]);
const ruleSaving = ref(false);
function openNewRuleForm() {
    editingRule.value = null;
    ruleFormName.value = '';
    ruleFormTrigger.value = 'lead_status_change';
    ruleFormTriggerConfig.value = {};
    ruleFormConditions.value = [];
    ruleFormActions.value = [];
    showRuleForm.value = true;
    showTemplates.value = false;
}
function openEditRuleForm(rule) {
    editingRule.value = rule;
    ruleFormName.value = rule.name;
    ruleFormTrigger.value = rule.trigger;
    ruleFormTriggerConfig.value = { ...rule.trigger_config };
    ruleFormConditions.value = rule.conditions.map((c) => ({ ...c }));
    ruleFormActions.value = rule.actions.map((a) => ({ ...a }));
    showRuleForm.value = true;
    showTemplates.value = false;
}
function cancelRuleForm() {
    showRuleForm.value = false;
    editingRule.value = null;
}
function addCondition() {
    ruleFormConditions.value.push({ field: 'to_status', operator: 'eq', value: '' });
}
function removeCondition(i) {
    ruleFormConditions.value.splice(i, 1);
}
function addAction() {
    ruleFormActions.value.push({ type: 'send_email', to: 'owner', subject: '', body: '' });
}
function removeAction(i) {
    ruleFormActions.value.splice(i, 1);
}
function onActionTypeChange(i, newType) {
    const defaults = {
        send_email: { type: 'send_email', to: 'owner', subject: '', body: '' },
        create_task: { type: 'create_task', title: '', days_from_now: '3' },
        update_field: { type: 'update_field', field: 'status', value: '' },
        call_webhook: { type: 'call_webhook', url: '', method: 'POST' },
        run_plugin_action: { type: 'run_plugin_action', plugin_name: '', action: '' },
    };
    ruleFormActions.value[i] = defaults[newType] ?? { type: newType };
}
async function loadAutomations() {
    if (!firmStore.activeFirm)
        return;
    automationsLoading.value = true;
    const res = await api.get('/api/v1/crm/automations');
    automationsLoading.value = false;
    if (res.ok && Array.isArray(res.data))
        automationRules.value = res.data;
}
async function loadAutomationTemplates() {
    const res = await api.get('/api/v1/crm/automations/templates');
    if (res.ok && Array.isArray(res.data))
        automationTemplates.value = res.data;
}
async function saveRule() {
    if (!ruleFormName.value.trim()) {
        toast.error('Rule name is required.');
        return;
    }
    ruleSaving.value = true;
    const body = {
        name: ruleFormName.value.trim(),
        trigger: ruleFormTrigger.value,
        trigger_config: ruleFormTriggerConfig.value,
        conditions: ruleFormConditions.value,
        actions: ruleFormActions.value,
    };
    const res = editingRule.value
        ? await api.patch(`/api/v1/crm/automations/${editingRule.value.id}`, body)
        : await api.post('/api/v1/crm/automations', { ...body, is_active: true });
    ruleSaving.value = false;
    if (res.ok && res.data) {
        if (editingRule.value) {
            const idx = automationRules.value.findIndex((r) => r.id === editingRule.value.id);
            if (idx !== -1)
                automationRules.value.splice(idx, 1, res.data);
        }
        else {
            automationRules.value.unshift(res.data);
        }
        toast.success(editingRule.value ? 'Rule updated.' : 'Automation rule created.');
        cancelRuleForm();
    }
    else {
        toast.error('Failed to save rule.');
    }
}
async function toggleRule(rule) {
    const res = await api.patch(`/api/v1/crm/automations/${rule.id}`, {
        is_active: !rule.is_active,
    });
    if (res.ok && res.data) {
        const idx = automationRules.value.findIndex((r) => r.id === rule.id);
        if (idx !== -1)
            automationRules.value.splice(idx, 1, res.data);
        toast.success(res.data.is_active ? 'Rule enabled.' : 'Rule disabled.');
    }
    else {
        toast.error('Failed to update rule.');
    }
}
async function deleteRule(rule) {
    if (!confirm(`Delete automation rule "${rule.name}"? This cannot be undone.`))
        return;
    const res = await api.delete(`/api/v1/crm/automations/${rule.id}`);
    if (res.ok || res.status === 204) {
        automationRules.value = automationRules.value.filter((r) => r.id !== rule.id);
        if (expandedRuleRuns.value === rule.id)
            expandedRuleRuns.value = null;
        toast.success('Rule deleted.');
    }
    else {
        toast.error('Failed to delete rule.');
    }
}
async function toggleRuleRuns(rule) {
    if (expandedRuleRuns.value === rule.id) {
        expandedRuleRuns.value = null;
        return;
    }
    expandedRuleRuns.value = rule.id;
    if (!ruleRunsMap.value[rule.id]) {
        ruleRunsLoading.value = true;
        const res = await api.get(`/api/v1/crm/automations/${rule.id}/runs?limit=10`);
        ruleRunsLoading.value = false;
        if (res.ok && Array.isArray(res.data))
            ruleRunsMap.value[rule.id] = res.data;
    }
}
async function createFromTemplate(tmpl) {
    const res = await api.post(`/api/v1/crm/automations/from-template/${tmpl.id}`);
    if (res.ok && res.data) {
        automationRules.value.unshift(res.data);
        toast.success(`Rule "${res.data.name}" created from template.`);
        showTemplates.value = false;
    }
    else {
        toast.error('Failed to create rule from template.');
    }
}
function ruleReadableSummary(rule) {
    const triggerLabel = TRIGGER_LABELS[rule.trigger] ?? rule.trigger;
    const condCount = rule.conditions.length;
    const actCount = rule.actions.length;
    const condPart = condCount ? ` + ${condCount} condition${condCount > 1 ? 's' : ''}` : '';
    const actPart = `${actCount} action${actCount !== 1 ? 's' : ''}`;
    return `${triggerLabel}${condPart} → ${actPart}`;
}
function actionSummary(action) {
    const label = ACTION_TYPE_LABELS[action.type] ?? action.type;
    if (action.type === 'send_email')
        return `${label} to ${action.to}`;
    if (action.type === 'create_task')
        return `${label}: "${action.title}"`;
    if (action.type === 'update_field')
        return `${label}: ${action.field} = ${action.value}`;
    if (action.type === 'call_webhook')
        return `${label}: ${action.url}`;
    if (action.type === 'run_plugin_action')
        return `${label}: ${action.plugin_name}.${action.action}`;
    return label;
}
const __VLS_ctx = {
    ...{},
    ...{},
};
let __VLS_components;
let __VLS_intrinsics;
let __VLS_directives;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "p-6 max-w-2xl mx-auto space-y-5" },
});
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center gap-4 mb-5" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "relative w-16 h-16 rounded-2xl bg-red-100 flex items-center justify-center overflow-hidden flex-shrink-0" },
});
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['w-16']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
if (__VLS_ctx.avatarPreview) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
        src: (__VLS_ctx.avatarPreview),
        alt: "Avatar preview",
        ...{ class: "w-full h-full object-cover" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-red-600 text-2xl font-semibold" },
    });
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    (__VLS_ctx.authStore.user?.first_name?.[0]?.toUpperCase() ?? '?');
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "cursor-pointer text-sm text-red-600 hover:text-red-700 font-medium" },
});
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    ...{ onChange: (__VLS_ctx.onAvatarChange) },
    ref: "avatarInput",
    type: "file",
    accept: "image/*",
    ...{ class: "hidden" },
});
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
if (__VLS_ctx.avatarPreview) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.uploadAvatar) },
        disabled: (__VLS_ctx.avatarLoading),
        ...{ class: "ml-3 text-sm text-gray-600 border border-gray-200 rounded-lg px-3 py-1 hover:bg-gray-50 disabled:opacity-50" },
    });
    /** @type {__VLS_StyleScopedClasses['ml-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.avatarLoading ? 'Uploading…' : 'Upload');
}
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-400 mt-1" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
if (__VLS_ctx.profileError) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
    (__VLS_ctx.profileError);
}
if (__VLS_ctx.profileSuccess) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-3 rounded-xl bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-green-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
    ...{ onSubmit: (__VLS_ctx.saveProfile) },
    ...{ class: "space-y-3" },
});
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "grid grid-cols-2 gap-3" },
});
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs font-medium text-gray-700 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.profileFirstName),
    type: "text",
    ...{ class: "w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs font-medium text-gray-700 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.profileLastName),
    type: "text",
    ...{ class: "w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs font-medium text-gray-700 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.authStore.user?.email),
    type: "email",
    disabled: true,
    ...{ class: "w-full rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-not-allowed']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs font-medium text-gray-700 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.profileTimezone),
    type: "text",
    ...{ class: "w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    placeholder: "Europe/Prague",
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    type: "submit",
    disabled: (__VLS_ctx.profileLoading),
    ...{ class: "px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
(__VLS_ctx.profileLoading ? 'Saving…' : 'Save Profile');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-500 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "font-mono" },
});
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
(__VLS_ctx.firmStore.activeFirm?.slug);
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-500 mb-3" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "capitalize" },
});
/** @type {__VLS_StyleScopedClasses['capitalize']} */ ;
(__VLS_ctx.firmStore.activeFirm?.subscription_tier);
if (__VLS_ctx.workspaceError) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-3 rounded-xl bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
    (__VLS_ctx.workspaceError);
}
if (__VLS_ctx.workspaceSuccess) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-3 rounded-xl bg-green-50 border border-green-200 px-4 py-2 text-sm text-green-700" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-green-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
    ...{ onSubmit: (__VLS_ctx.saveWorkspaceName) },
    ...{ class: "flex gap-2" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.workspaceName),
    type: "text",
    ...{ class: "flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    placeholder: "Workspace name",
});
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    type: "submit",
    disabled: (__VLS_ctx.workspaceLoading),
    ...{ class: "px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
(__VLS_ctx.workspaceLoading ? 'Saving…' : 'Rename');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-red-200 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-red-600 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
if (!__VLS_ctx.confirmDeleteWorkspace) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(!__VLS_ctx.confirmDeleteWorkspace))
                    return;
                __VLS_ctx.confirmDeleteWorkspace = true;
                // @ts-ignore
                [avatarPreview, avatarPreview, avatarPreview, authStore, authStore, onAvatarChange, uploadAvatar, avatarLoading, avatarLoading, profileError, profileError, profileSuccess, saveProfile, profileFirstName, profileLastName, profileTimezone, profileLoading, profileLoading, firmStore, firmStore, workspaceError, workspaceError, workspaceSuccess, saveWorkspaceName, workspaceName, workspaceLoading, workspaceLoading, confirmDeleteWorkspace, confirmDeleteWorkspace,];
            } },
        ...{ class: "px-4 py-2 border border-red-300 text-red-600 rounded-xl text-sm hover:bg-red-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-3" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-sm text-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
    (__VLS_ctx.firmStore.activeFirm?.name);
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        value: (__VLS_ctx.confirmDeleteText),
        type: "text",
        placeholder: (__VLS_ctx.firmStore.activeFirm?.name),
        ...{ class: "w-full rounded-xl border border-red-300 px-3 py-2 text-sm focus:outline-none focus:border-red-500" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-red-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-500']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.confirmDeleteWorkspace))
                    return;
                __VLS_ctx.confirmDeleteWorkspace = false;
                __VLS_ctx.confirmDeleteText = '';
                // @ts-ignore
                [firmStore, firmStore, confirmDeleteWorkspace, confirmDeleteText, confirmDeleteText,];
            } },
        ...{ class: "flex-1 rounded-xl border border-gray-200 py-2 text-sm" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.deleteWorkspace) },
        disabled: (__VLS_ctx.dangerLoading || __VLS_ctx.confirmDeleteText !== __VLS_ctx.firmStore.activeFirm?.name),
        ...{ class: "flex-1 bg-red-600 text-white rounded-xl py-2 text-sm font-medium hover:bg-red-700 disabled:opacity-50" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.dangerLoading ? 'Deleting…' : 'Delete Workspace');
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
    ...{ class: "font-mono bg-gray-100 px-1 rounded" },
});
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['px-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
if (__VLS_ctx.createdTokenValue) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-4 rounded-xl bg-green-50 border border-green-200 p-4" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-green-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-xs font-semibold text-green-800 mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-green-800']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
        ...{ class: "flex-1 text-xs font-mono bg-white border border-green-200 rounded-lg px-3 py-2 break-all select-all" },
    });
    /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-green-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['break-all']} */ ;
    /** @type {__VLS_StyleScopedClasses['select-all']} */ ;
    (__VLS_ctx.createdTokenValue);
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.copyToken) },
        ...{ class: "px-3 py-2 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 flex-shrink-0" },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-green-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-green-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.createdTokenValue))
                    return;
                __VLS_ctx.createdTokenValue = null;
                // @ts-ignore
                [firmStore, confirmDeleteText, deleteWorkspace, dangerLoading, dangerLoading, createdTokenValue, createdTokenValue, createdTokenValue, copyToken,];
            } },
        ...{ class: "mt-2 text-xs text-green-700 underline" },
    });
    /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['underline']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
    ...{ onSubmit: (__VLS_ctx.createToken) },
    ...{ class: "flex gap-2 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.newTokenName),
    type: "text",
    placeholder: "Token name (e.g. CI/CD pipeline)",
    ...{ class: "flex-1 rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    type: "submit",
    disabled: (__VLS_ctx.newTokenCreating || !__VLS_ctx.newTokenName.trim()),
    ...{ class: "px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
(__VLS_ctx.newTokenCreating ? 'Creating…' : 'Create');
if (__VLS_ctx.tokensLoading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
else if (__VLS_ctx.tokens.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "divide-y divide-gray-100" },
    });
    /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
    /** @type {__VLS_StyleScopedClasses['divide-gray-100']} */ ;
    for (const [token] of __VLS_vFor((__VLS_ctx.tokens))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
            key: (token.id),
            ...{ class: "flex items-center justify-between py-3 gap-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "min-w-0" },
        });
        /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-sm font-medium text-gray-800" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        (token.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: (token.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500') },
            ...{ class: "text-xs px-2 py-0.5 rounded-full" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        (token.is_active ? 'Active' : 'Revoked');
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 font-mono mt-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        (token.prefix);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 mt-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        (new Date(token.created_at).toLocaleDateString());
        if (token.last_used_at) {
            (new Date(token.last_used_at).toLocaleDateString());
        }
        if (token.is_active) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.tokensLoading))
                            return;
                        if (!!(__VLS_ctx.tokens.length === 0))
                            return;
                        if (!(token.is_active))
                            return;
                        __VLS_ctx.revokeToken(token);
                        // @ts-ignore
                        [createToken, newTokenName, newTokenName, newTokenCreating, newTokenCreating, tokensLoading, tokens, tokens, revokeToken,];
                    } },
                ...{ class: "flex-shrink-0 text-xs text-red-600 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-50" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
        }
        // @ts-ignore
        [];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.form, __VLS_intrinsics.form)({
    ...{ onSubmit: (__VLS_ctx.createWebhook) },
    ...{ class: "space-y-2 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    type: "url",
    placeholder: "https://your-server.com/webhook",
    ...{ class: "w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
});
(__VLS_ctx.newWebhookUrl);
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.newWebhookEvents),
    type: "text",
    placeholder: "Events (comma-separated, e.g. lead.created,activity.created)",
    ...{ class: "w-full rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    type: "submit",
    disabled: (__VLS_ctx.newWebhookCreating || !__VLS_ctx.newWebhookUrl.trim()),
    ...{ class: "px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-60" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
(__VLS_ctx.newWebhookCreating ? 'Adding…' : 'Add Endpoint');
if (__VLS_ctx.webhooksLoading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
else if (__VLS_ctx.webhooks.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "divide-y divide-gray-100" },
    });
    /** @type {__VLS_StyleScopedClasses['divide-y']} */ ;
    /** @type {__VLS_StyleScopedClasses['divide-gray-100']} */ ;
    for (const [wh] of __VLS_vFor((__VLS_ctx.webhooks))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
            key: (wh.id),
            ...{ class: "py-3" },
        });
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-start justify-between gap-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "min-w-0" },
        });
        /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-sm font-mono text-gray-800 break-all" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['break-all']} */ ;
        (wh.url);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 mt-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "font-medium" },
        });
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (wh.events.length ? wh.events.join(', ') : 'all');
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2 flex-shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.webhooksLoading))
                        return;
                    if (!!(__VLS_ctx.webhooks.length === 0))
                        return;
                    __VLS_ctx.toggleWebhook(wh);
                    // @ts-ignore
                    [createWebhook, newWebhookUrl, newWebhookUrl, newWebhookEvents, newWebhookCreating, newWebhookCreating, webhooksLoading, webhooks, webhooks, toggleWebhook,];
                } },
            ...{ class: (wh.is_active ? 'bg-green-100 text-green-700 hover:bg-green-200' : 'bg-gray-100 text-gray-500 hover:bg-gray-200') },
            ...{ class: "text-xs px-2 py-1 rounded-lg" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        (wh.is_active ? 'Active' : 'Disabled');
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.webhooksLoading))
                        return;
                    if (!!(__VLS_ctx.webhooks.length === 0))
                        return;
                    __VLS_ctx.deleteWebhook(wh);
                    // @ts-ignore
                    [deleteWebhook,];
                } },
            ...{ class: "text-xs text-red-600 border border-red-200 rounded-lg px-2 py-1 hover:bg-red-50" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
        // @ts-ignore
        [];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between py-3 border-b border-gray-50" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-50']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-sm font-medium text-gray-800" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-400 mt-0.5" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.toggleDigest) },
    disabled: (__VLS_ctx.digestLoading),
    ...{ class: (__VLS_ctx.digestEnabled ? 'bg-green-600' : 'bg-gray-200') },
    ...{ class: "relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-60 flex-shrink-0" },
    role: "switch",
    'aria-checked': (__VLS_ctx.digestEnabled),
    'aria-label': "Toggle weekly digest",
});
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['w-11']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span)({
    ...{ class: (__VLS_ctx.digestEnabled ? 'translate-x-6' : 'translate-x-1') },
    ...{ class: "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform" },
});
/** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['transform']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between py-3" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-sm font-medium text-gray-800" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "text-xs text-gray-400 mt-0.5" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
if (!__VLS_ctx.pushSupported) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-xs text-amber-600 mt-0.5" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-amber-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
}
if (__VLS_ctx.pushSupported) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.pushSupported))
                    return;
                __VLS_ctx.pushSubscribed ? __VLS_ctx.unsubscribePush() : __VLS_ctx.subscribePush();
                // @ts-ignore
                [toggleDigest, digestLoading, digestEnabled, digestEnabled, digestEnabled, pushSupported, pushSupported, pushSubscribed, unsubscribePush, subscribePush,];
            } },
        disabled: (__VLS_ctx.pushLoading),
        ...{ class: (__VLS_ctx.pushSubscribed ? 'bg-green-600' : 'bg-gray-200') },
        ...{ class: "relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-60 flex-shrink-0" },
        role: "switch",
        'aria-checked': (__VLS_ctx.pushSubscribed),
        'aria-label': "Toggle push notifications",
    });
    /** @type {__VLS_StyleScopedClasses['relative']} */ ;
    /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-11']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-60']} */ ;
    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
        ...{ class: (__VLS_ctx.pushSubscribed ? 'translate-x-6' : 'translate-x-1') },
        ...{ class: "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform" },
    });
    /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
    /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['transform']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['shadow']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mt-0.5" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
if (!__VLS_ctx.isPro) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "rounded-xl bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-700 px-4 py-3 text-sm text-purple-700 dark:text-purple-300" },
    });
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-purple-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-purple-900/20']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-purple-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-purple-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-purple-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-purple-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.strong, __VLS_intrinsics.strong)({});
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-2" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-4" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
    if (__VLS_ctx.brandLogoPreview || __VLS_ctx.firmStore.activeFirm?.logo_url) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
            src: (__VLS_ctx.brandLogoPreview || __VLS_ctx.firmStore.activeFirm?.logo_url),
            alt: "Logo preview",
            ...{ class: "h-12 w-auto rounded-lg border border-gray-200" },
        });
        /** @type {__VLS_StyleScopedClasses['h-12']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-auto']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    }
    else {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "h-12 w-24 rounded-lg bg-gray-100 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 flex items-center justify-center text-xs text-gray-400" },
        });
        /** @type {__VLS_StyleScopedClasses['h-12']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-24']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        ...{ onChange: (__VLS_ctx.onBrandLogoChange) },
        ref: "brandLogoInput",
        type: "file",
        accept: "image/*",
        ...{ class: "hidden" },
    });
    /** @type {__VLS_StyleScopedClasses['hidden']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                if (!!(!__VLS_ctx.isPro))
                    return;
                __VLS_ctx.brandLogoInput?.click();
                // @ts-ignore
                [firmStore, firmStore, pushSubscribed, pushSubscribed, pushSubscribed, pushLoading, isPro, brandLogoPreview, brandLogoPreview, onBrandLogoChange, brandLogoInput,];
            } },
        ...{ class: "px-3 py-1.5 border border-gray-200 dark:border-gray-600 text-sm rounded-xl hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-2" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center gap-3" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        type: "color",
        ...{ class: "h-9 w-14 cursor-pointer rounded-lg border border-gray-200 p-1" },
    });
    (__VLS_ctx.brandColor);
    /** @type {__VLS_StyleScopedClasses['h-9']} */ ;
    /** @type {__VLS_StyleScopedClasses['w-14']} */ ;
    /** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
        ...{ class: "text-xs font-mono text-gray-600 dark:text-gray-400" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    (__VLS_ctx.brandColor);
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.saveBranding) },
        disabled: (__VLS_ctx.brandSaving),
        ...{ class: "px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-blue-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-blue-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.brandSaving ? 'Saving…' : 'Save branding');
    if (__VLS_ctx.brandError) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-red-600" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
        (__VLS_ctx.brandError);
    }
    if (__VLS_ctx.brandSuccess) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-green-600" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5 space-y-4" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mt-0.5" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex gap-3" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
for (const [lang] of __VLS_vFor(([{ code: 'en', label: '🇬🇧 English' }, { code: 'cs', label: '🇨🇿 Čeština' }]))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.changeLocale(lang.code);
                // @ts-ignore
                [brandColor, brandColor, saveBranding, brandSaving, brandSaving, brandError, brandError, brandSuccess, changeLocale,];
            } },
        key: (lang.code),
        ...{ class: (__VLS_ctx.currentLocale === lang.code ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600') },
        ...{ class: "px-4 py-2 rounded-xl text-sm font-medium transition-colors" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
    (lang.label);
    // @ts-ignore
    [currentLocale,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-6" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-base font-semibold text-gray-900 dark:text-gray-100 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mb-5" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
if (__VLS_ctx.leadScoringStore.loading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "animate-pulse space-y-2 mb-4" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    for (const [i] of __VLS_vFor((2))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            key: (i),
            ...{ class: "h-10 bg-gray-100 dark:bg-gray-700 rounded-xl" },
        });
        /** @type {__VLS_StyleScopedClasses['h-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        // @ts-ignore
        [leadScoringStore,];
    }
}
else if (__VLS_ctx.leadScoringStore.rules.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400 dark:text-gray-500 mb-4" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
        ...{ class: "space-y-2 mb-5" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
    for (const [rule] of __VLS_vFor((__VLS_ctx.leadScoringStore.rules))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
            key: (rule.id),
            ...{ class: "flex items-center gap-3 px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-2.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "flex-1 text-sm text-gray-700 dark:text-gray-300" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "font-medium" },
        });
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        (__VLS_ctx.SCORING_FIELDS.find((f) => f.value === rule.field)?.label ?? rule.field);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-gray-400 mx-1" },
        });
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mx-1']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.code, __VLS_intrinsics.code)({
            ...{ class: "bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs" },
        });
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        (rule.operand);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-xs font-semibold px-2 py-0.5 rounded-full" },
            ...{ class: (rule.score_delta >= 0 ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300') },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        (rule.score_delta >= 0 ? '+' : '');
        (rule.score_delta);
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.leadScoringStore.loading))
                        return;
                    if (!!(__VLS_ctx.leadScoringStore.rules.length === 0))
                        return;
                    __VLS_ctx.removeScoringRule(rule.id);
                    // @ts-ignore
                    [leadScoringStore, leadScoringStore, SCORING_FIELDS, removeScoringRule,];
                } },
            ...{ class: "p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-500 text-xs" },
            'aria-label': (`Delete scoring rule for ${rule.field}`),
        });
        /** @type {__VLS_StyleScopedClasses['p-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:bg-red-900/30']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        // @ts-ignore
        [];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "border-t border-gray-100 dark:border-gray-700 pt-4" },
});
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h3, __VLS_intrinsics.h3)({
    ...{ class: "text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-3" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
if (__VLS_ctx.ruleError) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-2 text-xs text-red-600 dark:text-red-400" },
        role: "alert",
    });
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-red-400']} */ ;
    (__VLS_ctx.ruleError);
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex flex-wrap gap-2 items-end" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['items-end']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs text-gray-500 dark:text-gray-400 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
    value: (__VLS_ctx.newRuleField),
    ...{ class: "rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
for (const [f] of __VLS_vFor((__VLS_ctx.SCORING_FIELDS))) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
        key: (f.value),
        value: (f.value),
    });
    (f.label);
    // @ts-ignore
    [SCORING_FIELDS, ruleError, ruleError, newRuleField,];
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs text-gray-500 dark:text-gray-400 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.newRuleOperand),
    type: "text",
    placeholder: "e.g. won, web, 5000…",
    ...{ class: "rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 w-36 focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['w-36']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
__VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
    ...{ class: "block text-xs text-gray-500 dark:text-gray-400 mb-1" },
});
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    type: "number",
    ...{ class: "rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm px-3 py-1.5 w-24 focus:outline-none focus:border-red-400" },
    placeholder: "+10",
});
(__VLS_ctx.newRuleScoreDelta);
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['w-24']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.addScoringRule) },
    disabled: (__VLS_ctx.ruleLoading),
    ...{ class: "px-4 py-1.5 bg-[color:var(--brand-color)] text-white rounded-xl text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[color:var(--brand-color)]']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:opacity-90']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-opacity']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
(__VLS_ctx.ruleLoading ? 'Adding…' : '+ Add rule');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white rounded-2xl border border-gray-100 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
if (__VLS_ctx.propTemplatesLoading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "animate-pulse space-y-2 mb-4" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    for (const [i] of __VLS_vFor((2))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            key: (i),
            ...{ class: "h-10 bg-gray-100 rounded-xl" },
        });
        /** @type {__VLS_StyleScopedClasses['h-10']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        // @ts-ignore
        [newRuleOperand, newRuleScoreDelta, addScoringRule, ruleLoading, ruleLoading, propTemplatesLoading,];
    }
}
else if (__VLS_ctx.propTemplates.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400 mb-4" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-4 space-y-2" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    for (const [tmpl] of __VLS_vFor((__VLS_ctx.propTemplates))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (tmpl.id),
            ...{ class: "border border-gray-100 rounded-xl overflow-hidden" },
        });
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2 px-4 py-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.propTemplatesLoading))
                        return;
                    if (!!(__VLS_ctx.propTemplates.length === 0))
                        return;
                    __VLS_ctx.expandedTemplate = __VLS_ctx.expandedTemplate === tmpl.id ? null : tmpl.id;
                    // @ts-ignore
                    [propTemplates, propTemplates, expandedTemplate, expandedTemplate,];
                } },
            ...{ class: "flex-1 text-left text-sm font-medium text-gray-800 hover:text-red-600 transition-colors" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        (tmpl.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-xs text-gray-400 ml-2" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
        (tmpl.items.length);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-xs text-gray-400 ml-1" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
        (__VLS_ctx.expandedTemplate === tmpl.id ? '▲' : '▼');
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.propTemplatesLoading))
                        return;
                    if (!!(__VLS_ctx.propTemplates.length === 0))
                        return;
                    __VLS_ctx.deletePropTemplate(tmpl.id);
                    // @ts-ignore
                    [expandedTemplate, deletePropTemplate,];
                } },
            ...{ class: "text-xs text-red-400 hover:text-red-600 px-2" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        if (__VLS_ctx.expandedTemplate === tmpl.id) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "border-t border-gray-100 px-4 pb-3" },
            });
            /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['pb-3']} */ ;
            if (tmpl.items.length === 0) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "text-xs text-gray-400 py-2" },
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.table, __VLS_intrinsics.table)({
                    ...{ class: "w-full text-xs mb-2 mt-2" },
                });
                /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.thead, __VLS_intrinsics.thead)({});
                __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                    ...{ class: "border-b border-gray-100 text-gray-500" },
                });
                /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
                /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "text-left pb-1.5" },
                });
                /** @type {__VLS_StyleScopedClasses['text-left']} */ ;
                /** @type {__VLS_StyleScopedClasses['pb-1.5']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "text-right pb-1.5 w-12" },
                });
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['pb-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['w-12']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "text-right pb-1.5 w-20" },
                });
                /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                /** @type {__VLS_StyleScopedClasses['pb-1.5']} */ ;
                /** @type {__VLS_StyleScopedClasses['w-20']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.th, __VLS_intrinsics.th)({
                    ...{ class: "w-8" },
                });
                /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
                __VLS_asFunctionalElement1(__VLS_intrinsics.tbody, __VLS_intrinsics.tbody)({});
                for (const [item] of __VLS_vFor((tmpl.items))) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.tr, __VLS_intrinsics.tr)({
                        key: (item.id),
                        ...{ class: "border-b border-gray-50" },
                    });
                    /** @type {__VLS_StyleScopedClasses['border-b']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border-gray-50']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "py-1.5 text-gray-700" },
                    });
                    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    (item.description);
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "py-1.5 text-right text-gray-500" },
                    });
                    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                    (item.quantity);
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "py-1.5 text-right text-gray-500" },
                    });
                    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                    (Number(item.unit_price).toFixed(2));
                    __VLS_asFunctionalElement1(__VLS_intrinsics.td, __VLS_intrinsics.td)({
                        ...{ class: "py-1.5 text-right" },
                    });
                    /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                        ...{ onClick: (...[$event]) => {
                                if (!!(__VLS_ctx.propTemplatesLoading))
                                    return;
                                if (!!(__VLS_ctx.propTemplates.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedTemplate === tmpl.id))
                                    return;
                                if (!!(tmpl.items.length === 0))
                                    return;
                                __VLS_ctx.deleteTmplItem(tmpl, item.id);
                                // @ts-ignore
                                [expandedTemplate, deleteTmplItem,];
                            } },
                        ...{ class: "text-gray-300 hover:text-red-400 transition-colors" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['hover:text-red-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
                    // @ts-ignore
                    [];
                }
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex gap-2 mt-1" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                value: (__VLS_ctx.newTmplItemDesc),
                type: "text",
                placeholder: "Item description",
                ...{ class: "flex-1 rounded-lg border border-gray-200 px-2 py-1 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                type: "number",
                min: "1",
                step: "1",
                placeholder: "Qty",
                ...{ class: "w-14 rounded-lg border border-gray-200 px-2 py-1 text-xs text-right focus:outline-none focus:border-red-400" },
            });
            (__VLS_ctx.newTmplItemQty);
            /** @type {__VLS_StyleScopedClasses['w-14']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                type: "number",
                min: "0",
                step: "0.01",
                placeholder: "Price",
                ...{ class: "w-20 rounded-lg border border-gray-200 px-2 py-1 text-xs text-right focus:outline-none focus:border-red-400" },
            });
            (__VLS_ctx.newTmplItemPrice);
            /** @type {__VLS_StyleScopedClasses['w-20']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-right']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.propTemplatesLoading))
                            return;
                        if (!!(__VLS_ctx.propTemplates.length === 0))
                            return;
                        if (!(__VLS_ctx.expandedTemplate === tmpl.id))
                            return;
                        __VLS_ctx.addTmplItem(tmpl);
                        // @ts-ignore
                        [newTmplItemDesc, newTmplItemQty, newTmplItemPrice, addTmplItem,];
                    } },
                disabled: (__VLS_ctx.addingTmplItem || !__VLS_ctx.newTmplItemDesc.trim()),
                ...{ class: "px-3 py-1 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50" },
            });
            /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
        }
        // @ts-ignore
        [newTmplItemDesc, addingTmplItem,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "border border-dashed border-gray-200 rounded-xl p-4 space-y-2" },
});
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs font-medium text-gray-500" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.input)({
    value: (__VLS_ctx.newTemplateName),
    type: "text",
    placeholder: "Template name *",
    ...{ class: "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.textarea)({
    value: (__VLS_ctx.newTemplateIntro),
    rows: "2",
    placeholder: "Intro text (optional)…",
    ...{ class: "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.textarea)({
    value: (__VLS_ctx.newTemplateClosing),
    rows: "2",
    placeholder: "Closing text (optional)…",
    ...{ class: "w-full rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:border-red-400 resize-none" },
});
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.createPropTemplate) },
    disabled: (__VLS_ctx.newTemplateCreating || !__VLS_ctx.newTemplateName.trim()),
    ...{ class: "px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50" },
});
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
(__VLS_ctx.newTemplateCreating ? 'Creating…' : '+ Create Template');
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between mb-1" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
    ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
(__VLS_ctx.localPluginCount);
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    href: "/docs/plugins/",
    target: "_blank",
    ...{ class: "text-red-600 hover:underline" },
});
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
if (__VLS_ctx.pluginsLoading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "animate-pulse space-y-3" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    for (const [i] of __VLS_vFor((3))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            key: (i),
            ...{ class: "h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" },
        });
        /** @type {__VLS_StyleScopedClasses['h-14']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        // @ts-ignore
        [newTemplateName, newTemplateName, newTemplateIntro, newTemplateClosing, createPropTemplate, newTemplateCreating, newTemplateCreating, localPluginCount, pluginsLoading,];
    }
}
else if (__VLS_ctx.pluginConfigs.length === 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400 dark:text-gray-500 py-4 text-center" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
        href: "https://github.com/JakubMusil/LeadLab/tree/main/docs/plugin-registry.json",
        target: "_blank",
        ...{ class: "block mt-1 text-red-600 hover:underline text-xs" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
}
else {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-3" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    for (const [pc] of __VLS_vFor((__VLS_ctx.pluginConfigs))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (pc.plugin_name),
            ...{ class: "border border-gray-100 dark:border-gray-700 rounded-xl overflow-hidden" },
        });
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-3 px-4 py-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-700 flex items-center justify-center flex-shrink-0 overflow-hidden" },
        });
        /** @type {__VLS_StyleScopedClasses['w-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-8']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
        if (pc.plugin?.icon_url) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.img)({
                ...{ onError: ((e) => e.target.style.display = 'none') },
                src: (pc.plugin.icon_url),
                alt: (pc.plugin_name),
                ...{ class: "w-full h-full object-cover" },
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['h-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
        }
        else {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "text-lg" },
            });
            /** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex-1 min-w-0" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2 flex-wrap" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-sm font-medium text-gray-800 dark:text-gray-100" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        (pc.plugin_name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        (pc.plugin?.version ?? '?');
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-500 dark:text-gray-400 truncate" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
        (pc.plugin?.description ?? '');
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2 flex-shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        if (pc.plugin && Object.keys(pc.plugin.config_schema?.properties ?? {}).length > 0) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.pluginsLoading))
                            return;
                        if (!!(__VLS_ctx.pluginConfigs.length === 0))
                            return;
                        if (!(pc.plugin && Object.keys(pc.plugin.config_schema?.properties ?? {}).length > 0))
                            return;
                        __VLS_ctx.expandedPlugin = __VLS_ctx.expandedPlugin === pc.plugin_name ? null : pc.plugin_name;
                        // @ts-ignore
                        [pluginConfigs, pluginConfigs, expandedPlugin, expandedPlugin,];
                    } },
                ...{ class: "text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:text-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:hover:text-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
            (__VLS_ctx.expandedPlugin === pc.plugin_name ? 'Close' : 'Configure');
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.pluginsLoading))
                        return;
                    if (!!(__VLS_ctx.pluginConfigs.length === 0))
                        return;
                    __VLS_ctx.togglePlugin(pc);
                    // @ts-ignore
                    [expandedPlugin, togglePlugin,];
                } },
            ...{ class: (pc.enabled ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-600') },
            ...{ class: "relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0" },
            role: "switch",
            'aria-checked': (pc.enabled),
            'aria-label': (`Toggle ${pc.plugin_name}`),
        });
        /** @type {__VLS_StyleScopedClasses['relative']} */ ;
        /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-11']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ class: (pc.enabled ? 'translate-x-6' : 'translate-x-1') },
            ...{ class: "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform" },
        });
        /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['transform']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
        if (pc.plugin?.permissions?.length) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "px-4 pb-2 flex flex-wrap gap-1" },
            });
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['pb-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
            for (const [perm] of __VLS_vFor((pc.plugin.permissions))) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                    key: (perm),
                    ...{ class: "text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-full px-2 py-0.5" },
                });
                /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
                /** @type {__VLS_StyleScopedClasses['bg-blue-50']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:bg-blue-900/20']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-blue-300']} */ ;
                /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
                /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
                /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
                (perm);
                // @ts-ignore
                [];
            }
        }
        if (__VLS_ctx.expandedPlugin === pc.plugin_name && pc.plugin) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "border-t border-gray-100 dark:border-gray-700 px-4 pb-4 pt-3 space-y-3" },
            });
            /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['pb-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['pt-3']} */ ;
            /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
            for (const [prop, key] of __VLS_vFor(((pc.plugin.config_schema?.properties ?? {})))) {
                (key);
                if (prop.type === 'boolean') {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                        ...{ class: "flex items-center justify-between" },
                    });
                    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
                    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
                    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                        ...{ class: "text-xs font-medium text-gray-700 dark:text-gray-300" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    (prop.title ?? key);
                    if (prop.description) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                            ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
                        });
                        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                        (prop.description);
                    }
                    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                        ...{ onChange: (...[$event]) => {
                                if (!!(__VLS_ctx.pluginsLoading))
                                    return;
                                if (!!(__VLS_ctx.pluginConfigs.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedPlugin === pc.plugin_name && pc.plugin))
                                    return;
                                if (!(prop.type === 'boolean'))
                                    return;
                                __VLS_ctx.setDraftValue(pc.plugin_name, key, $event.target.checked);
                                // @ts-ignore
                                [expandedPlugin, setDraftValue,];
                            } },
                        type: "checkbox",
                        checked: (Boolean(__VLS_ctx.getDraftValue(pc.plugin_name, key) ?? prop.default ?? false)),
                        ...{ class: "rounded" },
                    });
                    /** @type {__VLS_StyleScopedClasses['rounded']} */ ;
                }
                else if (prop.type === 'number') {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
                    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
                    });
                    /** @type {__VLS_StyleScopedClasses['block']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
                    (prop.title ?? key);
                    if (prop.description) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                            ...{ class: "text-xs text-gray-400 dark:text-gray-500 mb-1" },
                        });
                        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                        /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
                        (prop.description);
                    }
                    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                        ...{ onInput: (...[$event]) => {
                                if (!!(__VLS_ctx.pluginsLoading))
                                    return;
                                if (!!(__VLS_ctx.pluginConfigs.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedPlugin === pc.plugin_name && pc.plugin))
                                    return;
                                if (!!(prop.type === 'boolean'))
                                    return;
                                if (!(prop.type === 'number'))
                                    return;
                                __VLS_ctx.setDraftValue(pc.plugin_name, key, Number($event.target.value));
                                // @ts-ignore
                                [setDraftValue, getDraftValue,];
                            } },
                        type: "number",
                        value: (__VLS_ctx.getDraftValue(pc.plugin_name, key) ?? prop.default ?? ''),
                        ...{ class: "w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
                    });
                    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
                    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                }
                else if (prop.secret) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
                    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
                    });
                    /** @type {__VLS_StyleScopedClasses['block']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
                    (prop.title ?? key);
                    if (prop.description) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                            ...{ class: "text-xs text-gray-400 dark:text-gray-500 mb-1" },
                        });
                        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                        /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
                        (prop.description);
                    }
                    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                        ...{ onInput: (...[$event]) => {
                                if (!!(__VLS_ctx.pluginsLoading))
                                    return;
                                if (!!(__VLS_ctx.pluginConfigs.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedPlugin === pc.plugin_name && pc.plugin))
                                    return;
                                if (!!(prop.type === 'boolean'))
                                    return;
                                if (!!(prop.type === 'number'))
                                    return;
                                if (!(prop.secret))
                                    return;
                                __VLS_ctx.setDraftValue(pc.plugin_name, key, $event.target.value);
                                // @ts-ignore
                                [setDraftValue, getDraftValue,];
                            } },
                        type: "password",
                        autocomplete: "new-password",
                        value: (__VLS_ctx.getDraftValue(pc.plugin_name, key) ?? ''),
                        ...{ class: "w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
                        placeholder: "••••••••",
                    });
                    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
                    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                }
                else {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
                    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
                    });
                    /** @type {__VLS_StyleScopedClasses['block']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
                    (prop.title ?? key);
                    if (prop.description) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                            ...{ class: "text-xs text-gray-400 dark:text-gray-500 mb-1" },
                        });
                        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
                        /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
                        (prop.description);
                    }
                    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                        ...{ onInput: (...[$event]) => {
                                if (!!(__VLS_ctx.pluginsLoading))
                                    return;
                                if (!!(__VLS_ctx.pluginConfigs.length === 0))
                                    return;
                                if (!(__VLS_ctx.expandedPlugin === pc.plugin_name && pc.plugin))
                                    return;
                                if (!!(prop.type === 'boolean'))
                                    return;
                                if (!!(prop.type === 'number'))
                                    return;
                                if (!!(prop.secret))
                                    return;
                                __VLS_ctx.setDraftValue(pc.plugin_name, key, $event.target.value);
                                // @ts-ignore
                                [setDraftValue, getDraftValue,];
                            } },
                        type: "text",
                        value: (__VLS_ctx.getDraftValue(pc.plugin_name, key) ?? prop.default ?? ''),
                        ...{ class: "w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
                    });
                    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border']} */ ;
                    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
                    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
                    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
                    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
                    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
                }
                // @ts-ignore
                [getDraftValue,];
            }
            __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
                ...{ onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.pluginsLoading))
                            return;
                        if (!!(__VLS_ctx.pluginConfigs.length === 0))
                            return;
                        if (!(__VLS_ctx.expandedPlugin === pc.plugin_name && pc.plugin))
                            return;
                        __VLS_ctx.savePluginConfig(pc);
                        // @ts-ignore
                        [savePluginConfig,];
                    } },
                disabled: (__VLS_ctx.pluginSaving[pc.plugin_name]),
                ...{ class: "px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50" },
            });
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
            /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
            (__VLS_ctx.pluginSaving[pc.plugin_name] ? 'Saving…' : 'Save settings');
        }
        // @ts-ignore
        [pluginSaving, pluginSaving,];
    }
}
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "mt-4 pt-4 border-t border-gray-100 dark:border-gray-700" },
});
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.a, __VLS_intrinsics.a)({
    href: "https://github.com/JakubMusil/LeadLab/blob/main/public/plugin-registry.json",
    target: "_blank",
    rel: "noopener",
    ...{ class: "text-xs text-red-600 hover:underline" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:underline']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700 p-5" },
});
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:bg-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex items-center justify-between mb-1" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.h2, __VLS_intrinsics.h2)({
    ...{ class: "text-sm font-semibold text-gray-900 dark:text-gray-100" },
});
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
    ...{ class: "flex gap-2" },
});
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.showTemplates = !__VLS_ctx.showTemplates;
            __VLS_ctx.showRuleForm = false;
            // @ts-ignore
            [showTemplates, showTemplates, showRuleForm,];
        } },
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
(__VLS_ctx.showTemplates ? 'Hide templates' : '📋 Templates');
__VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
    ...{ onClick: (__VLS_ctx.openNewRuleForm) },
    ...{ class: "text-xs bg-red-600 text-white rounded-lg px-3 py-1.5 hover:bg-red-700" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
__VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
    ...{ class: "text-xs text-gray-500 dark:text-gray-400 mb-4" },
});
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
if (__VLS_ctx.showTemplates) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-4 border border-dashed border-gray-200 dark:border-gray-600 rounded-xl p-4 space-y-2" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    if (__VLS_ctx.automationTemplates.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-sm text-gray-400" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    }
    for (const [tmpl] of __VLS_vFor((__VLS_ctx.automationTemplates))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (tmpl.id),
            ...{ class: "flex items-start gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-700" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex-1 min-w-0" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-sm font-medium text-gray-800 dark:text-gray-100" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        (tmpl.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-500 dark:text-gray-400 mt-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        (tmpl.description);
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500 mt-0.5 font-mono" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
        (__VLS_ctx.TRIGGER_LABELS[tmpl.trigger] ?? tmpl.trigger);
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showTemplates))
                        return;
                    __VLS_ctx.createFromTemplate(tmpl);
                    // @ts-ignore
                    [showTemplates, showTemplates, openNewRuleForm, automationTemplates, automationTemplates, TRIGGER_LABELS, createFromTemplate,];
                } },
            ...{ class: "flex-shrink-0 text-xs bg-red-600 text-white rounded-lg px-3 py-1.5 hover:bg-red-700" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
        // @ts-ignore
        [];
    }
}
if (__VLS_ctx.showRuleForm) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "mb-4 border border-gray-200 dark:border-gray-600 rounded-xl p-4 space-y-4" },
    });
    /** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['p-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
        ...{ class: "text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
    /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
    (__VLS_ctx.editingRule ? 'Edit rule' : 'New rule');
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
        value: (__VLS_ctx.ruleFormName),
        type: "text",
        placeholder: "e.g. Notify owner when lead won",
        ...{ class: "w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1" },
    });
    /** @type {__VLS_StyleScopedClasses['block']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
        value: (__VLS_ctx.ruleFormTrigger),
        ...{ class: "w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400" },
    });
    /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
    /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
    /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    for (const [label, key] of __VLS_vFor((__VLS_ctx.TRIGGER_LABELS))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
            key: (key),
            value: (key),
        });
        (label);
        // @ts-ignore
        [showRuleForm, TRIGGER_LABELS, editingRule, ruleFormName, ruleFormTrigger,];
    }
    if (__VLS_ctx.ruleFormTrigger === 'lead_inactive') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "text-xs font-medium text-gray-700 dark:text-gray-300 w-32" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-32']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            ...{ onInput: (...[$event]) => {
                    if (!(__VLS_ctx.showRuleForm))
                        return;
                    if (!(__VLS_ctx.ruleFormTrigger === 'lead_inactive'))
                        return;
                    __VLS_ctx.ruleFormTriggerConfig['inactive_days'] = Number($event.target.value);
                    // @ts-ignore
                    [ruleFormTrigger, ruleFormTriggerConfig,];
                } },
            value: (__VLS_ctx.ruleFormTriggerConfig['inactive_days'] ?? 30),
            type: "number",
            min: "1",
            ...{ class: "w-24 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" },
        });
        /** @type {__VLS_StyleScopedClasses['w-24']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    }
    else if (__VLS_ctx.ruleFormTrigger === 'task_overdue') {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
            ...{ class: "text-xs font-medium text-gray-700 dark:text-gray-300 w-32" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-32']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            ...{ onInput: (...[$event]) => {
                    if (!(__VLS_ctx.showRuleForm))
                        return;
                    if (!!(__VLS_ctx.ruleFormTrigger === 'lead_inactive'))
                        return;
                    if (!(__VLS_ctx.ruleFormTrigger === 'task_overdue'))
                        return;
                    __VLS_ctx.ruleFormTriggerConfig['warning_days'] = Number($event.target.value);
                    // @ts-ignore
                    [ruleFormTrigger, ruleFormTriggerConfig, ruleFormTriggerConfig,];
                } },
            value: (__VLS_ctx.ruleFormTriggerConfig['warning_days'] ?? 1),
            type: "number",
            min: "0",
            ...{ class: "w-24 rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-1.5 text-sm focus:outline-none focus:border-red-400" },
        });
        /** @type {__VLS_StyleScopedClasses['w-24']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-between mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "text-xs font-medium text-gray-700 dark:text-gray-300" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.addCondition) },
        ...{ class: "text-xs text-red-600 hover:text-red-700" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-red-700']} */ ;
    if (__VLS_ctx.ruleFormConditions.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500 italic" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['italic']} */ ;
    }
    for (const [cond, i] of __VLS_vFor((__VLS_ctx.ruleFormConditions))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (i),
            ...{ class: "flex gap-2 mb-2 items-center flex-wrap" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            value: (cond.field),
            type: "text",
            placeholder: "field (e.g. to_status)",
            ...{ class: "flex-1 min-w-[120px] rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-w-[120px]']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
            value: (cond.operator),
            ...{ class: "rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
        });
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        for (const [label, op] of __VLS_vFor((__VLS_ctx.OPERATOR_LABELS))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                key: (op),
                value: (op),
            });
            (label);
            // @ts-ignore
            [ruleFormTriggerConfig, addCondition, ruleFormConditions, ruleFormConditions, OPERATOR_LABELS,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
            value: (cond.value),
            type: "text",
            placeholder: "value",
            ...{ class: "flex-1 min-w-[100px] rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-w-[100px]']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showRuleForm))
                        return;
                    __VLS_ctx.removeCondition(i);
                    // @ts-ignore
                    [removeCondition,];
                } },
            ...{ class: "text-gray-300 hover:text-red-400 text-sm" },
        });
        /** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-red-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        // @ts-ignore
        [];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({});
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex items-center justify-between mb-2" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
    /** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
    /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
        ...{ class: "text-xs font-medium text-gray-700 dark:text-gray-300" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-300']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.addAction) },
        ...{ class: "text-xs text-red-600 hover:text-red-700" },
    });
    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:text-red-700']} */ ;
    if (__VLS_ctx.ruleFormActions.length === 0) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "text-xs text-gray-400 dark:text-gray-500 italic" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['italic']} */ ;
    }
    for (const [action, i] of __VLS_vFor((__VLS_ctx.ruleFormActions))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (i),
            ...{ class: "mb-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-700 space-y-2" },
        });
        /** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['p-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
            ...{ onChange: (...[$event]) => {
                    if (!(__VLS_ctx.showRuleForm))
                        return;
                    __VLS_ctx.onActionTypeChange(i, $event.target.value);
                    // @ts-ignore
                    [addAction, ruleFormActions, ruleFormActions, onActionTypeChange,];
                } },
            value: (action.type),
            ...{ class: "flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
        /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        for (const [label, key] of __VLS_vFor((__VLS_ctx.ACTION_TYPE_LABELS))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                key: (key),
                value: (key),
            });
            (label);
            // @ts-ignore
            [ACTION_TYPE_LABELS,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showRuleForm))
                        return;
                    __VLS_ctx.removeAction(i);
                    // @ts-ignore
                    [removeAction,];
                } },
            ...{ class: "text-gray-300 hover:text-red-400 text-sm" },
        });
        /** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:text-red-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        if (action.type === 'send_email') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex gap-2" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                ...{ class: "text-xs text-gray-500 dark:text-gray-400 w-10 pt-1.5" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['w-10']} */ ;
            /** @type {__VLS_StyleScopedClasses['pt-1.5']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
                value: (action.to),
                ...{ class: "flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "owner",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "assignee",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "customer",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                value: (action.subject),
                type: "text",
                placeholder: "Subject",
                ...{ class: "w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.textarea)({
                value: (action.body),
                rows: "3",
                placeholder: "Email body. Use {{lead_title}}, {{customer_name}}, {{assignee_name}}…",
                ...{ class: "w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400 resize-none" },
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['resize-none']} */ ;
        }
        else if (action.type === 'create_task') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                value: (action.title),
                type: "text",
                placeholder: "Task title (supports {{lead_title}})",
                ...{ class: "w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex items-center gap-2" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.label, __VLS_intrinsics.label)({
                ...{ class: "text-xs text-gray-500 dark:text-gray-400" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                type: "number",
                min: "0",
                ...{ class: "w-20 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            (action.days_from_now);
            /** @type {__VLS_StyleScopedClasses['w-20']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                ...{ class: "text-xs text-gray-500 dark:text-gray-400" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        }
        else if (action.type === 'update_field') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex gap-2" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.select, __VLS_intrinsics.select)({
                value: (action.field),
                ...{ class: "flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "status",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "source",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "currency",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.option, __VLS_intrinsics.option)({
                value: "description",
            });
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                value: (action.value),
                type: "text",
                placeholder: "New value",
                ...{ class: "flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        }
        else if (action.type === 'call_webhook') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                type: "url",
                placeholder: "https://your-server.com/webhook",
                ...{ class: "w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            (action.url);
            /** @type {__VLS_StyleScopedClasses['w-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        }
        else if (action.type === 'run_plugin_action') {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "flex gap-2" },
            });
            /** @type {__VLS_StyleScopedClasses['flex']} */ ;
            /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                value: (action.plugin_name),
                type: "text",
                placeholder: "Plugin name",
                ...{ class: "flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.input)({
                value: (action.action),
                type: "text",
                placeholder: "Action name",
                ...{ class: "flex-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5 text-xs focus:outline-none focus:border-red-400" },
            });
            /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
            /** @type {__VLS_StyleScopedClasses['border']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
            /** @type {__VLS_StyleScopedClasses['focus:border-red-400']} */ ;
        }
        // @ts-ignore
        [];
    }
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "flex gap-2 pt-1" },
    });
    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['pt-1']} */ ;
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.saveRule) },
        disabled: (__VLS_ctx.ruleSaving || !__VLS_ctx.ruleFormName.trim()),
        ...{ class: "px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 disabled:opacity-50" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['bg-red-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-white']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-red-700']} */ ;
    /** @type {__VLS_StyleScopedClasses['disabled:opacity-50']} */ ;
    (__VLS_ctx.ruleSaving ? 'Saving…' : (__VLS_ctx.editingRule ? 'Update rule' : 'Create rule'));
    __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
        ...{ onClick: (__VLS_ctx.cancelRuleForm) },
        ...{ class: "px-4 py-2 border border-gray-200 dark:border-gray-600 rounded-xl text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" },
    });
    /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-2']} */ ;
    /** @type {__VLS_StyleScopedClasses['border']} */ ;
    /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
}
if (__VLS_ctx.automationsLoading) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "animate-pulse space-y-3" },
    });
    /** @type {__VLS_StyleScopedClasses['animate-pulse']} */ ;
    /** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
    for (const [i] of __VLS_vFor((2))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div)({
            key: (i),
            ...{ class: "h-14 bg-gray-100 dark:bg-gray-700 rounded-xl" },
        });
        /** @type {__VLS_StyleScopedClasses['h-14']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        // @ts-ignore
        [editingRule, ruleFormName, saveRule, ruleSaving, ruleSaving, cancelRuleForm, automationsLoading,];
    }
}
else if (!__VLS_ctx.automationsLoading && __VLS_ctx.automationRules.length === 0 && !__VLS_ctx.showRuleForm) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "text-sm text-gray-400 dark:text-gray-500 py-4 text-center" },
    });
    /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
    /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
    /** @type {__VLS_StyleScopedClasses['py-4']} */ ;
    /** @type {__VLS_StyleScopedClasses['text-center']} */ ;
}
else if (__VLS_ctx.automationRules.length > 0) {
    __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
        ...{ class: "space-y-2" },
    });
    /** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
    for (const [rule] of __VLS_vFor((__VLS_ctx.automationRules))) {
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            key: (rule.id),
            ...{ class: "border border-gray-100 dark:border-gray-700 rounded-xl overflow-hidden" },
        });
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
        /** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-start gap-3 px-4 py-3" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex-1 min-w-0" },
        });
        /** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-2 flex-wrap" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: "text-sm font-medium text-gray-800 dark:text-gray-100" },
        });
        /** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
        /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-100']} */ ;
        (rule.name);
        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
            ...{ class: (rule.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400') },
            ...{ class: "text-xs px-2 py-0.5 rounded-full" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        (rule.is_active ? 'Active' : 'Disabled');
        __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
            ...{ class: "text-xs text-gray-500 dark:text-gray-400 mt-0.5" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
        (__VLS_ctx.ruleReadableSummary(rule));
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex flex-wrap gap-1 mt-1" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
        for (const [action, i] of __VLS_vFor((rule.actions))) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                key: (i),
                ...{ class: "text-[10px] bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-300 rounded-full px-2 py-0.5" },
            });
            /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
            /** @type {__VLS_StyleScopedClasses['bg-blue-50']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:bg-blue-900/20']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-blue-300']} */ ;
            /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
            (__VLS_ctx.actionSummary(action));
            // @ts-ignore
            [showRuleForm, automationsLoading, automationRules, automationRules, automationRules, ruleReadableSummary, actionSummary,];
        }
        __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
            ...{ class: "flex items-center gap-1.5 flex-shrink-0" },
        });
        /** @type {__VLS_StyleScopedClasses['flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.automationsLoading))
                        return;
                    if (!!(!__VLS_ctx.automationsLoading && __VLS_ctx.automationRules.length === 0 && !__VLS_ctx.showRuleForm))
                        return;
                    if (!(__VLS_ctx.automationRules.length > 0))
                        return;
                    __VLS_ctx.toggleRuleRuns(rule);
                    // @ts-ignore
                    [toggleRuleRuns,];
                } },
            ...{ class: "text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-700" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
        (__VLS_ctx.expandedRuleRuns === rule.id ? 'Hide log' : 'Log');
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.automationsLoading))
                        return;
                    if (!!(!__VLS_ctx.automationsLoading && __VLS_ctx.automationRules.length === 0 && !__VLS_ctx.showRuleForm))
                        return;
                    if (!(__VLS_ctx.automationRules.length > 0))
                        return;
                    __VLS_ctx.openEditRuleForm(rule);
                    // @ts-ignore
                    [expandedRuleRuns, openEditRuleForm,];
                } },
            ...{ class: "text-xs text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-700" },
        });
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['border']} */ ;
        /** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:border-gray-600']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['px-2']} */ ;
        /** @type {__VLS_StyleScopedClasses['py-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:bg-gray-700']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.automationsLoading))
                        return;
                    if (!!(!__VLS_ctx.automationsLoading && __VLS_ctx.automationRules.length === 0 && !__VLS_ctx.showRuleForm))
                        return;
                    if (!(__VLS_ctx.automationRules.length > 0))
                        return;
                    __VLS_ctx.toggleRule(rule);
                    // @ts-ignore
                    [toggleRule,];
                } },
            ...{ class: (rule.is_active ? 'bg-green-600' : 'bg-gray-200 dark:bg-gray-600') },
            ...{ class: "relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0" },
            role: "switch",
            'aria-checked': (rule.is_active),
            'aria-label': (`Toggle ${rule.name}`),
        });
        /** @type {__VLS_StyleScopedClasses['relative']} */ ;
        /** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-6']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-11']} */ ;
        /** @type {__VLS_StyleScopedClasses['items-center']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
        /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.span)({
            ...{ class: (rule.is_active ? 'translate-x-6' : 'translate-x-1') },
            ...{ class: "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform" },
        });
        /** @type {__VLS_StyleScopedClasses['inline-block']} */ ;
        /** @type {__VLS_StyleScopedClasses['h-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['w-4']} */ ;
        /** @type {__VLS_StyleScopedClasses['transform']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
        /** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
        /** @type {__VLS_StyleScopedClasses['shadow']} */ ;
        /** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
        __VLS_asFunctionalElement1(__VLS_intrinsics.button, __VLS_intrinsics.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.automationsLoading))
                        return;
                    if (!!(!__VLS_ctx.automationsLoading && __VLS_ctx.automationRules.length === 0 && !__VLS_ctx.showRuleForm))
                        return;
                    if (!(__VLS_ctx.automationRules.length > 0))
                        return;
                    __VLS_ctx.deleteRule(rule);
                    // @ts-ignore
                    [deleteRule,];
                } },
            ...{ class: "p-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-red-400 text-xs" },
            'aria-label': (`Delete rule ${rule.name}`),
        });
        /** @type {__VLS_StyleScopedClasses['p-1']} */ ;
        /** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
        /** @type {__VLS_StyleScopedClasses['hover:bg-red-50']} */ ;
        /** @type {__VLS_StyleScopedClasses['dark:hover:bg-red-900/30']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
        /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
        if (__VLS_ctx.expandedRuleRuns === rule.id) {
            __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                ...{ class: "border-t border-gray-100 dark:border-gray-700 px-4 py-3" },
            });
            /** @type {__VLS_StyleScopedClasses['border-t']} */ ;
            /** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:border-gray-700']} */ ;
            /** @type {__VLS_StyleScopedClasses['px-4']} */ ;
            /** @type {__VLS_StyleScopedClasses['py-3']} */ ;
            __VLS_asFunctionalElement1(__VLS_intrinsics.p, __VLS_intrinsics.p)({
                ...{ class: "text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2" },
            });
            /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
            /** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
            /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
            /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
            /** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
            /** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
            /** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
            if (__VLS_ctx.ruleRunsLoading && !__VLS_ctx.ruleRunsMap[rule.id]) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "text-xs text-gray-400" },
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
            }
            else if (!__VLS_ctx.ruleRunsMap[rule.id] || __VLS_ctx.ruleRunsMap[rule.id].length === 0) {
                __VLS_asFunctionalElement1(__VLS_intrinsics.div, __VLS_intrinsics.div)({
                    ...{ class: "text-xs text-gray-400 dark:text-gray-500" },
                });
                /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                /** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
                /** @type {__VLS_StyleScopedClasses['dark:text-gray-500']} */ ;
            }
            else {
                __VLS_asFunctionalElement1(__VLS_intrinsics.ul, __VLS_intrinsics.ul)({
                    ...{ class: "space-y-1.5" },
                });
                /** @type {__VLS_StyleScopedClasses['space-y-1.5']} */ ;
                for (const [run] of __VLS_vFor((__VLS_ctx.ruleRunsMap[rule.id]))) {
                    __VLS_asFunctionalElement1(__VLS_intrinsics.li, __VLS_intrinsics.li)({
                        key: (run.id),
                        ...{ class: "flex items-start gap-2 text-xs" },
                    });
                    /** @type {__VLS_StyleScopedClasses['flex']} */ ;
                    /** @type {__VLS_StyleScopedClasses['items-start']} */ ;
                    /** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                        ...{ class: ({
                                'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300': run.status === 'success',
                                'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300': run.status === 'failure',
                                'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400': run.status === 'skipped',
                            }) },
                        ...{ class: "px-1.5 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0" },
                    });
                    /** @type {__VLS_StyleScopedClasses['bg-green-100']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-green-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:bg-green-900/30']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-green-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['bg-red-100']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-red-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:bg-red-900/30']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-red-300']} */ ;
                    /** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:bg-gray-700']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
                    /** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
                    /** @type {__VLS_StyleScopedClasses['text-[10px]']} */ ;
                    /** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
                    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                    (run.status);
                    __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                        ...{ class: "text-gray-500 dark:text-gray-400 flex-shrink-0" },
                    });
                    /** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
                    /** @type {__VLS_StyleScopedClasses['dark:text-gray-400']} */ ;
                    /** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
                    (new Date(run.triggered_at).toLocaleString());
                    if (run.error_message) {
                        __VLS_asFunctionalElement1(__VLS_intrinsics.span, __VLS_intrinsics.span)({
                            ...{ class: "text-red-600 dark:text-red-400 truncate" },
                        });
                        /** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
                        /** @type {__VLS_StyleScopedClasses['dark:text-red-400']} */ ;
                        /** @type {__VLS_StyleScopedClasses['truncate']} */ ;
                        (run.error_message);
                    }
                    // @ts-ignore
                    [expandedRuleRuns, ruleRunsLoading, ruleRunsMap, ruleRunsMap, ruleRunsMap, ruleRunsMap,];
                }
            }
        }
        // @ts-ignore
        [];
    }
}
// @ts-ignore
[];
const __VLS_export = (await import('vue')).defineComponent({});
export default {};

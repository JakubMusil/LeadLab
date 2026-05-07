<script setup lang="ts">
/**
 * RoleWizard – 3-step modal for creating a new account type ("role").
 *
 * Step 1: Pick a template (5 system presets + "start from scratch").
 * Step 2: Name + description + collapsible advanced identifier (auto-slug).
 * Step 3: Permission matrix grouped into human-readable super-groups
 *         with master toggles per group.
 *
 * Emits `created` (with the new role) when the role is successfully created.
 *
 * Designed as the user-friendly replacement for the old "Create role" inline
 * form + presets modal in RolesSettingsView.
 */
import { ref, computed, watch, nextTick } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePermissionsStore, type RolePreset, type RoleOut } from '@/stores/permissions'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import {
  XMarkIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CheckIcon,
  SparklesIcon,
  PlusIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  close: []
  created: [role: RoleOut]
}>()

const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const toast = useToast()
const { t } = useI18n()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

const totalSteps = 3
const step = ref(1)

// Step 1: presets
const presets = ref<RolePreset[]>([])
const presetsLoading = ref(false)
const selectedPreset = ref<RolePreset | null>(null)
const startFromScratch = ref(false)

// Step 2: name / description / identifier
const name = ref('')
const description = ref('')
const identifier = ref('')
const identifierManuallyEdited = ref(false)
const showIdentifier = ref(false)
const nameError = ref('')

// Step 3: permission selection
const selectedPermissions = ref<Set<string>>(new Set())
// Locally collapsed human groups (default: all expanded except "Other")
const collapsedGroups = ref<Set<string>>(new Set())

const submitting = ref(false)
const submitError = ref('')

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
const dialogRef = ref<HTMLElement | null>(null)

/** Maps backend permission groups → human super-group key. */
const HUMAN_GROUP_MAP: Record<string, string> = {
  Records: 'records',
  Categories: 'records',
  Streamline: 'records',
  Proposals: 'records',
  Billing: 'billing',
  Teams: 'team',
  Roles: 'team',
  Firm: 'settings',
  Integrations: 'settings',
  Reports: 'settings',
}

const HUMAN_GROUP_ORDER = ['records', 'team', 'billing', 'settings', 'other'] as const
type HumanGroup = typeof HUMAN_GROUP_ORDER[number]

function humanGroupOf(group: string): HumanGroup {
  return (HUMAN_GROUP_MAP[group] as HumanGroup | undefined) ?? 'other'
}

function humanGroupLabel(g: HumanGroup): string {
  switch (g) {
    case 'records': return t('permissions.humanGroupRecords')
    case 'billing': return t('permissions.humanGroupBilling')
    case 'team': return t('permissions.humanGroupTeam')
    case 'settings': return t('permissions.humanGroupSettings')
    default: return t('permissions.humanGroupOther')
  }
}

interface HumanGroupBlock {
  key: HumanGroup
  label: string
  items: { code: string; description: string; rawGroup: string }[]
}

/** All catalogue items reorganised into human super-groups. */
const humanGroups = computed<HumanGroupBlock[]>(() => {
  const buckets: Record<HumanGroup, HumanGroupBlock> = {
    records: { key: 'records', label: humanGroupLabel('records'), items: [] },
    team: { key: 'team', label: humanGroupLabel('team'), items: [] },
    billing: { key: 'billing', label: humanGroupLabel('billing'), items: [] },
    settings: { key: 'settings', label: humanGroupLabel('settings'), items: [] },
    other: { key: 'other', label: humanGroupLabel('other'), items: [] },
  }
  for (const [group, items] of Object.entries(permissionsStore.catalogueByGroup)) {
    const hg = humanGroupOf(group)
    for (const item of items) {
      buckets[hg].items.push({ code: item.code, description: item.description, rawGroup: group })
    }
  }
  // Stable order of items inside each human group
  for (const block of Object.values(buckets)) {
    block.items.sort((a, b) => a.code.localeCompare(b.code))
  }
  return HUMAN_GROUP_ORDER.map(k => buckets[k]).filter(b => b.items.length > 0)
})

/**
 * Try to look up a friendlier description from the i18n codeDesc dictionary.
 * Falls back to the catalogue description.
 */
function permLabel(code: string, fallback: string): string {
  const key = `permissions.codeDesc.${code.replace(/\./g, '_')}`
  const localized = t(key)
  return localized && localized !== key ? localized : fallback
}

// ──────────────────────────────────────────────────────────────────────────
// Lifecycle / state reset
// ──────────────────────────────────────────────────────────────────────────

watch(() => props.open, async (val) => {
  if (val) {
    step.value = 1
    selectedPreset.value = null
    startFromScratch.value = false
    name.value = ''
    description.value = ''
    identifier.value = ''
    identifierManuallyEdited.value = false
    showIdentifier.value = false
    nameError.value = ''
    selectedPermissions.value = new Set()
    submitError.value = ''
    submitting.value = false
    collapsedGroups.value = new Set()

    if (firmId.value) {
      // Catalogue + presets needed for steps 1 & 3
      if (permissionsStore.catalogue.length === 0) {
        permissionsStore.fetchCatalogue(firmId.value)
      }
      loadPresets()
    }

    await nextTick()
    const firstFocusable = dialogRef.value?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
    firstFocusable?.focus()
  }
})

// Slugify name → default identifier (until user edits identifier explicitly)
watch(name, (val) => {
  if (!identifierManuallyEdited.value) {
    identifier.value = slugify(val)
  }
  if (nameError.value && val.trim()) {
    nameError.value = ''
  }
})

function slugify(s: string): string {
  return s
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // strip diacritics
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 32)
}

async function loadPresets() {
  if (!firmId.value) return
  presetsLoading.value = true
  presets.value = await permissionsStore.fetchRolePresets(firmId.value)
  presetsLoading.value = false
}

function pickPreset(preset: RolePreset) {
  selectedPreset.value = preset
  startFromScratch.value = false
  // Pre-fill subsequent steps from the preset
  name.value = preset.name
  description.value = preset.description
  identifier.value = slugify(preset.code || preset.name) || `role_${Date.now().toString(36)}`
  identifierManuallyEdited.value = false
  selectedPermissions.value = new Set(preset.permissions)
  step.value = 2
}

function pickStartFromScratch() {
  startFromScratch.value = true
  selectedPreset.value = null
  name.value = ''
  description.value = ''
  identifier.value = ''
  identifierManuallyEdited.value = false
  selectedPermissions.value = new Set()
  step.value = 2
}

function onIdentifierInput(e: Event) {
  const v = (e.target as HTMLInputElement).value
  identifier.value = slugify(v)
  // Once the user touches the field, stop auto-syncing from the name
  // even if they later clear it.
  identifierManuallyEdited.value = true
}

function validateStep2(): boolean {
  if (!name.value.trim()) {
    nameError.value = t('roleWizard.nameRequired')
    return false
  }
  // Auto-derive identifier if empty
  if (!identifier.value) {
    identifier.value = slugify(name.value) || `role_${Date.now().toString(36)}`
  }
  return true
}

function next() {
  if (step.value === 2 && !validateStep2()) return
  if (step.value < totalSteps) step.value++
}

function prev() {
  if (step.value > 1) step.value--
}

// ──────────────────────────────────────────────────────────────────────────
// Permission selection helpers
// ──────────────────────────────────────────────────────────────────────────

function togglePermission(code: string) {
  const next = new Set(selectedPermissions.value)
  if (next.has(code)) next.delete(code)
  else next.add(code)
  selectedPermissions.value = next
}

function groupState(block: HumanGroupBlock): 'all' | 'some' | 'none' {
  let on = 0
  for (const it of block.items) {
    if (selectedPermissions.value.has(it.code)) on++
  }
  if (on === 0) return 'none'
  if (on === block.items.length) return 'all'
  return 'some'
}

function setGroup(block: HumanGroupBlock, on: boolean) {
  const next = new Set(selectedPermissions.value)
  for (const it of block.items) {
    if (on) next.add(it.code)
    else next.delete(it.code)
  }
  selectedPermissions.value = next
}

function toggleGroupCollapsed(key: string) {
  const next = new Set(collapsedGroups.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedGroups.value = next
}

// ──────────────────────────────────────────────────────────────────────────
// Submit
// ──────────────────────────────────────────────────────────────────────────

async function submit() {
  if (!validateStep2()) {
    step.value = 2
    return
  }
  submitting.value = true
  submitError.value = ''
  try {
    const role = await permissionsStore.createRole(firmId.value, {
      code: identifier.value,
      name: name.value.trim(),
      description: description.value.trim(),
    })
    if (!role) {
      submitError.value = t('roleWizard.failed')
      return
    }
    // Persist permission selection (step 3)
    const perms = Array.from(selectedPermissions.value)
    if (perms.length > 0) {
      await permissionsStore.setRolePermissions(firmId.value, role.id, perms)
    }
    toast.success(t('permissions.roleCreated'))
    emit('created', role)
    emit('close')
  } finally {
    submitting.value = false
  }
}

// ──────────────────────────────────────────────────────────────────────────
// Keyboard / focus trap (mirrors InviteMemberWizard)
// ──────────────────────────────────────────────────────────────────────────

function onWizardKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close')
    return
  }
  if (e.key === 'Tab') {
    const focusable = Array.from(
      dialogRef.value?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
    )
    if (focusable.length === 0) {
      e.preventDefault()
      return
    }
    const first = focusable[0]!
    const last = focusable[focusable.length - 1]!
    const active = document.activeElement
    if (e.shiftKey) {
      if (active === first || !dialogRef.value?.contains(active as Node)) {
        e.preventDefault()
        last.focus()
      }
    } else {
      if (active === last || !dialogRef.value?.contains(active as Node)) {
        e.preventDefault()
        first.focus()
      }
    }
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        @click.self="emit('close')"
        @keydown="onWizardKeydown"
      >
        <div
          ref="dialogRef"
          class="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden flex flex-col max-h-[92vh]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="role-wizard-title"
        >
          <!-- Header -->
          <div class="flex items-center gap-3 px-6 pt-5 pb-4 border-b border-gray-100 dark:border-gray-800 shrink-0">
            <SparklesIcon class="h-5 w-5 text-amber-500 shrink-0" aria-hidden="true" />
            <div class="flex-1">
              <h2 id="role-wizard-title" class="text-base font-semibold text-gray-900 dark:text-gray-100">
                {{ t('roleWizard.title') }}
              </h2>
              <p class="text-xs text-gray-400 dark:text-gray-500">
                {{ t('roleWizard.stepOf', { step, total: totalSteps }) }}
              </p>
            </div>
            <button
              @click="emit('close')"
              class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
              :aria-label="t('roleWizard.cancel')"
            >
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Progress bar -->
          <div class="h-1 bg-gray-100 dark:bg-gray-800 shrink-0">
            <div
              class="h-full bg-brand transition-all duration-300"
              :style="{ width: `${(step / totalSteps) * 100}%` }"
            />
          </div>

          <!-- Step content -->
          <div class="px-6 py-5 overflow-y-auto flex-1">

            <!-- Step 1: Pick a template -->
            <div v-if="step === 1" class="space-y-4">
              <div>
                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('roleWizard.step1Title') }}</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('roleWizard.step1Hint') }}</p>
              </div>

              <div v-if="presetsLoading" class="text-sm text-gray-400 py-8 text-center">
                {{ t('roleWizard.step1Loading') }}
              </div>

              <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  v-for="preset in presets"
                  :key="preset.code"
                  type="button"
                  @click="pickPreset(preset)"
                  class="group text-left rounded-xl border border-gray-200 dark:border-gray-700 p-4 hover:border-brand hover:bg-brand/5 dark:hover:bg-brand/10 transition-colors focus:outline-none focus:ring-2 focus:ring-brand/40"
                >
                  <div class="flex items-start gap-2">
                    <SparklesIcon class="h-4 w-4 text-amber-500 shrink-0 mt-0.5" aria-hidden="true" />
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-semibold text-gray-900 dark:text-gray-100 group-hover:text-brand">{{ preset.name }}</p>
                      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-3">{{ preset.description }}</p>
                      <p class="mt-2 text-[10px] text-gray-400">
                        {{ t('roleWizard.selectedCount', { count: preset.permissions.length }) }}
                      </p>
                    </div>
                  </div>
                </button>

                <!-- Start from scratch card -->
                <button
                  type="button"
                  @click="pickStartFromScratch"
                  class="group text-left rounded-xl border border-dashed border-gray-300 dark:border-gray-600 p-4 hover:border-brand hover:bg-brand/5 dark:hover:bg-brand/10 transition-colors focus:outline-none focus:ring-2 focus:ring-brand/40"
                >
                  <div class="flex items-start gap-2">
                    <PlusIcon class="h-4 w-4 text-gray-500 shrink-0 mt-0.5" aria-hidden="true" />
                    <div class="flex-1 min-w-0">
                      <p class="text-sm font-semibold text-gray-900 dark:text-gray-100 group-hover:text-brand">{{ t('roleWizard.startFromScratch') }}</p>
                      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ t('roleWizard.startFromScratchDesc') }}</p>
                    </div>
                  </div>
                </button>
              </div>
            </div>

            <!-- Step 2: Name -->
            <div v-else-if="step === 2" class="space-y-4">
              <div>
                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('roleWizard.step2Title') }}</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('roleWizard.step2Hint') }}</p>
              </div>
              <div>
                <label for="rw-name" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {{ t('roleWizard.nameLabel') }}
                </label>
                <input
                  id="rw-name"
                  v-model="name"
                  type="text"
                  :placeholder="t('roleWizard.namePlaceholder')"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 px-3 py-2 text-sm focus:outline-none focus:border-brand"
                  @keydown.enter="next"
                  autofocus
                />
                <p v-if="nameError" class="mt-1 text-xs text-red-600">{{ nameError }}</p>
              </div>

              <div>
                <label for="rw-desc" class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {{ t('roleWizard.descriptionLabel') }}
                </label>
                <input
                  id="rw-desc"
                  v-model="description"
                  type="text"
                  :placeholder="t('roleWizard.descriptionPlaceholder')"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 px-3 py-2 text-sm focus:outline-none focus:border-brand"
                />
              </div>

              <!-- Advanced: identifier -->
              <div>
                <button
                  type="button"
                  @click="showIdentifier = !showIdentifier"
                  class="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                >
                  <ChevronDownIcon v-if="!showIdentifier" class="h-3.5 w-3.5" />
                  <ChevronUpIcon v-else class="h-3.5 w-3.5" />
                  {{ t('roleWizard.editIdentifier') }}
                </button>
                <div v-if="showIdentifier" class="mt-2 space-y-1">
                  <label for="rw-id" class="block text-xs font-medium text-gray-700 dark:text-gray-300">
                    {{ t('roleWizard.identifierLabel') }}
                  </label>
                  <input
                    id="rw-id"
                    :value="identifier"
                    @input="onIdentifierInput"
                    type="text"
                    class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm font-mono focus:outline-none focus:border-brand"
                    placeholder="junior_sales"
                  />
                  <p class="text-[11px] text-gray-400 dark:text-gray-500">{{ t('roleWizard.identifierHint') }}</p>
                </div>
              </div>
            </div>

            <!-- Step 3: Permissions -->
            <div v-else-if="step === 3" class="space-y-4">
              <div>
                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('roleWizard.step3Title') }}</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('roleWizard.step3Hint') }}</p>
                <p class="text-[11px] text-gray-400 mt-1">
                  {{ t('roleWizard.selectedCount', { count: selectedPermissions.size }) }}
                </p>
              </div>

              <div class="space-y-3">
                <div
                  v-for="block in humanGroups"
                  :key="block.key"
                  class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden"
                >
                  <!-- Group header -->
                  <div class="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800">
                    <button
                      type="button"
                      @click="toggleGroupCollapsed(block.key)"
                      class="p-0.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                      :aria-expanded="!collapsedGroups.has(block.key)"
                    >
                      <ChevronDownIcon v-if="!collapsedGroups.has(block.key)" class="h-4 w-4" />
                      <ChevronRightIcon v-else class="h-4 w-4" />
                    </button>
                    <p class="flex-1 text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {{ block.label }}
                      <span class="ml-1 text-xs font-normal text-gray-400">
                        ({{ block.items.filter(i => selectedPermissions.has(i.code)).length }} / {{ block.items.length }})
                      </span>
                    </p>
                    <div class="flex items-center gap-1">
                      <button
                        type="button"
                        @click="setGroup(block, true)"
                        class="px-2 py-0.5 text-[11px] rounded-md border transition-colors"
                        :class="groupState(block) === 'all'
                          ? 'border-brand bg-brand text-white'
                          : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-brand hover:text-brand'"
                      >{{ t('roleWizard.groupAll') }}</button>
                      <button
                        type="button"
                        @click="setGroup(block, false)"
                        class="px-2 py-0.5 text-[11px] rounded-md border transition-colors"
                        :class="groupState(block) === 'none'
                          ? 'border-gray-500 bg-gray-500 text-white'
                          : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-gray-500'"
                      >{{ t('roleWizard.groupNone') }}</button>
                    </div>
                  </div>

                  <!-- Group body -->
                  <div v-if="!collapsedGroups.has(block.key)" class="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
                    <label
                      v-for="item in block.items"
                      :key="item.code"
                      class="flex items-start gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                    >
                      <input
                        type="checkbox"
                        :checked="selectedPermissions.has(item.code)"
                        @change="togglePermission(item.code)"
                        class="mt-0.5 h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                      />
                      <div class="flex-1 min-w-0">
                        <p class="text-sm text-gray-800 dark:text-gray-200">
                          {{ permLabel(item.code, item.description) }}
                        </p>
                        <p class="text-[10px] text-gray-400 font-mono">{{ item.code }}</p>
                      </div>
                    </label>
                  </div>
                </div>
              </div>

              <p v-if="submitError" class="text-xs text-red-600">{{ submitError }}</p>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between px-6 py-4 border-t border-gray-100 dark:border-gray-800 shrink-0">
            <button
              v-if="step > 1"
              @click="prev"
              class="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            >
              <ChevronLeftIcon class="h-4 w-4" />
              {{ t('roleWizard.back') }}
            </button>
            <span v-else />

            <div class="flex gap-2">
              <button
                @click="emit('close')"
                class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                {{ t('roleWizard.cancel') }}
              </button>
              <button
                v-if="step === 2"
                @click="next"
                class="inline-flex items-center gap-1 px-4 py-2 bg-brand text-white text-sm font-medium rounded-xl hover:opacity-90"
              >
                {{ t('roleWizard.next') }}
                <ChevronRightIcon class="h-4 w-4" />
              </button>
              <button
                v-else-if="step === 3"
                @click="submit"
                :disabled="submitting"
                class="inline-flex items-center gap-1 px-4 py-2 bg-brand text-white text-sm font-medium rounded-xl hover:opacity-90 disabled:opacity-50"
              >
                <CheckIcon class="h-4 w-4" />
                {{ submitting ? t('roleWizard.creating') : t('roleWizard.create') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

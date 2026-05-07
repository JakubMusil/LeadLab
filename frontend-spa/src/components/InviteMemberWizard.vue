<script setup lang="ts">
/**
 * InviteMemberWizard – 3-step modal for inviting a new workspace member.
 *
 * Step 1: Email address.
 * Step 2: Role(s) + default scope.
 * Step 3: Team assignment (optional).
 *
 * Emits `invited` when the invitation is successfully sent.
 */
import { ref, computed, watch } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePermissionsStore } from '@/stores/permissions'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import {
  XMarkIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  CheckIcon,
  UserPlusIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  close: []
  invited: []
}>()

const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const toast = useToast()
const { t } = useI18n()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

// Wizard state
const step = ref(1)
const totalSteps = 3

// Step 1 fields
const email = ref('')
const emailError = ref('')

// Step 2 fields
const selectedRoleCodes = ref<string[]>(['member'])
const defaultScope = ref<'own' | 'team' | 'all'>('own')

// Step 3 fields
const selectedTeamId = ref<string>('')

// Submission state
const submitting = ref(false)
const submitError = ref('')

// Reset all state when modal opens/closes
watch(() => props.open, (val) => {
  if (val) {
    step.value = 1
    email.value = ''
    emailError.value = ''
    selectedRoleCodes.value = ['member']
    defaultScope.value = 'own'
    selectedTeamId.value = ''
    submitError.value = ''
    submitting.value = false
    // Ensure teams & roles are loaded
    if (firmId.value) {
      permissionsStore.fetchTeams(firmId.value)
      permissionsStore.fetchRoles(firmId.value)
    }
  }
})

const nonSystemRoles = computed(() =>
  permissionsStore.roles.filter(r => !r.is_system || r.code === 'member' || r.code === 'guest')
)
const allRoles = computed(() => permissionsStore.roles)

function toggleRole(code: string) {
  const idx = selectedRoleCodes.value.indexOf(code)
  if (idx >= 0) {
    selectedRoleCodes.value = selectedRoleCodes.value.filter(c => c !== code)
  } else {
    selectedRoleCodes.value = [...selectedRoleCodes.value, code]
  }
}

function validateStep1(): boolean {
  if (!email.value.trim()) {
    emailError.value = t('wizard.emailRequired')
    return false
  }
  if (!email.value.includes('@')) {
    emailError.value = t('wizard.emailInvalid')
    return false
  }
  emailError.value = ''
  return true
}

function next() {
  if (step.value === 1 && !validateStep1()) return
  if (step.value < totalSteps) step.value++
}

function prev() {
  if (step.value > 1) step.value--
}

async function submit() {
  submitting.value = true
  submitError.value = ''
  try {
    const payload: Record<string, unknown> = {
      email: email.value.trim(),
      role_codes: selectedRoleCodes.value,
      default_scope: defaultScope.value,
    }
    if (selectedTeamId.value) {
      payload.team_id = selectedTeamId.value
    }
    const res = await api.post(`/api/v1/firms/${firmId.value}/invitations/`, payload)
    if (res.ok || res.status === 202) {
      toast.success(t('wizard.invitationSent'))
      emit('invited')
      emit('close')
    } else {
      const data = res.data as Record<string, string> | null
      submitError.value = data?.detail ?? t('wizard.failedToInvite')
    }
  } finally {
    submitting.value = false
  }
}

const scopeOptions: Array<{ value: 'own' | 'team' | 'all'; label: string }> = [
  { value: 'own', label: '' },
  { value: 'team', label: '' },
  { value: 'all', label: '' },
]

const ROLE_COLORS: Record<string, string> = {
  owner: 'bg-red-100 text-red-700',
  admin: 'bg-blue-100 text-blue-700',
  member: 'bg-gray-100 text-gray-700',
  guest: 'bg-purple-100 text-purple-700',
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        @click.self="emit('close')"
      >
        <div
          class="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-lg mx-4 overflow-hidden"
          role="dialog"
          aria-modal="true"
          :aria-label="t('wizard.title')"
        >
          <!-- Header -->
          <div class="flex items-center gap-3 px-6 pt-5 pb-4 border-b border-gray-100 dark:border-gray-800">
            <UserPlusIcon class="h-5 w-5 text-brand shrink-0" />
            <div class="flex-1">
              <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('wizard.title') }}</h2>
              <p class="text-xs text-gray-400 dark:text-gray-500">
                {{ t('wizard.stepOf', { step, total: totalSteps }) }}
              </p>
            </div>
            <button @click="emit('close')" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
              <XMarkIcon class="h-5 w-5" />
            </button>
          </div>

          <!-- Progress bar -->
          <div class="h-1 bg-gray-100 dark:bg-gray-800">
            <div
              class="h-full bg-brand transition-all duration-300"
              :style="{ width: `${(step / totalSteps) * 100}%` }"
            />
          </div>

          <!-- Step content -->
          <div class="px-6 py-5 min-h-[260px]">

            <!-- Step 1: Email -->
            <div v-if="step === 1" class="space-y-4">
              <div>
                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('wizard.step1Title') }}</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('wizard.step1Hint') }}</p>
              </div>
              <div>
                <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {{ t('wizard.emailLabel') }}
                </label>
                <input
                  v-model="email"
                  type="email"
                  :placeholder="t('wizard.emailPlaceholder')"
                  class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 px-3 py-2 text-sm focus:outline-none focus:border-brand"
                  @keydown.enter="next"
                  autofocus
                />
                <p v-if="emailError" class="mt-1 text-xs text-red-600">{{ emailError }}</p>
              </div>
            </div>

            <!-- Step 2: Role & scope -->
            <div v-else-if="step === 2" class="space-y-4">
              <div>
                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('wizard.step2Title') }}</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('wizard.step2Hint') }}</p>
              </div>

              <!-- Role selector -->
              <div>
                <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('wizard.rolesLabel') }}</p>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="role in allRoles"
                    :key="role.id"
                    type="button"
                    @click="toggleRole(role.code)"
                    class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
                    :class="selectedRoleCodes.includes(role.code)
                      ? 'border-brand bg-brand/10 text-brand dark:border-brand dark:bg-brand/20'
                      : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
                  >
                    <CheckIcon v-if="selectedRoleCodes.includes(role.code)" class="h-3 w-3" />
                    {{ role.name }}
                    <span class="text-[10px] opacity-60">({{ role.code }})</span>
                  </button>
                </div>
                <p v-if="selectedRoleCodes.length === 0" class="mt-1 text-xs text-amber-600">
                  {{ t('wizard.roleRequired') }}
                </p>
              </div>

              <!-- Default scope -->
              <div>
                <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('wizard.scopeLabel') }}</p>
                <div class="grid grid-cols-3 gap-2">
                  <button
                    v-for="opt in [
                      { value: 'own', label: t('permissions.scopeOwn'), desc: t('wizard.scopeOwnDesc') },
                      { value: 'team', label: t('permissions.scopeTeam'), desc: t('wizard.scopeTeamDesc') },
                      { value: 'all', label: t('permissions.scopeAll'), desc: t('wizard.scopeAllDesc') },
                    ]"
                    :key="opt.value"
                    type="button"
                    @click="defaultScope = opt.value as 'own' | 'team' | 'all'"
                    class="flex flex-col items-start p-2 rounded-lg border text-left transition-colors"
                    :class="defaultScope === opt.value
                      ? 'border-brand bg-brand/5 dark:bg-brand/10'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'"
                  >
                    <span class="text-xs font-medium" :class="defaultScope === opt.value ? 'text-brand' : 'text-gray-700 dark:text-gray-300'">
                      {{ opt.label }}
                    </span>
                    <span class="text-[10px] text-gray-400 dark:text-gray-500 mt-0.5">{{ opt.desc }}</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Step 3: Team (optional) -->
            <div v-else-if="step === 3" class="space-y-4">
              <div>
                <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-1">{{ t('wizard.step3Title') }}</h3>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ t('wizard.step3Hint') }}</p>
              </div>

              <!-- Team picker -->
              <div>
                <p class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('wizard.teamLabel') }}</p>
                <div v-if="permissionsStore.teams.length === 0" class="text-xs text-gray-400 dark:text-gray-500 italic">
                  {{ t('wizard.noTeams') }}
                </div>
                <div v-else class="flex flex-wrap gap-2">
                  <!-- None option -->
                  <button
                    type="button"
                    @click="selectedTeamId = ''"
                    class="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
                    :class="!selectedTeamId
                      ? 'border-brand bg-brand/10 text-brand'
                      : 'border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-gray-300'"
                  >{{ t('wizard.noTeam') }}</button>
                  <button
                    v-for="team in permissionsStore.teams"
                    :key="team.id"
                    type="button"
                    @click="selectedTeamId = team.id"
                    class="px-3 py-1.5 rounded-full text-xs font-medium border transition-colors"
                    :class="selectedTeamId === team.id
                      ? 'border-brand bg-brand/10 text-brand'
                      : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:border-gray-300'"
                  >
                    <span
                      v-if="team.color"
                      class="inline-block w-2 h-2 rounded-full mr-1"
                      :style="{ background: team.color }"
                    />
                    {{ team.name }}
                  </button>
                </div>
              </div>

              <!-- Summary -->
              <div class="rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-3 space-y-1.5 text-xs">
                <p class="text-gray-500 dark:text-gray-400 font-medium">{{ t('wizard.summaryTitle') }}</p>
                <p class="text-gray-700 dark:text-gray-300"><span class="font-medium">{{ t('wizard.emailLabel') }}:</span> {{ email }}</p>
                <p class="text-gray-700 dark:text-gray-300">
                  <span class="font-medium">{{ t('wizard.rolesLabel') }}:</span>
                  {{ selectedRoleCodes.join(', ') || '–' }}
                </p>
                <p class="text-gray-700 dark:text-gray-300"><span class="font-medium">{{ t('wizard.scopeLabel') }}:</span> {{ defaultScope }}</p>
                <p v-if="selectedTeamId" class="text-gray-700 dark:text-gray-300">
                  <span class="font-medium">{{ t('wizard.teamLabel') }}:</span>
                  {{ permissionsStore.teams.find(t => t.id === selectedTeamId)?.name ?? selectedTeamId }}
                </p>
              </div>

              <p v-if="submitError" class="text-xs text-red-600">{{ submitError }}</p>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between px-6 py-4 border-t border-gray-100 dark:border-gray-800">
            <button
              v-if="step > 1"
              @click="prev"
              class="inline-flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            >
              <ChevronLeftIcon class="h-4 w-4" />
              {{ t('wizard.back') }}
            </button>
            <span v-else />

            <div class="flex gap-2">
              <button
                @click="emit('close')"
                class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-600 rounded-xl hover:bg-gray-50 dark:hover:bg-gray-800"
              >
                {{ t('wizard.cancel') }}
              </button>
              <button
                v-if="step < totalSteps"
                @click="next"
                class="inline-flex items-center gap-1 px-4 py-2 bg-brand text-white text-sm font-medium rounded-xl hover:opacity-90"
              >
                {{ t('wizard.next') }}
                <ChevronRightIcon class="h-4 w-4" />
              </button>
              <button
                v-else
                @click="submit"
                :disabled="submitting || selectedRoleCodes.length === 0"
                class="inline-flex items-center gap-1 px-4 py-2 bg-brand text-white text-sm font-medium rounded-xl hover:opacity-90 disabled:opacity-50"
              >
                <CheckIcon class="h-4 w-4" />
                {{ submitting ? t('wizard.sending') : t('wizard.sendInvite') }}
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

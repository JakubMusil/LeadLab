<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useFirmStore } from '@/stores/firm'
import { api } from '@/api'

const router = useRouter()
const firmStore = useFirmStore()

const currentStep = ref(1)
const totalSteps = 5

// Step 1 — Create workspace
const workspaceName = ref('')
const workspaceError = ref('')
const workspaceLoading = ref(false)
const workspaceCreated = ref(false)

// Step 2 — Invite team
const inviteEmail = ref('')
const inviteLoading = ref(false)
const inviteError = ref('')
const inviteSent = ref(false)

// Step 3 — Import leads
const importFile = ref<File | null>(null)
const importLoading = ref(false)
const importDone = ref(false)

// Step 4 — Pipeline info
// Step 5 — Complete

const steps = [
  { label: 'Create workspace' },
  { label: 'Invite team' },
  { label: 'Import leads' },
  { label: 'Configure pipeline' },
  { label: 'Complete' },
]

const completedSteps = computed(() => ({
  workspace: workspaceCreated.value,
  team: inviteSent.value,
  leads: importDone.value,
  pipeline: currentStep.value >= 5,
}))

async function handleCreateWorkspace() {
  workspaceError.value = ''
  if (!workspaceName.value.trim()) {
    workspaceError.value = 'Workspace name is required.'
    return
  }
  workspaceLoading.value = true
  const result = await firmStore.createFirm(workspaceName.value.trim())
  workspaceLoading.value = false
  if (result.ok) {
    workspaceCreated.value = true
    if (firmStore.activeFirm) {
      localStorage.setItem('onboarding_complete_' + firmStore.activeFirm.id, '1')
    }
    currentStep.value = 2
  } else {
    workspaceError.value = result.error ?? 'Failed to create workspace.'
  }
}

async function handleInvite() {
  if (!inviteEmail.value.trim() || !firmStore.activeFirm) return
  inviteLoading.value = true
  inviteError.value = ''
  const res = await api.post(`/api/v1/firms/${firmStore.activeFirm.id}/invitations/`, {
    email: inviteEmail.value.trim(),
    role: 'worker',
  })
  inviteLoading.value = false
  if (res.ok) {
    inviteSent.value = true
    inviteEmail.value = ''
  } else {
    inviteError.value = 'Failed to send invite.'
  }
}

function skipStep() {
  if (firmStore.activeFirm) {
    localStorage.setItem('onboarding_complete_' + firmStore.activeFirm.id, '1')
  }
  if (currentStep.value < totalSteps) currentStep.value++
}

function nextStep() {
  if (currentStep.value < totalSteps) currentStep.value++
}

function prevStep() {
  if (currentStep.value > 1) currentStep.value--
}

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.[0]) {
    importFile.value = input.files[0]
    importDone.value = true
  }
}

function finish() {
  if (firmStore.activeFirm) {
    localStorage.setItem('onboarding_complete_' + firmStore.activeFirm.id, '1')
  }
  router.push('/app/dashboard')
}
</script>

<template>
  <div class="min-h-screen flex flex-col justify-center items-center bg-gray-50 dark:bg-gray-900 p-8">
    <div class="w-full max-w-lg">
      <div class="text-center mb-8">
        <span class="text-3xl font-bold text-red-600">LeadLab</span>
        <p class="text-gray-500 dark:text-gray-400 mt-1 text-sm">Get started</p>
      </div>

      <!-- Step indicator -->
      <div class="flex items-center justify-center mb-8">
        <div v-for="(step, idx) in steps" :key="step.label" class="flex items-center">
          <div class="flex flex-col items-center">
            <div
              class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors"
              :class="{
                'bg-green-600 border-green-600 text-white': idx + 1 < currentStep,
                'bg-red-600 border-red-600 text-white': idx + 1 === currentStep,
                'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-600 text-gray-400': idx + 1 > currentStep,
              }"
            >
              <span v-if="idx + 1 < currentStep">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span
              class="mt-1 text-xs font-medium hidden sm:block"
              :class="{
                'text-green-600': idx + 1 < currentStep,
                'text-red-600': idx + 1 === currentStep,
                'text-gray-400': idx + 1 > currentStep,
              }"
            >{{ step.label }}</span>
          </div>
          <div
            v-if="idx < steps.length - 1"
            class="w-8 sm:w-12 h-0.5 mx-1 mb-5"
            :class="idx + 1 < currentStep ? 'bg-green-400' : 'bg-gray-200 dark:bg-gray-600'"
          />
        </div>
      </div>

      <div class="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-8">

        <!-- Step 1: Create workspace -->
        <div v-if="currentStep === 1">
          <h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Create your workspace</h1>
          <p class="text-gray-500 dark:text-gray-400 mb-6 text-sm">Your workspace is where you and your team manage leads and customers.</p>
          <div v-if="workspaceError" class="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{{ workspaceError }}</div>
          <form @submit.prevent="handleCreateWorkspace" class="space-y-4">
            <div>
              <label for="workspaceName" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Workspace name</label>
              <input
                id="workspaceName"
                v-model="workspaceName"
                type="text"
                required
                class="w-full rounded-xl border border-gray-300 dark:border-gray-600 px-4 py-2.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
                placeholder="Acme Inc."
              />
            </div>
            <button
              type="submit"
              :disabled="workspaceLoading"
              class="w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {{ workspaceLoading ? 'Creating…' : 'Create workspace' }}
            </button>
          </form>
        </div>

        <!-- Step 2: Invite team -->
        <div v-else-if="currentStep === 2">
          <h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Invite your team</h1>
          <p class="text-gray-500 dark:text-gray-400 mb-6 text-sm">Add colleagues to your workspace. You can skip this step.</p>
          <div v-if="inviteError" class="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{{ inviteError }}</div>
          <div v-if="inviteSent" class="mb-4 rounded-xl bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">Invite sent!</div>
          <div class="space-y-3 mb-6">
            <input
              v-model="inviteEmail"
              type="email"
              placeholder="colleague@example.com"
              class="w-full rounded-xl border border-gray-300 dark:border-gray-600 px-4 py-2.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
            />
            <button
              :disabled="inviteLoading || !inviteEmail"
              class="w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60"
              @click="handleInvite"
            >{{ inviteLoading ? 'Sending…' : 'Send invite' }}</button>
          </div>
          <div class="flex gap-3">
            <button class="flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="prevStep">Back</button>
            <button class="flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="skipStep">Skip</button>
            <button class="flex-1 bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" @click="nextStep">Next</button>
          </div>
        </div>

        <!-- Step 3: Import leads -->
        <div v-else-if="currentStep === 3">
          <h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Import leads</h1>
          <p class="text-gray-500 dark:text-gray-400 mb-6 text-sm">Upload a CSV file to import existing leads. You can skip this step.</p>
          <div class="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center mb-6">
            <div class="text-3xl mb-3" aria-hidden="true">📂</div>
            <p class="text-sm text-gray-500 dark:text-gray-400 mb-3">Drop a CSV file here or click to choose</p>
            <label class="cursor-pointer inline-block px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-xl text-sm hover:bg-gray-200 dark:hover:bg-gray-600">
              Choose file
              <input type="file" accept=".csv" class="hidden" @change="handleFileChange" />
            </label>
            <p v-if="importFile" class="mt-2 text-xs text-green-600">{{ importFile.name }} selected</p>
          </div>
          <div class="flex gap-3">
            <button class="flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="prevStep">Back</button>
            <button class="flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="skipStep">Skip</button>
            <button class="flex-1 bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" @click="nextStep">Next</button>
          </div>
        </div>

        <!-- Step 4: Configure pipeline -->
        <div v-else-if="currentStep === 4">
          <h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Configure pipeline</h1>
          <p class="text-gray-500 dark:text-gray-400 mb-6 text-sm">LeadLab uses a 5-stage pipeline to track your deals, with Won and Lost as terminal outcomes.</p>
          <div class="bg-gray-50 dark:bg-gray-700 rounded-xl p-4 mb-6">
            <div class="flex flex-wrap gap-2 justify-center">
              <template v-for="(stage, i) in ['New', 'Contacted', 'Qualified', 'Proposal', 'Won', 'Lost']" :key="stage">
                <span class="px-3 py-1.5 rounded-full text-xs font-medium bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 shadow-sm">{{ stage }}</span>
                <span v-if="i < 5" class="text-gray-300 dark:text-gray-600 self-center text-xs">→</span>
              </template>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-400 text-center mt-3">New → Contacted → Qualified → Proposal → Won / Lost</p>
          </div>
          <div class="flex gap-3">
            <button class="flex-1 py-2.5 rounded-xl border border-gray-300 dark:border-gray-600 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700" @click="prevStep">Back</button>
            <button class="flex-1 bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors" @click="nextStep">Got it</button>
          </div>
        </div>

        <!-- Step 5: Complete -->
        <div v-else-if="currentStep === 5">
          <div class="text-center mb-6">
            <div class="text-5xl mb-3" aria-hidden="true">🎉</div>
            <h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 mb-2">You're all set!</h1>
            <p class="text-gray-500 dark:text-gray-400 text-sm">Here's a summary of what you completed:</p>
          </div>
          <ul class="space-y-2 mb-6">
            <li class="flex items-center gap-3 text-sm">
              <span :class="completedSteps.workspace ? 'text-green-600' : 'text-gray-400'" aria-hidden="true">{{ completedSteps.workspace ? '✓' : '○' }}</span>
              <span :class="completedSteps.workspace ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400'">Workspace created</span>
            </li>
            <li class="flex items-center gap-3 text-sm">
              <span :class="completedSteps.team ? 'text-green-600' : 'text-gray-400'" aria-hidden="true">{{ completedSteps.team ? '✓' : '○' }}</span>
              <span :class="completedSteps.team ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400'">Team invited</span>
            </li>
            <li class="flex items-center gap-3 text-sm">
              <span :class="completedSteps.leads ? 'text-green-600' : 'text-gray-400'" aria-hidden="true">{{ completedSteps.leads ? '✓' : '○' }}</span>
              <span :class="completedSteps.leads ? 'text-gray-900 dark:text-gray-100' : 'text-gray-400'">Leads imported</span>
            </li>
            <li class="flex items-center gap-3 text-sm">
              <span class="text-green-600" aria-hidden="true">✓</span>
              <span class="text-gray-900 dark:text-gray-100">Pipeline configured</span>
            </li>
          </ul>
          <button
            class="w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors"
            @click="finish"
          >Go to dashboard</button>
        </div>

      </div>
    </div>
  </div>
</template>

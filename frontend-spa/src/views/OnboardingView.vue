<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useFirmStore } from '@/stores/firm'

const router = useRouter()
const firmStore = useFirmStore()

const workspaceName = ref('')
const errorMsg = ref('')
const isLoading = ref(false)

async function handleSubmit() {
  errorMsg.value = ''
  if (!workspaceName.value.trim()) {
    errorMsg.value = 'Workspace name is required.'
    return
  }
  isLoading.value = true
  const result = await firmStore.createFirm(workspaceName.value.trim())
  isLoading.value = false
  if (result.ok) {
    await router.push('/app/dashboard')
  } else {
    errorMsg.value = result.error ?? 'Failed to create workspace.'
  }
}

const steps = [
  { label: 'Account created', state: 'done' },
  { label: 'Create workspace', state: 'active' },
  { label: 'Go to dashboard', state: 'pending' },
]
</script>

<template>
  <div class="min-h-screen flex flex-col justify-center items-center bg-gray-50 p-8">
    <div class="w-full max-w-lg">
      <div class="text-center mb-8">
        <span class="text-3xl font-bold text-red-600">LeadLab</span>
        <p class="text-gray-500 mt-1 text-sm">Let's get you set up</p>
      </div>

      <!-- Step indicator -->
      <div class="flex items-center justify-center mb-8">
        <div v-for="(step, idx) in steps" :key="step.label" class="flex items-center">
          <div class="flex flex-col items-center">
            <div
              class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-colors"
              :class="{
                'bg-green-600 border-green-600 text-white': step.state === 'done',
                'bg-red-600 border-red-600 text-white': step.state === 'active',
                'bg-white border-gray-300 text-gray-400': step.state === 'pending',
              }"
            >
              <span v-if="step.state === 'done'">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <span
              class="mt-1 text-xs font-medium"
              :class="{
                'text-green-600': step.state === 'done',
                'text-red-600': step.state === 'active',
                'text-gray-400': step.state === 'pending',
              }"
            >
              {{ step.label }}
            </span>
          </div>
          <div
            v-if="idx < steps.length - 1"
            class="w-12 h-0.5 mx-2 mb-5"
            :class="idx === 0 ? 'bg-green-400' : 'bg-gray-200'"
          />
        </div>
      </div>

      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
        <h1 class="text-2xl font-semibold text-gray-900 mb-2">Create your workspace</h1>
        <p class="text-gray-500 mb-6 text-sm">Your workspace is where you and your team manage leads and customers.</p>

        <div v-if="errorMsg" class="mb-4 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {{ errorMsg }}
        </div>

        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label for="workspaceName" class="block text-sm font-medium text-gray-700 mb-1">Workspace name</label>
            <input
              id="workspaceName"
              v-model="workspaceName"
              type="text"
              required
              class="w-full rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-red-500 focus:ring-1 focus:ring-red-500"
              placeholder="Acme Inc."
            />
          </div>

          <button
            type="submit"
            :disabled="isLoading"
            class="w-full bg-red-600 text-white rounded-xl py-2.5 text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <svg v-if="isLoading" class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            {{ isLoading ? 'Creating…' : 'Create workspace' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

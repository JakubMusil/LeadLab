<script setup lang="ts">
/**
 * PeoplePicker – reusable autocomplete component for selecting a firm member.
 *
 * Usage:
 *   <PeoplePicker v-model="selectedMembershipId" :firm-id="firmId" />
 *
 * Emits the selected membership `id` (string) via `update:modelValue`.
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useMembersStore, type MemberOut } from '@/stores/members'
import { UserCircleIcon, ChevronUpDownIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import { useI18n } from '@/composables/useI18n'

const props = withDefaults(defineProps<{
  modelValue: string
  firmId: string
  placeholder?: string
  disabled?: boolean
}>(), {
  placeholder: '',
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useI18n()
const membersStore = useMembersStore()

const query = ref('')
const open = ref(false)
const containerRef = ref<HTMLElement | null>(null)

// Ensure members are loaded
onMounted(() => {
  if (props.firmId) membersStore.fetchMembers(props.firmId)
  document.addEventListener('mousedown', handleClickOutside)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', handleClickOutside)
})
watch(() => props.firmId, (id) => {
  if (id) membersStore.fetchMembers(id)
})

const selectedMember = computed<MemberOut | undefined>(() =>
  props.modelValue ? membersStore.memberById(props.modelValue) : undefined,
)

const filteredMembers = computed<MemberOut[]>(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return membersStore.members
  return membersStore.members.filter((m: MemberOut) => {
    const name = (m.user_full_name || '').toLowerCase()
    const email = m.user_email.toLowerCase()
    return name.includes(q) || email.includes(q)
  })
})

function selectMember(m: MemberOut) {
  emit('update:modelValue', m.id)
  query.value = ''
  open.value = false
}

function clear() {
  emit('update:modelValue', '')
  query.value = ''
}

function displayLabel(m: MemberOut): string {
  return m.user_full_name?.trim() || m.user_email
}

function handleClickOutside(e: MouseEvent) {
  if (containerRef.value && !containerRef.value.contains(e.target as Node)) {
    open.value = false
  }
}
</script>

<template>
  <div ref="containerRef" class="relative">
    <!-- Trigger / selected display -->
    <div
      class="flex items-center gap-2 w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm cursor-pointer"
      :class="disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-brand'"
      @click="!disabled && (open = !open)"
    >
      <UserCircleIcon class="h-4 w-4 text-gray-400 shrink-0" />
      <span v-if="selectedMember" class="flex-1 truncate text-gray-900 dark:text-gray-100">
        {{ displayLabel(selectedMember) }}
        <span class="text-gray-400 text-xs ml-1">{{ selectedMember.user_email }}</span>
      </span>
      <span v-else class="flex-1 text-gray-400">
        {{ placeholder || t('peoplePicker.placeholder') }}
      </span>
      <button v-if="selectedMember && !disabled" @click.stop="clear" class="text-gray-400 hover:text-red-500">
        <XMarkIcon class="h-4 w-4" />
      </button>
      <ChevronUpDownIcon v-else class="h-4 w-4 text-gray-400 shrink-0" />
    </div>

    <!-- Dropdown -->
    <div
      v-if="open && !disabled"
      class="absolute z-50 mt-1 w-full rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg max-h-56 overflow-auto"
    >
      <!-- Search input -->
      <div class="px-3 pt-2 pb-1">
        <input
          v-model="query"
          type="text"
          :placeholder="t('peoplePicker.search')"
          class="w-full rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 px-2 py-1 text-xs text-gray-900 dark:text-gray-100 focus:outline-none"
          @click.stop
        />
      </div>

      <!-- Members list -->
      <ul class="py-1">
        <li v-if="membersStore.loading" class="px-3 py-2 text-xs text-gray-400">…</li>
        <li v-else-if="filteredMembers.length === 0" class="px-3 py-2 text-xs text-gray-400">
          {{ t('peoplePicker.noResults') }}
        </li>
        <li
          v-for="m in filteredMembers"
          :key="m.id"
          @click="selectMember(m)"
          class="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
          :class="m.id === modelValue ? 'bg-brand/10 text-brand font-medium' : 'text-gray-900 dark:text-gray-100'"
        >
          <UserCircleIcon class="h-4 w-4 text-gray-400 shrink-0" />
          <span class="truncate">{{ displayLabel(m) }}</span>
          <span class="text-xs text-gray-400 truncate ml-auto">{{ m.user_email }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

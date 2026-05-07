<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useFirmStore } from '@/stores/firm'
import { usePermissionsStore, type RoleOut, type RolePreset } from '@/stores/permissions'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { PlusIcon, TrashIcon, PencilIcon, CheckIcon, XMarkIcon, SparklesIcon } from '@heroicons/vue/24/outline'
import { ConfirmDeleteModal } from '@/components/ui'

const firmStore = useFirmStore()
const permissionsStore = usePermissionsStore()
const toast = useToast()
const { t } = useI18n()

const firmId = computed(() => firmStore.activeFirm ? String(firmStore.activeFirm.id) : '')

const loading = ref(false)

// Create role form
const showCreateForm = ref(false)
const createCode = ref('')
const createName = ref('')
const createDescription = ref('')
const createError = ref('')
const createLoading = ref(false)

// Edit role
const editingRoleId = ref<string | null>(null)
const editName = ref('')
const editDescription = ref('')
const editLoading = ref(false)

// Delete role
const pendingDeleteRole = ref<RoleOut | null>(null)

// Permission matrix
const editingPermissionsRoleId = ref<string | null>(null)
const draftPermissions = ref<Set<string>>(new Set())
const permSaving = ref(false)

// Role presets (v3.3)
const showPresetsModal = ref(false)
const presets = ref<RolePreset[]>([])
const presetsLoading = ref(false)
const selectedPreset = ref<RolePreset | null>(null)

const customRoles = computed(() => permissionsStore.roles.filter(r => !r.is_system))
const systemRoles = computed(() => permissionsStore.roles.filter(r => r.is_system))
const groupedCatalogue = computed(() => permissionsStore.catalogueByGroup)

async function loadData() {
  if (!firmId.value) return
  loading.value = true
  try {
    await Promise.all([
      permissionsStore.fetchRoles(firmId.value),
      permissionsStore.fetchCatalogue(firmId.value),
    ])
  } finally {
    loading.value = false
  }
}

async function openPresetsModal() {
  showPresetsModal.value = true
  selectedPreset.value = null
  if (presets.value.length === 0) {
    presetsLoading.value = true
    presets.value = await permissionsStore.fetchRolePresets(firmId.value)
    presetsLoading.value = false
  }
}

function applyPreset(preset: RolePreset) {
  createCode.value = preset.code
  createName.value = preset.name
  createDescription.value = preset.description
  showPresetsModal.value = false
  showCreateForm.value = true
}

async function createRole() {
  if (!createCode.value.trim() || !createName.value.trim()) {
    createError.value = t('permissions.roleCode') + ' & ' + t('permissions.roleName') + ' required.'
    return
  }
  createLoading.value = true
  createError.value = ''
  const result = await permissionsStore.createRole(firmId.value, {
    code: createCode.value.trim(),
    name: createName.value.trim(),
    description: createDescription.value.trim(),
  })
  createLoading.value = false
  if (result) {
    toast.success(t('permissions.roleCreated'))
    createCode.value = ''
    createName.value = ''
    createDescription.value = ''
    showCreateForm.value = false
  } else {
    createError.value = t('permissions.failedToCreateRole')
  }
}

function startEditRole(role: RoleOut) {
  editingRoleId.value = role.id
  editName.value = role.name
  editDescription.value = role.description
}

async function saveEditRole(roleId: string) {
  editLoading.value = true
  const result = await permissionsStore.updateRole(firmId.value, roleId, {
    name: editName.value,
    description: editDescription.value,
  })
  editLoading.value = false
  if (result) {
    toast.success(t('permissions.roleUpdated'))
    editingRoleId.value = null
  } else {
    toast.error(t('permissions.failedToUpdateRole'))
  }
}

async function deleteRole() {
  if (!pendingDeleteRole.value) return
  const ok = await permissionsStore.deleteRole(firmId.value, pendingDeleteRole.value.id)
  pendingDeleteRole.value = null
  if (ok) {
    toast.success(t('permissions.roleDeleted'))
  } else {
    toast.error(t('permissions.failedToDeleteRole'))
  }
}

function startEditPermissions(role: RoleOut) {
  editingPermissionsRoleId.value = role.id
  draftPermissions.value = new Set(role.permissions)
}

function togglePermission(code: string) {
  if (draftPermissions.value.has(code)) {
    draftPermissions.value.delete(code)
  } else {
    draftPermissions.value.add(code)
  }
  // Trigger reactivity
  draftPermissions.value = new Set(draftPermissions.value)
}

async function savePermissions(roleId: string) {
  permSaving.value = true
  const result = await permissionsStore.setRolePermissions(firmId.value, roleId, Array.from(draftPermissions.value))
  permSaving.value = false
  if (result) {
    toast.success(t('permissions.permissionsSaved'))
    editingPermissionsRoleId.value = null
  } else {
    toast.error(t('permissions.failedToSavePermissions'))
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-8">
    <!-- System roles (read-only) -->
    <div>
      <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100 mb-3">
        {{ t('permissions.systemRole') }}
      </h3>
      <div class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead class="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{{ t('permissions.roleCode') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{{ t('permissions.roleName') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{{ t('permissions.rolePermissions') }}</th>
            </tr>
          </thead>
          <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
            <tr v-for="role in systemRoles" :key="role.id">
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-full bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-300">{{ role.code }}</span>
              </td>
              <td class="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">{{ role.name }}</td>
              <td class="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                {{ role.permissions.length }} {{ t('permissions.rolePermissions').toLowerCase() }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Custom roles -->
    <div>
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
          {{ t('permissions.customRole') }}
        </h3>
        <div v-if="permissionsStore.canManageRoles" class="flex gap-2">
          <button
            @click="openPresetsModal"
            class="inline-flex items-center gap-1 rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <SparklesIcon class="h-4 w-4 text-amber-500" />
            {{ t('permissions.createFromTemplate') }}
          </button>
          <button
            @click="showCreateForm = !showCreateForm"
            class="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
          >
            <PlusIcon class="h-4 w-4" />
            {{ t('permissions.createRole') }}
          </button>
        </div>
      </div>

      <!-- Create form -->
      <div v-if="showCreateForm" class="mb-4 rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('permissions.roleCode') }}</label>
            <input v-model="createCode" type="text" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100" placeholder="my_role" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('permissions.roleName') }}</label>
            <input v-model="createName" type="text" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100" :placeholder="t('permissions.roleName')" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('permissions.roleDescription') }}</label>
            <input v-model="createDescription" type="text" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100" :placeholder="t('permissions.noDescription')" />
          </div>
        </div>
        <p v-if="createError" class="mt-2 text-xs text-red-600">{{ createError }}</p>
        <div class="mt-3 flex gap-2">
          <button @click="createRole" :disabled="createLoading" class="inline-flex items-center gap-1 rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
            <CheckIcon class="h-4 w-4" />
            {{ t('permissions.createRole') }}
          </button>
          <button @click="showCreateForm = false" class="inline-flex items-center gap-1 rounded-md border border-gray-300 dark:border-gray-600 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700">
            <XMarkIcon class="h-4 w-4" />
          </button>
        </div>
      </div>

      <!-- Custom roles table -->
      <div v-if="customRoles.length === 0 && !loading" class="rounded-lg border border-dashed border-gray-300 dark:border-gray-600 p-8 text-center text-sm text-gray-500 dark:text-gray-400">
        {{ t('permissions.noRoles') }}
      </div>
      <div v-else class="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
        <table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead class="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{{ t('permissions.roleCode') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{{ t('permissions.roleName') }}</th>
              <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">{{ t('permissions.rolePermissions') }}</th>
              <th v-if="permissionsStore.canManageRoles" class="px-4 py-3" />
            </tr>
          </thead>
          <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
            <tr v-for="role in customRoles" :key="role.id">
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-800 px-2 py-0.5 text-xs font-mono text-gray-700 dark:text-gray-300">{{ role.code }}</span>
              </td>
              <td class="px-4 py-3">
                <template v-if="editingRoleId === role.id">
                  <input v-model="editName" type="text" class="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1 text-sm" />
                </template>
                <span v-else class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ role.name }}</span>
              </td>
              <td class="px-4 py-3">
                <button
                  v-if="editingPermissionsRoleId !== role.id"
                  @click="startEditPermissions(role)"
                  class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                >
                  {{ role.permissions.length }} {{ t('permissions.rolePermissions').toLowerCase() }}
                </button>
                <span v-else class="text-xs text-gray-500">{{ draftPermissions.size }} selected</span>
              </td>
              <td v-if="permissionsStore.canManageRoles" class="px-4 py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  <template v-if="editingRoleId === role.id">
                    <button @click="saveEditRole(role.id)" :disabled="editLoading" class="p-1 text-green-600 hover:text-green-700">
                      <CheckIcon class="h-4 w-4" />
                    </button>
                    <button @click="editingRoleId = null" class="p-1 text-gray-400 hover:text-gray-600">
                      <XMarkIcon class="h-4 w-4" />
                    </button>
                  </template>
                  <template v-else-if="editingPermissionsRoleId === role.id">
                    <button @click="savePermissions(role.id)" :disabled="permSaving" class="p-1 text-green-600 hover:text-green-700">
                      <CheckIcon class="h-4 w-4" />
                    </button>
                    <button @click="editingPermissionsRoleId = null" class="p-1 text-gray-400 hover:text-gray-600">
                      <XMarkIcon class="h-4 w-4" />
                    </button>
                  </template>
                  <template v-else>
                    <button @click="startEditRole(role)" class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
                      <PencilIcon class="h-4 w-4" />
                    </button>
                    <button @click="pendingDeleteRole = role" class="p-1 text-gray-400 hover:text-red-600">
                      <TrashIcon class="h-4 w-4" />
                    </button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Permission matrix (shown when editing permissions for a role) -->
      <div v-if="editingPermissionsRoleId" class="mt-4 rounded-lg border border-indigo-200 dark:border-indigo-800 p-4">
        <h4 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">{{ t('permissions.permissionMatrix') }}</h4>
        <div class="space-y-4">
          <div v-for="(items, group) in groupedCatalogue" :key="group">
            <p class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase mb-1.5">{{ group }}</p>
            <div class="flex flex-wrap gap-2">
              <label
                v-for="item in items"
                :key="item.code"
                class="flex items-center gap-1.5 cursor-pointer rounded border px-2 py-1 text-xs"
                :class="draftPermissions.has(item.code) ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300' : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400'"
              >
                <input
                  type="checkbox"
                  :checked="draftPermissions.has(item.code)"
                  @change="togglePermission(item.code)"
                  class="h-3 w-3 rounded border-gray-300 text-indigo-600"
                />
                {{ item.code }}
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete confirmation modal -->
    <ConfirmDeleteModal
      :open="!!pendingDeleteRole"
      :title="t('permissions.deleteRole')"
      :message="t('permissions.deleteRoleConfirm')"
      @confirm="deleteRole"
      @cancel="pendingDeleteRole = null"
    />

    <!-- Role presets modal (v3.3) -->
    <Teleport to="body">
      <Transition name="fade">
        <div
          v-if="showPresetsModal"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          @click.self="showPresetsModal = false"
        >
          <div class="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-2xl mx-4 overflow-hidden">
            <!-- Header -->
            <div class="flex items-center gap-3 px-6 pt-5 pb-4 border-b border-gray-100 dark:border-gray-800">
              <SparklesIcon class="h-5 w-5 text-amber-500 shrink-0" />
              <div class="flex-1">
                <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ t('permissions.rolePresetsTitle') }}</h2>
                <p class="text-xs text-gray-400 dark:text-gray-500">{{ t('permissions.rolePresetsHint') }}</p>
              </div>
              <button @click="showPresetsModal = false" class="p-1 text-gray-400 hover:text-gray-600">
                <XMarkIcon class="h-5 w-5" />
              </button>
            </div>

            <!-- Presets grid -->
            <div class="p-6">
              <div v-if="presetsLoading" class="flex justify-center py-8 text-gray-400 text-sm">{{ t('permissions.loadingPresets') }}</div>
              <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <button
                  v-for="preset in presets"
                  :key="preset.code"
                  type="button"
                  @click="applyPreset(preset)"
                  class="text-left rounded-xl border border-gray-200 dark:border-gray-700 p-4 hover:border-brand hover:bg-brand/5 dark:hover:bg-brand/10 transition-colors group"
                >
                  <p class="text-sm font-semibold text-gray-900 dark:text-gray-100 group-hover:text-brand">{{ preset.name }}</p>
                  <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 mb-2">{{ preset.description }}</p>
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="perm in preset.permissions.slice(0, 4)"
                      :key="perm"
                      class="inline-block rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-600 dark:text-gray-400"
                    >{{ perm }}</span>
                    <span v-if="preset.permissions.length > 4" class="inline-block rounded bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">+{{ preset.permissions.length - 4 }}</span>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

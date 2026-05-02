<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import { api } from '@/api'
import { type DocumentOut, docFileIcon, docFileIconColor, fmtDocBytes } from '@/types/documents'
import { TrashIcon, FolderOpenIcon, ArrowDownTrayIcon } from '@heroicons/vue/24/outline'
const toast = useToast()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const documents = ref<DocumentOut[]>([])
const loading = ref(false)
const uploading = ref(false)
const searchQuery = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const deleteConfirmId = ref<string | null>(null)

// ---------------------------------------------------------------------------
// Computed
// ---------------------------------------------------------------------------
const filtered = computed(() => {
  if (!searchQuery.value.trim()) return documents.value
  const q = searchQuery.value.toLowerCase()
  return documents.value.filter(d => d.name.toLowerCase().includes(q))
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('cs-CZ', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  })
}

function entityLabel(doc: DocumentOut): string {
  if (doc.lead_title) return doc.lead_title
  if (doc.customer_name) return doc.customer_name
  if (doc.realization_title) return doc.realization_title
  if (doc.management_title) return doc.management_title
  if (doc.task_title) return doc.task_title
  if (doc.proposal_title) return doc.proposal_title
  return t('documents.noEntity')
}

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------
async function loadDocuments() {
  loading.value = true
  try {
    const res = await api.get<DocumentOut[]>('/api/v1/erp/documents')
    if (res.ok) documents.value = res.data
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------
function triggerUpload() {
  fileInputRef.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return

  uploading.value = true
  let uploaded = 0
  for (const file of Array.from(files)) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', file.name)
    const res = await api.postForm<DocumentOut>('/api/v1/erp/documents', formData)
    if (res.ok) {
      documents.value.unshift(res.data)
      uploaded++
    }
  }
  uploading.value = false
  input.value = ''
  if (uploaded > 0) {
    toast.success(t('documents.uploadSuccess', { count: uploaded }))
  }
}

// ---------------------------------------------------------------------------
// Delete
// ---------------------------------------------------------------------------
async function confirmDelete(id: string) {
  deleteConfirmId.value = id
}

async function doDelete() {
  const id = deleteConfirmId.value
  if (!id) return
  deleteConfirmId.value = null
  const res = await api.delete(`/api/v1/erp/documents/${id}`)
  if (res.ok) {
    documents.value = documents.value.filter(d => d.id !== id)
    toast.success(t('documents.deleteSuccess'))
  }
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
onMounted(loadDocuments)
</script>

<template>
  <div class="p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">{{ t('documents.title') }}</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">{{ t('documents.subtitle') }}</p>
      </div>
      <div class="flex items-center gap-3">
        <input
          v-model="searchQuery"
          type="text"
          :placeholder="t('documents.searchPlaceholder')"
          class="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm w-56 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          @click="triggerUpload"
          :disabled="uploading"
          class="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
        >
          <span v-if="uploading">{{ t('documents.uploading') }}</span>
          <span v-else>⬆ {{ t('documents.upload') }}</span>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          multiple
          class="hidden"
          @change="onFileSelected"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16 text-gray-500 dark:text-gray-400">
      {{ t('documents.loading') }}
    </div>

    <!-- Empty state -->
    <div
      v-else-if="filtered.length === 0"
      class="text-center py-16"
    >
      <FolderOpenIcon class="w-14 h-14 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
      <p class="text-gray-500 dark:text-gray-400 text-lg">
        {{ searchQuery ? t('documents.noResults') : t('documents.empty') }}
      </p>
      <p v-if="!searchQuery" class="text-gray-400 dark:text-gray-500 text-sm mt-1">
        {{ t('documents.emptyHint') }}
      </p>
    </div>

    <!-- Documents table -->
    <div v-else class="bg-white dark:bg-gray-800 rounded-xl shadow border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
          <tr>
            <th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">{{ t('documents.colName') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">{{ t('documents.colEntity') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">{{ t('documents.colSize') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">{{ t('documents.colUploadedBy') }}</th>
            <th class="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">{{ t('documents.colDate') }}</th>
            <th class="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-700">
          <tr
            v-for="doc in filtered"
            :key="doc.id"
            class="hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
          >
            <!-- Name + icon -->
            <td class="px-4 py-3">
              <div class="flex items-center gap-2">
                <span :class="['text-xl', docFileIconColor(doc.content_type)]">{{ docFileIcon(doc.content_type) }}</span>
                <a
                  :href="doc.file_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="font-medium text-blue-600 dark:text-blue-400 hover:underline truncate max-w-xs"
                >{{ doc.name }}</a>
              </div>
            </td>
            <!-- Entity -->
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400 text-xs">
              {{ entityLabel(doc) }}
            </td>
            <!-- Size -->
            <td class="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
              {{ fmtDocBytes(doc.size_bytes) }}
            </td>
            <!-- Uploaded by -->
            <td class="px-4 py-3 text-gray-600 dark:text-gray-400 text-xs">
              {{ doc.uploaded_by_name || '—' }}
            </td>
            <!-- Date -->
            <td class="px-4 py-3 text-gray-500 dark:text-gray-400 text-xs whitespace-nowrap">
              {{ formatDate(doc.created_at) }}
            </td>
            <!-- Actions -->
            <td class="px-4 py-3 text-right">
              <div class="flex items-center gap-2 justify-end">
                <a
                  :href="doc.file_url"
                  target="_blank"
                  rel="noopener noreferrer"
                  :title="t('documents.download')"
                  class="text-gray-400 hover:text-blue-500 transition-colors"
                ><ArrowDownTrayIcon class="w-4 h-4" /></a>
                <button
                  @click="confirmDelete(doc.id)"
                  :title="t('documents.delete')"
                  class="text-gray-400 hover:text-red-500 transition-colors"
                ><TrashIcon class="w-4 h-4" /></button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Delete confirm dialog -->
    <div
      v-if="deleteConfirmId"
      class="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      @click.self="deleteConfirmId = null"
    >
      <div class="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-xl max-w-sm w-full mx-4">
        <p class="text-gray-800 dark:text-white font-medium mb-4">{{ t('documents.deleteConfirm') }}</p>
        <div class="flex gap-3 justify-end">
          <button
            @click="deleteConfirmId = null"
            class="px-4 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >{{ t('common.cancel') }}</button>
          <button
            @click="doDelete"
            class="px-4 py-2 text-sm bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
          >{{ t('common.delete') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * FileUploadComposer — sidebar form for the `file_upload` Streamline tool.
 *
 * Per Fáze 7.2 in `streamline_goals.md`:
 *   - One required user-facing field: **Title** (label of the file as a
 *     whole). Filename / MIME / size are hidden — backend fills them in.
 *   - Pill switcher between two source modes (same visual style as the
 *     message composer's channel/direction picker):
 *       1. **From URL** — single URL input + "Store locally" toggle
 *          (default ON). When ON the backend Celery task downloads the
 *          binary; when OFF only the link is kept.
 *       2. **Upload file(s)** — drop-zone + multi `<input type="file">`.
 *          Per-file size limit is plan-aware (15 MB free / 100 MB pro,
 *          read from the firm store); going over triggers an upgrade
 *          toast. Multiple files fan out into N separate activities.
 *
 * The component owns the upload step: when the user clicks **Save**, it
 * either POSTs the URL directly (no upload needed) or uploads the
 * blob(s) to ``/api/v1/crm/file-uploads/upload`` and emits one
 * ``submit`` event per resulting file. The parent then turns each
 * payload into a regular ``POST /activities`` of ``type=file_upload``.
 */
import { computed, ref } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import { useFirmStore } from '@/stores/firm'
import {
  ArrowUpTrayIcon,
  LinkIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'

interface Props {
  /** Endpoint the multi-file upload form posts to (already carries the
   *  parent entity ID as a query param). */
  uploadUrl: string
}

const props = defineProps<Props>()

/**
 * One activity-ready payload per file. The parent fans these out into
 * separate `POST /api/v1/crm/activities` calls (one Activity per file)
 * so the timeline shows a card per attachment.
 */
interface FileUploadSubmitPayload {
  title: string
  url: string
  filename: string
  size_bytes: number
  mime_type: string
  source_kind: 'url' | 'upload'
  store_locally: boolean
}

const emit = defineEmits<{
  (e: 'submit', payload: FileUploadSubmitPayload): void
  (e: 'cancel'): void
}>()

const { t } = useI18n()
const toast = useToast()
const firmStore = useFirmStore()

const FREE_LIMIT_BYTES = 15 * 1024 * 1024
const PRO_LIMIT_BYTES = 100 * 1024 * 1024

const planLimitBytes = computed(() => {
  const tier = (firmStore.activeFirm?.subscription_tier ?? '').toLowerCase()
  return tier === 'pro' ? PRO_LIMIT_BYTES : FREE_LIMIT_BYTES
})

const planLimitLabel = computed(() => `${planLimitBytes.value / (1024 * 1024)} MB`)

type SourceKind = 'url' | 'upload'

const sourceKind = ref<SourceKind>('upload')
const title = ref('')
const url = ref('')
const storeLocally = ref(true)
const selectedFiles = ref<File[]>([])
const dragActive = ref(false)
const submitting = ref(false)

function pickSource(kind: SourceKind) {
  sourceKind.value = kind
}

function _addFiles(list: FileList | File[] | null) {
  if (!list) return
  const incoming = Array.from(list)
  for (const file of incoming) {
    if (file.size > planLimitBytes.value) {
      toast.error(
        t('fileUpload.overLimit', { name: file.name, limit: planLimitLabel.value }),
      )
      continue
    }
    // Skip identical (name+size) files already queued so accidental
    // double-pick doesn't create duplicate activities.
    if (
      selectedFiles.value.some(
        (existing) => existing.name === file.name && existing.size === file.size,
      )
    ) continue
    selectedFiles.value.push(file)
  }
}

function onFilePick(event: Event) {
  const input = event.target as HTMLInputElement
  _addFiles(input.files)
  input.value = ''
}

function onDrop(event: DragEvent) {
  event.preventDefault()
  dragActive.value = false
  _addFiles(event.dataTransfer?.files ?? null)
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
  dragActive.value = true
}

function onDragLeave(event: DragEvent) {
  event.preventDefault()
  dragActive.value = false
}

function removeFile(index: number) {
  selectedFiles.value = selectedFiles.value.filter((_, i) => i !== index)
}

function formatSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const canSubmit = computed(() => {
  if (submitting.value) return false
  if (!title.value.trim()) return false
  if (sourceKind.value === 'url') return /^https?:\/\//i.test(url.value.trim())
  return selectedFiles.value.length > 0
})

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    if (sourceKind.value === 'url') {
      // For the URL branch we don't touch the backend until the parent
      // POSTs the activity — the Celery worker on the server side will
      // then (if `store_locally`) async-fetch the binary and patch the
      // metadata in place.
      emit('submit', {
        title: title.value.trim(),
        url: url.value.trim(),
        filename: '',
        size_bytes: 0,
        mime_type: '',
        source_kind: 'url',
        store_locally: storeLocally.value,
      })
      return
    }

    // Upload branch: send all selected files in one multipart request,
    // then emit one activity payload per returned entry.
    const fd = new FormData()
    for (const file of selectedFiles.value) fd.append('files', file)
    const res = await fetch(props.uploadUrl, {
      method: 'POST',
      credentials: 'include',
      body: fd,
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => null)
      toast.error(errorData?.detail ?? t('fileUpload.uploadFailed'))
      return
    }
    const body = (await res.json()) as {
      files: Array<{
        url: string
        filename: string
        content_type: string
        size_bytes: number
        document_id: string
      }>
    }
    // The user-facing title applies to all files in this batch — when
    // the user uploads multiple files at once they're treated as
    // siblings under the same logical "upload" event.
    for (const entry of body.files) {
      emit('submit', {
        title: title.value.trim(),
        url: entry.url,
        filename: entry.filename,
        size_bytes: entry.size_bytes,
        mime_type: entry.content_type,
        source_kind: 'upload',
        store_locally: true,
      })
    }
  } catch {
    toast.error(t('fileUpload.uploadFailed'))
  } finally {
    submitting.value = false
  }
}

function cancel() {
  emit('cancel')
}
</script>

<template>
  <div class="space-y-3" data-testid="file-upload-composer" :data-source-kind="sourceKind">
    <!-- Source kind switcher (mirrors message channel/direction styling) -->
    <div data-field="file-upload-source-kind">
      <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
        {{ t('fileUpload.sourceLabel') }}<span class="text-red-500 ml-0.5">*</span>
      </label>
      <div class="flex flex-wrap gap-1.5">
        <button
          type="button"
          data-testid="file-upload-source-upload"
          :data-active="sourceKind === 'upload' ? 'true' : 'false'"
          class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors inline-flex items-center gap-1.5"
          :class="sourceKind === 'upload'
            ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
            : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-red-300'"
          @click="pickSource('upload')"
        >
          <ArrowUpTrayIcon class="w-3.5 h-3.5" />
          {{ t('fileUpload.sourceUpload') }}
        </button>
        <button
          type="button"
          data-testid="file-upload-source-url"
          :data-active="sourceKind === 'url' ? 'true' : 'false'"
          class="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors inline-flex items-center gap-1.5"
          :class="sourceKind === 'url'
            ? 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-700 text-red-700 dark:text-red-300'
            : 'border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-red-300'"
          @click="pickSource('url')"
        >
          <LinkIcon class="w-3.5 h-3.5" />
          {{ t('fileUpload.sourceUrl') }}
        </button>
      </div>
    </div>

    <!-- Title (always required) -->
    <div data-field="file-upload-title">
      <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
        {{ t('fileUpload.titleLabel') }}<span class="text-red-500 ml-0.5">*</span>
      </label>
      <input
        v-model="title"
        type="text"
        data-testid="file-upload-title"
        :placeholder="t('fileUpload.titlePlaceholder')"
        class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
      />
    </div>

    <!-- URL branch -->
    <template v-if="sourceKind === 'url'">
      <div data-field="file-upload-url">
        <label class="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
          {{ t('fileUpload.urlLabel') }}<span class="text-red-500 ml-0.5">*</span>
        </label>
        <input
          v-model="url"
          type="url"
          data-testid="file-upload-url"
          placeholder="https://…"
          class="w-full rounded-xl border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:border-red-400"
        />
      </div>
      <label
        class="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-300 cursor-pointer select-none"
        data-testid="file-upload-store-locally"
      >
        <input v-model="storeLocally" type="checkbox" class="rounded border-gray-300 text-red-600 focus:ring-red-500" />
        <span>{{ t('fileUpload.storeLocally') }}</span>
      </label>
    </template>

    <!-- Upload branch -->
    <template v-else>
      <div
        data-testid="file-upload-dropzone"
        class="rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm transition-colors cursor-pointer"
        :class="dragActive
          ? 'border-red-400 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300'
          : 'border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:border-red-300'"
        @drop="onDrop"
        @dragover="onDragOver"
        @dragleave="onDragLeave"
        @click="($refs.fileInput as HTMLInputElement | undefined)?.click()"
      >
        <ArrowUpTrayIcon class="w-5 h-5 mx-auto mb-1" />
        <p class="text-xs">{{ t('fileUpload.dropHint') }}</p>
        <p class="text-[11px] mt-1 opacity-80" data-testid="file-upload-limit-hint">
          {{ t('fileUpload.limitHint', { limit: planLimitLabel }) }}
        </p>
        <input
          ref="fileInput"
          type="file"
          multiple
          class="hidden"
          data-testid="file-upload-input"
          @change="onFilePick"
        />
      </div>

      <ul
        v-if="selectedFiles.length"
        class="space-y-1.5"
        data-testid="file-upload-selected-list"
      >
        <li
          v-for="(file, idx) in selectedFiles"
          :key="`${file.name}-${file.size}-${idx}`"
          class="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-600 px-2.5 py-1.5"
          data-testid="file-upload-selected-item"
        >
          <span class="text-sm text-gray-700 dark:text-gray-200 truncate flex-1 min-w-0">{{ file.name }}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400 tabular-nums flex-shrink-0">{{ formatSize(file.size) }}</span>
          <button
            type="button"
            class="text-gray-400 hover:text-red-500"
            data-testid="file-upload-remove-selected"
            @click="removeFile(idx)"
          >
            <TrashIcon class="w-4 h-4" />
          </button>
        </li>
      </ul>
    </template>

    <div class="flex items-center justify-end gap-2 pt-1">
      <button
        type="button"
        data-testid="file-upload-cancel"
        class="px-3 py-2 rounded-xl text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-red-600"
        @click="cancel"
      >{{ t('fileUpload.cancel') }}</button>
      <button
        type="button"
        data-testid="file-upload-submit"
        :disabled="!canSubmit"
        class="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
        @click="submit"
      >{{ submitting ? t('fileUpload.saving') : t('fileUpload.save') }}</button>
    </div>
  </div>
</template>

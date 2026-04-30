<script setup lang="ts">
/**
 * VoiceMemoRecorder — diktafonový UI pro nový `voice_memo` záznam v sidebaru.
 *
 * Workflow (per Fáze 7 v `streamline_goals.md`):
 *   - uživatel vidí jen tlačítka **Start / Pauza / Pokračovat / Uložit /
 *     Zahodit** a běžící časomíru. Filename, MIME, size_bytes a
 *     duration_seconds si počítáme **interně** a uživatel je nikdy nezadává.
 *   - Po stisku „Uložit" se nahrávka POSTne na
 *     ``/api/v1/crm/voice-memos/upload`` (vrací URL + size_bytes), a poté
 *     vystavíme `submit` event s payloadem připraveným pro standardní
 *     ``POST /api/v1/crm/activities`` (``type: 'voice_memo'``,
 *     ``metadata: { url, duration_seconds, size_bytes, filename, content_type }``).
 *   - Pokud má firma aktivní AI plugin pro STT, parent komponenta může
 *     transkripci doplnit zpětně (out-of-scope tohoto komponentu).
 *
 * Browser API: ``navigator.mediaDevices.getUserMedia`` + ``MediaRecorder``.
 * Pokud uživatel mikrofon zamítne (nebo prohlížeč API nepodporuje),
 * zobrazíme srozumitelnou chybovou hlášku.
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useToast } from '@/composables/useToast'
import {
  MicrophoneIcon,
  PauseIcon,
  PlayIcon,
  StopIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'

interface Props {
  /** Endpoint to which the recorded audio blob will be POSTed. */
  uploadUrl: string
}

const props = defineProps<Props>()

interface VoiceMemoSubmitPayload {
  url: string
  duration_seconds: number
  size_bytes: number
  filename: string
  content_type: string
}

const emit = defineEmits<{
  (e: 'submit', payload: VoiceMemoSubmitPayload): void
  (e: 'cancel'): void
}>()

const { t } = useI18n()
const toast = useToast()

type Phase = 'idle' | 'recording' | 'paused' | 'review' | 'uploading'

const phase = ref<Phase>('idle')
const elapsedSeconds = ref(0)
const errorMessage = ref('')

let mediaStream: MediaStream | null = null
let mediaRecorder: MediaRecorder | null = null
let recordedChunks: Blob[] = []
let timerHandle: number | null = null

// Final blob exposed once the user stops the recording (review state).
const recordedBlob = ref<Blob | null>(null)
const recordedMimeType = ref<string>('')
const playbackUrl = ref<string>('')

/**
 * Pick a recording MIME type the browser actually supports.  Chromium-based
 * browsers favour ``audio/webm``, Safari prefers ``audio/mp4``.  We fall
 * back to letting ``MediaRecorder`` pick its own default if neither is
 * available.
 */
function _pickRecordingMimeType(): string {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
  ]
  if (typeof MediaRecorder === 'undefined') return ''
  for (const candidate of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(candidate)) return candidate
    } catch {
      /* some browsers throw on unsupported types — ignore */
    }
  }
  return ''
}

function _stopTimer() {
  if (timerHandle !== null) {
    window.clearInterval(timerHandle)
    timerHandle = null
  }
}

function _startTimer() {
  _stopTimer()
  timerHandle = window.setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

function _releaseStream() {
  if (mediaStream) {
    for (const track of mediaStream.getTracks()) track.stop()
    mediaStream = null
  }
}

function _resetState() {
  _stopTimer()
  _releaseStream()
  if (playbackUrl.value) {
    URL.revokeObjectURL(playbackUrl.value)
    playbackUrl.value = ''
  }
  mediaRecorder = null
  recordedChunks = []
  recordedBlob.value = null
  recordedMimeType.value = ''
  elapsedSeconds.value = 0
  errorMessage.value = ''
  phase.value = 'idle'
}

async function startRecording() {
  errorMessage.value = ''
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    errorMessage.value = t('voiceMemo.unsupported')
    return
  }
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    errorMessage.value = t('voiceMemo.permissionDenied')
    return
  }
  const mimeType = _pickRecordingMimeType()
  try {
    mediaRecorder = mimeType
      ? new MediaRecorder(mediaStream, { mimeType })
      : new MediaRecorder(mediaStream)
  } catch {
    errorMessage.value = t('voiceMemo.unsupported')
    _releaseStream()
    return
  }
  recordedChunks = []
  mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) recordedChunks.push(event.data)
  }
  mediaRecorder.onstop = () => {
    const blobType = mediaRecorder?.mimeType || mimeType || 'audio/webm'
    const blob = new Blob(recordedChunks, { type: blobType })
    recordedBlob.value = blob
    recordedMimeType.value = blobType
    if (playbackUrl.value) URL.revokeObjectURL(playbackUrl.value)
    playbackUrl.value = blob.size > 0 ? URL.createObjectURL(blob) : ''
    _releaseStream()
    phase.value = 'review'
  }
  mediaRecorder.start()
  elapsedSeconds.value = 0
  phase.value = 'recording'
  _startTimer()
}

function pauseRecording() {
  if (!mediaRecorder || mediaRecorder.state !== 'recording') return
  mediaRecorder.pause()
  _stopTimer()
  phase.value = 'paused'
}

function resumeRecording() {
  if (!mediaRecorder || mediaRecorder.state !== 'paused') return
  mediaRecorder.resume()
  _startTimer()
  phase.value = 'recording'
}

function stopRecording() {
  if (!mediaRecorder) return
  if (mediaRecorder.state === 'inactive') return
  // Triggers `onstop` which transitions us to `review`.
  mediaRecorder.stop()
  _stopTimer()
}

function discardRecording() {
  _resetState()
  emit('cancel')
}

async function saveRecording() {
  if (!recordedBlob.value) return
  phase.value = 'uploading'
  errorMessage.value = ''

  // Mirror the recorded MIME type into a sensible file extension.  The
  // user never sees this name; it's just so the storage URL has a
  // recognisable suffix when the audio is downloaded later.
  const mime = recordedMimeType.value || 'audio/webm'
  let extension = 'webm'
  if (mime.includes('mp4')) extension = 'm4a'
  else if (mime.includes('ogg')) extension = 'ogg'
  else if (mime.includes('mpeg')) extension = 'mp3'
  const filename = `voice-memo-${Date.now()}.${extension}`

  const fd = new FormData()
  fd.append('file', recordedBlob.value, filename)

  try {
    const res = await fetch(props.uploadUrl, {
      method: 'POST',
      credentials: 'include',
      body: fd,
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => null)
      const message = errorData?.detail ?? t('voiceMemo.uploadFailed')
      errorMessage.value = message
      toast.error(message)
      phase.value = 'review'
      return
    }
    const uploaded = (await res.json()) as {
      url: string
      size_bytes: number
      filename: string
      content_type: string
    }
    emit('submit', {
      url: uploaded.url,
      filename: uploaded.filename,
      content_type: uploaded.content_type,
      size_bytes: uploaded.size_bytes,
      duration_seconds: elapsedSeconds.value,
    })
    _resetState()
  } catch {
    errorMessage.value = t('voiceMemo.uploadFailed')
    toast.error(errorMessage.value)
    phase.value = 'review'
  }
}

const formattedTimer = computed(() => {
  const total = Math.max(0, Math.floor(elapsedSeconds.value))
  const minutes = Math.floor(total / 60).toString().padStart(2, '0')
  const seconds = (total % 60).toString().padStart(2, '0')
  return `${minutes}:${seconds}`
})

const canSave = computed(
  () => phase.value === 'review' && !!recordedBlob.value && elapsedSeconds.value > 0,
)

onBeforeUnmount(() => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    try {
      mediaRecorder.stop()
    } catch {
      /* nothing */
    }
  }
  _stopTimer()
  _releaseStream()
  if (playbackUrl.value) URL.revokeObjectURL(playbackUrl.value)
})
</script>

<template>
  <div
    class="space-y-3"
    data-testid="voice-memo-recorder"
    :data-phase="phase"
  >
    <!-- Timer + status row -->
    <div
      class="flex items-center gap-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700/40 px-4 py-3"
    >
      <span
        class="inline-flex items-center justify-center w-9 h-9 rounded-full"
        :class="phase === 'recording'
          ? 'bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-300 animate-pulse'
          : 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'"
      >
        <MicrophoneIcon class="w-5 h-5" />
      </span>
      <div class="flex-1 min-w-0">
        <p
          class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400"
          data-testid="voice-memo-recorder-status"
        >
          <template v-if="phase === 'idle'">{{ t('voiceMemo.statusIdle') }}</template>
          <template v-else-if="phase === 'recording'">{{ t('voiceMemo.statusRecording') }}</template>
          <template v-else-if="phase === 'paused'">{{ t('voiceMemo.statusPaused') }}</template>
          <template v-else-if="phase === 'review'">{{ t('voiceMemo.statusReview') }}</template>
          <template v-else-if="phase === 'uploading'">{{ t('voiceMemo.statusUploading') }}</template>
        </p>
        <p
          class="text-2xl font-semibold tabular-nums text-gray-900 dark:text-gray-100"
          data-testid="voice-memo-recorder-timer"
        >{{ formattedTimer }}</p>
      </div>
    </div>

    <!-- Playback preview (only in review state) -->
    <audio
      v-if="phase === 'review' && playbackUrl"
      data-testid="voice-memo-recorder-preview"
      :src="playbackUrl"
      controls
      class="w-full"
    />

    <!-- Error state -->
    <p
      v-if="errorMessage"
      class="text-sm text-red-600 dark:text-red-400"
      data-testid="voice-memo-recorder-error"
    >{{ errorMessage }}</p>

    <!-- Action buttons -->
    <div class="flex flex-wrap items-center gap-2">
      <button
        v-if="phase === 'idle'"
        type="button"
        data-testid="voice-memo-recorder-start"
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700"
        @click="startRecording"
      >
        <MicrophoneIcon class="w-4 h-4" />
        {{ t('voiceMemo.start') }}
      </button>

      <button
        v-if="phase === 'recording'"
        type="button"
        data-testid="voice-memo-recorder-pause"
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-200 hover:border-red-300"
        @click="pauseRecording"
      >
        <PauseIcon class="w-4 h-4" />
        {{ t('voiceMemo.pause') }}
      </button>

      <button
        v-if="phase === 'paused'"
        type="button"
        data-testid="voice-memo-recorder-resume"
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-200 hover:border-red-300"
        @click="resumeRecording"
      >
        <PlayIcon class="w-4 h-4" />
        {{ t('voiceMemo.resume') }}
      </button>

      <button
        v-if="phase === 'recording' || phase === 'paused'"
        type="button"
        data-testid="voice-memo-recorder-stop"
        class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-600 text-sm font-medium text-gray-700 dark:text-gray-200 hover:border-red-300"
        @click="stopRecording"
      >
        <StopIcon class="w-4 h-4" />
        {{ t('voiceMemo.stop') }}
      </button>

      <div class="ml-auto flex items-center gap-2">
        <button
          v-if="phase !== 'idle'"
          type="button"
          data-testid="voice-memo-recorder-discard"
          :disabled="phase === 'uploading'"
          class="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-red-600 disabled:opacity-50"
          @click="discardRecording"
        >
          <TrashIcon class="w-4 h-4" />
          {{ t('voiceMemo.discard') }}
        </button>

        <button
          v-if="phase === 'review' || phase === 'uploading'"
          type="button"
          data-testid="voice-memo-recorder-save"
          :disabled="!canSave || phase === 'uploading'"
          class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
          @click="saveRecording"
        >
          {{ phase === 'uploading' ? t('voiceMemo.saving') : t('voiceMemo.save') }}
        </button>
      </div>
    </div>
  </div>
</template>

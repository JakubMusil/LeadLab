import { ref, onUnmounted } from 'vue'

export function useClipboard() {
  const copiedId = ref<string | null>(null)
  let _timer: ReturnType<typeof setTimeout> | null = null

  function copyToClipboard(text: string, id: string = '__default__') {
    navigator.clipboard.writeText(text).then(() => {
      copiedId.value = id
      if (_timer) clearTimeout(_timer)
      _timer = setTimeout(() => {
        copiedId.value = null
        _timer = null
      }, 2000)
    }).catch(() => {
      // clipboard write failed (permission denied or insecure context) — no-op
    })
  }

  onUnmounted(() => {
    if (_timer) {
      clearTimeout(_timer)
      _timer = null
    }
  })

  return { copiedId, copyToClipboard }
}

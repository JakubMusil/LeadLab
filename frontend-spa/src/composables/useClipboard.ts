import { ref } from 'vue'

export function useClipboard() {
  const copiedId = ref<string | null>(null)
  let _timer: ReturnType<typeof setTimeout> | null = null

  function copyToClipboard(text: string, id: string = '__default__') {
    navigator.clipboard.writeText(text).then(() => {
      copiedId.value = id
      if (_timer) clearTimeout(_timer)
      _timer = setTimeout(() => {
        copiedId.value = null
      }, 2000)
    })
  }

  return { copiedId, copyToClipboard }
}

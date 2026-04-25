import { ref } from 'vue'

export type ToastType = 'success' | 'error' | 'info'
export interface Toast {
  id: number
  message: string
  type: ToastType
}

const toasts = ref<Toast[]>([])
let counter = 0

export function useToast() {
  function show(message: string, type: ToastType = 'info', duration = 3500) {
    const id = ++counter
    toasts.value.push({ id, message, type })
    setTimeout(() => {
      toasts.value = toasts.value.filter((t) => t.id !== id)
    }, duration)
  }
  function success(msg: string) {
    show(msg, 'success')
  }
  function error(msg: string) {
    show(msg, 'error')
  }
  function info(msg: string) {
    show(msg, 'info')
  }
  return { toasts, show, success, error, info }
}

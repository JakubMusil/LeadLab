import { ref } from 'vue';
const toasts = ref([]);
let counter = 0;
export function useToast() {
    function show(message, type = 'info', duration = 3500) {
        const id = ++counter;
        toasts.value.push({ id, message, type });
        setTimeout(() => {
            toasts.value = toasts.value.filter((t) => t.id !== id);
        }, duration);
    }
    function success(msg) {
        show(msg, 'success');
    }
    function error(msg) {
        show(msg, 'error');
    }
    function info(msg) {
        show(msg, 'info');
    }
    return { toasts, show, success, error, info };
}

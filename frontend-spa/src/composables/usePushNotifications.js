/**
 * usePushNotifications — Web Push API composable.
 *
 * Usage:
 *   const { isSupported, isSubscribed, isLoading, subscribe, unsubscribe } = usePushNotifications()
 *
 * The composable fetches the server's VAPID public key, registers the service
 * worker, and manages the browser push subscription lifecycle.
 */
import { ref, readonly } from 'vue';
import { api } from '@/api';
// Singleton state so that every component shares the same subscription status.
const isSubscribed = ref(false);
const isLoading = ref(false);
/**
 * Convert a base64url string to a Uint8Array expected by
 * `PushManager.subscribe({ applicationServerKey })`.
 */
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}
/** True when the browser supports service workers and the Push API. */
const isSupported = typeof window !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window;
export function usePushNotifications() {
    async function checkCurrentSubscription() {
        if (!isSupported)
            return;
        try {
            const reg = await navigator.serviceWorker.getRegistration();
            if (!reg)
                return;
            const sub = await reg.pushManager.getSubscription();
            isSubscribed.value = !!sub;
        }
        catch {
            isSubscribed.value = false;
        }
    }
    async function subscribe() {
        if (!isSupported || isLoading.value)
            return;
        isLoading.value = true;
        try {
            // 1. Get VAPID public key from server.
            const keyRes = await api.get('/api/v1/push/vapid-public-key');
            if (!keyRes.ok || !keyRes.data?.public_key) {
                console.warn('usePushNotifications: VAPID public key not available.');
                return;
            }
            // 2. Request notification permission.
            const permission = await Notification.requestPermission();
            if (permission !== 'granted')
                return;
            // 3. Register / retrieve service worker.
            const reg = await navigator.serviceWorker.ready;
            // 4. Subscribe to push.
            const pushSub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(keyRes.data.public_key),
            });
            // 5. Send subscription to the server.
            const json = pushSub.toJSON();
            await api.post('/api/v1/push/subscribe', {
                endpoint: pushSub.endpoint,
                p256dh: json.keys?.p256dh ?? '',
                auth: json.keys?.auth ?? '',
                user_agent: navigator.userAgent.slice(0, 500),
            });
            isSubscribed.value = true;
        }
        catch (err) {
            console.error('usePushNotifications: subscribe failed', err);
        }
        finally {
            isLoading.value = false;
        }
    }
    async function unsubscribe() {
        if (!isSupported || isLoading.value)
            return;
        isLoading.value = true;
        try {
            const reg = await navigator.serviceWorker.getRegistration();
            if (!reg)
                return;
            const pushSub = await reg.pushManager.getSubscription();
            if (!pushSub) {
                isSubscribed.value = false;
                return;
            }
            // Notify server first so it can clean up.
            await api.post('/api/v1/push/unsubscribe', { endpoint: pushSub.endpoint });
            await pushSub.unsubscribe();
            isSubscribed.value = false;
        }
        catch (err) {
            console.error('usePushNotifications: unsubscribe failed', err);
        }
        finally {
            isLoading.value = false;
        }
    }
    // Initialise subscription status on first use.
    checkCurrentSubscription();
    return {
        isSupported,
        isSubscribed: readonly(isSubscribed),
        isLoading: readonly(isLoading),
        subscribe,
        unsubscribe,
    };
}

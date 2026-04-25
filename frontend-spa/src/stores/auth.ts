import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '@/api'
import router from '@/router'

export interface UserOut {
  id: number
  email: string
  first_name: string
  last_name: string
  timezone: string
  full_name: string
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserOut | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  async function fetchMe() {
    const res = await api.get<UserOut>('/api/v1/users/me')
    if (res.ok) {
      user.value = res.data
    } else {
      user.value = null
    }
  }

  async function init() {
    if (initialized.value) return
    initialized.value = true
    await fetchMe()
  }

  async function login(email: string, password: string): Promise<{ ok: boolean; error?: string }> {
    loading.value = true
    try {
      const res = await api.post<UserOut>('/api/v1/users/login', { email, password })
      if (res.ok) {
        user.value = res.data
        return { ok: true }
      }
      const msg =
        (res.data as unknown as Record<string, string>)?.detail ??
        'Invalid credentials. Please try again.'
      return { ok: false, error: msg }
    } finally {
      loading.value = false
    }
  }

  async function register(
    email: string,
    password: string,
    firstName: string,
    lastName: string,
  ): Promise<{ ok: boolean; error?: string }> {
    loading.value = true
    try {
      const res = await api.post<UserOut>('/api/v1/users/register', {
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      })
      if (res.ok) {
        // Auto-login after register
        const loginRes = await api.post<UserOut>('/api/v1/users/login', { email, password })
        if (loginRes.ok) {
          user.value = loginRes.data
        }
        return { ok: true }
      }
      const errData = res.data as unknown as Record<string, unknown>
      const firstKey = Object.keys(errData ?? {})[0]
      const msg = firstKey
        ? `${firstKey}: ${(errData[firstKey] as string[])[0]}`
        : 'Registration failed. Please try again.'
      return { ok: false, error: msg }
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    await api.post('/api/v1/users/logout')
    user.value = null
    await router.push('/app/login')
  }

  return { user, loading, initialized, fetchMe, init, login, register, logout }
})

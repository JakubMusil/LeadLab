const FIRM_ID_KEY = 'firmId'

function getCsrf(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/)
  return match?.[1] ?? ''
}

function getFirmId(): string {
  return localStorage.getItem(FIRM_ID_KEY) ?? ''
}

async function request<T>(
  method: string,
  url: string,
  body?: unknown,
): Promise<{ ok: boolean; status: number; data: T }> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrf(),
  }
  const firmId = getFirmId()
  if (firmId) {
    headers['X-Firm-ID'] = firmId
  }
  const res = await fetch(url, {
    method,
    credentials: 'include',
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  let data: T
  try {
    data = await res.json()
  } catch {
    data = null as T
  }
  return { ok: res.ok, status: res.status, data }
}

async function requestFormData<T>(
  method: string,
  url: string,
  formData: FormData,
): Promise<{ ok: boolean; status: number; data: T }> {
  const headers: Record<string, string> = {
    'X-CSRFToken': getCsrf(),
  }
  const firmId = getFirmId()
  if (firmId) {
    headers['X-Firm-ID'] = firmId
  }
  const res = await fetch(url, {
    method,
    credentials: 'include',
    headers,
    body: formData,
  })
  let data: T
  try {
    data = await res.json()
  } catch {
    data = null as T
  }
  return { ok: res.ok, status: res.status, data }
}

export const api = {
  get: <T>(url: string) => request<T>('GET', url),
  post: <T>(url: string, body?: unknown) => request<T>('POST', url, body),
  put: <T>(url: string, body?: unknown) => request<T>('PUT', url, body),
  patch: <T>(url: string, body?: unknown) => request<T>('PATCH', url, body),
  delete: <T>(url: string) => request<T>('DELETE', url),
  postForm: <T>(url: string, formData: FormData) => requestFormData<T>('POST', url, formData),
}

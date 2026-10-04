// Only main is called, under /api. Empty VITE_API_URL = same origin (front served by main)
const API_URL = import.meta.env.VITE_API_URL ?? ''

const TOKEN_KEY = 'token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  // FastAPI's detail: a string, or a list of errors on a 422
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `Request failed with status ${status}`)
    this.status = status
    this.detail = detail
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  // only JSON strings: fetch sets the type itself for FormData and URLSearchParams
  if (typeof init.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_URL}/api${path}`, { ...init, headers })

  if (response.status === 401) {
    clearToken()
    // full reload: the app restarts logged out
    if (window.location.pathname !== '/login') {
      window.location.assign('/login')
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, body?.detail ?? response.statusText)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json()
}

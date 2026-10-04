// Only main is called, under /api. Empty VITE_API_URL = same origin (front served by main)
const API_URL = import.meta.env.VITE_API_URL ?? ''

const TOKEN_KEY = 'token'

// Full URL of a route of main, for what doesn't go through api() (video player, links)
export function apiUrl(path: string): string {
  return `${API_URL}/api${path}`
}

// ws:// or wss:// version of main's URL, for the WebSocket routes (ingest, chat)
export function wsUrl(path: string): string {
  const base = API_URL || window.location.origin
  return `${base.replace(/^http/, 'ws')}/api${path}`
}

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

// FastAPI sends a string in detail, except on a 422 where it's a list of errors
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Server error'
  }
  if (Array.isArray(error.detail) && error.detail.length > 0) {
    return error.detail[0].msg
  }
  return error.message
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

  const response = await fetch(apiUrl(path), { ...init, headers })

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

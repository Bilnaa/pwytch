import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import { api, clearToken, getToken, setToken } from '@/lib/api'

export interface User {
  id: number
  username: string
  display_name: string
  role: string
}

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
}

// Logged in user, shared by the whole app (header, pages that need a user)
const AuthContext = createContext<AuthContextValue>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  // true while /auth/me loads, so the header doesn't flash "Log in" on refresh
  const [loading, setLoading] = useState(getToken() !== null)

  useEffect(() => {
    // the token is in localStorage, but we still need the user behind it
    if (!getToken()) {
      return
    }
    api<User>('/auth/me')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  async function login(username: string, password: string) {
    // main uses OAuth2PasswordRequestForm, so it's a form body and not JSON
    const body = new URLSearchParams({ username, password })
    const data = await api<{ access_token: string }>('/auth/login', { method: 'POST', body })
    setToken(data.access_token)
    setUser(await api<User>('/auth/me'))
  }

  async function register(username: string, password: string) {
    await api('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    // register doesn't return a token, log in right after
    await login(username, password)
  }

  function logout() {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

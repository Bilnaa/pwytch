import { Navigate, Outlet } from 'react-router'

import { useAuth } from '@/lib/auth'

// Wraps the routes that need a logged in user
export function RequireAuth() {
  const { user, loading } = useAuth()

  // wait for /auth/me, otherwise a refresh would always go to /login
  if (loading) {
    return null
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

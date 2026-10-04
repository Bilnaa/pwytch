import { useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router'

import { AuthForm } from '@/components/auth-form'
import { FormField } from '@/components/form-field'
import { useAuth } from '@/lib/auth'

export function LoginPage() {
  const { user, login } = useAuth()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // already logged in, or just logged in with the form. Back to the page that
  // sent us here (the chat of a live), else home
  if (user) {
    return <Navigate to={location.state?.from ?? '/'} replace />
  }

  return (
    <AuthForm
      title="Log in"
      submitLabel="Log in"
      onSubmit={() => login(username, password)}
      footer={
        <>
          No account yet?{' '}
          <Link to="/register" className="text-primary hover:underline">
            Sign up
          </Link>
        </>
      }
    >
      <FormField
        id="username"
        label="Username"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <FormField
        id="password"
        label="Password"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
    </AuthForm>
  )
}

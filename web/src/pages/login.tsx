import { useState } from 'react'
import { Link, Navigate } from 'react-router'

import { AuthForm } from '@/components/auth-form'
import { FormField } from '@/components/form-field'
import { useAuth } from '@/lib/auth'

export function LoginPage() {
  const { user, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  // already logged in, or just logged in with the form
  if (user) {
    return <Navigate to="/" replace />
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

import { useState } from 'react'
import { Link, Navigate } from 'react-router'

import { AuthForm } from '@/components/auth-form'
import { FormField } from '@/components/form-field'
import { useAuth } from '@/lib/auth'

export function RegisterPage() {
  const { user, register } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  if (user) {
    return <Navigate to="/" replace />
  }

  // pattern and minLength are the same rules as RegisterRequest in main,
  // so most errors are caught before calling the API
  return (
    <AuthForm
      title="Sign up"
      submitLabel="Sign up"
      onSubmit={() => register(username, password)}
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="text-primary hover:underline">
            Log in
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
        pattern="[a-zA-Z0-9_]{3,30}"
        title="3 to 30 letters, digits or _"
      />
      <FormField
        id="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        hint="At least 8 characters"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={8}
      />
    </AuthForm>
  )
}

import { useState, type FormEvent, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { errorMessage } from '@/lib/api'

type AuthFormProps = {
  title: string
  submitLabel: string
  onSubmit: () => Promise<void>
  // link to the other page (login <-> register)
  footer: ReactNode
  children: ReactNode
}

// Card shared by the login and register pages, the fields are passed as children
export function AuthForm({ title, submitLabel, onSubmit, footer, children }: AuthFormProps) {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onSubmit()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="mx-auto mt-10 max-w-sm">
      <CardHeader>
        <CardTitle className="text-xl">{title}</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {children}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
        <CardFooter className="mt-6 flex-col gap-3">
          <Button type="submit" className="w-full" disabled={loading}>
            {submitLabel}
          </Button>
          <p className="text-sm text-muted-foreground">{footer}</p>
        </CardFooter>
      </form>
    </Card>
  )
}

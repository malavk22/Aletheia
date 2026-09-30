import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { login, register } from '../api/auth.ts'
import type { Credentials } from '../api/auth.ts'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { AuthLayout } from '../components/AuthLayout.tsx'
import { Button } from '../components/Button.tsx'
import { FormError } from '../components/FormError.tsx'
import { TextField } from '../components/TextField.tsx'
import { currentUserKey } from '../hooks/useCurrentUser.ts'

const MIN_PASSWORD_LENGTH = 8

// What to show under the email field for an error the backend sent back.
function emailErrorFor(error: unknown) {
  if (!(error instanceof ApiError)) return undefined
  if (error.status === 409) return 'An account with this email already exists.'
  if (error.status === 422) return 'Enter a valid email address.'
  return undefined
}

export function RegisterPage() {
  const queryClient = useQueryClient()
  const [passwordError, setPasswordError] = useState<string>()
  const mutation = useMutation({
    // The register endpoint does not sign you in, so we log in straight after
    // with the same details.
    mutationFn: async (credentials: Credentials) => {
      await register(credentials)
      return login(credentials)
    },
    onSuccess: (user) => queryClient.setQueryData(currentUserKey, user),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const password = String(form.get('password'))

    if (password.length < MIN_PASSWORD_LENGTH) {
      setPasswordError(`Use at least ${MIN_PASSWORD_LENGTH} characters.`)
      return
    }
    setPasswordError(undefined)
    mutation.mutate({ email: String(form.get('email')), password })
  }

  const emailError = emailErrorFor(mutation.error)

  return (
    <AuthLayout title="Create your account" intro="You only need an email and a password.">
      <form className="space-y-5" onSubmit={handleSubmit}>
        {mutation.isError && !emailError && <FormError>{UNREACHABLE_MESSAGE}</FormError>}
        <TextField
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          required
          error={emailError}
        />
        <TextField
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          maxLength={128}
          hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}
          error={passwordError}
        />
        <Button type="submit" className="w-full" loading={mutation.isPending}>
          Create account
        </Button>
      </form>
      <p className="mt-6 text-sm text-ink-muted">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-accent underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}

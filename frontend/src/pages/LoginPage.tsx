import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { login } from '../api/auth.ts'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { AuthLayout } from '../components/AuthLayout.tsx'
import { Button } from '../components/Button.tsx'
import { FormError } from '../components/FormError.tsx'
import { PasswordField } from '../components/PasswordField.tsx'
import { TextField } from '../components/TextField.tsx'
import { currentUserKey } from '../hooks/useCurrentUser.ts'

export function LoginPage() {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: login,
    // Storing the user is what signs the page in: the route guard sees a user
    // and moves on to the app.
    onSuccess: (user) => queryClient.setQueryData(currentUserKey, user),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    mutation.mutate({
      email: String(form.get('email')),
      password: String(form.get('password')),
    })
  }

  const error = mutation.error
  // 401: wrong details. 429: too many failed attempts; the message says when
  // to try again. Anything else: the server could not be reached.
  const errorMessage =
    error instanceof ApiError && error.status === 401
      ? 'Invalid email or password.'
      : error instanceof ApiError && error.status === 429
        ? error.message
        : UNREACHABLE_MESSAGE

  return (
    <AuthLayout title="Sign in" intro="Use the email you registered with.">
      <form className="space-y-5" onSubmit={handleSubmit}>
        {mutation.isError && (
          <FormError>{errorMessage}</FormError>
        )}
        <TextField label="Email" name="email" type="email" autoComplete="email" required />
        <PasswordField label="Password" name="password" autoComplete="current-password" required />
        <Button type="submit" className="w-full" loading={mutation.isPending}>
          Sign in
        </Button>
      </form>
      <p className="mt-6 text-sm text-ink-muted">
        New to Aletheia?{' '}
        <Link to="/register" className="font-medium text-accent underline underline-offset-4">
          Create an account
        </Link>
      </p>
    </AuthLayout>
  )
}

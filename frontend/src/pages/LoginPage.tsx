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

  const isWrongCredentials = mutation.error instanceof ApiError && mutation.error.status === 401

  return (
    <AuthLayout title="Sign in" intro="Use the email you registered with.">
      <form className="space-y-5" onSubmit={handleSubmit}>
        {mutation.isError && (
          <FormError>
            {isWrongCredentials ? 'Invalid email or password.' : UNREACHABLE_MESSAGE}
          </FormError>
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

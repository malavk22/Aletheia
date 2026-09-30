import { Navigate, Outlet } from 'react-router'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { useCurrentUser } from '../hooks/useCurrentUser.ts'
import { Button } from './Button.tsx'

// These guards are for convenience only: they decide which page to show.
// The real protection is the backend, which rejects requests with no session.

// Pages for signed-in people. Signed out -> go to the sign-in page.
export function RequireAuth() {
  const { data: user, isPending, isError, refetch } = useCurrentUser()

  // Show nothing while we wait, so the wrong page never flashes on screen.
  if (isPending) return null
  if (isError) return <ServerUnreachable onRetry={() => refetch()} />
  return user ? <Outlet /> : <Navigate to="/login" replace />
}

// Pages for signed-out people (sign in, register). Signed in -> go to the app.
export function GuestOnly() {
  const { data: user, isPending, isError, refetch } = useCurrentUser()

  if (isPending) return null
  if (isError) return <ServerUnreachable onRetry={() => refetch()} />
  return user ? <Navigate to="/" replace /> : <Outlet />
}

// We could not find out whether you are signed in, so say so rather than guess.
function ServerUnreachable({ onRetry }: { onRetry: () => void }) {
  return (
    <main className="px-6 py-12 sm:px-12">
      <h1 className="font-serif text-3xl font-semibold tracking-tight">Aletheia</h1>
      <p role="alert" className="mt-2 mb-6 text-sm text-ink-muted">
        {UNREACHABLE_MESSAGE}
      </p>
      <Button variant="secondary" onClick={onRetry}>
        Try again
      </Button>
    </main>
  )
}

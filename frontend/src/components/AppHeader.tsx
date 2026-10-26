import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router'
import { logout } from '../api/auth.ts'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { clearSession, useCurrentUser } from '../hooks/useCurrentUser.ts'
import { Button } from './Button.tsx'

// The header on every signed-in page: wordmark, the person's email, Log out.
export function AppHeader() {
  const { data: user } = useCurrentUser()
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: logout,
    onSuccess: () => clearSession(queryClient),
  })

  return (
    // Stays at the top while the page scrolls, over a lightly blurred page.
    <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-line bg-paper/85 px-6 py-3 backdrop-blur sm:px-12">
      <Link to="/" className="font-display text-2xl font-medium tracking-tight">
        Aletheia
      </Link>
      <div className="flex items-center gap-4">
        {mutation.isError && <span className="text-sm text-danger">{UNREACHABLE_MESSAGE}</span>}
        <span className="hidden text-sm text-ink-muted sm:inline">{user?.email}</span>
        <Button variant="ghost" loading={mutation.isPending} onClick={() => mutation.mutate()}>
          Log out
        </Button>
      </div>
    </header>
  )
}

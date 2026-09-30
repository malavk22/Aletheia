import { useMutation, useQueryClient } from '@tanstack/react-query'
import { logout } from '../api/auth.ts'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { Button } from '../components/Button.tsx'
import { currentUserKey, useCurrentUser } from '../hooks/useCurrentUser.ts'

// The signed-in page. Deliberately bare for now: the workspace list replaces
// the placeholder text in the next step.
export function AppPage() {
  const { data: user } = useCurrentUser()
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: logout,
    // Clearing the user is what signs the page out: the route guard sees no
    // user and goes to the sign-in page.
    onSuccess: () => queryClient.setQueryData(currentUserKey, null),
  })

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between gap-4 border-b border-line px-6 py-3 sm:px-12">
        <p className="font-display text-2xl font-medium tracking-tight">Aletheia</p>
        <div className="flex items-center gap-4">
          {mutation.isError && <span className="text-sm text-danger">{UNREACHABLE_MESSAGE}</span>}
          <span className="text-sm text-ink-muted">{user?.email}</span>
          <Button variant="secondary" loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Log out
          </Button>
        </div>
      </header>
      <main className="px-6 py-12 sm:px-12">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">Workspaces</h1>
        <p className="mt-2 text-sm text-ink-muted">Your workspaces will appear here.</p>
      </main>
    </div>
  )
}

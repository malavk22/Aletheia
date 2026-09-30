import { useQuery } from '@tanstack/react-query'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { listWorkspaces, workspacesKey } from '../api/workspaces.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'

export function WorkspaceList() {
  const {
    data: workspaces,
    isPending,
    isError,
    refetch,
  } = useQuery({ queryKey: workspacesKey, queryFn: listWorkspaces })

  if (isPending) return <p className="text-sm text-ink-muted">Loading workspaces…</p>

  return (
    <div className="space-y-4">
      {isError && (
        <div className="space-y-3">
          <FormError>{UNREACHABLE_MESSAGE}</FormError>
          <Button variant="secondary" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      )}
      {/* After a failed refresh the last list we got is still shown. */}
      {workspaces?.length === 0 && (
        <p className="border-t border-line pt-4 text-sm text-ink-muted">
          No workspaces yet. Create your first one above.
        </p>
      )}
      {workspaces && workspaces.length > 0 && (
        <ul className="divide-y divide-line border-y border-line">
          {workspaces.map((workspace) => (
            <li key={workspace.id} className="py-3 text-sm font-medium">
              {workspace.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

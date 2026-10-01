import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { listWorkspaces, workspacesKey } from '../api/workspaces.ts'
import type { Workspace } from '../api/workspaces.ts'
import { Button } from './Button.tsx'
import { ConfirmDeleteWorkspace } from './ConfirmDeleteWorkspace.tsx'
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
            <WorkspaceRow key={workspace.id} workspace={workspace} />
          ))}
        </ul>
      )}
    </div>
  )
}

function WorkspaceRow({ workspace }: { workspace: Workspace }) {
  const [confirming, setConfirming] = useState(false)

  return (
    <li>
      <div className="flex items-center gap-2">
        <Link
          to={`/workspaces/${workspace.id}`}
          className="min-w-0 flex-1 truncate py-3 text-sm font-medium hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
        >
          {workspace.name}
        </Link>
        <button
          type="button"
          aria-label={`Delete ${workspace.name}`}
          title="Delete workspace"
          aria-expanded={confirming}
          onClick={() => setConfirming(!confirming)}
          className="rounded-sm p-2 text-ink-muted hover:text-danger focus-visible:outline-2 focus-visible:outline-accent"
        >
          <TrashIcon />
        </button>
      </div>
      {/* No onDeleted needed here: the list refreshes and this row goes away. */}
      {confirming && (
        <div className="pb-4">
          <ConfirmDeleteWorkspace workspace={workspace} onCancel={() => setConfirming(false)} />
        </div>
      )}
    </li>
  )
}

// A plain outline trash can, drawn inline so no icon library is needed.
function TrashIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4"
    >
      <path d="M3.5 5.5h13M8 5.5V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1.5M5 5.5l.8 10.1a1.5 1.5 0 0 0 1.5 1.4h5.4a1.5 1.5 0 0 0 1.5-1.4L15 5.5M8.5 9v5M11.5 9v5" />
    </svg>
  )
}

import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { Workspace } from '../api/workspaces.ts'
import { Button } from './Button.tsx'
import { ConfirmDeleteWorkspace } from './ConfirmDeleteWorkspace.tsx'

// The "Delete workspace" section at the bottom of a workspace's own page.
export function DeleteWorkspace({ workspace }: { workspace: Workspace }) {
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)

  return (
    <section className="max-w-3xl border-t border-line pt-8">
      <h2 className="text-sm font-semibold">Delete workspace</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Permanently deletes this workspace and every document in it. This cannot be undone.
      </p>
      <div className="mt-4">
        {confirming ? (
          <ConfirmDeleteWorkspace
            workspace={workspace}
            onCancel={() => setConfirming(false)}
            // The page being shown no longer exists, so go back to the list.
            onDeleted={() => navigate('/', { replace: true })}
          />
        ) : (
          <Button variant="secondary" onClick={() => setConfirming(true)}>
            Delete workspace
          </Button>
        )}
      </div>
    </section>
  )
}

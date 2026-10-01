import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { deleteWorkspace, workspacesKey } from '../api/workspaces.ts'
import type { Workspace } from '../api/workspaces.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'
import { TextField } from './TextField.tsx'

type ConfirmDeleteWorkspaceProps = {
  workspace: Workspace
  onCancel: () => void
  onDeleted?: () => void
}

// The confirmation for deleting a workspace, used on the Workspaces list and on
// the workspace's own page. Deleting removes every document in it, so the
// person must type the workspace's exact name before the button works.
export function ConfirmDeleteWorkspace({
  workspace,
  onCancel,
  onDeleted,
}: ConfirmDeleteWorkspaceProps) {
  const queryClient = useQueryClient()
  const [typedName, setTypedName] = useState('')
  const mutation = useMutation({
    mutationFn: () => deleteWorkspace(workspace.id),
    onSuccess: () => {
      // exact: only the list. The deleted workspace's own data is left alone
      // so an open workspace page does not re-ask for it (and get a 404).
      queryClient.invalidateQueries({ queryKey: workspacesKey, exact: true })
      onDeleted?.()
    },
  })

  const nameMatches = typedName === workspace.name

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (nameMatches) mutation.mutate()
  }

  // The backend's 403 message ("Only the owner can delete this workspace")
  // is written for people, so show it as-is.
  const errorMessage =
    mutation.error instanceof ApiError && mutation.error.status === 403
      ? `${mutation.error.message}.`
      : UNREACHABLE_MESSAGE

  return (
    <form className="max-w-sm space-y-4" onSubmit={handleSubmit}>
      {mutation.isError && <FormError>{errorMessage}</FormError>}
      <TextField
        label={`Type "${workspace.name}" to confirm`}
        name="confirm-name"
        autoComplete="off"
        autoFocus
        value={typedName}
        onChange={(event) => setTypedName(event.target.value)}
      />
      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="danger" disabled={!nameMatches} loading={mutation.isPending}>
          Delete permanently
        </Button>
        <Button variant="secondary" disabled={mutation.isPending} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

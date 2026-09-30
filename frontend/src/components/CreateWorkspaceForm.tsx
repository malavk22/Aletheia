import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { createWorkspace, workspacesKey } from '../api/workspaces.ts'
import { Button } from './Button.tsx'
import { TextField } from './TextField.tsx'

export function CreateWorkspaceForm() {
  const queryClient = useQueryClient()
  const [nameError, setNameError] = useState<string>()
  const mutation = useMutation({
    mutationFn: createWorkspace,
    // The list on screen is now out of date, so ask the server for it again.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: workspacesKey }),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const name = String(new FormData(form).get('name')).trim()

    if (!name) {
      setNameError('Enter a name for the workspace.')
      return
    }
    setNameError(undefined)
    mutation.mutate(name, { onSuccess: () => form.reset() })
  }

  return (
    <form className="flex flex-wrap items-start gap-3" onSubmit={handleSubmit}>
      <div className="w-full max-w-sm">
        <TextField
          label="New workspace"
          name="name"
          placeholder="e.g. Supplier contracts"
          maxLength={100}
          error={nameError ?? (mutation.isError ? UNREACHABLE_MESSAGE : undefined)}
        />
      </div>
      {/* mt-6.5 = the height of the field's label, so the button lines up with
          the input and stays put when an error appears under the field. */}
      <Button type="submit" className="mt-6.5" loading={mutation.isPending}>
        Create workspace
      </Button>
    </form>
  )
}

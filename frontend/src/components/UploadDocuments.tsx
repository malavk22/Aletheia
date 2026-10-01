import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentsKey, uploadDocument } from '../api/documents.ts'
import { Button } from './Button.tsx'

type UploadResult = {
  filename: string
  error?: string
}

// Our own API's messages for these are written for people, so show them as-is.
function uploadErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 413 || error.status === 415)) {
    return error.message
  }
  return UNREACHABLE_MESSAGE
}

export function UploadDocuments({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [results, setResults] = useState<UploadResult[]>([])
  const mutation = useMutation({
    mutationFn: (file: File) => uploadDocument(workspaceId, file),
    // Refresh the list after each file, so documents appear as they finish.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentsKey(workspaceId) }),
  })

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget
    const files = Array.from(input.files ?? [])
    setResults([])

    // One request per file, one after another, so each gets its own result.
    for (const file of files) {
      try {
        await mutation.mutateAsync(file)
        setResults((previous) => [...previous, { filename: file.name }])
      } catch (error) {
        setResults((previous) => [
          ...previous,
          { filename: file.name, error: uploadErrorMessage(error) },
        ])
      }
    }
    // Clear the picker so choosing the same file again still triggers a change.
    input.value = ''
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4">
        <Button loading={mutation.isPending} onClick={() => inputRef.current?.click()}>
          Upload files
        </Button>
        <p className="text-sm text-ink-muted">PDF or DOCX, up to 20 MB each.</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          multiple
          hidden
          onChange={handleFiles}
        />
      </div>
      {results.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm" aria-live="polite">
          {results.map((result, index) => (
            <li key={index} className={result.error ? 'text-danger' : 'text-ink-muted'}>
              <span className="font-medium">{result.filename}</span>
              {' — '}
              {result.error ?? 'uploaded'}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

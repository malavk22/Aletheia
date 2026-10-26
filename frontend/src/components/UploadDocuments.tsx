import { useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentsKey, uploadDocument } from '../api/documents.ts'
import { Button } from './Button.tsx'

// The file being sent now, and how much of it (0 to 1).
type Progress = {
  filename: string
  number: number
  total: number
  fraction: number
}

type FailedUpload = {
  filename: string
  error: string
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
  // Only failures are listed here. A successful upload shows up in the
  // document list itself, so a separate "uploaded" line would only go stale
  // (for example after that document is deleted).
  const [failures, setFailures] = useState<FailedUpload[]>([])
  const [progress, setProgress] = useState<Progress | null>(null)
  const mutation = useMutation({
    mutationFn: (file: File) =>
      uploadDocument(workspaceId, file, (fraction) =>
        setProgress((current) => current && { ...current, fraction }),
      ),
    // Refresh the list after each file, so documents appear as they finish.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentsKey(workspaceId) }),
  })

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget
    const files = Array.from(input.files ?? [])
    setFailures([])

    // One request per file, one after another, so each gets its own result.
    for (const [index, file] of files.entries()) {
      setProgress({ filename: file.name, number: index + 1, total: files.length, fraction: 0 })
      try {
        await mutation.mutateAsync(file)
      } catch (error) {
        setFailures((previous) => [
          ...previous,
          { filename: file.name, error: uploadErrorMessage(error) },
        ])
      }
    }
    setProgress(null)
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
      {progress && (
        <div className="mt-4 max-w-md">
          <p className="flex justify-between gap-4 text-sm text-ink-muted">
            <span className="truncate">
              Uploading <span className="font-medium text-ink">{progress.filename}</span>
              {progress.total > 1 && ` (${progress.number} of ${progress.total})`}
            </span>
            <span className="tabular-nums">{Math.round(progress.fraction * 100)}%</span>
          </p>
          <div
            role="progressbar"
            aria-label={`Uploading ${progress.filename}`}
            aria-valuenow={Math.round(progress.fraction * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line"
          >
            {/* A key per file: the next file starts a fresh bar at 0
                instead of the last one shrinking back. */}
            <motion.div
              key={progress.number}
              className="h-full rounded-full bg-accent"
              initial={false}
              animate={{ width: `${progress.fraction * 100}%` }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
            />
          </div>
        </div>
      )}
      {failures.length > 0 && (
        <div role="alert" className="mt-4 border-l-2 border-danger bg-danger-soft px-3 py-2">
          <p className="text-sm font-medium text-danger">
            {failures.length === 1 ? 'This file was not uploaded:' : 'These files were not uploaded:'}
          </p>
          <ul className="mt-1 space-y-0.5 text-sm text-danger">
            {failures.map((failure, index) => (
              <li key={index}>
                <span className="font-medium">{failure.filename}</span> — {failure.error}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => setFailures([])}
            className="mt-2 rounded-sm text-sm font-medium text-danger underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}

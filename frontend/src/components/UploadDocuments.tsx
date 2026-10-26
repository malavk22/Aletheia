import { motion } from 'motion/react'
import { useRef } from 'react'
import type { ChangeEvent } from 'react'
import type { Uploads } from '../hooks/useUploads.ts'
import { Button } from './Button.tsx'

// The Upload button, the progress of the file being sent, and the files that
// failed. The uploading itself is in useUploads, shared with dropping files on
// the workspace page.
export function UploadDocuments({ uploads }: { uploads: Uploads }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const { progress, failures } = uploads

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget
    await uploads.upload(Array.from(input.files ?? []))
    // Clear the picker so choosing the same file again still triggers a change.
    input.value = ''
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4">
        <Button loading={progress !== null} onClick={() => inputRef.current?.click()}>
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
            onClick={uploads.dismissFailures}
            className="mt-2 rounded-sm text-sm font-medium text-danger underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-accent"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}

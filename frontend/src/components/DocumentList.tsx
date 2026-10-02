import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { deleteDocument, documentsKey, listDocuments } from '../api/documents.ts'
import type { WorkspaceDocument } from '../api/documents.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'

const TYPE_LABELS: Record<string, string> = {
  'application/pdf': 'PDF',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(isoDate: string) {
  return new Date(isoDate).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function DocumentList({ workspaceId }: { workspaceId: string }) {
  const {
    data: documents,
    isPending,
    isError,
    refetch,
  } = useQuery({ queryKey: documentsKey(workspaceId), queryFn: () => listDocuments(workspaceId) })

  if (isPending) return <p className="text-sm text-ink-muted">Loading documents…</p>

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
      {documents?.length === 0 && (
        <p className="border-t border-line pt-4 text-sm text-ink-muted">
          No documents yet. Upload your first one above.
        </p>
      )}
      {documents && documents.length > 0 && (
        <ul className="divide-y divide-line border-y border-line">
          {documents.map((document) => (
            <DocumentRow key={document.id} workspaceId={workspaceId} document={document} />
          ))}
        </ul>
      )}
    </div>
  )
}

// Whether the document's text has been extracted yet.
function DocumentStatus({ document }: { document: WorkspaceDocument }) {
  if (document.status === 'ready') {
    // A PDF is stored page by page; a Word file has no fixed pages, so it is
    // stored section by section (split at its headings).
    const unit = document.content_type === 'application/pdf' ? 'page' : 'section'
    const count = document.part_count ?? 0
    return (
      <p className="mt-0.5 text-sm text-ink-muted">
        Text extracted · {count} {count === 1 ? unit : `${unit}s`}
      </p>
    )
  }
  if (document.status === 'failed') {
    return (
      <p className="mt-0.5 text-sm text-danger">Text not extracted: {document.error}</p>
    )
  }
  return <p className="mt-0.5 text-sm text-ink-muted">Waiting for text extraction</p>
}

function DocumentRow({
  workspaceId,
  document,
}: {
  workspaceId: string
  document: WorkspaceDocument
}) {
  const queryClient = useQueryClient()
  // Deleting takes two clicks: "Delete", then "Confirm delete".
  const [confirming, setConfirming] = useState(false)
  const mutation = useMutation({
    mutationFn: () => deleteDocument(workspaceId, document.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentsKey(workspaceId) }),
  })

  const textButton =
    'rounded-sm px-2 py-1 text-sm font-medium focus-visible:outline-2 focus-visible:outline-accent'

  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{document.filename}</p>
        <p className="mt-0.5 text-sm text-ink-muted">
          {TYPE_LABELS[document.content_type] ?? 'File'} · {formatSize(document.size_bytes)} ·{' '}
          {formatDate(document.created_at)}
        </p>
        <DocumentStatus document={document} />
        {mutation.isError && <p className="mt-0.5 text-sm text-danger">{UNREACHABLE_MESSAGE}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {confirming ? (
          <>
            <button
              type="button"
              className={`${textButton} text-danger hover:underline`}
              disabled={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? 'Deleting…' : 'Confirm delete'}
            </button>
            <button
              type="button"
              className={`${textButton} text-ink-muted hover:text-ink`}
              disabled={mutation.isPending}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            className={`${textButton} text-ink-muted hover:text-danger`}
            aria-label={`Delete ${document.filename}`}
            onClick={() => setConfirming(true)}
          >
            Delete
          </button>
        )}
      </div>
    </li>
  )
}

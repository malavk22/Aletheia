import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import {
  documentFileUrl,
  documentKey,
  getDocument,
  listParts,
} from '../api/documents.ts'
import type { DocumentPart, WorkspaceDocument } from '../api/documents.ts'
import { getWorkspace, workspaceKey } from '../api/workspaces.ts'
import { AppHeader } from '../components/AppHeader.tsx'
import { Button } from '../components/Button.tsx'
import { DocumentDetails } from '../components/DocumentDetails.tsx'
import { FormError } from '../components/FormError.tsx'

// 404: not a member, no such document, or it belongs to another workspace
// (the backend does not say which). 422: the address has no valid id.
function isNotFound(error: unknown) {
  return error instanceof ApiError && (error.status === 404 || error.status === 422)
}

// One document: its details, a way to open the original, and the text
// Aletheia extracted from it, so the two can be compared.
// The ids come from the address, /workspaces/<id>/documents/<id>.
export function DocumentPage() {
  const { workspaceId = '', documentId = '' } = useParams()
  const workspace = useQuery({
    queryKey: workspaceKey(workspaceId),
    queryFn: () => getWorkspace(workspaceId),
  })
  const document = useQuery({
    queryKey: documentKey(workspaceId, documentId),
    queryFn: () => getDocument(workspaceId, documentId),
  })

  const notFound = isNotFound(document.error) || isNotFound(workspace.error)

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="px-6 py-12 sm:px-12">
        <Link to={`/workspaces/${workspaceId}`} className="text-sm text-ink-muted hover:text-ink">
          ← {workspace.data?.name ?? 'Back to workspace'}
        </Link>

        {document.isPending && !notFound && (
          <p className="mt-6 text-sm text-ink-muted">Loading document…</p>
        )}

        {notFound && (
          <div className="mt-6">
            <h1 className="font-serif text-3xl font-semibold tracking-tight">Document not found</h1>
            <p className="mt-2 text-sm text-ink-muted">
              It may have been deleted, or you may not have access to it.
            </p>
          </div>
        )}

        {document.isError && !notFound && (
          <div className="mt-6 max-w-2xl space-y-3">
            <FormError>{UNREACHABLE_MESSAGE}</FormError>
            <Button variant="secondary" onClick={() => document.refetch()}>
              Try again
            </Button>
          </div>
        )}

        {document.data && !notFound && (
          <>
            <h1 className="mt-4 font-serif text-3xl font-semibold tracking-tight break-words">
              {document.data.filename}
            </h1>
            <DocumentDetails document={document.data} />
            <OpenOriginal workspaceId={workspaceId} document={document.data} />
            <ExtractedText workspaceId={workspaceId} document={document.data} />
          </>
        )}
      </main>
    </div>
  )
}

function OpenOriginal({
  workspaceId,
  document,
}: {
  workspaceId: string
  document: WorkspaceDocument
}) {
  const isPdf = document.content_type === 'application/pdf'
  // A link, not a fetch: the browser opens a PDF in a new tab and downloads
  // a Word file (the backend tells it which), sending the session cookie.
  return (
    <a
      href={documentFileUrl(workspaceId, document.id)}
      target={isPdf ? '_blank' : undefined}
      rel={isPdf ? 'noopener' : undefined}
      className="mt-5 inline-flex h-10 items-center rounded-sm border border-line-strong bg-surface px-4 text-sm font-medium hover:bg-paper-deep focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    >
      {isPdf ? 'Open original PDF' : 'Download original'}
    </a>
  )
}

function ExtractedText({
  workspaceId,
  document,
}: {
  workspaceId: string
  document: WorkspaceDocument
}) {
  const isReady = document.status === 'ready'
  const parts = useQuery({
    queryKey: [...documentKey(workspaceId, document.id), 'parts'],
    queryFn: () => listParts(workspaceId, document.id),
    enabled: isReady,
  })

  return (
    <section className="mt-12 max-w-3xl border-t border-line pt-8">
      <h2 className="text-sm font-semibold">Extracted text</h2>

      {!isReady && (
        <p className="mt-1 text-sm text-ink-muted">
          {document.status === 'failed'
            ? 'No text could be extracted from this file, so there is nothing to show.'
            : 'Text has not been extracted from this file yet.'}
        </p>
      )}

      {isReady && (
        <p className="mt-1 text-sm text-ink-muted">
          The text Aletheia read from the file. Compare it with the original to check it.
        </p>
      )}

      {isReady && parts.isPending && (
        <p className="mt-6 text-sm text-ink-muted">Loading text…</p>
      )}

      {parts.isError && (
        <div className="mt-6 space-y-3">
          <FormError>{UNREACHABLE_MESSAGE}</FormError>
          <Button variant="secondary" onClick={() => parts.refetch()}>
            Try again
          </Button>
        </div>
      )}

      {parts.data && (
        <ol className="mt-6 space-y-8">
          {parts.data.map((part) => (
            // The id lets later features (citations) link straight to a part.
            <li key={part.position} id={`part-${part.position}`}>
              <PartLabel part={part} />
              {part.text.trim() ? (
                // Evidence is shown in a quiet box so it stands apart from the
                // app's own words. Line breaks are kept as extracted.
                // Blank lines at the very start and end are trimmed for display
                // only; the stored text is unchanged.
                <p className="mt-2 rounded-sm border border-line bg-surface px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
                  {part.text.trim()}
                </p>
              ) : (
                <p className="mt-2 text-sm text-ink-muted italic">No text on this page.</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

// Where the part is: "Page 3" for a PDF, the section heading for a Word file.
function PartLabel({ part }: { part: DocumentPart }) {
  if (part.page_number !== null) {
    return (
      <p className="text-xs font-medium tracking-wide text-ink-muted uppercase">
        Page {part.page_number}
      </p>
    )
  }
  if (part.heading) {
    return <h3 className="font-serif text-lg font-semibold tracking-tight">{part.heading}</h3>
  }
  return (
    <p className="text-xs font-medium tracking-wide text-ink-muted uppercase">
      Before the first heading
    </p>
  )
}

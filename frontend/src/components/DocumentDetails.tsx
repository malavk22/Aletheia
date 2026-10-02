import type { WorkspaceDocument } from '../api/documents.ts'

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

// "PDF · 1.4 MB · Oct 2, 2026, 11:38 AM", then whether its text was extracted.
// Used in the document list and on the document's own page.
export function DocumentDetails({ document }: { document: WorkspaceDocument }) {
  return (
    <>
      <p className="mt-0.5 text-sm text-ink-muted">
        {TYPE_LABELS[document.content_type] ?? 'File'} · {formatSize(document.size_bytes)} ·{' '}
        {formatDate(document.created_at)}
      </p>
      <DocumentStatus document={document} />
    </>
  )
}

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
    return <p className="mt-0.5 text-sm text-danger">Text not extracted: {document.error}</p>
  }
  return <p className="mt-0.5 text-sm text-ink-muted">Waiting for text extraction</p>
}

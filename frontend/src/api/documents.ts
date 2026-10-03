import { api } from './client.ts'

// Named WorkspaceDocument because "Document" is already the browser's own type
// for the web page.
export type WorkspaceDocument = {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  // processing: text being extracted in the background; ready: done;
  // failed: see `error`. (pending: older uploads that were never processed.)
  status: 'pending' | 'processing' | 'ready' | 'failed'
  error: string | null
  // How many parts the text was stored in: pages for a PDF, sections for a DOCX.
  part_count: number | null
  // How many of those parts were read by OCR (scanned pages).
  ocr_part_count: number | null
  created_at: string
}

export function documentsKey(workspaceId: string) {
  return ['workspaces', workspaceId, 'documents']
}

function documentsPath(workspaceId: string) {
  return `/workspaces/${workspaceId}/documents`
}

export function listDocuments(workspaceId: string) {
  return api<WorkspaceDocument[]>(documentsPath(workspaceId))
}

export function uploadDocument(workspaceId: string, file: File) {
  const form = new FormData()
  form.append('file', file)
  return api<WorkspaceDocument>(documentsPath(workspaceId), { method: 'POST', body: form })
}

export function deleteDocument(workspaceId: string, documentId: string) {
  return api<void>(`${documentsPath(workspaceId)}/${documentId}`, { method: 'DELETE' })
}

// The original file. A plain link to this opens a PDF in the browser and
// downloads a Word file; the session cookie is sent with it automatically.
export function documentFileUrl(workspaceId: string, documentId: string) {
  return `/api/v1${documentsPath(workspaceId)}/${documentId}/file`
}

import { api } from './client.ts'

// Named WorkspaceDocument because "Document" is already the browser's own type
// for the web page.
export type WorkspaceDocument = {
  id: string
  filename: string
  content_type: string
  size_bytes: number
  // pending: not processed yet; ready: text extracted; failed: see `error`.
  status: 'pending' | 'ready' | 'failed'
  error: string | null
  // How many parts the text was stored in: pages for a PDF, sections for a DOCX.
  part_count: number | null
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

export type DocumentPart = {
  position: number
  // Where the text is: a page number (PDF) or the heading above it (DOCX).
  page_number: number | null
  heading: string | null
  text: string
}

export function documentKey(workspaceId: string, documentId: string) {
  return ['workspaces', workspaceId, 'documents', documentId]
}

export function getDocument(workspaceId: string, documentId: string) {
  return api<WorkspaceDocument>(`${documentsPath(workspaceId)}/${documentId}`)
}

export function listParts(workspaceId: string, documentId: string) {
  return api<DocumentPart[]>(`${documentsPath(workspaceId)}/${documentId}/parts`)
}

// The original file. A plain link to this opens a PDF in the browser and
// downloads a Word file; the session cookie is sent with it automatically.
export function documentFileUrl(workspaceId: string, documentId: string) {
  return `/api/v1${documentsPath(workspaceId)}/${documentId}/file`
}

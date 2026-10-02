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
  page_count: number | null
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

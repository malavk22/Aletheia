import { ApiError, api } from './client.ts'

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
  // When key facts were last extracted; null if never.
  facts_extracted_at: string | null
  // When actions were last found; null if never.
  actions_extracted_at: string | null
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

// XMLHttpRequest, not fetch (api()): only it reports how much of the file has
// been sent, for the progress bar. Errors take the same shape as api()'s.
export function uploadDocument(
  workspaceId: string,
  file: File,
  onProgress: (fraction: number) => void,
) {
  const form = new FormData()
  form.append('file', file)
  return new Promise<WorkspaceDocument>((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `/api/v1${documentsPath(workspaceId)}`)
    request.responseType = 'json'
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    request.onload = () => {
      if (request.status >= 200 && request.status < 300) {
        resolve(request.response)
        return
      }
      const detail = request.response?.detail
      reject(new ApiError(request.status, typeof detail === 'string' ? detail : 'Request failed'))
    }
    // No response at all (server down, network lost): like a failed fetch.
    request.onerror = () => reject(new TypeError('Network error'))
    request.send(form)
  })
}

export function deleteDocument(workspaceId: string, documentId: string) {
  return api<void>(`${documentsPath(workspaceId)}/${documentId}`, { method: 'DELETE' })
}

// One page (PDF) or section (DOCX) of a document, in reading order.
export type DocumentPart = {
  position: number
  page_number: number | null
  heading: string | null
}

export function partsKey(workspaceId: string, documentId: string) {
  return ['workspaces', workspaceId, 'documents', documentId, 'parts']
}

export function listParts(workspaceId: string, documentId: string) {
  return api<DocumentPart[]>(`${documentsPath(workspaceId)}/${documentId}/parts`)
}

// The original file. A plain link to this opens a PDF in the browser and
// downloads a Word file; the session cookie is sent with it automatically.
export function documentFileUrl(workspaceId: string, documentId: string) {
  return `/api/v1${documentsPath(workspaceId)}/${documentId}/file`
}

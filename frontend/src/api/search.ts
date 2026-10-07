import { api } from './client.ts'

// semantic: by meaning; keyword: by the exact words.
export type SearchMode = 'semantic' | 'keyword'

export type SearchResult = {
  document_id: string
  filename: string
  chunk_position: number
  // Which page or section of the document (reading order, from 1).
  part_position: number
  // Where the text is: a page number (PDF) or the heading above it (DOCX).
  page_number: number | null
  heading: string | null
  // "text" (taken from the file, exact) or "ocr" (read from an image).
  source: 'text' | 'ocr'
  text: string
  score: number
}

export function searchKey(workspaceId: string, query: string, mode: SearchMode) {
  return ['workspaces', workspaceId, 'search', mode, query]
}

// More than are shown: overlapping chunks of one page often match together,
// and only the best one per page is shown (see SearchDocuments).
const FETCH_LIMIT = 10

export function searchWorkspace(workspaceId: string, query: string, mode: SearchMode) {
  const params = new URLSearchParams({ q: query, mode, limit: String(FETCH_LIMIT) })
  return api<SearchResult[]>(`/workspaces/${workspaceId}/search?${params}`)
}

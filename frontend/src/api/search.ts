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

// `documentIds`: only search these documents; null: all of the workspace's.
// Pages or sections of the one chosen document (positions, both included).
export type PartRange = { from: number; to: number }

export function searchKey(
  workspaceId: string,
  query: string,
  mode: SearchMode,
  documentIds: string[] | null,
  parts: PartRange | null,
) {
  return ['workspaces', workspaceId, 'search', mode, query, documentIds, parts]
}

// More than are shown: overlapping chunks of one page often match together,
// and only the best one per page is shown (see PassageResults).
const FETCH_LIMIT = 10

export function searchWorkspace(
  workspaceId: string,
  query: string,
  mode: SearchMode,
  documentIds: string[] | null,
  parts: PartRange | null,
) {
  const params = new URLSearchParams({ q: query, mode, limit: String(FETCH_LIMIT) })
  for (const id of documentIds ?? []) params.append('document_id', id)
  if (parts) {
    params.set('part_from', String(parts.from))
    params.set('part_to', String(parts.to))
  }
  return api<SearchResult[]>(`/workspaces/${workspaceId}/search?${params}`)
}

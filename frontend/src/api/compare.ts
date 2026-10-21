import { api } from './client.ts'

// changed: the words changed; formatting: only spacing, capitals or
// punctuation; removed / added: only in the old / new version.
export type ChangeKind = 'changed' | 'formatting' | 'removed' | 'added'

// A sentence and where it is in its version.
export type Sentence = {
  text: string
  part_position: number
  // A page number (PDF) or the heading above it (DOCX).
  page_number: number | null
  heading: string | null
}

export type Change = {
  kind: ChangeKind
  // null for "added".
  old: Sentence | null
  // null for "removed".
  new: Sentence | null
}

export type Comparison = {
  changes: Change[]
  counts: Record<ChangeKind, number>
}

export function comparisonKey(workspaceId: string, oldId: string, newId: string) {
  return ['workspaces', workspaceId, 'compare', oldId, newId]
}

// A local diff of the stored text: never calls the AI.
export function compareDocuments(workspaceId: string, oldId: string, newId: string) {
  const params = new URLSearchParams({ old: oldId, new: newId })
  return api<Comparison>(`/workspaces/${workspaceId}/compare?${params}`)
}

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

// One document's side of a potential conflict.
export type ConflictSide = {
  // What this document says, in a few words (Gemini's reading).
  claim: string
  // The document's own words, checked to be in its passage: the evidence.
  quote: string
  part_position: number
  page_number: number | null
  heading: string | null
}

export type Conflict = {
  topic: string
  // Why both can't be true: Gemini's reading, not evidence.
  explanation: string
  a: ConflictSide
  b: ConflictSide
}

export type Conflicts = {
  potential_conflicts: Conflict[]
  // How many passage pairs were checked, and how many of Gemini's answers
  // were dropped because a quote wasn't in its passage.
  checked_pairs: number
  dropped: number
}

// Sends the most alike passages of the two documents to Google Gemini.
export function checkConflicts(workspaceId: string, documentA: string, documentB: string) {
  return api<Conflicts>(`/workspaces/${workspaceId}/compare/conflicts`, {
    method: 'POST',
    body: { document_a: documentA, document_b: documentB },
  })
}

// A local diff of the stored text: never calls the AI.
export function compareDocuments(workspaceId: string, oldId: string, newId: string) {
  const params = new URLSearchParams({ old: oldId, new: newId })
  return api<Comparison>(`/workspaces/${workspaceId}/compare?${params}`)
}

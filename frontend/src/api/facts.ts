import { api } from './client.ts'

export type FactKind = 'person' | 'organization' | 'date' | 'amount' | 'requirement'

// A fact pulled out of a document, with the sentence it comes from and where.
export type Fact = {
  position: number
  kind: FactKind
  value: string
  // Dates only: YYYY-MM-DD, when the document gives a full date.
  normalized: string | null
  about: string | null
  // The document's own words. Only facts whose quote was found on their
  // page are stored.
  quote: string
  part_position: number
  page_number: number | null
  heading: string | null
  source: 'text' | 'ocr'
}

export type Facts = {
  // When facts were last extracted; null if never.
  extracted_at: string | null
  facts: Fact[]
  // After an extraction only: facts left out because their evidence didn't check out.
  dropped: number | null
}

export function factsKey(workspaceId: string, documentId: string) {
  return ['workspaces', workspaceId, 'documents', documentId, 'facts']
}

function factsPath(workspaceId: string, documentId: string) {
  return `/workspaces/${workspaceId}/documents/${documentId}/facts`
}

// Only what is stored: never calls the AI.
export function getFacts(workspaceId: string, documentId: string) {
  return api<Facts>(factsPath(workspaceId, documentId))
}

// Runs the AI over the document and replaces the stored facts.
export function extractFacts(workspaceId: string, documentId: string) {
  return api<Facts>(factsPath(workspaceId, documentId), { method: 'POST' })
}

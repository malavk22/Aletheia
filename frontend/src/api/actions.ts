import { api } from './client.ts'

// exact: the document gives a full date; relative: "within 30 days of
// leaving", or a date without a year; none: no time given.
export type DueKind = 'exact' | 'relative' | 'none'
export type ActionStatus = 'suggested' | 'confirmed' | 'dismissed'

// Something someone must do, found by the AI. It only counts once a person
// confirms it.
export type Action = {
  id: string
  document_id: string
  filename: string
  kind: 'deadline' | 'task'
  title: string
  responsible: string | null
  due_kind: DueKind
  // The "when" in the document's own words.
  due_text: string | null
  // YYYY-MM-DD, or null (always null for a relative deadline until a person
  // sets one).
  due_date: string | null
  // Where the date came from: the document (exact only) or a person.
  due_date_source: 'document' | 'person' | null
  // The document's own words, checked to be on the page.
  quote: string
  // Worked out by rules from the evidence, not asked from the AI.
  confidence: 'high' | 'medium' | 'low'
  status: ActionStatus
  confirmed_at: string | null
  part_position: number
  page_number: number | null
  heading: string | null
  source: 'text' | 'ocr'
}

export type DocumentActions = {
  // When actions were last found; null if never.
  extracted_at: string | null
  actions: Action[]
  // After finding only: actions left out because their evidence didn't check out.
  dropped: number | null
}

// A person's decision. Only the fields given are changed; due_date null
// clears a date.
export type ActionChange = {
  status?: ActionStatus
  title?: string
  due_date?: string | null
}

export function documentActionsKey(workspaceId: string, documentId: string) {
  return ['workspaces', workspaceId, 'documents', documentId, 'actions']
}

export function workspaceActionsKey(workspaceId: string) {
  return ['workspaces', workspaceId, 'actions']
}

// Names a running search, so the document list can show it.
export function findActionsKey(documentId: string) {
  return ['find-actions', documentId]
}

function documentActionsPath(workspaceId: string, documentId: string) {
  return `/workspaces/${workspaceId}/documents/${documentId}/actions`
}

// Only what is stored: never calls the AI.
export function getDocumentActions(workspaceId: string, documentId: string) {
  return api<DocumentActions>(documentActionsPath(workspaceId, documentId))
}

// Runs the AI over the document; earlier suggestions are replaced, decisions kept.
export function findActions(workspaceId: string, documentId: string) {
  return api<DocumentActions>(documentActionsPath(workspaceId, documentId), { method: 'POST' })
}

// Every document's actions with this status, dated ones first, by date.
export function listWorkspaceActions(workspaceId: string, status: ActionStatus) {
  return api<Action[]>(`/workspaces/${workspaceId}/actions?status=${status}`)
}

export function updateAction(workspaceId: string, actionId: string, change: ActionChange) {
  return api<Action>(`/workspaces/${workspaceId}/actions/${actionId}`, {
    method: 'PATCH',
    body: change,
  })
}

// "15 Mar 2026" for "2026-03-15". Read as UTC, so the day never shifts with
// the viewer's time zone.
export function formatDate(isoDate: string) {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${isoDate}T00:00:00Z`))
}

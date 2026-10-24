import { api } from './client.ts'
import type { SearchResult } from './search.ts'

// A passage the answer cites: "[2]" in the answer is the citation with number 2.
export type Citation = SearchResult & { number: number }

export type Answer = {
  // Written by the AI from the workspace's passages, with [n] markers.
  // When the documents don't answer the question, it says so and there are
  // no citations.
  answer: string
  citations: Citation[]
}

// `documentIds`: only search these documents; null: all of the workspace's.
export function askQuestion(workspaceId: string, question: string, documentIds: string[] | null) {
  return api<Answer>(`/workspaces/${workspaceId}/ask`, {
    method: 'POST',
    body: { question, document_ids: documentIds },
  })
}

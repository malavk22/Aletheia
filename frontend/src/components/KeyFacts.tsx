import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentFileUrl, documentsKey } from '../api/documents.ts'
import { extractFacts, extractFactsKey, factsKey, getFacts } from '../api/facts.ts'
import type { Fact, FactKind } from '../api/facts.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'
import { Tag } from './PassageResults.tsx'

// The groups, in the order they are shown.
const GROUPS: { kind: FactKind; label: string }[] = [
  { kind: 'person', label: 'People' },
  { kind: 'organization', label: 'Organizations' },
  { kind: 'date', label: 'Dates' },
  { kind: 'amount', label: 'Amounts' },
  { kind: 'requirement', label: 'Requirements' },
]

// Dates in date order when the document gives full dates; the rest (and the
// other groups) in the order they were found.
function inOrder(kind: FactKind, facts: Fact[]) {
  if (kind !== 'date') return facts
  return [...facts].sort((a, b) => {
    if (a.normalized === null || b.normalized === null) {
      return (a.normalized === null ? 1 : 0) - (b.normalized === null ? 1 : 0)
    }
    return a.normalized.localeCompare(b.normalized)
  })
}

// Grey bars in the shape of facts, shown while Gemini reads the document.
function FactsSkeleton() {
  return (
    <div aria-hidden="true" className="mt-3 animate-pulse space-y-4">
      {[0, 1, 2].map((row) => (
        <div key={row} className="space-y-2">
          <div className="h-3.5 w-2/5 rounded-sm bg-paper-deep" />
          <div className="h-3 w-full rounded-sm bg-paper-deep" />
          <div className="h-3 w-4/5 rounded-sm bg-paper-deep" />
        </div>
      ))}
    </div>
  )
}

// A document's key facts: people, organizations, dates, amounts and
// requirements, each with the sentence it comes from. Shown under a document
// in the list once it is processed. With `extractOnOpen`, a document that was
// never extracted is extracted as soon as the panel opens.
export function KeyFacts({
  workspaceId,
  documentId,
  extractOnOpen,
}: {
  workspaceId: string
  documentId: string
  extractOnOpen: boolean
}) {
  const queryClient = useQueryClient()
  const key = factsKey(workspaceId, documentId)
  const { data, isPending, error } = useQuery({
    queryKey: key,
    queryFn: () => getFacts(workspaceId, documentId),
  })
  const extraction = useMutation({
    // Lets the "Key facts" button in the list show that this one is running.
    mutationKey: extractFactsKey(documentId),
    mutationFn: () => extractFacts(workspaceId, documentId),
    onSuccess: (facts) => {
      // The reply holds the new facts: show them without asking again.
      queryClient.setQueryData(key, facts)
      // The list now has to know this document was extracted.
      return queryClient.invalidateQueries({ queryKey: documentsKey(workspaceId) })
    },
  })
  // The group shown; one at a time keeps a long document's panel short.
  const [chosenKind, setChosenKind] = useState<FactKind | null>(null)

  // Start only once, even if React runs this effect twice (development mode).
  const started = useRef(false)
  const { mutate } = extraction
  useEffect(() => {
    if (extractOnOpen && data?.extracted_at === null && !started.current) {
      started.current = true
      mutate()
    }
  }, [extractOnOpen, data, mutate])

  if (isPending) return <FactsSkeleton />
  if (error || !data) return <FormError>{UNREACHABLE_MESSAGE}</FormError>

  const extracted = data.extracted_at !== null
  // 409 (not processed) and 503 (AI unavailable) come with a message for
  // people. Anything else: the server could not be reached.
  const extractionError =
    extraction.error instanceof ApiError &&
    (extraction.error.status === 409 || extraction.error.status === 503)
      ? extraction.error.message
      : UNREACHABLE_MESSAGE
  // Only the reply to an extraction says how many facts were left out.
  const dropped = extraction.data?.dropped ?? 0
  const groups = GROUPS.map((group) => ({
    ...group,
    facts: data.facts.filter((fact) => fact.kind === group.kind),
  })).filter((group) => group.facts.length > 0)
  // The chosen group, or the first one with facts.
  const shown = groups.find((group) => group.kind === chosenKind) ?? groups[0]

  return (
    <div className="mt-3 rounded-sm border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">
          Key facts
          {extracted && data.facts.length > 0 && (
            <span className="font-normal text-ink-muted"> · {data.facts.length}</span>
          )}
        </h3>
        <Button
          variant={extracted ? 'secondary' : 'primary'}
          loading={extraction.isPending}
          onClick={() => extraction.mutate()}
        >
          {extracted ? 'Extract again' : 'Extract key facts'}
        </Button>
      </div>

      <div aria-live="polite">
        {!extracted && !extraction.isPending && (
          <p className="mt-2 text-sm text-ink-muted">
            Pulls out the people, organizations, dates, amounts and requirements in this document,
            each with the sentence it comes from.
          </p>
        )}

        {extraction.isPending && (
          <>
            <p className="mt-2 text-sm text-ink-muted">
              Reading the document… This can take up to a minute for a long document.
            </p>
            <FactsSkeleton />
          </>
        )}

        {extraction.isError && !extraction.isPending && (
          <div className="mt-3">
            <FormError>{extractionError}</FormError>
          </div>
        )}

        {extracted && !extraction.isPending && (
          <>
            {dropped > 0 && (
              // Honest about what the checks threw away.
              <p className="mt-2 text-sm text-ink-muted">
                {dropped === 1 ? '1 fact was' : `${dropped} facts were`} left out because the
                sentence it came from couldn't be found on its page.
              </p>
            )}
            {shown === undefined ? (
              <p className="mt-2 text-sm text-ink-muted">No key facts found in this document.</p>
            ) : (
              <>
                {/* One button per group with its count; the active one is dark. */}
                <div className="mt-3 flex flex-wrap gap-2 border-b border-line pb-3">
                  {groups.map(({ kind, label, facts }) => (
                    <button
                      key={kind}
                      type="button"
                      aria-pressed={kind === shown.kind}
                      className={`rounded-sm px-2.5 py-1 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                        kind === shown.kind
                          ? 'bg-accent text-white'
                          : 'border border-line-strong text-ink-muted hover:text-ink'
                      }`}
                      onClick={() => setChosenKind(kind)}
                    >
                      {label} <span className="opacity-75">{facts.length}</span>
                    </button>
                  ))}
                </div>
                <ul className="divide-y divide-line">
                  {inOrder(shown.kind, shown.facts).map((fact) => (
                    <FactItem
                      key={fact.position}
                      workspaceId={workspaceId}
                      documentId={documentId}
                      fact={fact}
                    />
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function FactItem({
  workspaceId,
  documentId,
  fact,
}: {
  workspaceId: string
  documentId: string
  fact: Fact
}) {
  const where =
    fact.page_number !== null ? `p. ${fact.page_number}` : (fact.heading ?? 'Before the first heading')

  return (
    <li className="py-3">
      <div className="flex items-start justify-between gap-4">
        <p className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
          <span className="font-medium">{fact.value}</span>
          {fact.about && <span className="text-ink-muted">{fact.about}</span>}
          <Tag>{where}</Tag>
          {fact.source === 'ocr' && <Tag>Read by OCR</Tag>}
        </p>
        {fact.page_number !== null && (
          <a
            href={`${documentFileUrl(workspaceId, documentId)}#page=${fact.page_number}`}
            target="_blank"
            rel="noopener"
            className="shrink-0 rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Open p. {fact.page_number} ↗
          </a>
        )}
      </div>
      {/* The document's own words: the evidence for the fact. */}
      <blockquote className="mt-1.5 border-l-2 border-line-strong pl-3 font-serif text-[14px] leading-relaxed text-ink-muted">
        {fact.quote}
      </blockquote>
    </li>
  )
}

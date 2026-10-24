import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { ReactNode } from 'react'
import type { FormEvent } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentFileUrl, documentsKey, listDocuments, listParts, partsKey } from '../api/documents.ts'
import type { DocumentPart, WorkspaceDocument } from '../api/documents.ts'
import { askQuestion } from '../api/qa.ts'
import type { Citation } from '../api/qa.ts'
import type { PartRange } from '../api/search.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'
import { PassageResults, Tag } from './PassageResults.tsx'
import { TextField } from './TextField.tsx'

// One place in a document (a page or a section) that the answer cites. Two
// overlapping chunks of the same page are cited as [2] and [3], but they are
// one source to the reader, so they share one label and one entry below.
type Source = {
  label: number
  citations: Citation[]
}

// Sources are labelled 1, 2, 3… in the order the answer first cites them,
// so the chips read in order.
function groupByPlace(answer: string, citations: Citation[]) {
  const firstSeen = (citation: Citation) => answer.indexOf(`[${citation.number}]`)
  const inReadingOrder = [...citations].sort((a, b) => firstSeen(a) - firstSeen(b))
  const sources: Source[] = []
  const labelOf = new Map<number, number>() // citation number -> source label
  const byPlace = new Map<string, Source>()
  for (const citation of inReadingOrder) {
    const place = `${citation.document_id}:${citation.part_position}`
    let source = byPlace.get(place)
    if (!source) {
      source = { label: sources.length + 1, citations: [] }
      byPlace.set(place, source)
      sources.push(source)
    }
    source.citations.push(citation)
    labelOf.set(citation.number, source.label)
  }
  return { sources, labelOf }
}

// What the box last asked for: a written answer, or the matching passages.
type View = { kind: 'answer' } | { kind: 'passages'; query: string } | null

// The workspace's one question box. "Ask" (or Enter) writes an answer from the
// documents with its sources; "Find passages" lists the matching passages,
// without AI: instant, and it works even when the AI is unavailable.
export function AskQuestion({ workspaceId }: { workspaceId: string }) {
  const [question, setQuestion] = useState('')
  const [view, setView] = useState<View>(null)
  // The source opened by a click on a [n] chip.
  const [selected, setSelected] = useState<number | null>(null)

  // The documents to search in; null: all of them.
  const [chosen, setChosen] = useState<string[] | null>(null)
  const { data: documents } = useQuery({
    queryKey: documentsKey(workspaceId),
    queryFn: () => listDocuments(workspaceId),
  })
  const ready = documents?.filter((document) => document.status === 'ready') ?? []
  // A chosen document deleted since is dropped; if none is left, all are searched.
  const stillThere = chosen?.filter((id) => ready.some((document) => document.id === id)) ?? []
  const documentIds = stillThere.length > 0 ? stillThere : null
  // Pages or sections can be chosen within one document: the one ticked, or
  // the workspace's only one.
  const single = documentIds?.length === 1 ? documentIds[0] : ready.length === 1 ? ready[0].id : null
  const [range, setRange] = useState<PartRange | null>(null)
  const parts = single !== null ? range : null
  // The backend takes pages only with their document named.
  const searchedIds = parts && single ? [single] : documentIds

  // A mutation, not a query: asking is an action (it calls the AI each time),
  // and an answer is not kept to be shown again later.
  const mutation = useMutation({
    mutationFn: (text: string) => askQuestion(workspaceId, text, searchedIds, parts),
  })

  function ask(event: FormEvent) {
    event.preventDefault()
    const text = question.trim()
    if (text === '') return
    setSelected(null)
    setView({ kind: 'answer' })
    mutation.mutate(text)
  }

  function findPassages() {
    const text = question.trim()
    if (text === '') return
    setView({ kind: 'passages', query: text })
  }

  function choose(id: string, checked: boolean) {
    const current = documentIds ?? ready.map((document) => document.id)
    const next = checked ? [...current, id] : current.filter((other) => other !== id)
    // Every document ticked is the same as all of them.
    setChosen(next.length === ready.length ? null : next)
    // Page numbers belong to one document: a new choice starts with all pages.
    setRange(null)
  }

  function clear() {
    setQuestion('')
    setView(null)
    mutation.reset()
  }

  const showingPassages = view?.kind === 'passages'
  const error = mutation.error
  // 422 (empty question), 429 (AI usage limit, with when to try again) and
  // 503 (AI unavailable) come with a message written for people. Anything
  // else: the server could not be reached.
  const errorMessage =
    error instanceof ApiError && [422, 429, 503].includes(error.status)
      ? error.message
      : UNREACHABLE_MESSAGE

  return (
    <section aria-labelledby="ask-heading">
      <h2 id="ask-heading" className="font-serif text-xl font-semibold tracking-tight">
        Ask your documents
      </h2>
      <form onSubmit={ask} className="mt-3 flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <TextField
            label="Ask a question, or find the passages about something"
            placeholder="e.g. Who supervised the project?"
            value={question}
            maxLength={500}
            onChange={(event) => {
              setQuestion(event.target.value)
              // Emptying the box hides what it showed.
              if (event.target.value === '') clear()
            }}
          />
        </div>
        {/* The button whose results are showing is the dark one; Ask is dark
            before anything is shown, as the main action and the Enter key. */}
        <div className="flex gap-3">
          <Button
            type="submit"
            variant={showingPassages ? 'secondary' : 'primary'}
            loading={mutation.isPending}
          >
            Ask
          </Button>
          <Button
            type="button"
            variant={showingPassages ? 'primary' : 'secondary'}
            aria-pressed={showingPassages}
            onClick={findPassages}
          >
            Find passages
          </Button>
        </div>
      </form>
      {ready.length >= 1 && (
        <ChooseDocuments documents={ready} documentIds={documentIds} onChoose={choose}>
          {single !== null && (
            // Keyed by the document: its own pages, starting with all of them.
            <ChooseParts
              key={single}
              workspaceId={workspaceId}
              documentId={single}
              range={range}
              onChange={setRange}
            />
          )}
        </ChooseDocuments>
      )}
      <p className="mt-2 text-sm text-ink-muted">
        Ask writes an answer from your documents, with its sources. Find passages lists where
        they mention it.
      </p>

      {/* aria-live: screen readers announce the answer when it arrives. */}
      <div aria-live="polite">
        {view?.kind === 'answer' && mutation.isPending && (
          <p className="mt-5 text-sm text-ink-muted">
            Reading the passages and writing an answer… This takes a few seconds.
          </p>
        )}

        {view?.kind === 'answer' && error && !mutation.isPending && (
          <div className="mt-5 space-y-3">
            <FormError>{errorMessage}</FormError>
            {error instanceof ApiError && [429, 503].includes(error.status) && (
              // Not a dead end: finding passages needs no AI.
              <Button variant="secondary" onClick={findPassages}>
                Find passages instead
              </Button>
            )}
          </div>
        )}

        {view?.kind === 'answer' && mutation.data && !mutation.isPending && (
          <AnswerView
            workspaceId={workspaceId}
            answer={mutation.data.answer}
            citations={mutation.data.citations}
            selected={selected}
            onSelect={setSelected}
          />
        )}

        {view?.kind === 'passages' && (
          <PassageResults
            workspaceId={workspaceId}
            query={view.query}
            documentIds={searchedIds}
            parts={parts}
            onClear={clear}
          />
        )}
      </div>
    </section>
  )
}

// "Search in: All documents", opening to a tick box per document.
function ChooseDocuments({
  documents,
  documentIds,
  onChoose,
  children,
}: {
  documents: WorkspaceDocument[]
  documentIds: string[] | null
  onChoose: (id: string, checked: boolean) => void
  children: ReactNode
}) {
  const summary =
    documentIds === null
      ? 'All documents'
      : documentIds.length === 1
        ? documents.find((document) => document.id === documentIds[0])!.filename
        : `${documentIds.length} of ${documents.length} documents`

  return (
    <details className="mt-3 text-sm">
      <summary className="w-fit cursor-pointer rounded-sm text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent">
        Search in: <span className="font-medium text-ink">{summary}</span>
      </summary>
      <fieldset className="mt-2 space-y-1.5 border-l-2 border-line pl-4">
        <legend className="sr-only">Documents to search in</legend>
        {documents.map((document) => {
          const checked = documentIds === null || documentIds.includes(document.id)
          // The last ticked box can't be unticked: searching nothing finds nothing.
          const last = checked && (documentIds?.length === 1 || documents.length === 1)
          return (
            <label key={document.id} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={checked}
                disabled={last}
                onChange={(event) => onChoose(document.id, event.target.checked)}
                className="accent-accent"
              />
              <span className="truncate">{document.filename}</span>
            </label>
          )
        })}
      </fieldset>
      {children}
    </details>
  )
}

// "Pages from … to …" (or sections, for a Word file) within one document.
function ChooseParts({
  workspaceId,
  documentId,
  range,
  onChange,
}: {
  workspaceId: string
  documentId: string
  range: PartRange | null
  onChange: (range: PartRange | null) => void
}) {
  const { data: parts } = useQuery({
    queryKey: partsKey(workspaceId, documentId),
    queryFn: () => listParts(workspaceId, documentId),
  })
  // One page or section has nothing to choose from.
  if (!parts || parts.length < 2) return null

  const first = parts[0].position
  const last = parts[parts.length - 1].position
  const from = range?.from ?? first
  const to = range?.to ?? last
  const isPdf = parts[0].page_number !== null

  function set(nextFrom: number, nextTo: number) {
    // Kept in order: choosing a start after the end moves the end too.
    const start = Math.min(nextFrom, nextTo)
    const end = Math.max(nextFrom, nextTo)
    onChange(start === first && end === last ? null : { from: start, to: end })
  }

  const select =
    'rounded-sm border border-line-strong bg-surface px-2 py-1 text-sm focus-visible:outline-2 focus-visible:outline-accent'

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-l-2 border-line pl-4">
      <span>{isPdf ? 'Pages' : 'Sections'} from</span>
      <select
        aria-label={isPdf ? 'First page' : 'First section'}
        className={select}
        value={from}
        onChange={(event) => set(Number(event.target.value), Math.max(Number(event.target.value), to))}
      >
        {parts.map((part) => (
          <option key={part.position} value={part.position}>
            {partLabel(part)}
          </option>
        ))}
      </select>
      <span>to</span>
      <select
        aria-label={isPdf ? 'Last page' : 'Last section'}
        className={select}
        value={to}
        onChange={(event) => set(Math.min(from, Number(event.target.value)), Number(event.target.value))}
      >
        {parts.map((part) => (
          <option key={part.position} value={part.position}>
            {partLabel(part)}
          </option>
        ))}
      </select>
    </div>
  )
}

function partLabel(part: DocumentPart) {
  if (part.page_number !== null) return String(part.page_number)
  return part.heading ?? 'Before the first heading'
}

function AnswerView({
  workspaceId,
  answer,
  citations,
  selected,
  onSelect,
}: {
  workspaceId: string
  answer: string
  citations: Citation[]
  selected: number | null
  onSelect: (label: number) => void
}) {
  // No citations: the documents don't answer it (the backend never returns
  // an answer without evidence).
  if (citations.length === 0) {
    return (
      <div className="mt-6 rounded-sm border border-line bg-surface p-5">
        <p>{answer}</p>
        <p className="mt-2 text-sm text-ink-muted">
          Try other words, or use Find passages to see where the documents mention it.
        </p>
      </div>
    )
  }

  const { sources, labelOf } = groupByPlace(answer, citations)

  function select(label: number) {
    onSelect(label)
    document.getElementById(`source-${label}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  return (
    <div className="mt-6 rounded-sm border border-line bg-surface p-5">
      <p className="leading-relaxed">
        <WithChips text={answer} labelOf={labelOf} selected={selected} onSelect={select} />
      </p>
      <p className="mt-3 text-xs text-ink-muted">
        Written by AI from the passages below. Check the sources before relying on it.
      </p>

      <h3 className="mt-6 border-b border-line pb-2 text-sm font-medium text-ink-muted">
        {sources.length === 1 ? '1 source' : `${sources.length} sources`}
      </h3>
      <ol className="divide-y divide-line">
        {sources.map((source) => (
          <SourceItem
            key={source.label}
            workspaceId={workspaceId}
            source={source}
            selected={selected === source.label}
          />
        ))}
      </ol>
    </div>
  )
}

// The answer text with each [n] turned into a button showing its source's
// label. "[2][3]" from the same page becomes a single chip.
function WithChips({
  text,
  labelOf,
  selected,
  onSelect,
}: {
  text: string
  labelOf: Map<number, number>
  selected: number | null
  onSelect: (label: number) => void
}) {
  const pieces = []
  let last = 0
  let previousLabel: number | null = null
  for (const match of text.matchAll(/\[(\d+)\]/g)) {
    const between = text.slice(last, match.index)
    const label = labelOf.get(Number(match[1]))
    last = match.index + match[0].length
    // A chip right after a chip for the same source adds nothing.
    if (between === '' && label === previousLabel) continue
    pieces.push(between)
    previousLabel = label ?? null
    if (label === undefined) continue
    pieces.push(
      <button
        key={match.index}
        type="button"
        onClick={() => onSelect(label)}
        aria-label={`Source ${label}`}
        className={`mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-sm px-1 align-text-top text-xs font-semibold focus-visible:outline-2 focus-visible:outline-accent ${
          selected === label ? 'bg-accent text-white' : 'bg-paper-deep text-accent hover:bg-line'
        }`}
      >
        {label}
      </button>,
    )
  }
  pieces.push(text.slice(last))
  return pieces
}

function SourceItem({
  workspaceId,
  source,
  selected,
}: {
  workspaceId: string
  source: Source
  selected: boolean
}) {
  const first = source.citations[0]
  const where =
    first.page_number !== null ? `p. ${first.page_number}` : (first.heading ?? 'Before the first heading')

  return (
    <li
      id={`source-${source.label}`}
      className={`-mx-2 scroll-mt-4 rounded-sm px-2 py-4 ${selected ? 'bg-paper-deep' : ''}`}
    >
      <div className="flex items-start justify-between gap-4">
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span
            className={`inline-flex h-5 min-w-5 items-center justify-center rounded-sm px-1 text-xs font-semibold ${
              selected ? 'bg-accent text-white' : 'bg-paper-deep text-accent'
            }`}
          >
            {source.label}
          </span>
          <span className="truncate font-medium">{first.filename}</span>
          <Tag>{where}</Tag>
          {first.source === 'ocr' && <Tag>Read by OCR</Tag>}
        </p>
        {first.page_number !== null && (
          <a
            href={`${documentFileUrl(workspaceId, first.document_id)}#page=${first.page_number}`}
            target="_blank"
            rel="noopener"
            className="shrink-0 rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Open p. {first.page_number} ↗
          </a>
        )}
      </div>
      {/* The document's own words. The source picked in the answer is shown
          whole; the others are shortened. */}
      <blockquote className="mt-2 space-y-2 border-l-2 border-line-strong pl-4 font-serif text-[15px] leading-relaxed">
        {source.citations.map((citation) => (
          <p key={citation.chunk_position} className={selected ? undefined : 'line-clamp-3'}>
            {citation.text}
          </p>
        ))}
      </blockquote>
    </li>
  )
}

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentFileUrl } from '../api/documents.ts'
import { searchKey, searchWorkspace } from '../api/search.ts'
import type { SearchMode, SearchResult } from '../api/search.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'
import { TextField } from './TextField.tsx'

// Only the best few: weaker matches add little, and a long list pushes the
// documents far down the page.
const SHOWN_RESULTS = 5

// Neighbouring chunks overlap, so one page often matches two or three times
// with almost the same text. Keep only the best match per page or section
// (results arrive best first).
function onePerPlace(results: SearchResult[]) {
  const seen = new Set<string>()
  return results.filter((result) => {
    const place = `${result.document_id}:${result.part_position}`
    if (seen.has(place)) return false
    seen.add(place)
    return true
  })
}

const MODES: { value: SearchMode; label: string; hint: string; summary: string }[] = [
  {
    value: 'semantic',
    label: 'Meaning',
    hint: 'Finds passages that mean the same, in any words.',
    summary: 'by meaning',
  },
  {
    value: 'keyword',
    label: 'Exact words',
    hint: 'Finds passages containing every word you type.',
    summary: 'containing these words',
  },
]

export function SearchDocuments({ workspaceId }: { workspaceId: string }) {
  // What is typed, and what was last searched for. Searching runs only on
  // Enter or the button: each search runs the AI model, and results changing
  // on every key press would be distracting.
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('semantic')
  const current = MODES.find((option) => option.value === mode)!

  // Switching the mode searches the same words again (the mode is in the key).
  const { data: results, isFetching, error } = useQuery({
    queryKey: searchKey(workspaceId, query, mode),
    queryFn: () => searchWorkspace(workspaceId, query, mode),
    enabled: query !== '',
    select: (found) => onePerPlace(found).slice(0, SHOWN_RESULTS),
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setQuery(draft.trim())
  }

  function clear() {
    setDraft('')
    setQuery('')
  }

  return (
    <section aria-labelledby="search-heading">
      <h2 id="search-heading" className="font-serif text-xl font-semibold tracking-tight">
        Search
      </h2>
      <form onSubmit={handleSubmit} className="mt-3 flex items-end gap-3">
        <div className="flex-1">
          <TextField
            label="Ask a question, or look for exact words"
            type="search"
            placeholder="e.g. When can the contract be ended?"
            value={draft}
            maxLength={500}
            onChange={(event) => {
              setDraft(event.target.value)
              // Emptying the box (or its clear button) hides the results.
              if (event.target.value === '') setQuery('')
            }}
          />
        </div>
        <Button type="submit" variant="secondary" loading={isFetching}>
          Search
        </Button>
      </form>

      <fieldset className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        <legend className="sr-only">Search by</legend>
        <div className="inline-flex rounded-sm border border-line-strong bg-surface p-0.5">
          {MODES.map((option) => (
            <label
              key={option.value}
              className={`cursor-pointer rounded-[3px] px-3 py-1 text-sm font-medium has-focus-visible:outline-2 has-focus-visible:outline-accent ${
                mode === option.value ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'
              }`}
            >
              <input
                type="radio"
                name="search-mode"
                value={option.value}
                checked={mode === option.value}
                onChange={() => setMode(option.value)}
                className="sr-only"
              />
              {option.label}
            </label>
          ))}
        </div>
        <p className="text-sm text-ink-muted">{current.hint}</p>
      </fieldset>

      {error && (
        <div className="mt-5">
          <FormError>
            {error instanceof ApiError && error.status === 422 ? error.message : UNREACHABLE_MESSAGE}
          </FormError>
        </div>
      )}

      {results && !error && (
        <div className="mt-6">
          <div className="flex items-baseline justify-between gap-4 border-b border-line pb-2">
            {/* With no results the message below says so already. */}
            <p className="text-sm text-ink-muted">
              {results.length > 0 &&
                `${results.length === 1 ? '1 passage' : `${results.length} passages`} ${current.summary}`}
            </p>
            <button
              type="button"
              onClick={clear}
              className="rounded-sm text-sm font-medium text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
            >
              Clear
            </button>
          </div>
          {results.length === 0 && mode === 'keyword' && (
            // Not a dead end: offer the search that is most likely to find something.
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
              <p className="text-sm text-ink-muted">No passage contains all of these words.</p>
              <Button variant="secondary" onClick={() => setMode('semantic')}>
                Search by meaning instead
              </Button>
            </div>
          )}
          {results.length === 0 && mode === 'semantic' && (
            <p className="mt-4 text-sm text-ink-muted">
              Nothing to search yet. Upload a document, and search again once it is processed.
            </p>
          )}
          {results.length > 0 && (
            <ol className="divide-y divide-line">
              {results.map((result) => (
                <SearchResultItem
                  key={`${result.document_id}-${result.chunk_position}`}
                  workspaceId={workspaceId}
                  result={result}
                  // Only exact-word results show what matched: in meaning mode
                  // a passage is found by sense, not by sharing words.
                  terms={mode === 'keyword' ? matchTerms(query) : []}
                />
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  )
}

function SearchResultItem({
  workspaceId,
  result,
  terms,
}: {
  workspaceId: string
  result: SearchResult
  terms: string[]
}) {
  const [expanded, setExpanded] = useState(false)
  const where =
    result.page_number !== null
      ? `p. ${result.page_number}`
      : (result.heading ?? 'Before the first heading')

  return (
    <li className="py-5">
      <div className="flex items-start justify-between gap-4">
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span className="truncate font-medium">{result.filename}</span>
          <Tag>{where}</Tag>
          {/* OCR text can contain misread words: say so. */}
          {result.source === 'ocr' && <Tag>Read by OCR</Tag>}
        </p>
        {/* Browsers' PDF viewers open at "#page=14". A Word file cannot be
            shown in the browser, and downloading a whole file from a search
            result would be surprising, so it gets no link. */}
        {result.page_number !== null && (
          <a
            href={`${documentFileUrl(workspaceId, result.document_id)}#page=${result.page_number}`}
            target="_blank"
            rel="noopener"
            className="shrink-0 rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
          >
            Open p. {result.page_number} ↗
          </a>
        )}
      </div>
      {/* The document's own words, set apart from anything the app writes. */}
      <blockquote className="mt-2 border-l-2 border-line-strong pl-4 font-serif text-[15px] leading-relaxed">
        <p className={expanded ? undefined : 'line-clamp-4'}>
          <Highlighted text={expanded ? result.text : excerpt(result.text, terms)} terms={terms} />
        </p>
      </blockquote>
      {/* Four lines are about 400 characters; shorter passages are shown whole. */}
      {result.text.length > 400 && (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
          className="mt-1.5 ml-4 rounded-sm text-sm font-medium text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          {expanded ? 'Show less' : 'Show the whole passage'}
        </button>
      )}
    </li>
  )
}

function Tag({ children }: { children: string }) {
  return (
    <span className="rounded-sm bg-paper-deep px-1.5 py-0.5 text-xs font-medium text-ink-muted">
      {children}
    </span>
  )
}

// Common words that PostgreSQL ignores in keyword search, so they never match.
const COMMON_WORDS = new Set(['the', 'and', 'for', 'are', 'was', 'with', 'that', 'this'])

// The beginnings of the searched words, for highlighting. Keyword search
// matches word stems ("termination" also finds "terminated"), so a word is
// highlighted when it starts like a searched word. Excluded words (-pets) and
// "or" are left out.
function matchTerms(query: string) {
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter((word) => !word.startsWith('-') && word !== 'or')
    .flatMap((word) => word.split(/[^\p{L}\p{N}]+/u))
    .filter((word) => word.length >= 3 && !COMMON_WORDS.has(word))
    .map((word) => word.slice(0, Math.max(4, word.length - 3)))
}

function termPattern(terms: string[]) {
  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  return new RegExp(`(?<![\\p{L}\\p{N}])(?:${escaped.join('|')})[\\p{L}\\p{N}]*`, 'giu')
}

// Only four lines are shown, so a match deep in the passage would be hidden.
// Start shortly before the first match instead.
function excerpt(text: string, terms: string[]) {
  if (terms.length === 0) return text
  const first = text.search(termPattern(terms))
  if (first < 160) return text
  return '…' + text.slice(text.lastIndexOf(' ', first - 60) + 1)
}

function Highlighted({ text, terms }: { text: string; terms: string[] }) {
  if (terms.length === 0) return text
  const pattern = termPattern(terms)
  const pieces = []
  let last = 0
  for (const match of text.matchAll(pattern)) {
    pieces.push(text.slice(last, match.index))
    pieces.push(
      <mark key={match.index} className="rounded-[2px] bg-highlight px-0.5 text-ink">
        {match[0]}
      </mark>,
    )
    last = match.index + match[0].length
  }
  pieces.push(text.slice(last))
  return pieces
}

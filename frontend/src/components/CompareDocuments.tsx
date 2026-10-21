import { useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { compareDocuments, comparisonKey } from '../api/compare.ts'
import type { Change, Sentence } from '../api/compare.ts'
import { documentFileUrl, documentsKey, listDocuments } from '../api/documents.ts'
import { FormError } from './FormError.tsx'
import { Tag } from './PassageResults.tsx'

// A word without capitals or punctuation, so "water." and "WATER!" count as
// the same word (the backend compares sentences the same way).
function plain(word: string) {
  return word.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '')
}

// Which words of two versions of a sentence are new: the words not in their
// longest common sequence (LCS). A sentence has a few dozen words, so the
// table stays small.
function changedWords(before: string, after: string) {
  const a = before.split(' ')
  const b = after.split(' ')
  // common[i][j]: how many words a[i..] and b[j..] have in common, in order.
  const common = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      common[i][j] =
        plain(a[i]) === plain(b[j])
          ? common[i + 1][j + 1] + 1
          : Math.max(common[i + 1][j], common[i][j + 1])
    }
  }
  const oldChanged = a.map(() => true)
  const newChanged = b.map(() => true)
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (plain(a[i]) === plain(b[j])) {
      oldChanged[i++] = false
      newChanged[j++] = false
    } else if (common[i + 1][j] >= common[i][j + 1]) {
      i++
    } else {
      j++
    }
  }
  return {
    old: a.map((word, index) => ({ word, changed: oldChanged[index] })),
    new: b.map((word, index) => ({ word, changed: newChanged[index] })),
  }
}

// Compares two documents of the workspace sentence by sentence: what was
// changed, removed or added, with the page in both versions. A local diff,
// no AI.
export function CompareDocuments({ workspaceId }: { workspaceId: string }) {
  const [oldId, setOldId] = useState('')
  const [newId, setNewId] = useState('')
  const { data: documents } = useQuery({
    queryKey: documentsKey(workspaceId),
    queryFn: () => listDocuments(workspaceId),
  })
  const ready = documents?.filter((document) => document.status === 'ready') ?? []
  const chosen = oldId !== '' && newId !== '' && oldId !== newId
  const comparison = useQuery({
    queryKey: comparisonKey(workspaceId, oldId, newId),
    queryFn: () => compareDocuments(workspaceId, oldId, newId),
    enabled: chosen,
  })

  if (ready.length < 2) {
    return (
      <p className="text-sm text-ink-muted">
        Upload two documents, for example two versions of a contract, to compare them.
      </p>
    )
  }

  // 404 (a document was deleted meanwhile) and 409 (not processed) come with
  // a message for people. Anything else: the server could not be reached.
  const error = comparison.error
  const errorMessage =
    error instanceof ApiError && (error.status === 404 || error.status === 409)
      ? error.message
      : UNREACHABLE_MESSAGE
  const data = comparison.data
  const meaningful = data?.changes.filter((change) => change.kind !== 'formatting') ?? []
  const formatting = data?.changes.filter((change) => change.kind === 'formatting') ?? []

  const select =
    'mt-1 block w-full rounded-sm border border-line-strong bg-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-accent'

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        {(
          [
            ['Old version', oldId, setOldId],
            ['New version', newId, setNewId],
          ] as const
        ).map(([label, value, setValue]) => (
          <label key={label} className="block text-sm font-medium">
            {label}
            <select className={select} value={value} onChange={(event) => setValue(event.target.value)}>
              <option value="">Choose a document…</option>
              {ready.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.filename}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <div aria-live="polite">
        {oldId !== '' && oldId === newId && (
          <p className="text-sm text-ink-muted">Choose two different documents.</p>
        )}
        {chosen && comparison.isPending && <p className="text-sm text-ink-muted">Comparing…</p>}
        {chosen && comparison.isError && <FormError>{errorMessage}</FormError>}

        {chosen && data && (
          <>
            {meaningful.length === 0 ? (
              <p className="text-sm text-ink-muted">No changes in wording.</p>
            ) : (
              <div className="flex flex-wrap gap-2 text-xs font-medium">
                {(['changed', 'removed', 'added'] as const)
                  .filter((kind) => data.counts[kind] > 0)
                  .map((kind) => (
                    <span key={kind} className={`rounded-sm px-2 py-0.5 ${BADGES[kind]}`}>
                      {data.counts[kind]} {kind}
                    </span>
                  ))}
              </div>
            )}
            {meaningful.length > 0 && (
              <ul className="mt-3 space-y-3">
                {meaningful.map((change, index) => (
                  <ChangeItem
                    key={index}
                    workspaceId={workspaceId}
                    oldId={oldId}
                    newId={newId}
                    change={change}
                  />
                ))}
              </ul>
            )}
            {formatting.length > 0 && (
              // Kept apart and closed: re-typed text shouldn't hide real changes.
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer text-ink-muted hover:text-ink">
                  {formatting.length === 1
                    ? '1 formatting-only change'
                    : `${formatting.length} formatting-only changes`}{' '}
                  (spacing, capitals or punctuation)
                </summary>
                <ul className="mt-3 space-y-3">
                  {formatting.map((change, index) => (
                    <li key={index} className="space-y-1.5 rounded-sm border border-line bg-surface p-3">
                      <Row side="old" tone="neutral">
                        {change.old?.text}
                      </Row>
                      <Row side="new" tone="neutral">
                        {change.new?.text}
                      </Row>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </>
        )}
      </div>
    </div>
  )
}

const LABELS = { changed: 'Changed', removed: 'Removed', added: 'Added', formatting: 'Formatting' }

const BADGES = {
  changed: 'bg-paper-deep text-ink',
  removed: 'bg-danger-soft text-danger',
  added: 'bg-added-soft text-added',
}

// Unchanged words kept on each side of a changed word; the rest of a long
// sentence becomes "…" until "Show full sentence".
const CONTEXT = 5

type Word = { word: string; changed: boolean }

// The words to show: changed words with CONTEXT words around them; each run
// of other words becomes one null ("…").
function trimmed(words: Word[]) {
  const keep = words.map((_, index) =>
    words
      .slice(Math.max(0, index - CONTEXT), index + CONTEXT + 1)
      .some((word) => word.changed),
  )
  const shown: (Word | null)[] = []
  words.forEach((word, index) => {
    if (keep[index]) shown.push(word)
    else if (shown.at(-1) !== null) shown.push(null)
  })
  return shown
}

function ChangeItem({
  workspaceId,
  oldId,
  newId,
  change,
}: {
  workspaceId: string
  oldId: string
  newId: string
  change: Change
}) {
  const [full, setFull] = useState(false)
  const words =
    change.kind === 'changed' && change.old && change.new
      ? changedWords(change.old.text, change.new.text)
      : null
  const short = words && { old: trimmed(words.old), new: trimmed(words.new) }
  const shown = full ? words : short
  // A whole removed/added sentence has no changed words to centre on: long
  // ones are cut to two lines instead.
  const long = words === null && (change.old ?? change.new)!.text.length > 160
  const canExpand = long || (short !== null && [...short.old, ...short.new].includes(null))

  return (
    <li className="rounded-sm border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className={`text-xs font-semibold tracking-wide uppercase ${
            change.kind === 'removed'
              ? 'text-danger'
              : change.kind === 'added'
                ? 'text-added'
                : 'text-ink-muted'
          }`}
        >
          {LABELS[change.kind]}
        </span>
        {/* Where the sentence is in each version: the provenance of the change. */}
        <span className="flex flex-wrap gap-3">
          {change.old && (
            <Place label="Old" workspaceId={workspaceId} documentId={oldId} sentence={change.old} />
          )}
          {change.new && (
            <Place label="New" workspaceId={workspaceId} documentId={newId} sentence={change.new} />
          )}
        </span>
      </div>

      <div className="mt-2 space-y-1.5">
        {shown ? (
          <>
            <Row side="old" tone="removed">
              <Words words={shown.old} side="old" />
            </Row>
            <Row side="new" tone="added">
              <Words words={shown.new} side="new" />
            </Row>
          </>
        ) : change.kind === 'removed' ? (
          <Row side="old" tone="removed" clamp={long && !full}>
            {change.old?.text}
          </Row>
        ) : (
          <Row side="new" tone="added" clamp={long && !full}>
            {change.new?.text}
          </Row>
        )}
      </div>

      {canExpand && (
        <button
          type="button"
          className="mt-2 rounded-sm text-xs font-medium text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
          onClick={() => setFull(!full)}
        >
          {full ? 'Show less' : 'Show full sentence'}
        </button>
      )}
    </li>
  )
}

// One line of a change: an OLD/NEW label, a coloured bar, then the text.
function Row({
  side,
  tone,
  clamp = false,
  children,
}: {
  side: 'old' | 'new'
  tone: 'removed' | 'added' | 'neutral'
  clamp?: boolean
  children: ReactNode
}) {
  const bar = { removed: 'border-danger/50', added: 'border-added/50', neutral: 'border-line-strong' }
  return (
    <div className="grid grid-cols-[2.5rem_1fr] items-baseline gap-2">
      <span className="text-[11px] font-semibold tracking-wide text-ink-muted uppercase">
        {side}
      </span>
      <p className={`border-l-2 pl-3 text-sm leading-relaxed ${bar[tone]} ${clamp ? 'line-clamp-2' : ''}`}>
        {children}
      </p>
    </div>
  )
}

// A changed sentence's words: the changed ones marked (struck through on the
// old side, highlighted on the new), "…" where unchanged words were cut.
function Words({ words, side }: { words: (Word | null)[]; side: 'old' | 'new' }) {
  return words.map((word, index) => (
    // The space after each word stays outside its highlight.
    <Fragment key={index}>
      {word === null ? (
        <span className="text-ink-muted">…</span>
      ) : !word.changed ? (
        word.word
      ) : side === 'old' ? (
        <del className="rounded-sm bg-danger-soft px-0.5 text-danger">{word.word}</del>
      ) : (
        <ins className="rounded-sm bg-added-soft px-0.5 font-medium text-added no-underline">
          {word.word}
        </ins>
      )}{' '}
    </Fragment>
  ))
}

// "Old p. 2 ↗" opening that page of the PDF; a heading tag for a Word file.
function Place({
  label,
  workspaceId,
  documentId,
  sentence,
}: {
  label: string
  workspaceId: string
  documentId: string
  sentence: Sentence
}) {
  if (sentence.page_number === null) {
    return <Tag>{`${label}: ${sentence.heading ?? 'Before the first heading'}`}</Tag>
  }
  return (
    <a
      href={`${documentFileUrl(workspaceId, documentId)}#page=${sentence.page_number}`}
      target="_blank"
      rel="noopener"
      className="rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
    >
      {label} p. {sentence.page_number} ↗
    </a>
  )
}

import { useMutation, useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { checkConflicts, compareDocuments, comparisonKey } from '../api/compare.ts'
import type { Change, ChangeKind, Sentence } from '../api/compare.ts'
import { documentFileUrl, documentsKey, listDocuments } from '../api/documents.ts'
import type { WorkspaceDocument } from '../api/documents.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'
import { FactsSkeleton } from './KeyFacts.tsx'
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
  // Only this kind of change is listed (a badge was clicked); null: all.
  const [only, setOnly] = useState<ChangeKind | null>(null)
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
  const listed = meaningful.filter((change) => only === null || change.kind === only)
  const formatting = data?.changes.filter((change) => change.kind === 'formatting') ?? []

  const select =
    'mt-1 block w-full rounded-sm border border-line-strong bg-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-accent'

  return (
    <div className="space-y-5">
      <div className="grid items-end gap-4 sm:grid-cols-[1fr_auto_1fr]">
        {(
          [
            ['Old version', oldId, setOldId],
            ['New version', newId, setNewId],
          ] as const
        ).map(([label, value, setValue], index) => (
          <Fragment key={label}>
            {index === 1 && (
              // Picked the wrong way round? One click flips old and new.
              <button
                type="button"
                aria-label="Swap old and new version"
                title="Swap old and new version"
                className="h-[38px] rounded-sm border border-line-strong bg-surface px-3 text-sm text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
                onClick={() => {
                  setOldId(newId)
                  setNewId(oldId)
                  // Swapping turns removed into added: the filter no longer fits.
                  setOnly(null)
                }}
              >
                ⇄
              </button>
            )}
            <label className="block text-sm font-medium">
              {label}
              <select
                className={select}
                value={value}
                onChange={(event) => {
                  setValue(event.target.value)
                  setOnly(null)
                }}
              >
                <option value="">Choose a document…</option>
                {ready.map((document) => (
                  // The document chosen in the other dropdown can't be chosen
                  // here: a document isn't compared with itself.
                  <option
                    key={document.id}
                    value={document.id}
                    disabled={document.id === (index === 0 ? newId : oldId)}
                  >
                    {document.filename}
                  </option>
                ))}
              </select>
            </label>
          </Fragment>
        ))}
      </div>

      <div aria-live="polite">
        {chosen && comparison.isPending && <p className="text-sm text-ink-muted">Comparing…</p>}
        {chosen && comparison.isError && <FormError>{errorMessage}</FormError>}

        {chosen && data && (
          <>
            {meaningful.length === 0 ? (
              <p className="text-sm text-ink-muted">No changes in wording.</p>
            ) : (
              <div className="flex flex-wrap items-center gap-2 text-xs font-medium">
                {/* Each count is also a filter: click to list only that kind,
                    click again for all. */}
                {(['changed', 'removed', 'added'] as const)
                  .filter((kind) => data.counts[kind] > 0)
                  .map((kind) => (
                    <button
                      key={kind}
                      type="button"
                      aria-pressed={only === kind}
                      className={`rounded-sm px-2 py-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${BADGES[kind]} ${
                        only === kind ? 'ring-2 ring-current' : only !== null ? 'opacity-50' : ''
                      }`}
                      onClick={() => setOnly(only === kind ? null : kind)}
                    >
                      {data.counts[kind]} {kind}
                    </button>
                  ))}
                {only !== null && (
                  <button
                    type="button"
                    className="rounded-sm px-1 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
                    onClick={() => setOnly(null)}
                  >
                    Show all
                  </button>
                )}
              </div>
            )}
            {listed.length > 0 && (
              // Keyed by the pair and filter: a new choice starts again at 5.
              <ShowMore
                key={`${oldId} ${newId} ${only}`}
                items={listed}
                noun="change"
                render={(change, index) => (
                  <ChangeItem
                    key={index}
                    workspaceId={workspaceId}
                    oldId={oldId}
                    newId={newId}
                    change={change}
                  />
                )}
              />
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
                <ShowMore
                  key={`${oldId} ${newId}`}
                  items={formatting}
                  noun="change"
                  render={(change, index) => (
                    <li key={index} className="space-y-1.5 rounded-sm border border-line bg-surface p-3">
                      <Row side="old" tone="neutral">
                        {change.old?.text}
                      </Row>
                      <Row side="new" tone="neutral">
                        {change.new?.text}
                      </Row>
                    </li>
                  )}
                />
              </details>
            )}
          </>
        )}
      </div>

      {chosen && (
        // Keyed by the pair: choosing other documents clears the last check.
        <PotentialConflicts
          key={`${oldId} ${newId}`}
          workspaceId={workspaceId}
          a={ready.find((document) => document.id === oldId)!}
          b={ready.find((document) => document.id === newId)!}
        />
      )}
    </div>
  )
}

// Statements in the two documents that may contradict each other. Checked on
// request only: the most alike passages are sent to Google Gemini.
function PotentialConflicts({
  workspaceId,
  a,
  b,
}: {
  workspaceId: string
  a: WorkspaceDocument
  b: WorkspaceDocument
}) {
  const check = useMutation({ mutationFn: () => checkConflicts(workspaceId, a.id, b.id) })
  // 404, 409 and 503 (AI unavailable) come with a message for people.
  // Anything else: the server could not be reached.
  const errorMessage =
    check.error instanceof ApiError && [404, 409, 503].includes(check.error.status)
      ? check.error.message
      : UNREACHABLE_MESSAGE
  const result = check.data

  return (
    <div className="border-t border-line pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-xl">
          <h3 className="text-sm font-medium">Potential conflicts</h3>
          <p className="mt-1 text-sm text-ink-muted">
            Statements in the two documents that may contradict each other, such as different
            notice periods. The most alike passages are sent to Google Gemini.
          </p>
        </div>
        <Button
          variant={result ? 'secondary' : 'primary'}
          loading={check.isPending}
          onClick={() => check.mutate()}
        >
          {check.isPending ? 'Checking…' : result ? 'Check again' : 'Check for conflicts'}
        </Button>
      </div>

      <div aria-live="polite">
        {check.isPending && <FactsSkeleton />}
        {check.isError && !check.isPending && (
          <div className="mt-3">
            <FormError>{errorMessage}</FormError>
          </div>
        )}
        {result && !check.isPending && (
          <>
            <p className="mt-3 text-sm text-ink-muted">
              {result.potential_conflicts.length === 0
                ? `No potential conflicts in the ${result.checked_pairs} most alike passage pairs.`
                : `${result.potential_conflicts.length} potential ${
                    result.potential_conflicts.length === 1 ? 'conflict' : 'conflicts'
                  } in the ${result.checked_pairs} most alike passage pairs. Check each one: the quotes are real, the conflict is the AI's reading.`}
            </p>
            {result.dropped > 0 && (
              // Honest about what the checks threw away.
              <p className="mt-1 text-sm text-ink-muted">
                {result.dropped === 1 ? '1 answer was' : `${result.dropped} answers were`} left
                out because a quote couldn't be found in its document.
              </p>
            )}
            <ul className="mt-3 space-y-3">
              {result.potential_conflicts.map((conflict, index) => (
                <li key={index} className="rounded-sm border border-line bg-surface p-3">
                  <p className="text-xs font-semibold tracking-wide text-danger uppercase">
                    Potential conflict
                    {conflict.topic && (
                      <span className="font-medium tracking-normal text-ink normal-case">
                        {' '}
                        · {conflict.topic}
                      </span>
                    )}
                  </p>
                  <div className="mt-2 space-y-3">
                    {(
                      [
                        [a, conflict.a],
                        [b, conflict.b],
                      ] as const
                    ).map(([document, side]) => (
                      <div key={document.id} className="border-l-2 border-line-strong pl-3">
                        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                          <p className="text-sm">
                            <span className="text-ink-muted">{document.filename}:</span>{' '}
                            <span className="font-medium">{side.claim}</span>
                          </p>
                          <Place
                            workspaceId={workspaceId}
                            documentId={document.id}
                            sentence={side}
                          />
                        </div>
                        {/* The document's own words: the evidence. */}
                        <blockquote className="mt-1 font-serif text-[14px] leading-relaxed text-ink-muted">
                          “{side.quote}”
                        </blockquote>
                      </div>
                    ))}
                  </div>
                  {conflict.explanation && (
                    // Gemini's reasoning, marked as such: not evidence.
                    <p className="mt-3 text-sm text-ink-muted">
                      <span className="font-medium">AI's reading:</span> {conflict.explanation}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

// How many changes are shown at first, and added by each "Show more".
const PAGE = 5

// A long list shown PAGE items at a time, so a big comparison doesn't mean
// endless scrolling.
function ShowMore<T>({
  items,
  noun,
  render,
}: {
  items: T[]
  noun: string
  render: (item: T, index: number) => ReactNode
}) {
  const [count, setCount] = useState(PAGE)
  const left = items.length - count
  const next = Math.min(PAGE, left)
  const button =
    'rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent'

  return (
    <>
      <ul className="mt-3 space-y-3">{items.slice(0, count).map(render)}</ul>
      {(left > 0 || count > PAGE) && (
        <div className="mt-3 flex flex-wrap gap-4">
          {left > 0 && (
            <button type="button" className={button} onClick={() => setCount(count + PAGE)}>
              Show {next} more {next === 1 ? noun : `${noun}s`} ({left} left)
            </button>
          )}
          {/* Once more are shown, back to the first PAGE at any time. */}
          {count > PAGE && (
            <button type="button" className={button} onClick={() => setCount(PAGE)}>
              Show less
            </button>
          )}
        </div>
      )}
    </>
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
// Without a label: "p. 2 ↗".
function Place({
  label,
  workspaceId,
  documentId,
  sentence,
}: {
  label?: string
  workspaceId: string
  documentId: string
  sentence: Pick<Sentence, 'page_number' | 'heading'>
}) {
  if (sentence.page_number === null) {
    const heading = sentence.heading ?? 'Before the first heading'
    return <Tag>{label ? `${label}: ${heading}` : heading}</Tag>
  }
  return (
    <a
      href={`${documentFileUrl(workspaceId, documentId)}#page=${sentence.page_number}`}
      target="_blank"
      rel="noopener"
      className="rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
    >
      {label && `${label} `}p. {sentence.page_number} ↗
    </a>
  )
}

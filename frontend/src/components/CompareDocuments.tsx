import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
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
            <p className="text-sm text-ink-muted">
              {meaningful.length === 0
                ? 'No changes in wording.'
                : `${data.counts.changed} changed · ${data.counts.removed} removed · ${data.counts.added} added`}
            </p>
            {meaningful.length > 0 && (
              <ul className="mt-2 divide-y divide-line border-y border-line">
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
                <ul className="mt-2 divide-y divide-line">
                  {formatting.map((change, index) => (
                    <li key={index} className="py-2">
                      <p className="text-ink-muted">{change.old?.text}</p>
                      <p>{change.new?.text}</p>
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
  const words = change.kind === 'changed' && change.old && change.new
    ? changedWords(change.old.text, change.new.text)
    : null

  return (
    <li className="py-4">
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

      <div className="mt-1.5 space-y-1 font-serif text-[15px] leading-relaxed">
        {words ? (
          <>
            <p>
              {words.old.map(({ word, changed }, index) =>
                changed ? (
                  <del key={index} className="bg-danger-soft text-danger">
                    {word}{' '}
                  </del>
                ) : (
                  <span key={index}>{word} </span>
                ),
              )}
            </p>
            <p>
              {words.new.map(({ word, changed }, index) =>
                changed ? (
                  <ins key={index} className="bg-added-soft text-added no-underline">
                    {word}{' '}
                  </ins>
                ) : (
                  <span key={index}>{word} </span>
                ),
              )}
            </p>
          </>
        ) : change.kind === 'removed' ? (
          <p>
            <del className="bg-danger-soft text-danger">{change.old?.text}</del>
          </p>
        ) : (
          <p>
            <ins className="bg-added-soft text-added no-underline">{change.new?.text}</ins>
          </p>
        )}
      </div>
    </li>
  )
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

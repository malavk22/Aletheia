import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import {
  documentActionsKey,
  findActions,
  findActionsKey,
  formatDate,
  formatDay,
  getDocumentActions,
  updateAction,
  workspaceActionsKey,
} from '../api/actions.ts'
import type { Action, ActionChange } from '../api/actions.ts'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentFileUrl, documentsKey } from '../api/documents.ts'
import { Button } from './Button.tsx'
import { FormError } from './FormError.tsx'
import { FactsSkeleton } from './KeyFacts.tsx'
import { Tag } from './PassageResults.tsx'

// Why an action has its confidence: worked out by rules, so it can be explained.
const CONFIDENCE = {
  high: { label: 'High confidence', why: 'A full date is written in the document.' },
  medium: { label: 'Medium confidence', why: 'No full date is written, or there is no deadline.' },
  low: {
    label: 'Low confidence',
    why: 'The text was read by OCR, or the AI gave a date the document does not state.',
  },
}

const smallButton =
  'rounded-sm px-2 py-1 text-sm font-medium focus-visible:outline-2 focus-visible:outline-accent'

// A document's deadlines and tasks, found by the AI. They are suggestions
// until a person confirms them; only confirmed ones count. Finding calls
// Gemini, so it starts only when the person presses the button.
export function DocumentActions({
  workspaceId,
  documentId,
}: {
  workspaceId: string
  documentId: string
}) {
  const queryClient = useQueryClient()
  const key = documentActionsKey(workspaceId, documentId)
  const { data, isPending, error } = useQuery({
    queryKey: key,
    queryFn: () => getDocumentActions(workspaceId, documentId),
  })
  const finding = useMutation({
    // Lets the "Actions" button in the list show that this one is running.
    mutationKey: findActionsKey(documentId),
    mutationFn: () => findActions(workspaceId, documentId),
    onSuccess: (found) => {
      queryClient.setQueryData(key, found)
      queryClient.invalidateQueries({ queryKey: workspaceActionsKey(workspaceId) })
      return queryClient.invalidateQueries({ queryKey: documentsKey(workspaceId) })
    },
  })

  if (isPending) return <FactsSkeleton />
  if (error || !data) return <FormError>{UNREACHABLE_MESSAGE}</FormError>

  const searched = data.extracted_at !== null
  const findError =
    finding.error instanceof ApiError && [409, 429, 503].includes(finding.error.status)
      ? finding.error.message
      : UNREACHABLE_MESSAGE
  const dropped = finding.data?.dropped ?? 0
  const toReview = data.actions.filter((action) => action.status === 'suggested')
  const confirmed = data.actions.filter((action) => action.status === 'confirmed')
  const dismissed = data.actions.filter((action) => action.status === 'dismissed')
  const done = data.actions.filter((action) => action.status === 'done')

  return (
    <div className="mt-3 rounded-sm border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-medium">Actions</h3>
          <p className="mt-0.5 text-sm text-ink-muted">
            Deadlines and tasks found by AI. They count only once you confirm them.
          </p>
        </div>
        <Button
          variant="secondary"
          loading={finding.isPending}
          onClick={() => finding.mutate()}
        >
          {searched ? 'Find again' : 'Find actions'}
        </Button>
      </div>

      <div aria-live="polite">
        {finding.isPending && (
          <>
            <p className="mt-3 text-sm text-ink-muted">
              Reading the document… This can take up to a minute for a long document.
            </p>
            <FactsSkeleton />
          </>
        )}
        {finding.isError && !finding.isPending && (
          <div className="mt-3">
            <FormError>{findError}</FormError>
          </div>
        )}
        {searched && !finding.isPending && (
          <>
            {dropped > 0 && (
              <p className="mt-3 text-sm text-ink-muted">
                {dropped === 1 ? '1 action was' : `${dropped} actions were`} left out because
                its sentence couldn't be found on its page.
              </p>
            )}
            {data.actions.length === 0 && (
              <p className="mt-3 text-sm text-ink-muted">No actions found in this document.</p>
            )}
            <ActionGroup title="To review" actions={toReview} workspaceId={workspaceId} />
            <ActionGroup title="Confirmed" actions={confirmed} workspaceId={workspaceId} />
            {done.length > 0 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm text-ink-muted hover:text-ink">
                  Done ({done.length})
                </summary>
                <ActionGroup actions={done} workspaceId={workspaceId} />
              </details>
            )}
            {dismissed.length > 0 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm text-ink-muted hover:text-ink">
                  Dismissed ({dismissed.length})
                </summary>
                <ActionGroup actions={dismissed} workspaceId={workspaceId} />
              </details>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ActionGroup({
  title,
  actions,
  workspaceId,
}: {
  title?: string
  actions: Action[]
  workspaceId: string
}) {
  if (actions.length === 0) return null
  return (
    <section className="mt-4">
      {title && (
        <h4 className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
          {title} ({actions.length})
        </h4>
      )}
      <ul className="mt-2 space-y-3">
        {actions.map((action) => (
          <ActionCard key={action.id} workspaceId={workspaceId} action={action} />
        ))}
      </ul>
    </section>
  )
}

function ActionCard({ workspaceId, action }: { workspaceId: string; action: Action }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const change = useMutation({
    mutationFn: (body: ActionChange) => updateAction(workspaceId, action.id, body),
    onSuccess: () => {
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: workspaceActionsKey(workspaceId) })
      return queryClient.invalidateQueries({
        queryKey: documentActionsKey(workspaceId, action.document_id),
      })
    },
  })
  const changeError =
    change.error instanceof ApiError && change.error.status === 422
      ? change.error.message
      : UNREACHABLE_MESSAGE
  const confidence = CONFIDENCE[action.confidence]

  return (
    <li
      className={`rounded-sm border p-3 ${['dismissed', 'done'].includes(action.status) ? 'border-line bg-paper' : 'border-line bg-surface'}`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold tracking-wide text-ink-muted uppercase">{action.kind}</span>
        <span
          title={confidence.why}
          className={`rounded-sm px-1.5 py-0.5 font-medium ${
            action.confidence === 'low' ? 'bg-danger-soft text-danger' : 'bg-paper-deep text-ink-muted'
          }`}
        >
          {confidence.label}
        </span>
        {action.source === 'ocr' && <Tag>Read by OCR</Tag>}
        <span className="ml-auto">
          <PageLink workspaceId={workspaceId} action={action} />
        </span>
      </div>

      <p className="mt-1.5 text-sm">
        <span className="font-medium">{action.title}</span>
        {action.responsible && <span className="text-ink-muted"> · {action.responsible}</span>}
      </p>
      <When action={action} />
      {/* The document's own words: the evidence. */}
      <blockquote className="mt-2 border-l-2 border-line-strong pl-3 font-serif text-[14px] leading-relaxed text-ink-muted">
        “{action.quote}”
      </blockquote>

      {editing ? (
        <EditForm
          action={action}
          saving={change.isPending}
          onSave={(body) => change.mutate(body)}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {action.status === 'suggested' && (
            <>
              <button
                type="button"
                className="rounded-sm bg-accent px-3 py-1 text-sm font-medium text-on-fill hover:bg-accent-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-60"
                disabled={change.isPending}
                onClick={() => change.mutate({ status: 'confirmed' })}
              >
                Confirm
              </button>
              <button type="button" className={`${smallButton} text-ink-muted hover:text-ink`} onClick={() => setEditing(true)}>
                Edit
              </button>
              <button
                type="button"
                className={`${smallButton} text-ink-muted hover:text-danger`}
                disabled={change.isPending}
                onClick={() => change.mutate({ status: 'dismissed' })}
              >
                Dismiss
              </button>
            </>
          )}
          {action.status === 'confirmed' && (
            <>
              <span className="mr-1 text-sm font-medium text-added">✓ Confirmed</span>
              <button
                type="button"
                className={`${smallButton} text-added hover:underline`}
                disabled={change.isPending}
                onClick={() => change.mutate({ status: 'done' })}
              >
                Mark done
              </button>
              <button type="button" className={`${smallButton} text-ink-muted hover:text-ink`} onClick={() => setEditing(true)}>
                Edit
              </button>
              <button
                type="button"
                className={`${smallButton} text-ink-muted hover:text-ink`}
                disabled={change.isPending}
                onClick={() => change.mutate({ status: 'suggested' })}
              >
                Undo
              </button>
            </>
          )}
          {action.status === 'done' && action.done_at !== null && (
            <>
              <span className="mr-1 text-sm font-medium text-added">
                ✓ Done {formatDay(action.done_at)}
              </span>
              {/* Back to confirmed: it counts again in Upcoming. */}
              <button
                type="button"
                className={`${smallButton} text-ink-muted hover:text-ink`}
                disabled={change.isPending}
                onClick={() => change.mutate({ status: 'confirmed' })}
              >
                Undo
              </button>
            </>
          )}
          {action.status === 'dismissed' && (
            <button
              type="button"
              className={`${smallButton} text-ink-muted hover:text-ink`}
              disabled={change.isPending}
              onClick={() => change.mutate({ status: 'suggested' })}
            >
              Restore
            </button>
          )}
        </div>
      )}
      {change.isError && (
        <div className="mt-2">
          <FormError>{changeError}</FormError>
        </div>
      )}
    </li>
  )
}

// When the action is due, with exact dates and relative deadlines clearly
// apart, and a date a person set marked as theirs.
function When({ action }: { action: Action }) {
  if (action.due_kind === 'none' && action.due_date === null) {
    return <p className="mt-1 text-sm text-ink-muted">No deadline</p>
  }
  const badge =
    action.due_kind === 'exact' ? (
      <span className="rounded-sm border border-accent px-1.5 text-xs font-medium text-accent">
        Exact date
      </span>
    ) : action.due_kind === 'relative' ? (
      <span className="rounded-sm bg-highlight px-1.5 text-xs font-medium text-ink">Relative</span>
    ) : null

  return (
    <p className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
      {badge}
      {action.due_date !== null && (
        <span className="font-medium">
          {formatDate(action.due_date)}
          <span className="font-normal text-ink-muted">
            {action.due_date_source === 'person' ? ' · set by you' : ' · from the document'}
          </span>
        </span>
      )}
      {/* The document's own words, unless they are just the same date. */}
      {action.due_text && !(action.due_kind === 'exact' && action.due_date_source === 'document') && (
        <span className="text-ink-muted">
          the document says “{action.due_text}”
        </span>
      )}
      {action.due_kind === 'relative' && action.due_date === null && (
        <span className="text-ink-muted">· no date yet</span>
      )}
    </p>
  )
}

function EditForm({
  action,
  saving,
  onSave,
  onCancel,
}: {
  action: Action
  saving: boolean
  onSave: (body: ActionChange) => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(action.title)
  const [dueDate, setDueDate] = useState(action.due_date ?? '')
  const input =
    'mt-1 block w-full rounded-sm border border-line-strong bg-surface px-2 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-accent'

  function save(event: FormEvent) {
    event.preventDefault()
    // Only what changed is sent; an emptied date is cleared.
    const body: ActionChange = {}
    if (title.trim() !== action.title) body.title = title
    if (dueDate !== (action.due_date ?? '')) body.due_date = dueDate === '' ? null : dueDate
    if (Object.keys(body).length === 0) onCancel()
    else onSave(body)
  }

  return (
    <form className="mt-3 space-y-3 rounded-sm bg-paper p-3" onSubmit={save}>
      <label className="block text-sm font-medium">
        Title
        <input className={input} value={title} required maxLength={300} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label className="block text-sm font-medium">
        Due date
        <input
          className={input}
          type="date"
          value={dueDate}
          // An exact deadline always keeps a date.
          required={action.due_kind === 'exact'}
          onChange={(e) => setDueDate(e.target.value)}
        />
        <span className="mt-1 block text-xs font-normal text-ink-muted">
          {action.due_kind === 'relative'
            ? `The document says “${action.due_text}”: set the date it works out to. It will be marked as set by you.`
            : 'A date you set is marked as set by you.'}
        </span>
      </label>
      <div className="flex gap-2">
        <Button type="submit" loading={saving}>
          Save
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function PageLink({ workspaceId, action }: { workspaceId: string; action: Action }) {
  if (action.page_number === null) {
    return <Tag>{action.heading ?? 'Before the first heading'}</Tag>
  }
  return (
    <a
      href={`${documentFileUrl(workspaceId, action.document_id)}#page=${action.page_number}`}
      target="_blank"
      rel="noopener"
      className="rounded-sm text-sm font-medium text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
    >
      p. {action.page_number} ↗
    </a>
  )
}

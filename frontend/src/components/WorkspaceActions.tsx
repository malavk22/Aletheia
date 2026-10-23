import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { formatDate, formatDay, listWorkspaceActions, workspaceActionsKey } from '../api/actions.ts'
import type { Action } from '../api/actions.ts'
import { UNREACHABLE_MESSAGE } from '../api/client.ts'
import { PageLink } from './DocumentActions.tsx'
import { FormError } from './FormError.tsx'
import { FactsSkeleton } from './KeyFacts.tsx'

// Due within this many days from today counts as upcoming.
const SOON_DAYS = 14

const TABS = [
  { id: 'upcoming', label: 'Upcoming' },
  { id: 'timeline', label: 'Timeline' },
  { id: 'undated', label: 'No fixed date' },
] as const
type Tab = (typeof TABS)[number]['id']

type Dated = Action & { due_date: string }

// Today in the viewer's own calendar, as YYYY-MM-DD.
function localToday() {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// Whole days from `from` to `to` (both YYYY-MM-DD); negative if `to` is earlier.
function daysBetween(from: string, to: string) {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000)
}

// Confirmed and done actions sorted into the three tabs. `actions` come from
// the API dated first, by date, so every group keeps that order. Done ones
// are never overdue or upcoming: they stay in the timeline as history.
function groupActions(actions: Action[], today: string) {
  const dated = actions.filter((action): action is Dated => action.due_date !== null)
  const toDo = dated.filter((action) => action.status !== 'done')
  const overdue = toDo.filter((action) => daysBetween(today, action.due_date) < 0)
  const soon = toDo.filter((action) => {
    const days = daysBetween(today, action.due_date)
    return days >= 0 && days <= SOON_DAYS
  })
  // "2026-03" → its actions, in date order.
  const months = new Map<string, Dated[]>()
  for (const action of dated) {
    const month = action.due_date.slice(0, 7)
    months.set(month, [...(months.get(month) ?? []), action])
  }
  // Still to do first, then done.
  const undated = actions
    .filter((action) => action.due_date === null)
    .sort((a, b) => Number(a.status === 'done') - Number(b.status === 'done'))
  return { dated, overdue, soon, months: [...months], undated }
}

// "March 2026" for "2026-03".
function formatMonth(month: string) {
  return new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(
    new Date(`${month}-01T00:00:00Z`),
  )
}

// The confirmed (and done) actions of every document in the workspace: what
// is overdue or coming up, all dated ones by month, and those with no date. A reminder in
// the page only: nothing is sent by email or phone.
export function WorkspaceActions({ workspaceId }: { workspaceId: string }) {
  const [tab, setTab] = useState<Tab>('upcoming')
  const { data, isPending, error } = useQuery({
    // Under the workspace's actions key, so every change in a panel refreshes it.
    queryKey: [...workspaceActionsKey(workspaceId), 'confirmed', 'done'],
    queryFn: () => listWorkspaceActions(workspaceId, ['confirmed', 'done']),
  })

  if (isPending) return <FactsSkeleton />
  if (error || !data) return <FormError>{UNREACHABLE_MESSAGE}</FormError>
  if (data.length === 0) {
    return (
      <p className="border-t border-line pt-4 text-sm text-ink-muted">
        No confirmed actions yet. Open a document's Actions and confirm the ones that apply.
      </p>
    )
  }

  const today = localToday()
  const groups = groupActions(data, today)
  const counts = {
    upcoming: groups.overdue.length + groups.soon.length,
    timeline: groups.dated.length,
    undated: groups.undated.length,
  }

  return (
    <div className="space-y-4">
      <p className="text-sm" aria-live="polite">
        {counts.upcoming === 0 ? (
          <span className="text-ink-muted">Nothing overdue or due in the next {SOON_DAYS} days.</span>
        ) : (
          <>
            {groups.overdue.length > 0 && (
              <span className="font-medium text-danger">{groups.overdue.length} overdue</span>
            )}
            {groups.overdue.length > 0 && groups.soon.length > 0 && ' · '}
            {groups.soon.length > 0 && (
              <span className="font-medium">
                {groups.soon.length} due in the next {SOON_DAYS} days
              </span>
            )}
          </>
        )}
      </p>

      <div role="tablist" aria-label="Confirmed actions" className="flex gap-1 border-b border-line">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-accent ${
              tab === id ? 'border-accent text-accent' : 'border-transparent text-ink-muted hover:text-ink'
            }`}
            onClick={() => setTab(id)}
          >
            {label} ({counts[id]})
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {tab === 'upcoming' &&
          (counts.upcoming === 0 ? (
            <Empty>Nothing here. Dated actions further ahead are in Timeline.</Empty>
          ) : (
            <>
              <Group title="Overdue" actions={groups.overdue} workspaceId={workspaceId} today={today} />
              <Group
                title={`Next ${SOON_DAYS} days`}
                actions={groups.soon}
                workspaceId={workspaceId}
                today={today}
              />
            </>
          ))}
        {tab === 'timeline' &&
          (groups.months.length === 0 ? (
            <Empty>No confirmed action has a date yet.</Empty>
          ) : (
            groups.months.map(([month, actions]) => (
              <Group
                key={month}
                title={formatMonth(month)}
                actions={actions}
                workspaceId={workspaceId}
                today={today}
              />
            ))
          ))}
        {tab === 'undated' &&
          (groups.undated.length === 0 ? (
            <Empty>Every confirmed action has a date.</Empty>
          ) : (
            <>
              <p className="text-sm text-ink-muted">
                Set a date in the document's Actions to move one onto the timeline.
              </p>
              <Group actions={groups.undated} workspaceId={workspaceId} today={today} />
            </>
          ))}
      </div>
    </div>
  )
}

function Empty({ children }: { children: string }) {
  return <p className="text-sm text-ink-muted">{children}</p>
}

function Group({
  title,
  actions,
  workspaceId,
  today,
}: {
  title?: string
  actions: Action[]
  workspaceId: string
  today: string
}) {
  if (actions.length === 0) return null
  return (
    <section className="mt-4 first:mt-0">
      {title && (
        <h3 className="text-xs font-semibold tracking-wide text-ink-muted uppercase">
          {title} ({actions.length})
        </h3>
      )}
      <ul className="mt-1 divide-y divide-line">
        {actions.map((action) => (
          <ActionRow key={action.id} workspaceId={workspaceId} action={action} today={today} />
        ))}
      </ul>
    </section>
  )
}

// One line per action: when, what and who, and which document and page.
// The quote stays in the document's Actions panel.
function ActionRow({ workspaceId, action, today }: { workspaceId: string; action: Action; today: string }) {
  const done = action.status === 'done' && action.done_at !== null
  return (
    <li className={`flex gap-4 py-2.5 ${done ? 'opacity-60' : ''}`}>
      <div className="w-28 shrink-0 text-sm">
        {action.due_date !== null ? (
          <>
            <p className="font-medium">{formatDate(action.due_date)}</p>
            {done ? null : <DueLabel days={daysBetween(today, action.due_date)} />}
          </>
        ) : action.due_kind === 'relative' ? (
          <span className="rounded-sm bg-highlight px-1.5 text-xs font-medium text-ink">Relative</span>
        ) : (
          <p className="text-ink-muted">No deadline</p>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm">
          <span className={`font-medium ${done ? 'line-through' : ''}`}>{action.title}</span>
          {action.responsible && <span className="text-ink-muted"> · {action.responsible}</span>}
          {done && action.done_at !== null && (
            <span className="ml-2 text-xs font-medium text-added">✓ Done {formatDay(action.done_at)}</span>
          )}
        </p>
        {action.due_date === null && action.due_text && (
          <p className="mt-0.5 text-sm text-ink-muted">the document says “{action.due_text}”</p>
        )}
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-ink-muted">
          <span className="truncate">{action.filename}</span>
          <PageLink workspaceId={workspaceId} action={action} />
          {action.due_date_source !== null && (
            <span>
              · {action.due_date_source === 'person' ? 'date set by you' : 'date from the document'}
            </span>
          )}
        </p>
      </div>
    </li>
  )
}

function DueLabel({ days }: { days: number }) {
  if (days < 0) {
    return (
      <p className="text-xs font-medium text-danger">
        Overdue · {days === -1 ? '1 day' : `${-days} days`} late
      </p>
    )
  }
  if (days === 0) return <p className="text-xs font-medium text-accent">Due today</p>
  if (days === 1) return <p className="text-xs text-ink-muted">Tomorrow</p>
  if (days <= SOON_DAYS) return <p className="text-xs text-ink-muted">In {days} days</p>
  return null
}

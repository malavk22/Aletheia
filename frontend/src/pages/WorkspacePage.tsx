import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { getWorkspace, workspaceKey } from '../api/workspaces.ts'
import { AppHeader } from '../components/AppHeader.tsx'
import { AskQuestion } from '../components/AskQuestion.tsx'
import { Button } from '../components/Button.tsx'
import { CompareDocuments } from '../components/CompareDocuments.tsx'
import { DeleteWorkspace } from '../components/DeleteWorkspace.tsx'
import { DocumentList } from '../components/DocumentList.tsx'
import { FormError } from '../components/FormError.tsx'
import { UploadDocuments } from '../components/UploadDocuments.tsx'
import { WorkspaceActions } from '../components/WorkspaceActions.tsx'

// The workspace's tabs, one job each. The open one is in the address
// (?tab=documents), so Back, refresh and shared links keep it.
const TABS = [
  { id: 'ask', label: 'Ask' },
  { id: 'documents', label: 'Documents' },
  { id: 'actions', label: 'Actions' },
  { id: 'compare', label: 'Compare' },
  { id: 'settings', label: 'Settings' },
] as const

type TabId = (typeof TABS)[number]['id']

// One workspace: its name and tabs. The id comes from the address,
// /workspaces/<id>.
export function WorkspacePage() {
  const { workspaceId = '' } = useParams()
  const [searchParams] = useSearchParams()
  // An unknown or missing tab opens Ask.
  const tab: TabId = TABS.find((t) => t.id === searchParams.get('tab'))?.id ?? 'ask'
  const {
    data: workspace,
    isPending,
    error,
    refetch,
  } = useQuery({ queryKey: workspaceKey(workspaceId), queryFn: () => getWorkspace(workspaceId) })

  // 404: not a member, or no such workspace (the backend does not say which).
  // 422: the address does not even contain a valid id.
  const notFound = error instanceof ApiError && (error.status === 404 || error.status === 422)

  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="px-6 py-12 sm:px-12">
        <Link to="/" className="text-sm text-ink-muted hover:text-ink">
          ← All workspaces
        </Link>

        {isPending && <p className="mt-6 text-sm text-ink-muted">Loading workspace…</p>}

        {notFound && (
          <div className="mt-6">
            <h1 className="font-serif text-3xl font-semibold tracking-tight">Workspace not found</h1>
            <p className="mt-2 text-sm text-ink-muted">
              It may have been removed, or you may not have access to it.
            </p>
          </div>
        )}

        {error && !notFound && (
          <div className="mt-6 max-w-2xl space-y-3">
            <FormError>{UNREACHABLE_MESSAGE}</FormError>
            <Button variant="secondary" onClick={() => refetch()}>
              Try again
            </Button>
          </div>
        )}

        {workspace && (
          <>
            <h1 className="mt-4 font-serif text-3xl font-semibold tracking-tight">
              {workspace.name}
            </h1>
            <p className="mt-2 text-sm text-ink-muted">
              Documents in this workspace are only visible to its members.
            </p>
            <nav aria-label="Workspace" className="mt-8 flex gap-1 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-line)]">
              {TABS.map((t) => (
                <Link
                  key={t.id}
                  to={`?tab=${t.id}`}
                  aria-current={t.id === tab ? 'page' : undefined}
                  className={`relative px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
                    t.id === tab ? 'text-ink' : 'text-ink-muted hover:text-ink'
                  }`}
                >
                  {t.label}
                  {/* One underline that slides from the old tab to the new one
                      (same layoutId: motion animates it between places). */}
                  {t.id === tab && (
                    <motion.span
                      layoutId="tab-underline"
                      transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                      className="absolute inset-x-0 bottom-0 h-0.5 bg-accent"
                    />
                  )}
                </Link>
              ))}
            </nav>
            {/* Every tab stays mounted and only the open one shows, so moving
                between tabs keeps a typed question, an answer or an upload. */}
            <div className="mt-10 max-w-3xl">
              <TabPanel open={tab === 'ask'}>
                <AskQuestion workspaceId={workspace.id} />
              </TabPanel>
              <TabPanel open={tab === 'documents'}>
                <section aria-labelledby="documents-heading" className="space-y-6">
                  <div>
                    <h2 id="documents-heading" className="font-serif text-xl font-semibold tracking-tight">
                      Documents
                    </h2>
                    <p className="mt-1 text-sm text-ink-muted">
                      Ask, Key facts and Actions use Google Gemini: the relevant text of your
                      documents is sent to Google.
                    </p>
                  </div>
                  <UploadDocuments workspaceId={workspace.id} />
                  <DocumentList workspaceId={workspace.id} />
                </section>
              </TabPanel>
              <TabPanel open={tab === 'actions'}>
                <section aria-labelledby="actions-heading" className="space-y-6">
                  <div>
                    <h2 id="actions-heading" className="font-serif text-xl font-semibold tracking-tight">
                      Actions
                    </h2>
                    <p className="mt-1 text-sm text-ink-muted">
                      The deadlines and tasks you confirmed, from every document.
                    </p>
                  </div>
                  <WorkspaceActions workspaceId={workspace.id} />
                </section>
              </TabPanel>
              <TabPanel open={tab === 'compare'}>
                <section aria-labelledby="compare-heading" className="space-y-6">
                  <div>
                    <h2 id="compare-heading" className="font-serif text-xl font-semibold tracking-tight">
                      Compare versions
                    </h2>
                    <p className="mt-1 text-sm text-ink-muted">
                      What changed between two documents, sentence by sentence. Runs without AI.
                    </p>
                  </div>
                  <CompareDocuments workspaceId={workspace.id} />
                </section>
              </TabPanel>
              <TabPanel open={tab === 'settings'}>
                <DeleteWorkspace workspace={workspace} />
              </TabPanel>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

// A tab's content rises in slightly each time it opens.
function TabPanel({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <motion.div
      hidden={!open}
      initial={false}
      animate={open ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}

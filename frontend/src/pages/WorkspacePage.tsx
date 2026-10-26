import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentsKey, listDocuments } from '../api/documents.ts'
import { getWorkspace, workspaceKey } from '../api/workspaces.ts'
import { AppHeader } from '../components/AppHeader.tsx'
import { AskQuestion } from '../components/AskQuestion.tsx'
import { Button } from '../components/Button.tsx'
import { CompareDocuments } from '../components/CompareDocuments.tsx'
import { DeleteWorkspace } from '../components/DeleteWorkspace.tsx'
import { DocumentList } from '../components/DocumentList.tsx'
import { DropFiles } from '../components/DropFiles.tsx'
import { FormError } from '../components/FormError.tsx'
import { UploadDocuments } from '../components/UploadDocuments.tsx'
import { WorkspaceActions } from '../components/WorkspaceActions.tsx'
import { useUploads } from '../hooks/useUploads.ts'
import { TABS } from '../workspaceTabs.ts'
import type { TabId } from '../workspaceTabs.ts'
import type { Uploads } from '../hooks/useUploads.ts'

// One workspace: its name and tabs. The id comes from the address,
// /workspaces/<id>.
export function WorkspacePage() {
  const { workspaceId = '' } = useParams()
  const [searchParams] = useSearchParams()
  // An unknown or missing tab opens Ask.
  const tab: TabId = TABS.find((t) => t.id === searchParams.get('tab'))?.id ?? 'ask'
  const navigate = useNavigate()
  const uploads = useUploads(workspaceId)
  // Shared with the Documents tab's list (same key): asked for once.
  const { data: documents } = useQuery({
    queryKey: documentsKey(workspaceId),
    queryFn: () => listDocuments(workspaceId),
  })

  // Dropped files go up at once; the Documents tab shows their progress.
  function uploadDropped(files: File[]) {
    navigate('?tab=documents')
    uploads.upload(files)
  }
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

        {isPending && (
          <div aria-hidden="true" className="mt-6 animate-pulse">
            <div className="h-8 w-64 rounded-sm bg-paper-deep" />
            <div className="mt-3 h-3.5 w-80 max-w-full rounded-sm bg-paper-deep" />
            <div className="mt-8 h-9 w-96 max-w-full rounded-sm bg-paper-deep" />
          </div>
        )}
        {isPending && <p className="sr-only">Loading workspace…</p>}

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
          <DropFiles target={workspace.name} onDrop={uploadDropped}>
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
                {documents?.length === 0 && <GettingStarted uploads={uploads} />}
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
                  <UploadDocuments uploads={uploads} />
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
          </DropFiles>
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

// On Ask while the workspace has no documents: what to do first, with the
// Upload button right here.
function GettingStarted({ uploads }: { uploads: Uploads }) {
  const steps = [
    ['Upload documents', 'PDF or Word files, or drop them anywhere on this page.'],
    ['Ask a question', 'In your own words, as you would ask a colleague.'],
    ['Check the sources', 'Every answer points to the page it came from.'],
  ]
  return (
    <div className="mb-10 rounded-lg border border-line bg-surface p-6 shadow-xs">
      <h2 className="font-serif text-xl font-semibold tracking-tight">Start here</h2>
      <ol className="mt-4 space-y-3">
        {steps.map(([title, detail], index) => (
          <li key={title} className="flex gap-3">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-paper-deep text-xs font-semibold text-accent">
              {index + 1}
            </span>
            <p className="text-sm">
              <span className="font-medium">{title}</span>
              <span className="text-ink-muted"> — {detail}</span>
            </p>
          </li>
        ))}
      </ol>
      <div className="mt-6">
        <UploadDocuments uploads={uploads} />
      </div>
    </div>
  )
}

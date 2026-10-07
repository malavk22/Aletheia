import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { getWorkspace, workspaceKey } from '../api/workspaces.ts'
import { AppHeader } from '../components/AppHeader.tsx'
import { Button } from '../components/Button.tsx'
import { DeleteWorkspace } from '../components/DeleteWorkspace.tsx'
import { DocumentList } from '../components/DocumentList.tsx'
import { FormError } from '../components/FormError.tsx'
import { SearchDocuments } from '../components/SearchDocuments.tsx'
import { UploadDocuments } from '../components/UploadDocuments.tsx'

// One workspace: its name, search, an upload button, and its documents.
// The id comes from the address, /workspaces/<id>.
export function WorkspacePage() {
  const { workspaceId = '' } = useParams()
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
            <div className="mt-10 max-w-3xl space-y-14">
              <SearchDocuments workspaceId={workspace.id} />
              <section aria-labelledby="documents-heading" className="space-y-6">
                <h2 id="documents-heading" className="font-serif text-xl font-semibold tracking-tight">
                  Documents
                </h2>
                <UploadDocuments workspaceId={workspace.id} />
                <DocumentList workspaceId={workspace.id} />
              </section>
            </div>
            <div className="mt-16">
              <DeleteWorkspace workspace={workspace} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}

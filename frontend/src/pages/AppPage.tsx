import { AppHeader } from '../components/AppHeader.tsx'
import { CreateWorkspaceForm } from '../components/CreateWorkspaceForm.tsx'
import { WorkspaceList } from '../components/WorkspaceList.tsx'

// The signed-in home page: the person's workspaces.
export function AppPage() {
  return (
    <div className="min-h-screen">
      <AppHeader />
      <main className="px-6 py-12 sm:px-12">
        <h1 className="font-serif text-3xl font-semibold tracking-tight">Workspaces</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Each workspace keeps its own set of documents.
        </p>
        <div className="mt-8 max-w-2xl space-y-8">
          <CreateWorkspaceForm />
          <WorkspaceList />
        </div>
      </main>
    </div>
  )
}

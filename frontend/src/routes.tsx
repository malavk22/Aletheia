import { createBrowserRouter } from 'react-router'
import { GuestOnly, RequireAuth } from './components/AuthGuards.tsx'
import { AppPage } from './pages/AppPage.tsx'
import { DocumentPage } from './pages/DocumentPage.tsx'
import { LoginPage } from './pages/LoginPage.tsx'
import { RegisterPage } from './pages/RegisterPage.tsx'
import { WorkspacePage } from './pages/WorkspacePage.tsx'

// The address -> page map. Each group sits behind a guard (see AuthGuards).
export const router = createBrowserRouter([
  {
    element: <RequireAuth />,
    children: [
      { path: '/', element: <AppPage /> },
      { path: '/workspaces/:workspaceId', element: <WorkspacePage /> },
      {
        path: '/workspaces/:workspaceId/documents/:documentId',
        element: <DocumentPage />,
      },
    ],
  },
  {
    element: <GuestOnly />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
    ],
  },
])

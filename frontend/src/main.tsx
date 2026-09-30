import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import '@fontsource-variable/inter'
import '@fontsource-variable/source-serif-4'
// Display typeface for the large wordmark (see --font-display in index.css).
// opsz.css includes its "optical size" axis, which AnimatedWordmark uses to get
// the sharp large-size cut.
import '@fontsource-variable/newsreader/opsz.css'
import './index.css'
import { ApiError } from './api/client.ts'
import { clearSession } from './hooks/useCurrentUser.ts'
import { router } from './routes.tsx'

// If any request comes back 401, the session has ended (expired, or logged out
// elsewhere). Sign the page out so the guard shows the sign-in page.
function handleError(error: unknown) {
  if (error instanceof ApiError && error.status === 401) clearSession(queryClient)
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleError }),
  mutationCache: new MutationCache({ onError: handleError }),
  // Fail straight away instead of retrying three times, so errors show quickly.
  defaultOptions: { queries: { retry: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)

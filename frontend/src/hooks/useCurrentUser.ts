import { useQuery } from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import { getCurrentUser } from '../api/auth.ts'

export const currentUserKey = ['current-user']

// Asks the backend "who am I?". data is the user, or null when signed out.
// The session cookie is HttpOnly, so asking is the only way the page can know.
export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserKey,
    queryFn: getCurrentUser,
    // The answer only changes when we log in or out, and those update it directly.
    staleTime: Infinity,
    retry: false,
  })
}

// Signs the page out: the route guard sees no user and shows the sign-in page.
// Everything fetched for that user is dropped too, so the next person to sign
// in on this browser never sees a flash of someone else's data.
export function clearSession(queryClient: QueryClient) {
  queryClient.setQueryData(currentUserKey, null)
  queryClient.removeQueries({
    predicate: (query) => query.queryKey[0] !== currentUserKey[0],
  })
}

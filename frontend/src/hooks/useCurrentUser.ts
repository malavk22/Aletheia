import { useQuery } from '@tanstack/react-query'
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

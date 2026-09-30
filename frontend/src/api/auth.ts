import { api, ApiError } from './client.ts'

export type User = {
  id: string
  email: string
}

export type Credentials = {
  email: string
  password: string
}

export function register(credentials: Credentials) {
  return api<User>('/auth/register', { method: 'POST', body: credentials })
}

export function login(credentials: Credentials) {
  return api<User>('/auth/login', { method: 'POST', body: credentials })
}

export function logout() {
  return api<void>('/auth/logout', { method: 'POST' })
}

// "Not signed in" (401) is a normal answer here, not a failure, so it becomes
// null. Anything else (server down, 500) is still thrown.
export async function getCurrentUser(): Promise<User | null> {
  try {
    return await api<User>('/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

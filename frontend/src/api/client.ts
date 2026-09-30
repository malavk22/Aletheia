// An error response from the API (any status that is not 2xx).
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Shown when a request fails for a reason the page has no specific message for
// (backend not running, network down, unexpected server error).
export const UNREACHABLE_MESSAGE = "Can't reach the server. Try again."

type ApiOptions = {
  method?: string
  body?: unknown
}

// The one place that talks to the backend. Paths are relative to /api/v1, which
// the Vite dev proxy forwards to FastAPI, so the session cookie is sent
// automatically.
export async function api<T>(path: string, { method = 'GET', body }: ApiOptions = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const detail = typeof data?.detail === 'string' ? data.detail : 'Request failed'
    throw new ApiError(response.status, detail)
  }

  // 204 No Content (logout) has no body to read.
  if (response.status === 204) return undefined as T
  return response.json()
}

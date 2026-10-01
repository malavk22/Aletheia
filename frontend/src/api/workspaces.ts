import { api } from './client.ts'

export type Workspace = {
  id: string
  name: string
}

// The name TanStack Query stores the list under. Anything that changes the
// list (creating a workspace) marks this key as out of date.
export const workspacesKey = ['workspaces']

export function workspaceKey(workspaceId: string) {
  return ['workspaces', workspaceId]
}

export function getWorkspace(workspaceId: string) {
  return api<Workspace>(`/workspaces/${workspaceId}`)
}

export function listWorkspaces() {
  return api<Workspace[]>('/workspaces')
}

export function createWorkspace(name: string) {
  return api<Workspace>('/workspaces', { method: 'POST', body: { name } })
}

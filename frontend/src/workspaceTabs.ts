// The workspace's tabs, one job each. The open one is in the address
// (?tab=documents), so Back, refresh and shared links keep it. Also listed by
// Quick search.
export const TABS = [
  { id: 'ask', label: 'Ask' },
  { id: 'documents', label: 'Documents' },
  { id: 'actions', label: 'Actions' },
  { id: 'compare', label: 'Compare' },
  { id: 'settings', label: 'Settings' },
] as const

export type TabId = (typeof TABS)[number]['id']

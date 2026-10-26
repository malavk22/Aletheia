import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { useNavigate, useParams } from 'react-router'
import { documentFileUrl, documentsKey, listDocuments } from '../api/documents.ts'
import { listWorkspaces, workspacesKey } from '../api/workspaces.ts'
import { TABS } from '../workspaceTabs.ts'

type Item = {
  id: string
  group: string
  label: string
  run: () => void
}

const IS_MAC = navigator.platform.toUpperCase().includes('MAC')

// Ctrl+K (⌘K on a Mac), or the Search button in the header: jump to a tab of
// this workspace, open one of its documents, or go to another workspace,
// by typing a few letters.
export function QuickSearch() {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [open, setOpen] = useState(false)

  function show() {
    setOpen(true)
    dialogRef.current?.showModal()
  }

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        // Otherwise the browser focuses its own address bar search.
        event.preventDefault()
        if (!dialogRef.current?.open) show()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <>
      <button
        type="button"
        onClick={show}
        className="inline-flex h-8 items-center gap-3 rounded-sm border border-line bg-surface px-2.5 text-sm text-ink-muted shadow-xs transition-colors hover:border-line-strong hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
      >
        Search
        <kbd className="hidden rounded border border-line px-1 font-sans text-xs sm:inline">
          {IS_MAC ? '⌘K' : 'Ctrl K'}
        </kbd>
      </button>
      {/* A native dialog: it keeps focus inside, closes on Escape and
          returns focus to where it was. */}
      <dialog
        ref={dialogRef}
        aria-label="Quick search"
        onClose={() => setOpen(false)}
        // A click on the dimmed backdrop lands on the dialog itself: close.
        onClick={(event) => event.target === dialogRef.current && dialogRef.current.close()}
        className="mx-auto mt-[12vh] w-[min(36rem,calc(100%-2rem))] overflow-hidden rounded-xl border border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/50 backdrop:backdrop-blur-sm"
      >
        {/* Mounted only while open: it starts empty each time, and the lists
            are asked for only when needed. */}
        {open && <Palette onDone={() => dialogRef.current?.close()} />}
      </dialog>
    </>
  )
}

function Palette({ onDone }: { onDone: () => void }) {
  const navigate = useNavigate()
  const { workspaceId } = useParams()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const { data: workspaces } = useQuery({ queryKey: workspacesKey, queryFn: listWorkspaces })
  const { data: documents } = useQuery({
    queryKey: documentsKey(workspaceId ?? ''),
    queryFn: () => listDocuments(workspaceId ?? ''),
    enabled: workspaceId !== undefined,
  })

  const all: Item[] = [
    ...(workspaceId
      ? TABS.map((tab) => ({
          id: `tab-${tab.id}`,
          group: 'This workspace',
          label: tab.label,
          run: () => navigate(`/workspaces/${workspaceId}?tab=${tab.id}`),
        }))
      : []),
    ...(documents ?? []).map((document) => ({
      id: `document-${document.id}`,
      group: 'Documents',
      label: document.filename,
      // A PDF opens in a new tab; a Word file downloads (as in the list).
      run: () => {
        const url = documentFileUrl(workspaceId ?? '', document.id)
        if (document.content_type === 'application/pdf') window.open(url, '_blank', 'noopener')
        else window.location.assign(url)
      },
    })),
    ...(workspaces ?? [])
      .filter((workspace) => workspace.id !== workspaceId)
      .map((workspace) => ({
        id: `workspace-${workspace.id}`,
        group: 'Workspaces',
        label: workspace.name,
        run: () => navigate(`/workspaces/${workspace.id}`),
      })),
  ]
  const words = query.trim().toLowerCase()
  const items = all.filter((item) => item.label.toLowerCase().includes(words))
  // The highlighted item stays in range as the list gets shorter.
  const current = Math.min(active, items.length - 1)

  function choose(item: Item) {
    onDone()
    item.run()
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive((current + step + items.length) % items.length)
    } else if (event.key === 'Enter' && items[current]) {
      event.preventDefault()
      choose(items[current])
    }
  }

  return (
    <div>
      <input
        autoFocus
        role="combobox"
        aria-expanded="true"
        aria-controls="quick-search-list"
        aria-activedescendant={items[current]?.id}
        aria-label="Search tabs, documents and workspaces"
        placeholder="Search tabs, documents and workspaces…"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setActive(0)
        }}
        onKeyDown={onKeyDown}
        className="block h-12 w-full border-b border-line bg-transparent px-4 text-base outline-none placeholder:text-ink-muted"
      />
      <ul id="quick-search-list" role="listbox" className="max-h-80 overflow-y-auto p-2">
        {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-ink-muted">Nothing matches.</li>}
        {items.map((item, index) => (
          <li
            key={item.id}
            id={item.id}
            role="option"
            aria-selected={index === current}
            onMouseMove={() => setActive(index)}
            onClick={() => choose(item)}
            className={`flex cursor-pointer items-center justify-between gap-4 rounded-md px-3 py-2 text-sm ${index === current ? 'bg-paper-deep text-ink' : 'text-ink-muted'}`}
          >
            <span className="truncate">{item.label}</span>
            <span className="shrink-0 text-xs text-ink-muted">{item.group}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

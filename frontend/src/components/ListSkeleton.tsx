// Grey rows shaped like a list card, while it loads. Screen readers hear the
// label instead.
export function ListSkeleton({ label, rows = 3 }: { label: string; rows?: number }) {
  return (
    <div>
      <p className="sr-only">{label}</p>
      <ul
        aria-hidden="true"
        className="animate-pulse divide-y divide-line rounded-lg border border-line bg-surface shadow-xs"
      >
        {Array.from({ length: rows }, (_, row) => (
          <li key={row} className="space-y-2 px-4 py-4">
            <div className="h-3.5 w-2/5 rounded-sm bg-paper-deep" />
            <div className="h-3 w-1/4 rounded-sm bg-paper-deep" />
          </li>
        ))}
      </ul>
    </div>
  )
}

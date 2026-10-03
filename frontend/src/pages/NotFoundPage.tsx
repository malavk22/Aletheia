import { Link } from 'react-router'

// Shown for any address the app doesn't know (a mistyped link, an old
// bookmark). It sits outside the sign-in guards so it never redirects; the
// link home lets the guard decide between the workspaces and the sign-in page.
export function NotFoundPage() {
  return (
    <main className="px-6 py-12 sm:px-12">
      <p className="font-display text-2xl font-medium tracking-tight">Aletheia</p>
      <h1 className="mt-12 font-serif text-3xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-2 text-sm text-ink-muted">
        This address doesn't lead anywhere. It may be mistyped, or the page may have moved.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex h-10 items-center rounded-sm border border-line-strong bg-surface px-4 text-sm font-medium hover:bg-paper-deep focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        Go to your workspaces
      </Link>
    </main>
  )
}

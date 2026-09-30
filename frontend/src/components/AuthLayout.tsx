import type { ReactNode } from 'react'
import { AnimatedWordmark } from './AnimatedWordmark.tsx'

type AuthLayoutProps = {
  title: string
  intro: string
  children: ReactNode
}

// The screen shared by the sign-in and register pages: form on the left,
// a quiet statement of what the product is on the right (wide screens only).
export function AuthLayout({ title, intro, children }: AuthLayoutProps) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,34rem)_1fr]">
      <main className="flex flex-col px-6 py-8 sm:px-12">
        {/* Only on narrow screens, where the right panel (and its large
            wordmark) is hidden and the page would otherwise show no name. */}
        <p className="font-serif text-xl font-semibold tracking-tight lg:hidden">Aletheia</p>
        <div className="my-auto w-full max-w-sm py-12">
          <h1 className="font-serif text-3xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-2 text-sm text-ink-muted">{intro}</p>
          <div className="mt-8">{children}</div>
        </div>
      </main>
      <aside className="relative hidden flex-col justify-end border-l border-line bg-paper-deep p-12 lg:flex">
        {/* Centred in the whole panel, independent of the sentence below. */}
        <div className="absolute inset-0 grid place-items-center">
          <AnimatedWordmark />
        </div>
        <p className="max-w-md font-serif text-2xl leading-snug text-balance">
          Documents are the evidence. Every answer points back to the page it came from.
        </p>
        <p className="mt-4 text-sm text-ink-muted">Document intelligence workspace</p>
      </aside>
    </div>
  )
}

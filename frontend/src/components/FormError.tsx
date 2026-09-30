import type { ReactNode } from 'react'

export function FormError({ children }: { children: ReactNode }) {
  return (
    <p
      role="alert"
      className="border-l-2 border-danger bg-danger-soft px-3 py-2 text-sm text-danger"
    >
      {children}
    </p>
  )
}

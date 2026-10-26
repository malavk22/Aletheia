import type { ButtonHTMLAttributes } from 'react'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  loading?: boolean
}

// One primary per screen: the thing to do next. Secondary for the others,
// ghost for the least important (Log out, Cancel).
const variants = {
  primary: 'bg-accent text-on-fill shadow-sm hover:bg-accent-hover',
  secondary: 'border border-line-strong/50 bg-surface text-ink shadow-xs hover:border-line-strong',
  ghost: 'text-ink-muted hover:bg-paper-deep hover:text-ink',
  // Only for actions that destroy data.
  danger: 'bg-danger text-on-fill hover:bg-danger/90',
}

export function Button({
  variant = 'primary',
  loading = false,
  disabled,
  className = '',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-sm px-4 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:pointer-events-none disabled:opacity-60 ${variants[variant]} ${className}`}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="size-3.5 animate-spin rounded-full border-2 border-current border-r-transparent"
        />
      )}
      {children}
    </button>
  )
}

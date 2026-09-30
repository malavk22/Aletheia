import { useId } from 'react'
import type { InputHTMLAttributes, ReactNode } from 'react'

export type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string
  hint?: string
  error?: string
  // Something small shown inside the right end of the input (e.g. a Show button).
  action?: ReactNode
}

export function TextField({ label, hint, error, action, ...props }: TextFieldProps) {
  const id = useId()
  const message = error ?? hint

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <div className="relative mt-1.5">
        <input
          {...props}
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={message ? `${id}-message` : undefined}
          className={`block h-10 w-full rounded-sm border bg-surface px-3 text-base placeholder:text-ink-muted focus:outline-2 focus:outline-accent disabled:bg-paper-deep disabled:text-ink-muted sm:text-sm ${action ? 'pr-16' : ''} ${error ? 'border-danger' : 'border-line-strong'}`}
        />
        {action && <div className="absolute inset-y-0 right-0 flex items-center">{action}</div>}
      </div>
      {message && (
        <p
          id={`${id}-message`}
          className={`mt-1.5 text-sm ${error ? 'text-danger' : 'text-ink-muted'}`}
        >
          {message}
        </p>
      )}
    </div>
  )
}

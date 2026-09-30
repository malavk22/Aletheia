import { useId } from 'react'
import type { InputHTMLAttributes } from 'react'

type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string
  hint?: string
  error?: string
}

export function TextField({ label, hint, error, ...props }: TextFieldProps) {
  const id = useId()
  const message = error ?? hint

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        {...props}
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? `${id}-message` : undefined}
        className={`mt-1.5 block h-10 w-full rounded-sm border bg-surface px-3 text-base placeholder:text-ink-muted focus:outline-2 focus:outline-accent disabled:bg-paper-deep disabled:text-ink-muted sm:text-sm ${error ? 'border-danger' : 'border-line-strong'}`}
      />
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

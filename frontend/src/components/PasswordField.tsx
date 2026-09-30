import { useState } from 'react'
import { TextField } from './TextField.tsx'
import type { TextFieldProps } from './TextField.tsx'

// A password input with a Show / Hide button, so people can check what they typed.
export function PasswordField(props: Omit<TextFieldProps, 'type' | 'action'>) {
  const [visible, setVisible] = useState(false)

  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      action={
        // type="button" so clicking it never submits the form.
        <button
          type="button"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          className="mr-1 rounded-sm px-2 py-1 text-sm font-medium text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      }
    />
  )
}

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { AuthLayout } from '../components/AuthLayout.tsx'
import { Button } from '../components/Button.tsx'
import { FormError } from '../components/FormError.tsx'
import { TextField } from '../components/TextField.tsx'

// Temporary page for reviewing the visual design. Nothing here is wired to
// the backend except the connection check. It is removed once the real
// sign-in and register pages exist.
export function DesignPreview() {
  return (
    <>
      <AuthLayout title="Sign in" intro="Use the email you registered with.">
        <form className="space-y-5" onSubmit={(event) => event.preventDefault()}>
          <TextField label="Email" type="email" autoComplete="email" />
          <TextField label="Password" type="password" autoComplete="current-password" />
          <Button type="submit" className="w-full">
            Sign in
          </Button>
        </form>
        <p className="mt-6 text-sm text-ink-muted">
          New to Aletheia?{' '}
          <a href="#states" className="font-medium text-accent underline underline-offset-4">
            Create an account
          </a>
        </p>
      </AuthLayout>

      <section id="states" className="border-t border-line px-6 py-12 sm:px-12">
        <h2 className="font-serif text-2xl font-semibold tracking-tight">Component states</h2>
        <p className="mt-2 text-sm text-ink-muted">
          Review page only. Backend: <BackendStatus />
        </p>

        <div className="mt-10 grid max-w-4xl gap-x-12 gap-y-10 md:grid-cols-2">
          <Example caption="Buttons">
            <div className="flex flex-wrap gap-3">
              <Button>Sign in</Button>
              <Button variant="secondary">Cancel</Button>
            </div>
          </Example>
          <Example caption="Buttons: working and disabled">
            <div className="flex flex-wrap gap-3">
              <Button loading>Signing in</Button>
              <Button disabled>Sign in</Button>
              <Button variant="secondary" disabled>
                Cancel
              </Button>
            </div>
          </Example>
          <Example caption="Field with a hint">
            <TextField label="Password" type="password" hint="At least 8 characters." />
          </Example>
          <Example caption="Field with an error">
            <TextField
              label="Password"
              type="password"
              defaultValue="short"
              error="Use at least 8 characters."
            />
          </Example>
          <Example caption="Disabled field">
            <TextField label="Email" defaultValue="ada@example.com" disabled />
          </Example>
          <Example caption="Form-level error">
            <FormError>Invalid email or password.</FormError>
          </Example>
        </div>
      </section>
    </>
  )
}

function Example({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div>
      <p className="mb-3 text-xs font-medium tracking-wide text-ink-muted uppercase">{caption}</p>
      {children}
    </div>
  )
}

function BackendStatus() {
  const [status, setStatus] = useState('checking…')

  useEffect(() => {
    fetch('/api/v1/health')
      .then((response) => setStatus(response.ok ? 'connected' : 'not reachable'))
      .catch(() => setStatus('not reachable'))
  }, [])

  return <span className="font-medium text-ink">{status}</span>
}

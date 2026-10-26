import { AnimatePresence, motion } from 'motion/react'
import { useCallback, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ToastContext } from '../hooks/useToast.ts'

// Short notices at the bottom of the screen ("Uploaded lease.pdf") that go
// away by themselves. For things done, not for errors: an error stays next to
// what failed, until the person deals with it.

const SHOWN_MS = 3500

type Toast = { id: number; message: string }

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const show = useCallback((message: string) => {
    const id = nextId.current++
    setToasts((current) => [...current, { id, message }])
    setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), SHOWN_MS)
  }, [])

  return (
    <ToastContext.Provider value={show}>
      {children}
      {/* role="status": screen readers read each notice out, without
          interrupting what they are reading. */}
      <div
        role="status"
        className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex flex-col items-center gap-2 px-4"
      >
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.p
              key={toast.id}
              layout
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="max-w-sm rounded-lg bg-ink px-4 py-2.5 text-sm text-paper shadow-lg"
            >
              {toast.message}
            </motion.p>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

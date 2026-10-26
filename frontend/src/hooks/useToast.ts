import { createContext, useContext } from 'react'

// Shows a short notice ("Uploaded lease.pdf"); see ToastProvider.
export const ToastContext = createContext<(message: string) => void>(() => {})

export function useToast() {
  return useContext(ToastContext)
}

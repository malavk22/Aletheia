import { AnimatePresence, motion } from 'motion/react'
import { useRef, useState } from 'react'
import type { DragEvent, ReactNode } from 'react'

// Lets files be dropped anywhere on what it wraps. While files are dragged
// over it, a full-screen sign says where they will go.
export function DropFiles({
  target,
  onDrop,
  children,
}: {
  // Shown on the sign: "Drop to upload to <target>".
  target: string
  onDrop: (files: File[]) => void
  children: ReactNode
}) {
  const [dragging, setDragging] = useState(false)
  // dragenter/dragleave fire for every child the pointer crosses; counting
  // them tells when it has really left.
  const depth = useRef(0)

  // Only files: dragging selected text or a link around the page is ignored.
  const hasFiles = (event: DragEvent) => event.dataTransfer.types.includes('Files')

  return (
    <div
      onDragEnter={(event) => {
        if (!hasFiles(event)) return
        depth.current += 1
        setDragging(true)
      }}
      onDragLeave={(event) => {
        if (!hasFiles(event)) return
        depth.current -= 1
        if (depth.current === 0) setDragging(false)
      }}
      // Without preventDefault on dragover the browser opens the file itself.
      onDragOver={(event) => {
        if (hasFiles(event)) event.preventDefault()
      }}
      onDrop={(event) => {
        if (!hasFiles(event)) return
        event.preventDefault()
        depth.current = 0
        setDragging(false)
        onDrop(Array.from(event.dataTransfer.files))
      }}
    >
      {children}
      <AnimatePresence>
        {dragging && (
          <motion.div
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            // pointer-events-none: the drag events keep reaching the page
            // underneath, so the counting above stays right.
            className="pointer-events-none fixed inset-0 z-40 grid place-items-center bg-paper/80 p-6 backdrop-blur-sm"
          >
            <div className="rounded-xl border-2 border-dashed border-accent px-10 py-8 text-center">
              <p className="font-serif text-2xl font-semibold tracking-tight">Drop to upload</p>
              <p className="mt-1 text-sm text-ink-muted">
                to {target} · PDF or DOCX, up to 20 MB each
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

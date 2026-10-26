import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { ApiError, UNREACHABLE_MESSAGE } from '../api/client.ts'
import { documentsKey, uploadDocument } from '../api/documents.ts'
import { useToast } from './useToast.ts'

// The file being sent now, and how much of it (0 to 1).
export type Progress = {
  filename: string
  number: number
  total: number
  fraction: number
}

export type FailedUpload = {
  filename: string
  error: string
}

// Our own API's messages for these are written for people, so show them as-is.
function uploadErrorMessage(error: unknown) {
  if (error instanceof ApiError && (error.status === 413 || error.status === 415)) {
    return error.message
  }
  return UNREACHABLE_MESSAGE
}

// Uploading files to a workspace, shared by the Upload button and dropping
// files anywhere on the workspace page, so both show the same progress and
// failures.
export function useUploads(workspaceId: string) {
  const queryClient = useQueryClient()
  const toast = useToast()
  // Failures are listed until dismissed; successes get a short notice, and
  // the document itself appears in the list.
  const [failures, setFailures] = useState<FailedUpload[]>([])
  const [progress, setProgress] = useState<Progress | null>(null)
  // A ref, not state: a second drop in the same moment must see it at once.
  const busy = useRef(false)
  const mutation = useMutation({
    mutationFn: (file: File) =>
      uploadDocument(workspaceId, file, (fraction) =>
        setProgress((current) => current && { ...current, fraction }),
      ),
    // Refresh the list after each file, so documents appear as they finish.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentsKey(workspaceId) }),
  })

  async function upload(files: File[]) {
    if (files.length === 0) return
    if (busy.current) {
      toast('Wait for the current upload to finish.')
      return
    }
    busy.current = true
    setFailures([])
    const uploaded: string[] = []

    // One request per file, one after another, so each gets its own result.
    for (const [index, file] of files.entries()) {
      setProgress({ filename: file.name, number: index + 1, total: files.length, fraction: 0 })
      try {
        await mutation.mutateAsync(file)
        uploaded.push(file.name)
      } catch (error) {
        setFailures((previous) => [
          ...previous,
          { filename: file.name, error: uploadErrorMessage(error) },
        ])
      }
    }
    setProgress(null)
    busy.current = false
    if (uploaded.length > 0) {
      toast(uploaded.length === 1 ? `Uploaded ${uploaded[0]}` : `Uploaded ${uploaded.length} files`)
    }
  }

  return { upload, progress, failures, dismissFailures: () => setFailures([]) }
}

export type Uploads = ReturnType<typeof useUploads>

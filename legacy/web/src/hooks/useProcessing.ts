import { useEffect, useState } from 'react'
import { getStatus, type VideoStatus } from '../api'

/**
 * useProcessing polls a video's status until it finishes indexing (or fails).
 * Returns the latest status, or null until the first poll completes.
 */
export function useProcessing(videoId: string): VideoStatus | null {
  const [status, setStatus] = useState<VideoStatus | null>(null)

  useEffect(() => {
    setStatus(null)
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      try {
        const next = await getStatus(videoId)
        if (cancelled) return
        setStatus(next)
        // Keep polling until the video is fully indexed (or has failed) —
        // this covers both the "downloading" and "processing" states.
        if (next.status !== 'indexed' && next.status !== 'error') {
          timer = window.setTimeout(poll, 1500)
        }
      } catch {
        if (!cancelled) timer = window.setTimeout(poll, 3000)
      }
    }
    void poll()

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [videoId])

  return status
}

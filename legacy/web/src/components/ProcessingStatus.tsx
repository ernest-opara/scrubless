import { useEffect } from 'react'
import { useProcessing } from '../hooks/useProcessing'
import { mediaUrl, type VideoStatus } from '../api'

interface Props {
  videoId: string
  onIndexed: (status: VideoStatus) => void
}

/** stageLabel describes what the pipeline is doing right now. */
function stageLabel(status: VideoStatus): string {
  if (status.status === 'downloading') return 'Downloading video'
  const pct = status.progress_pct
  if (pct < 25) return 'Extracting frames'
  if (pct < 60) return 'Transcribing audio'
  if (pct < 85) return 'Understanding frames with CLIP'
  return 'Building the search index'
}

/** ProcessingStatus polls indexing progress and reports when the video is ready. */
export function ProcessingStatus({ videoId, onIndexed }: Props) {
  const status = useProcessing(videoId)

  useEffect(() => {
    if (status?.status === 'indexed') onIndexed(status)
  }, [status, onIndexed])

  const pct = status?.progress_pct ?? 0
  const failed = status?.status === 'error'

  if (failed) {
    return (
      <div className="animate-fade-in rounded-lg border border-line bg-panel px-8 py-16 text-center">
        <p className="text-base font-semibold text-accent">Processing failed</p>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted">
          {status?.error_message}
        </p>
      </div>
    )
  }

  return (
    <div className="animate-fade-in-up rounded-lg border border-line bg-panel px-8 py-14">
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        {/* thumbnail (or a dark stand-in) with a sweeping scan line */}
        <div className="relative mb-6 h-28 w-48 overflow-hidden rounded-md border border-line bg-screen">
          {status?.thumbnail_url && (
            <img
              src={mediaUrl(status.thumbnail_url)}
              alt=""
              className="h-full w-full object-cover"
            />
          )}
          <div className="scanline" />
        </div>

        {status?.title && (
          <p className="mb-1.5 max-w-full truncate text-base font-semibold text-ink">
            {status.title}
          </p>
        )}

        <p className="text-sm text-muted">
          {status ? stageLabel(status) : 'Starting'}
          <span className="text-faint"> · {pct}%</span>
        </p>

        <div className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-panel-2">
          <div
            className="relative h-full overflow-hidden rounded-full bg-accent transition-[width] duration-700 ease-out"
            style={{ width: `${pct}%` }}
          >
            <span className="bar-sheen" />
          </div>
        </div>
      </div>
    </div>
  )
}

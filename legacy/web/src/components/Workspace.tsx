import { useCallback, useRef, useState } from 'react'
import { mediaUrl, type SearchResult, type VideoStatus } from '../api'
import { youtubeId } from '../youtube'
import { useVideoSearch } from '../hooks/useVideoSearch'
import { SearchBar } from './SearchBar'
import { ResultsList } from './ResultsList'
import { VideoPlayer } from './VideoPlayer'
import { YouTubePlayer } from './YouTubePlayer'
import { ClipExport } from './ClipExport'
import { ShareMoment } from './ShareMoment'

interface Props {
  videoId: string
  status: VideoStatus
}

/**
 * Workspace is the main operational page: player + export on the left, search
 * + results on the right. App mounts it with key={videoId}, so every video
 * gets a fully fresh Workspace.
 *
 * Uploads have a stored source — HTML5 player + clip export. Imports are
 * processed then discarded — they play from their origin (a YouTube embed, or
 * the direct URL) and offer a shareable timestamp link instead of clip export.
 */
export function Workspace({ videoId, status }: Props) {
  const [range, setRange] = useState<{ start: number; end: number } | null>(null)
  const [seekTime, setSeekTime] = useState(0)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const search = useVideoSearch(videoId)

  const isImport = status.kind === 'import'
  const ytId = isImport ? youtubeId(status.import_url) : null
  // The <video> element's source: a YouTube import uses the embed instead.
  const videoSrc = isImport ? status.import_url : mediaUrl(status.source_url)

  // Selecting a result seeks the player and records the moment's range.
  const handleSelect = useCallback(
    (r: SearchResult) => {
      if (ytId) {
        setSeekTime(Math.max(0, Math.floor(r.timestamp_start)))
      } else {
        const v = videoRef.current
        if (v) {
          v.currentTime = r.timestamp_start
          void v.play()
        }
      }
      setRange({ start: r.timestamp_start, end: r.timestamp_end })
    },
    [ytId],
  )

  return (
    <div>
      {status.title && (
        <h2 className="mb-4 truncate text-lg font-semibold text-ink animate-fade-in">
          {status.title}
        </h2>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.45fr_1fr]">
        <div
          className="flex flex-col gap-5 animate-fade-in-up"
          style={{ animationDelay: '40ms' }}
        >
          {ytId ? (
            <YouTubePlayer youtubeId={ytId} seekTime={seekTime} />
          ) : (
            <VideoPlayer src={videoSrc} videoRef={videoRef} />
          )}

          {isImport ? (
            <ShareMoment
              importUrl={status.import_url}
              ytId={ytId}
              range={range}
            />
          ) : (
            <ClipExport
              videoId={videoId}
              videoRef={videoRef}
              duration={status.duration_sec}
              range={range}
            />
          )}
        </div>

        <div
          className="flex min-h-0 flex-col gap-4 animate-fade-in-up"
          style={{ animationDelay: '120ms' }}
        >
          <SearchBar onSearch={search.run} loading={search.loading} />
          <div className="scroll-area max-h-[68vh] min-h-0 overflow-y-auto pr-1">
            <ResultsList
              results={search.results}
              loading={search.loading}
              searched={search.searched}
              error={search.error}
              onSelect={handleSelect}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

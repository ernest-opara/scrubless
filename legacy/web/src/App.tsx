import { useState } from 'react'
import type { VideoStatus } from './api'
import { LandingInput } from './components/LandingInput'
import { ProcessingStatus } from './components/ProcessingStatus'
import { Workspace } from './components/Workspace'

export default function App() {
  const [videoId, setVideoId] = useState<string | null>(null)
  const [indexed, setIndexed] = useState<VideoStatus | null>(null)

  const reset = () => {
    setVideoId(null)
    setIndexed(null)
  }

  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col px-6 py-7">
      <header className="mb-9 flex items-center justify-between border-b border-line pb-5 animate-fade-in">
        <div className="flex items-center gap-2.5">
          {/* timeline-scrubber mark — track + scrub handle */}
          <div className="flex h-8 w-8 items-center justify-center rounded-md border border-line">
            <svg width="18" height="18" viewBox="0 0 24 24" className="text-accent">
              <line
                x1="3"
                y1="12"
                x2="21"
                y2="12"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <circle
                className="logo-handle"
                cx="15"
                cy="12"
                r="4.5"
                fill="currentColor"
              />
            </svg>
          </div>
          <div>
            <h1 className="text-[17px] font-semibold tracking-tight text-ink">
              Scrubless
            </h1>
            <p className="text-xs text-muted">Stop scrubbing. Start searching.</p>
          </div>
        </div>
        {videoId && (
          <button
            onClick={reset}
            className="rounded-md border border-line bg-panel px-3.5 py-2 text-sm font-medium text-ink transition hover:border-ink/30"
          >
            New video
          </button>
        )}
      </header>

      {/* keys on the stage components guarantee a clean remount per video,
          so switching to a second video never inherits stale state. */}
      {!videoId && <LandingInput onReady={setVideoId} />}

      {videoId && !indexed && (
        <ProcessingStatus key={videoId} videoId={videoId} onIndexed={setIndexed} />
      )}

      {videoId && indexed && (
        <Workspace key={videoId} videoId={videoId} status={indexed} />
      )}
    </div>
  )
}

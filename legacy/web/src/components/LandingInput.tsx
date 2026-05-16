import { useState } from 'react'
import { importVideo } from '../api'
import { CyclingWord } from './CyclingWord'
import { FilmstripHero } from './FilmstripHero'
import { VideoUpload } from './VideoUpload'

interface Props {
  onReady: (videoId: string) => void
}

/**
 * LandingInput is the entry screen: a video URL field as the primary input,
 * with file upload offered as a secondary option below.
 */
export function LandingInput({ onReady }: Props) {
  const [url, setUrl] = useState('')
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    const trimmed = url.trim()
    if (!trimmed || importing) return
    setImporting(true)
    setError(null)
    try {
      const res = await importVideo(trimmed)
      onReady(res.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'import failed')
      setImporting(false)
    }
  }

  return (
    <div className="animate-fade-in-up">
      <div className="rounded-lg border border-line bg-panel px-8 py-14 text-center sm:px-12">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-accent">
          Semantic video search
        </p>
        <h2 className="mx-auto mt-3 max-w-2xl text-3xl font-semibold leading-tight tracking-tight text-ink sm:text-[2.6rem]">
          Find any <CyclingWord /> in any video.
        </h2>

        <FilmstripHero />

        <p className="mx-auto mt-8 max-w-md text-sm text-muted">
          Paste a link to any video — YouTube, Vimeo, a direct file. Scrubless
          indexes it in seconds, then you search it by describing what you
          remember.
        </p>

        <div className="mx-auto mt-6 flex max-w-xl flex-col gap-2 sm:flex-row">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void submit()}
            disabled={importing}
            placeholder="Paste any video URL…"
            className="flex-1 rounded-md border border-line bg-panel-2 px-4 py-3 text-sm text-ink placeholder:text-faint transition focus:border-accent focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={() => void submit()}
            disabled={importing || url.trim() === ''}
            className="rounded-md bg-accent px-6 py-3 text-sm font-semibold text-accent-ink transition hover:brightness-95 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {importing ? 'Importing…' : 'Search this video'}
          </button>
        </div>

        {error && (
          <p className="mt-3 animate-fade-in text-sm text-accent">{error}</p>
        )}
      </div>

      <div className="my-5 flex items-center gap-4">
        <div className="h-px flex-1 bg-line" />
        <span className="text-xs uppercase tracking-[0.14em] text-faint">
          or upload a file
        </span>
        <div className="h-px flex-1 bg-line" />
      </div>

      <VideoUpload onUploaded={onReady} />
    </div>
  )
}

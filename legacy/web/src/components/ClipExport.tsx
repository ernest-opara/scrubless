import { useEffect, useState } from 'react'
import type { RefObject } from 'react'
import { exportClip, mediaUrl } from '../api'
import { formatTime } from '../format'
import { IconDownload, IconScissors } from './icons'

interface Props {
  videoId: string
  videoRef: RefObject<HTMLVideoElement | null>
  duration: number
  /** Pre-fills the range when a search result is selected. */
  range: { start: number; end: number } | null
}

const round = (n: number) => Math.round(n * 10) / 10

/** ClipExport lets the user pick a time range and export a downloadable clip. */
export function ClipExport({ videoId, videoRef, duration, range }: Props) {
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [clipUrl, setClipUrl] = useState<string | null>(null)

  useEffect(() => {
    if (duration > 0 && end === 0) setEnd(Math.min(15, duration))
  }, [duration, end])

  useEffect(() => {
    if (range) {
      setStart(round(range.start))
      setEnd(round(range.end))
      setClipUrl(null)
    }
  }, [range])

  const playhead = () => round(videoRef.current?.currentTime ?? 0)
  const valid = start >= 0 && end > start

  const doExport = async () => {
    setBusy(true)
    setError(null)
    setClipUrl(null)
    try {
      const res = await exportClip(videoId, start, end)
      setClipUrl(res.clip_url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'export failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <IconScissors width={14} height={14} className="text-accent" />
          Export clip
        </h3>
        <span className="text-xs tabular-nums text-muted">
          {valid ? `length ${formatTime(end - start)}` : 'end must follow start'}
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <Field
          label="Start"
          value={start}
          max={duration}
          onChange={setStart}
          onUsePlayhead={() => setStart(playhead())}
        />
        <Field
          label="End"
          value={end}
          max={duration}
          onChange={setEnd}
          onUsePlayhead={() => setEnd(playhead())}
        />
        <button
          onClick={doExport}
          disabled={!valid || busy}
          className="rounded-md bg-accent px-5 py-2 text-sm font-semibold text-accent-ink transition hover:brightness-95 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? 'Exporting…' : 'Export'}
        </button>
      </div>

      {error && (
        <p className="mt-2 animate-fade-in text-sm text-accent">{error}</p>
      )}
      {clipUrl && (
        <a
          href={mediaUrl(clipUrl)}
          download
          className="mt-3 inline-flex animate-fade-in items-center gap-1.5 text-sm font-semibold text-accent hover:underline"
        >
          <IconDownload width={14} height={14} />
          Download clip
        </a>
      )}
    </div>
  )
}

interface FieldProps {
  label: string
  value: number
  max: number
  onChange: (v: number) => void
  onUsePlayhead: () => void
}

function Field({ label, value, max, onChange, onUsePlayhead }: FieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-muted">
        {label} · {formatTime(value)}
      </label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          min={0}
          max={max || undefined}
          step={0.5}
          value={value}
          onChange={(e) => onChange(Math.max(0, Number(e.target.value)))}
          className="w-24 rounded-md border border-line bg-panel-2 px-2 py-1.5 text-sm tabular-nums text-ink focus:border-accent focus:outline-none"
        />
        <button
          onClick={onUsePlayhead}
          title="Use current playhead position"
          className="rounded-md border border-line bg-panel px-2 py-1.5 text-xs text-muted transition hover:border-accent hover:text-accent"
        >
          ⤓ now
        </button>
      </div>
    </div>
  )
}

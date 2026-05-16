import { useEffect, useState } from 'react'
import { formatTime } from '../format'
import { IconLink } from './icons'

interface Props {
  importUrl: string
  /** YouTube video id, if the import is a YouTube video. */
  ytId: string | null
  /** The selected search result's range, or null if none is selected. */
  range: { start: number; end: number } | null
}

/**
 * ShareMoment is the export panel for imported videos. Scrubless keeps no
 * stored source for imports, so instead of trimming a file it produces a
 * deep link that opens the original video at the matched timestamp.
 */
export function ShareMoment({ importUrl, ytId, range }: Props) {
  const [copied, setCopied] = useState(false)

  useEffect(() => setCopied(false), [range])

  const linkFor = (start: number) => {
    const at = Math.floor(start)
    return ytId ? `https://youtu.be/${ytId}?t=${at}` : `${importUrl}#t=${at}`
  }

  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className="mb-2.5 flex items-center justify-between">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <IconLink width={14} height={14} className="text-accent" />
          Share a moment
        </h3>
        {range && (
          <span className="text-xs tabular-nums text-muted">
            at {formatTime(range.start)}
          </span>
        )}
      </div>

      {!range ? (
        <p className="text-[13px] text-muted">
          Select a result to get a link that opens the video at that moment.
        </p>
      ) : (
        <ShareRow
          link={linkFor(range.start)}
          copied={copied}
          onCopied={() => setCopied(true)}
        />
      )}
    </div>
  )
}

function ShareRow({
  link,
  copied,
  onCopied,
}: {
  link: string
  copied: boolean
  onCopied: () => void
}) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link)
      onCopied()
    } catch {
      /* clipboard blocked — the user can still copy from the field */
    }
  }

  return (
    <div className="flex gap-2">
      <input
        readOnly
        value={link}
        onFocus={(e) => e.currentTarget.select()}
        className="min-w-0 flex-1 rounded-md border border-line bg-panel-2 px-3 py-2 text-sm text-muted focus:border-accent focus:outline-none"
      />
      <button
        onClick={() => void copy()}
        className="rounded-md border border-line bg-panel px-3 py-2 text-sm font-medium text-ink transition hover:border-ink/30"
      >
        {copied ? 'Copied' : 'Copy'}
      </button>
      <a
        href={link}
        target="_blank"
        rel="noreferrer"
        className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-accent-ink transition hover:brightness-95"
      >
        Open ↗
      </a>
    </div>
  )
}

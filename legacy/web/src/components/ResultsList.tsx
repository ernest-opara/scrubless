import { mediaUrl, type SearchResult } from '../api'
import { displayConfidence, formatTime } from '../format'
import { useCountUp } from '../hooks/useCountUp'
import { IconClock, IconPlay, IconSpark } from './icons'

interface Props {
  results: SearchResult[]
  loading: boolean
  searched: boolean
  error: string | null
  onSelect: (result: SearchResult) => void
}

/** ResultsList renders ranked search hits as clickable thumbnail cards. */
export function ResultsList({ results, loading, searched, error, onSelect }: Props) {
  if (error) return <Empty text={error} tone="error" />
  if (loading) return <SkeletonList />
  if (!searched) {
    return <Empty text="Search your footage to surface matching moments." />
  }
  if (results.length === 0) {
    return <Empty text="No matching moments found. Try other words." />
  }

  return (
    <div className="flex flex-col gap-2">
      {results.map((r, i) => (
        <ResultCard
          key={`${r.timestamp_start}-${i}`}
          result={r}
          rank={i}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

function ResultCard({
  result: r,
  rank,
  onSelect,
}: {
  result: SearchResult
  rank: number
  onSelect: (r: SearchResult) => void
}) {
  const confidence = displayConfidence(r.score)
  const shown = useCountUp(confidence)
  const strong = confidence >= 85

  return (
    <button
      onClick={() => onSelect(r)}
      style={{ animationDelay: `${rank * 55}ms` }}
      className={`group flex animate-result-in gap-3 rounded-lg border bg-panel p-2.5 text-left transition duration-150 hover:-translate-y-0.5 hover:border-accent ${
        strong ? 'border-line border-l-2 border-l-accent' : 'border-line'
      }`}
    >
      <div className="relative h-[4.25rem] w-[7.5rem] shrink-0 overflow-hidden rounded-md bg-screen">
        {r.thumbnail_url && (
          <img
            src={mediaUrl(r.thumbnail_url)}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.06]"
          />
        )}
        {/* play affordance on hover */}
        <span className="absolute inset-0 flex items-center justify-center bg-black/35 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
          <span className="flex h-7 w-7 scale-90 items-center justify-center rounded-full bg-accent text-accent-ink transition-transform duration-150 group-hover:scale-100">
            <IconPlay width={13} height={13} />
          </span>
        </span>
        <span className="absolute bottom-1 right-1 rounded bg-black/75 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-white">
          {formatTime(r.timestamp_start)}
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1 text-sm font-semibold tabular-nums text-ink">
            <IconClock width={12} height={12} className="text-faint" />
            {formatTime(r.timestamp_start)} – {formatTime(r.timestamp_end)}
          </span>
          <span
            className={`flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold tabular-nums ${
              strong ? 'bg-accent text-accent-ink' : 'border border-line text-muted'
            }`}
          >
            {strong && <IconSpark width={10} height={10} />}
            {shown}%
          </span>
        </div>
        {r.description ? (
          <p className="mt-0.5 line-clamp-2 text-[13px] text-muted">
            {r.description}
          </p>
        ) : (
          <p className="mt-0.5 text-[13px] text-faint">Matched moment</p>
        )}
        {r.transcript_snippet && (
          <p className="mt-0.5 line-clamp-1 text-xs italic text-faint">
            “{r.transcript_snippet}”
          </p>
        )}
      </div>
    </button>
  )
}

function SkeletonList() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex animate-pulse gap-3 rounded-lg border border-line bg-panel p-2.5"
        >
          <div className="h-[4.25rem] w-[7.5rem] shrink-0 rounded-md bg-panel-2" />
          <div className="flex flex-1 flex-col justify-center gap-2">
            <div className="h-3.5 w-1/3 rounded bg-panel-2" />
            <div className="h-3 w-3/4 rounded bg-panel-2" />
            <div className="h-3 w-1/2 rounded bg-panel-2" />
          </div>
        </div>
      ))}
    </div>
  )
}

function Empty({ text, tone }: { text: string; tone?: 'error' }) {
  return (
    <div className="animate-fade-in rounded-lg border border-dashed border-line bg-panel px-6 py-12 text-center">
      <p className={`text-sm ${tone === 'error' ? 'text-accent' : 'text-muted'}`}>
        {text}
      </p>
    </div>
  )
}

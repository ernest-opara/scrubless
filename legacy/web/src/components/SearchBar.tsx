import { useState } from 'react'
import { IconSearch } from './icons'

interface Props {
  onSearch: (query: string) => void
  loading: boolean
}

const SUGGESTIONS = ['someone laughing', 'a wide outdoor shot', 'close-up on a face']

/** SearchBar takes a natural-language query and submits it. */
export function SearchBar({ onSearch, loading }: Props) {
  const [query, setQuery] = useState('')

  const submit = (q: string) => {
    const trimmed = q.trim()
    if (trimmed) onSearch(trimmed)
  }

  return (
    <div>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <IconSearch className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit(query)}
            placeholder="Describe a moment to find it…"
            className="w-full rounded-md border border-line bg-panel py-2.5 pl-9 pr-3 text-sm text-ink placeholder:text-faint transition focus:border-accent focus:outline-none"
          />
        </div>
        <button
          onClick={() => submit(query)}
          disabled={loading || query.trim() === ''}
          className="flex items-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-ink transition hover:brightness-95 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? (
            <>
              Searching
              <span className="flex gap-0.5">
                <span className="dot h-1 w-1 rounded-full bg-accent-ink" />
                <span
                  className="dot h-1 w-1 rounded-full bg-accent-ink"
                  style={{ animationDelay: '0.15s' }}
                />
                <span
                  className="dot h-1 w-1 rounded-full bg-accent-ink"
                  style={{ animationDelay: '0.3s' }}
                />
              </span>
            </>
          ) : (
            'Search'
          )}
        </button>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => {
              setQuery(s)
              submit(s)
            }}
            className="rounded-full border border-line bg-panel px-2.5 py-1 text-xs text-muted transition hover:border-accent hover:text-accent"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}

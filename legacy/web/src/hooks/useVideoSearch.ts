import { useCallback, useState } from 'react'
import { search, type SearchResult } from '../api'

interface VideoSearch {
  results: SearchResult[]
  loading: boolean
  error: string | null
  searched: boolean
  run: (query: string) => Promise<void>
}

/** useVideoSearch wraps the search endpoint with loading and error state. */
export function useVideoSearch(videoId: string): VideoSearch {
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  const run = useCallback(
    async (query: string) => {
      setLoading(true)
      setError(null)
      try {
        setResults(await search(videoId, query))
        setSearched(true)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'search failed')
      } finally {
        setLoading(false)
      }
    },
    [videoId],
  )

  return { results, loading, error, searched, run }
}

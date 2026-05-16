// API client for the Scrubless Go backend.
//
// In dev the Vite proxy forwards /api and /storage to :8080, so API_BASE is
// empty. For a deployed build, set VITE_API_BASE to the API origin.

const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''

export type ProcessingStatus =
  | 'downloading'
  | 'processing'
  | 'indexed'
  | 'error'

export type VideoKind = 'upload' | 'import'

export interface UploadResponse {
  id: string
  status: ProcessingStatus
}

export interface ImportResponse {
  id: string
  status: ProcessingStatus
  title: string
  duration: number
}

export interface VideoStatus {
  status: ProcessingStatus
  progress_pct: number
  segments_indexed: number
  duration_sec: number
  error_message: string
  source_url: string
  import_url: string
  kind: VideoKind
  title: string
  thumbnail_url: string
}

export interface SearchResult {
  timestamp_start: number
  timestamp_end: number
  thumbnail_url: string
  score: number
  description: string
  transcript_snippet: string
}

export interface ClipResponse {
  clip_url: string
  duration: number
}

/** mediaUrl resolves a storage path returned by the API into a loadable URL. */
export function mediaUrl(u: string): string {
  if (!u) return ''
  if (/^https?:\/\//.test(u)) return u
  return API_BASE + u
}

/** uploadVideo posts a file and reports upload progress (0-100). */
export function uploadVideo(
  file: File,
  onProgress: (pct: number) => void,
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const form = new FormData()
    form.append('file', file)

    xhr.open('POST', `${API_BASE}/api/videos/upload`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as UploadResponse)
      } else {
        reject(new Error(parseError(xhr.responseText, xhr.status)))
      }
    }
    xhr.onerror = () => reject(new Error('network error during upload'))
    xhr.send(form)
  })
}

/** importVideo imports a video from any supported video URL. */
export function importVideo(url: string): Promise<ImportResponse> {
  return request<ImportResponse>('/api/videos/import', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

export function getStatus(id: string): Promise<VideoStatus> {
  return request<VideoStatus>(`/api/videos/${id}/status`)
}

export function search(
  id: string,
  query: string,
  limit = 10,
): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/api/videos/${id}/search`, {
    method: 'POST',
    body: JSON.stringify({ query, limit }),
  })
}

export function exportClip(
  id: string,
  start: number,
  end: number,
): Promise<ClipResponse> {
  return request<ClipResponse>(`/api/videos/${id}/clip`, {
    method: 'POST',
    body: JSON.stringify({ start, end }),
  })
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const text = await res.text()
  if (!res.ok) throw new Error(parseError(text, res.status))
  return (text ? JSON.parse(text) : null) as T
}

/** parseError pulls the {"error": ...} message out of a failed response. */
function parseError(body: string, status: number): string {
  try {
    const j = JSON.parse(body)
    if (j && typeof j.error === 'string') return j.error
  } catch {
    /* not JSON */
  }
  return `request failed (${status})`
}

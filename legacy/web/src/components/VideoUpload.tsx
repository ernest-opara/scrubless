import { useRef, useState } from 'react'
import { uploadVideo } from '../api'
import { IconUpload } from './icons'

interface Props {
  onUploaded: (videoId: string) => void
}

/** VideoUpload is a drag-and-drop / click upload zone with a progress bar. */
export function VideoUpload({ onUploaded }: Props) {
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const uploading = progress !== null

  const handleFile = async (file: File) => {
    setError(null)
    setProgress(0)
    try {
      const res = await uploadVideo(file, setProgress)
      onUploaded(res.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'upload failed')
      setProgress(null)
    }
  }

  return (
    <div className="animate-fade-in">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          if (!uploading) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (uploading) return
          const file = e.dataTransfer.files[0]
          if (file) void handleFile(file)
        }}
        onClick={() => !uploading && inputRef.current?.click()}
        className={`group flex flex-col items-center justify-center rounded-lg border border-dashed px-8 py-12 text-center transition-colors ${
          uploading ? 'cursor-default' : 'cursor-pointer'
        } ${
          dragging
            ? 'border-accent bg-accent-soft'
            : 'border-line bg-panel hover:border-ink/25'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleFile(file)
          }}
        />

        {uploading ? (
          <div className="w-full max-w-md">
            <p className="mb-3 text-sm font-medium text-ink">
              Uploading… {progress}%
            </p>
            <div className="h-1.5 overflow-hidden rounded-full bg-panel-2">
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ) : (
          <>
            <span
              className={`mb-3 flex h-11 w-11 items-center justify-center rounded-full border transition-colors ${
                dragging
                  ? 'border-accent text-accent'
                  : 'border-line text-muted group-hover:text-ink'
              }`}
            >
              <IconUpload width={20} height={20} />
            </span>
            <p className="text-base font-medium text-ink">
              Drop a video file here
            </p>
            <p className="mt-1 text-sm text-muted">
              or <span className="font-medium text-accent">click to browse</span>{' '}
              · MP4, MOV, MKV, WEBM, AVI, M4V
            </p>
          </>
        )}
      </div>

      {error && (
        <p className="mt-3 animate-fade-in text-center text-sm text-accent">
          {error}
        </p>
      )}
    </div>
  )
}

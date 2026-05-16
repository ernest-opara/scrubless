import type { RefObject } from 'react'

interface Props {
  src: string
  videoRef: RefObject<HTMLVideoElement | null>
}

/**
 * VideoPlayer is a plain HTML5 player. The parent holds videoRef and seeks the
 * element imperatively when a search result is selected. The key on <video>
 * forces a fresh element (and reload) whenever the source changes.
 */
export function VideoPlayer({ src, videoRef }: Props) {
  return (
    <div className="overflow-hidden rounded-lg border border-line bg-screen">
      <video
        key={src}
        ref={videoRef}
        src={src}
        controls
        playsInline
        className="aspect-video w-full bg-screen"
      />
    </div>
  )
}

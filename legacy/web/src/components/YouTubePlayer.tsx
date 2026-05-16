interface Props {
  youtubeId: string
  /** Seconds to start playback from; changing it re-seeks the player. */
  seekTime: number
}

/**
 * YouTubePlayer embeds the YouTube IFrame player. Imported videos aren't
 * stored by Scrubless, so a YouTube import plays from YouTube itself —
 * selecting a result re-mounts the iframe at the new start time.
 */
export function YouTubePlayer({ youtubeId, seekTime }: Props) {
  const src =
    `https://www.youtube.com/embed/${youtubeId}` +
    `?start=${seekTime}&autoplay=${seekTime > 0 ? 1 : 0}&rel=0`

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-screen">
      <iframe
        key={seekTime}
        src={src}
        title="YouTube player"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        allowFullScreen
        className="aspect-video w-full"
      />
    </div>
  )
}

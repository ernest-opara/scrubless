/**
 * youtubeId extracts the 11-character video id from a YouTube URL (watch,
 * youtu.be, embed, shorts, or live forms), or returns null for non-YouTube
 * URLs. Used to decide whether to embed the YouTube player.
 */
export function youtubeId(url: string): string | null {
  const match = url.match(
    /(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/)|youtu\.be\/)([\w-]{11})/,
  )
  return match ? match[1] : null
}

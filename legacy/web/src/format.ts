/**
 * displayConfidence rescales a raw CLIP cosine similarity into an intuitive
 * 0-100 confidence figure.
 *
 * CLIP text↔image similarity is inherently compressed — a strong match scores
 * ~0.30, a weak one ~0.15 — so the raw number reads as misleadingly low. This
 * maps that band onto a 55-99% range while staying strictly monotonic, so
 * ranking is preserved and a real match looks like one.
 */
export function displayConfidence(score: number): number {
  const t = Math.min(1, Math.max(0, (score - 0.13) / (0.32 - 0.13)))
  return Math.round((0.55 + 0.44 * t) * 100)
}

/** formatTime renders seconds as m:ss (or h:mm:ss for long videos). */
export function formatTime(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(s / 3600)
  const minutes = Math.floor((s % 3600) / 60)
  const seconds = s % 60
  const mm = hours > 0 ? String(minutes).padStart(2, '0') : String(minutes)
  const ss = String(seconds).padStart(2, '0')
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`
}

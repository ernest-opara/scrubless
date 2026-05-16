import type { ReactNode } from 'react'

// Cell base tones — muted, varied cool tones behind each scene.
const CELLS = ['#3a444e', '#473f52', '#37463f', '#2e3942', '#4a4348', '#3f4a4a']
const MATCH_INDEX = 3

// Minimal flat "scenes" so each frame reads as a different video still.
// Shapes use plain white/black alpha, so they sit on any cell tone.
const SCENES: ReactNode[] = [
  // sunset landscape
  <>
    <circle cx="24" cy="6" r="3.4" fill="#fff" opacity="0.55" />
    <path d="M0 18V13c5-3 9-3 14 0s12 1 18-2v7Z" fill="#000" opacity="0.32" />
  </>,
  // portrait
  <>
    <circle cx="16" cy="7.4" r="3.5" fill="#fff" opacity="0.5" />
    <path d="M9 18c0-4 3.4-6 7-6s7 2 7 6Z" fill="#fff" opacity="0.5" />
  </>,
  // mountain peaks
  <path d="M0 18 7 7 13 13 20 5 27 13 32 9V18Z" fill="#000" opacity="0.34" />,
  // a figure in frame (the match)
  <>
    <circle cx="16" cy="6.6" r="2.5" fill="#fff" opacity="0.62" />
    <path d="M11.4 18c0-4 2-6.6 4.6-6.6S20.6 14 20.6 18Z" fill="#fff" opacity="0.62" />
  </>,
  // city skyline
  <>
    <circle cx="6" cy="5" r="1.9" fill="#fff" opacity="0.5" />
    <g fill="#000" opacity="0.36">
      <rect x="3" y="10" width="4" height="8" />
      <rect x="8.6" y="7" width="4" height="11" />
      <rect x="14" y="11" width="3.6" height="7" />
      <rect x="19" y="8.6" width="4" height="9.4" />
      <rect x="24.6" y="12" width="4" height="6" />
    </g>
  </>,
  // close-up face
  <>
    <circle cx="16" cy="11.5" r="7.4" fill="#fff" opacity="0.42" />
    <circle cx="13" cy="10" r="1.1" fill="#000" opacity="0.42" />
    <circle cx="19" cy="10" r="1.1" fill="#000" opacity="0.42" />
  </>,
]

function Cell({ index, lit }: { index: number; lit: boolean }) {
  return (
    <div className="cell" style={{ background: CELLS[index] }}>
      <svg
        viewBox="0 0 32 18"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
      >
        {SCENES[index]}
      </svg>
      {lit && index === MATCH_INDEX && (
        <>
          <span className="pointer-events-none absolute inset-0 rounded-[7px] border-2 border-accent" />
          <span className="match-chip absolute bottom-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-accent px-1.5 py-0.5 text-[9px] font-bold tracking-wide text-accent-ink">
            ✦ MATCH
          </span>
        </>
      )}
    </div>
  )
}

/**
 * FilmstripHero is the landing-page showpiece: a row of illustrated video
 * frames with a scrubbing playhead that sweeps across, lighting frames as it
 * passes and locking onto a match. Pure CSS — a dim strip, a bright copy
 * revealed by an animated clip-path, and a playhead on the same clock.
 */
export function FilmstripHero() {
  return (
    <div className="filmstrip mx-auto mt-8 max-w-lg" aria-hidden>
      <div className="strip strip-dim">
        {CELLS.map((_, i) => (
          <Cell key={i} index={i} lit={false} />
        ))}
      </div>

      <div className="strip strip-lit">
        {CELLS.map((_, i) => (
          <Cell key={i} index={i} lit />
        ))}
      </div>

      <div className="playhead" />
    </div>
  )
}

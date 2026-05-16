import { useEffect, useState } from 'react'

const WORDS = ['moment', 'scene', 'quote', 'reaction', 'detail']

/**
 * CyclingWord rotates through words in a fixed-width, underlined slot — a
 * fill-in-the-blank that keeps filling itself in. The slot width is fixed so
 * the surrounding headline never reflows.
 */
export function CyclingWord() {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(
      () => setIndex((i) => (i + 1) % WORDS.length),
      2300,
    )
    return () => window.clearInterval(timer)
  }, [])

  return (
    <span className="inline-block min-w-[5.4em] border-b-2 border-accent/40 text-center text-accent">
      <span key={index} className="inline-block animate-word-in">
        {WORDS[index]}
      </span>
    </span>
  )
}

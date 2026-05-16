import { useEffect, useState } from 'react'

/**
 * useCountUp animates an integer from 0 up to target (ease-out) on mount —
 * used to give search-result confidence scores a little life.
 */
export function useCountUp(target: number, durationMs = 650): number {
  const [value, setValue] = useState(0)

  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      setValue(Math.round(target * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, durationMs])

  return value
}

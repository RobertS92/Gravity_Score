import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { formatScore } from '../../lib/formatters'

export function ScoreDisplay({
  value,
  animate,
  className,
  style,
}: {
  value: number | null | undefined
  animate: boolean
  className?: string
  style?: CSSProperties
}) {
  const [display, setDisplay] = useState(() => (animate && value != null ? 0 : value ?? null))
  const started = useRef(false)

  useEffect(() => {
    if (!animate || value == null) {
      setDisplay(value ?? null)
      return
    }
    if (started.current) {
      setDisplay(value)
      return
    }
    started.current = true
    const target = value
    const t0 = performance.now()
    const dur = 800
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / dur)
      setDisplay(target * p)
      if (p < 1) requestAnimationFrame(tick)
      else setDisplay(target)
    }
    requestAnimationFrame(tick)
  }, [animate, value])

  return (
    <span className={className} style={style}>
      {formatScore(display)}
    </span>
  )
}

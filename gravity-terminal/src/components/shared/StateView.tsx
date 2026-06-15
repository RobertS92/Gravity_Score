import type { ReactNode } from 'react'
import styles from './StateView.module.css'

type StateVariant = 'loading' | 'empty' | 'error'

interface StateViewProps {
  variant: StateVariant
  title: string
  body?: ReactNode
  hint?: ReactNode
  action?: ReactNode
  /** Optional ASCII prefix override (e.g. ">>", "$$", "**"). Defaults
   * are picked per variant so empty/error feel different from loading. */
  prefix?: string
}

const PREFIX_BY_VARIANT: Record<StateVariant, string> = {
  loading: '...',
  empty: '!!',
  error: 'EE',
}

/**
 * Shared loading / empty / error state component. The terminal aesthetic
 * keeps the look consistent across views — a tiny ASCII prefix, a small
 * caps title, and a muted explanation. Every view that fetches data should
 * use this rather than rolling its own "Loading..." or "No data" copy.
 *
 * @example
 *   if (loading) return <StateView variant="loading" title="Fetching report" />
 *   if (!rows.length) return (
 *     <StateView
 *       variant="empty"
 *       title="No comparables"
 *       hint="Widen the confidence threshold or include unverified deals."
 *     />
 *   )
 */
export function StateView({ variant, title, body, hint, action, prefix }: StateViewProps) {
  const finalPrefix = prefix ?? PREFIX_BY_VARIANT[variant]
  return (
    <div className={`${styles.root} ${styles[variant]}`} role={variant === 'error' ? 'alert' : 'status'}>
      <div className={styles.title}>
        <span className={styles.prefix}>{finalPrefix}</span>
        {title}
      </div>
      {variant === 'loading' && (
        <div className={styles.scanline} aria-hidden />
      )}
      {body && <div className={styles.body}>{body}</div>}
      {hint && <div className={styles.hint}>{hint}</div>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { etTimeString } from '../../lib/time'
import { useUiStore } from '../../stores/uiStore'
import { useAuthStore } from '../../stores/authStore'
import styles from './StatusLEDBar.module.css'

type LedState = 'ok' | 'warn' | 'err' | 'idle'

function ledClass(state: LedState): string {
  switch (state) {
    case 'ok':
      return `${styles.led} ${styles.ledOk}`
    case 'warn':
      return `${styles.led} ${styles.ledWarn}`
    case 'err':
      return `${styles.led} ${styles.ledErr}`
    default:
      return `${styles.led} ${styles.ledIdle}`
  }
}

/**
 * Bottom-of-shell status bar. Surfaces operational state at a glance:
 *
 *   NET    — network connectivity (matches navigator.onLine + last fetch)
 *   MODEL  — most recently rendered Gravity model status (production vs fallback)
 *   SCRAPE — pipeline freshness indicator (TODO: wire to /ops/health)
 *   ET     — Eastern Time clock (canonical timezone for the league business day)
 *
 * Keeping the LEDs in a sticky bottom strip frees the top bar for navigation
 * and lets operators eyeball pipeline health without leaving their current
 * view. Each LED carries a tooltip with the underlying status so screen
 * readers and curious users can still get the detail.
 */
export function StatusLEDBar() {
  const [clock, setClock] = useState(etTimeString)
  const [online, setOnline] = useState<boolean>(() => navigator.onLine)
  const lockedFromAgent = useUiStore((s) => s.cscLockedFromAgent)
  const role = useAuthStore((s) => s.role)

  useEffect(() => {
    const t = setInterval(() => setClock(etTimeString()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const onOnline = () => setOnline(true)
    const onOffline = () => setOnline(false)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)
    return () => {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  // Until we have a streaming model/pipeline health endpoint wired into the
  // shell, derive a sensible "is this view live or replayed" indicator from
  // the agent-locked flag. Production wiring will replace these with the
  // real health probes from /ops.
  const netState: LedState = online ? 'ok' : 'err'
  const modelState: LedState = lockedFromAgent ? 'warn' : 'ok'
  const scrapeState: LedState = role === 'admin' ? 'ok' : 'idle'

  return (
    <footer className={styles.bar} aria-label="System status">
      <Led label="NET" state={netState} value={online ? 'live' : 'offline'} />
      <Led label="MODEL" state={modelState} value={lockedFromAgent ? 'agent-locked' : 'live'} />
      <Led label="SCRAPE" state={scrapeState} value={scrapeState === 'ok' ? 'nominal' : 'standby'} />
      <span className={styles.flex} />
      <span className={styles.clock} aria-label={`Eastern time ${clock}`}>
        {clock} <span className={styles.clockSuffix}>ET</span>
      </span>
    </footer>
  )
}

function Led({ label, state, value }: { label: string; state: LedState; value: string }) {
  return (
    <span className={styles.group} title={`${label}: ${value}`}>
      <span className={ledClass(state)} aria-hidden />
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </span>
  )
}

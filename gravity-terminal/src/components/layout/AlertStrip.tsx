import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAlertStore } from '../../stores/alertStore'
import { useAthleteStore } from '../../stores/athleteStore'
import { usePreferencesStore, watchlistPromptForOrgType } from '../../stores/preferencesStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import styles from './AlertStrip.module.css'

const SPORT_LABEL: Record<string, string> = {
  CFB: 'CFB',
  NCAAB: 'MBB',
  NCAAW: 'WBB',
}

export function AlertStrip() {
  const navigate = useNavigate()
  const orgType = usePreferencesStore((s) => s.orgType)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const wl = useWatchlistStore((s) => s.athletes)
  const alerts = useAlertStore((s) => s.alerts)
  const markRead = useAlertStore((s) => s.markRead)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)
  const setFinderOpen = useUiStore((s) => s.setWatchlistFinderOpen)
  const setInitialNavDone = usePreferencesStore((s) => s.setInitialNavDone)

  const openAthlete = (athleteId: string, alertId?: string) => {
    if (alertId) markRead(alertId)
    setInitialNavDone()
    void setActive(athleteId)
    navigate('/')
  }

  const sportHint = useMemo(
    () =>
      activeSports.length
        ? activeSports.map((s) => SPORT_LABEL[s] ?? s).join(' · ')
        : 'CFB',
    [activeSports],
  )

  if (wl.length === 0) {
    return (
      <div className={styles.strip} role="status">
        <span className={styles.label}>WATCHLIST</span>
        <span className={styles.msg}>{watchlistPromptForOrgType(orgType)}</span>
        <button type="button" className={styles.linkBtn} onClick={() => setFinderOpen(true)}>
          + FIND
        </button>
        <span className={styles.meta}>{sportHint}</span>
      </div>
    )
  }

  if (!alerts.length) {
    return (
      <div className={styles.strip} role="status">
        <span className={styles.label}>ALERTS</span>
        <span className={styles.msg}>No alerts for your watchlist in the selected sports.</span>
        <button type="button" className={styles.linkBtn} onClick={() => navigate('/monitoring')}>
          ALERT CENTER
        </button>
        <span className={styles.meta}>{sportHint}</span>
      </div>
    )
  }

  return (
    <div className={styles.strip} role="region" aria-label="Alerts">
      <span className={styles.label}>ALERTS</span>
      <div className={styles.scroller}>
        {alerts.slice(0, 12).map((a) => (
          <button
            key={a.alert_id}
            type="button"
            className={styles.pill}
            onClick={() => openAthlete(a.athlete_id, a.alert_id)}
            title={a.description}
          >
            <span className={styles.pillName}>{a.athlete_name}</span>
            <span className={styles.pillDesc}>{a.description}</span>
          </button>
        ))}
      </div>
      <button type="button" className={styles.linkBtn} onClick={() => navigate('/monitoring')}>
        VIEW ALL
      </button>
    </div>
  )
}

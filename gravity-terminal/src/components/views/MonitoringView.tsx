import { useNavigate } from 'react-router-dom'
import { formatNilMillions, formatScore } from '../../lib/formatters'
import { formatFeedTime } from '../../lib/time'
import type { AlertRecord, AlertType } from '../../types/alerts'
import { useAlertStore } from '../../stores/alertStore'
import { useAthleteStore } from '../../stores/athleteStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import styles from './MonitoringView.module.css'

function formatAlertChange(a: AlertRecord) {
  if (a.numeric_change == null) return '\u2014'
  if (a.alert_type === 'NIL_SIGNAL' || a.alert_type === 'DEAL_DETECTED') {
    const v = Math.abs(a.numeric_change)
    if (v >= 1_000_000) return `${a.numeric_change < 0 ? '\u2212' : ''}$${(v / 1_000_000).toFixed(1)}M`
    return `${a.numeric_change < 0 ? '\u2212' : ''}$${Math.round(v / 1000)}K`
  }
  return formatScore(a.numeric_change)
}

const BADGE: Record<AlertType, string> = {
  SCORE_MOVE: styles.badgeScore,
  NIL_SIGNAL: styles.badgeNil,
  RISK_FLAG: styles.badgeRisk,
  DEAL_DETECTED: styles.badgeDeal,
}

export function MonitoringView() {
  const navigate = useNavigate()
  const alerts = useAlertStore((s) => s.alerts)
  const markRead = useAlertStore((s) => s.markRead)
  const wl = useWatchlistStore((s) => s.athletes)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)

  const openAthlete = async (a: AlertRecord) => {
    markRead(a.alert_id)
    await setActive(a.athlete_id)
    navigate('/')
  }

  return (
    <div className={styles.root}>
      <div className={styles.title}>ALERT FEED</div>
      <div className={styles.feed}>
        {alerts.map((a) => (
          <button key={a.alert_id} type="button" className={styles.feedRow} onClick={() => void openAthlete(a)}>
            <span className={styles.ts}>{formatFeedTime(a.timestamp)}</span>
            <span className={styles.who}>
              {a.athlete_name}
              {a.school ? ` · ${a.school}` : ''}
            </span>
            <span className={`${styles.badge} ${BADGE[a.alert_type]}`}>
              {a.alert_type.replaceAll('_', ' ')}
            </span>
            <span className={styles.desc}>{a.description}</span>
            <span className={styles.num}>{formatAlertChange(a)}</span>
          </button>
        ))}
      </div>

      <div className={styles.title}>WATCHLIST GRID</div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>NAME</th>
              <th className={styles.thR}>GS</th>
              <th className={styles.thR}>NIL EST.</th>
              <th className={styles.thR}>VEL</th>
              <th className={styles.thR}>RISK</th>
            </tr>
          </thead>
          <tbody>
            {wl.map((x) => (
              <tr key={x.athlete_id}>
                <td className={styles.td}>{x.name}</td>
                <td className={styles.tdR}>{formatScore(x.gravity_score)}</td>
                <td className={styles.tdR}>{formatNilMillions(x.nil_valuation_consensus)}</td>
                <td className={styles.tdR}>{formatScore(x.velocity_score)}</td>
                <td className={styles.tdR}>{formatScore(x.risk_score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

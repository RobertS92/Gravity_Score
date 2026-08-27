import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatNilValue, formatScore } from '../../lib/formatters'
import { formatFeedTime } from '../../lib/time'
import { ALERT_TYPES, type AlertRecord, type AlertType } from '../../types/alerts'
import { useAlertStore } from '../../stores/alertStore'
import { useAthleteStore } from '../../stores/athleteStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { ActionButton } from '../shared/ActionButton'
import styles from './MonitoringView.module.css'

function formatAlertChange(a: AlertRecord) {
  if (a.numeric_change == null) return '\u2014'
  if (a.alert_type === 'NIL_SIGNAL' || a.alert_type === 'DEAL_DETECTED') {
    const v = Math.abs(a.numeric_change)
    // Persisted score_alerts rows store Gravity delta in `delta`, not dollars.
    if (v < 1000) {
      const sign = a.numeric_change > 0 ? '+' : ''
      return `${sign}${formatScore(a.numeric_change)}`
    }
    if (v >= 1_000_000) return `${a.numeric_change < 0 ? '\u2212' : ''}$${(v / 1_000_000).toFixed(1)}M`
    return `${a.numeric_change < 0 ? '\u2212' : ''}$${Math.round(v / 1000)}K`
  }
  const sign = a.numeric_change > 0 ? '+' : ''
  return `${sign}${formatScore(a.numeric_change)}`
}

const BADGE: Record<AlertType, string> = {
  SCORE_MOVE: styles.badgeScore,
  NIL_SIGNAL: styles.badgeNil,
  RISK_FLAG: styles.badgeRisk,
  DEAL_DETECTED: styles.badgeDeal,
}

const TYPE_LABEL: Record<AlertType, string> = {
  SCORE_MOVE: 'SCORE MOVE',
  NIL_SIGNAL: 'NIL SIGNAL',
  RISK_FLAG: 'RISK FLAG',
  DEAL_DETECTED: 'DEAL',
}

export function MonitoringView() {
  const navigate = useNavigate()
  const alerts = useAlertStore((s) => s.alerts)
  const unreadCount = useAlertStore((s) => s.unreadCount)
  const isLoading = useAlertStore((s) => s.isLoading)
  const error = useAlertStore((s) => s.error)
  const markRead = useAlertStore((s) => s.markRead)
  const markAllRead = useAlertStore((s) => s.markAllRead)
  const loadAlerts = useAlertStore((s) => s.loadAlerts)
  const readIds = useAlertStore((s) => s.readIds)
  const wl = useWatchlistStore((s) => s.athletes)
  const loadWatchlist = useWatchlistStore((s) => s.loadWatchlist)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)
  const setFinderOpen = useUiStore((s) => s.setWatchlistFinderOpen)
  const setInitialNavDone = usePreferencesStore((s) => s.setInitialNavDone)
  const [typeFilter, setTypeFilter] = useState<AlertType | 'ALL'>('ALL')

  useEffect(() => {
    void loadAlerts()
    void loadWatchlist()
  }, [loadAlerts, loadWatchlist])

  const openAthlete = (a: AlertRecord) => {
    markRead(a.alert_id)
    setInitialNavDone()
    void setActive(a.athlete_id)
    navigate('/')
  }

  const isUnread = (a: AlertRecord) => !a.read && !readIds.has(a.alert_id)

  const filtered = useMemo(
    () => (typeFilter === 'ALL' ? alerts : alerts.filter((a) => a.alert_type === typeFilter)),
    [alerts, typeFilter],
  )

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>ALERT CENTER</h1>
          <p className={styles.subtitle}>
            Watchlist score moves (3+ pts), NIL P50 at $250K+, and elevated risk. Click a row to
            open the athlete.
          </p>
        </div>
        <div className={styles.headerStats}>
          <div className={styles.stat}>
            <span className={styles.statLabel}>UNREAD</span>
            <span className={styles.statValue}>{unreadCount}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>FEED</span>
            <span className={styles.statValue}>{alerts.length}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>WATCHLIST</span>
            <span className={styles.statValue}>{wl.length}</span>
          </div>
        </div>
      </header>

      <div className={styles.toolbar}>
        <div className={styles.chipRow}>
          <button
            type="button"
            className={typeFilter === 'ALL' ? styles.chipActive : styles.chip}
            onClick={() => setTypeFilter('ALL')}
          >
            ALL
          </button>
          {ALERT_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={typeFilter === t ? styles.chipActive : styles.chip}
              onClick={() => setTypeFilter(t)}
            >
              {TYPE_LABEL[t]}
            </button>
          ))}
        </div>
        <div className={styles.toolbarActions}>
          <ActionButton variant="secondary" onClick={() => void loadAlerts()} disabled={isLoading}>
            {isLoading ? 'LOADING…' : 'REFRESH'}
          </ActionButton>
          <ActionButton variant="secondary" onClick={markAllRead} disabled={unreadCount === 0}>
            MARK ALL READ
          </ActionButton>
        </div>
      </div>

      {error && <div className={styles.error}>Could not load alerts: {error}</div>}

      {wl.length === 0 && (
        <div className={styles.emptyCard}>
          <div className={styles.emptyTitle}>No athletes on your watchlist</div>
          <p className={styles.emptyCopy}>
            Alert Center only monitors players you watch. Add athletes to start seeing score moves,
            NIL signals, and risk flags.
          </p>
          <ActionButton variant="primary" onClick={() => setFinderOpen(true)}>
            + FIND PLAYERS
          </ActionButton>
        </div>
      )}

      <div className={styles.sectionLabel}>ALERT FEED</div>
      <div className={styles.feed}>
        {isLoading && alerts.length === 0 && <div className={styles.empty}>Loading alerts…</div>}
        {!isLoading && filtered.length === 0 && wl.length > 0 && (
          <div className={styles.empty}>
            {typeFilter === 'ALL'
              ? 'No score moves or threshold signals yet for your watchlist in the selected sports.'
              : `No ${TYPE_LABEL[typeFilter].toLowerCase()} alerts in the current feed.`}
          </div>
        )}
        {filtered.map((a) => (
          <button
            key={a.alert_id}
            type="button"
            className={`${styles.feedRow} ${isUnread(a) ? styles.feedRowUnread : ''}`}
            onClick={() => openAthlete(a)}
          >
            <span className={styles.ts}>{formatFeedTime(a.timestamp)}</span>
            <span className={styles.who}>
              {a.athlete_name}
              {a.school ? ` · ${a.school}` : ''}
            </span>
            <span className={`${styles.badge} ${BADGE[a.alert_type]}`}>
              {TYPE_LABEL[a.alert_type]}
              {a.source === 'live' ? ' · LIVE' : ''}
            </span>
            <span className={styles.desc}>{a.description}</span>
            <span className={styles.num}>{formatAlertChange(a)}</span>
          </button>
        ))}
      </div>

      <div className={styles.sectionLabel}>WATCHLIST GRID</div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>NAME</th>
              <th className={styles.th}>SCHOOL</th>
              <th className={styles.thR}>GS</th>
              <th className={styles.thR}>NIL EST.</th>
              <th className={styles.thR}>VEL</th>
              <th className={styles.thR}>RISK</th>
            </tr>
          </thead>
          <tbody>
            {wl.length === 0 && (
              <tr>
                <td className={styles.emptyCell} colSpan={6}>
                  Empty — use + FIND to add athletes.
                </td>
              </tr>
            )}
            {wl.map((x) => (
              <tr
                key={x.athlete_id}
                className={styles.clickRow}
                onClick={() => {
                  setInitialNavDone()
                  void setActive(x.athlete_id)
                  navigate('/')
                }}
              >
                <td className={styles.td}>{x.name}</td>
                <td className={styles.td}>{x.school ?? '—'}</td>
                <td className={styles.tdR}>{formatScore(x.gravity_score)}</td>
                <td className={styles.tdR}>{formatNilValue(x.nil_valuation_consensus)}</td>
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

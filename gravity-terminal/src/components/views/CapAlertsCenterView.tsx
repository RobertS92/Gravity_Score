import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCapAlerts, type CapSport } from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

export function CapAlertsCenterView() {
  const orgId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() => primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports))
  const [data, setData] = useState<Awaited<ReturnType<typeof fetchCapAlerts>> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])

  const load = useCallback(async () => {
    if (!orgId) return
    setErr(null)
    try {
      setData(await fetchCapAlerts(orgId, sport))
    } catch (e) {
      setErr(String(e))
    }
  }, [orgId, sport])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Alerts Center</div>
        <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
          <option value="CFB">CFB</option>
          <option value="NCAAB">NCAAB</option>
          <option value="NCAAW">NCAAW</option>
        </select>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.grid2}>
        {(data?.derived ?? []).map((a, idx) => (
          <div key={`${a.type}-${idx}`} className={styles.metric}>
            <div className={styles.metricLabel}>{a.severity.toUpperCase()}</div>
            <div className={styles.metricValue}>{a.title}</div>
            <div className={styles.muted}>Metric: {a.value.toFixed(2)}</div>
          </div>
        ))}
      </div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Created</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Title</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {(data?.events ?? []).map((e) => (
              <tr key={e.id}>
                <td>{e.created_at ?? '—'}</td>
                <td>{e.alert_type}</td>
                <td>{e.severity}</td>
                <td>{e.title}</td>
                <td>{e.description ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

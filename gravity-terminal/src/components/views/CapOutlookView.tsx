import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCapOutlook, type CapSport } from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

function money(cents: number | null | undefined) {
  if (cents == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(
    cents / 100,
  )
}

export function CapOutlookView() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() =>
    primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports),
  )
  const [years, setYears] = useState<Array<{ fiscal_year: number; committed_cents: number; incentive_exposure_cents: number; headcount: number; available_cap_cents: number | null }>>([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])

  const load = useCallback(async () => {
    if (!organizationId) return
    setErr(null)
    try {
      const r = await fetchCapOutlook(organizationId, sport)
      setYears(r.years)
    } catch (e) {
      setErr(String(e))
    }
  }, [organizationId, sport])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>5-Year Outlook</div>
        <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
          <option value="CFB">CFB</option>
          <option value="NCAAB">NCAAB</option>
          <option value="NCAAW">NCAAW</option>
        </select>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Year</th>
              <th>Committed</th>
              <th>Incentive Exposure</th>
              <th>Headcount</th>
              <th>Available</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {years.map((y) => {
              const risk = y.available_cap_cents == null ? 'unknown' : y.available_cap_cents < 0 ? 'critical' : y.available_cap_cents < 2_000_000_00 ? 'warning' : 'healthy'
              return (
                <tr key={y.fiscal_year}>
                  <td>{y.fiscal_year}</td>
                  <td>{money(y.committed_cents)}</td>
                  <td>{money(y.incentive_exposure_cents)}</td>
                  <td>{y.headcount}</td>
                  <td>{money(y.available_cap_cents)}</td>
                  <td>
                    <span className={risk === 'critical' ? styles.statusCritical : styles.muted}>{risk.toUpperCase()}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

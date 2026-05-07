import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCapCashFlow, type CapCashFlowResponse, type CapSport } from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

function money(cents: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(cents / 100)
}

export function CapCashFlowView() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() =>
    primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports),
  )
  const [year, setYear] = useState<number>(new Date().getFullYear())
  const [data, setData] = useState<CapCashFlowResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])

  const load = useCallback(async () => {
    if (!organizationId) return
    setErr(null)
    try {
      setData(await fetchCapCashFlow(organizationId, sport, year))
    } catch (e) {
      setErr(String(e))
    }
  }, [organizationId, sport, year])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Cash Flow Planner (July-June)</div>
        <div className={styles.controls}>
          <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
            <option value="CFB">CFB</option>
            <option value="NCAAB">NCAAB</option>
            <option value="NCAAW">NCAAW</option>
          </select>
          <input className={styles.input} value={year} onChange={(e) => setYear(Number(e.target.value) || new Date().getFullYear())} />
        </div>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Month</th>
              <th>Cap</th>
              <th>Third-party</th>
              <th>Incentives</th>
              <th>Total</th>
              <th>Cumulative</th>
            </tr>
          </thead>
          <tbody>
            {(data?.months ?? []).map((m) => (
              <tr key={m.month}>
                <td>{m.month}</td>
                <td>{money(m.cap_cents)}</td>
                <td>{money(m.third_party_cents)}</td>
                <td>{money(m.incentive_cents)}</td>
                <td>{money(m.total_cents)}</td>
                <td>{money(m.cumulative_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

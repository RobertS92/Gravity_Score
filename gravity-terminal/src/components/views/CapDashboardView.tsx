import type { CSSProperties } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  type CapContract,
  type CapSport,
  fetchCapContracts,
  fetchCapOutlook,
  fetchCapRollup,
  fetchCapUtilization,
} from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapDashboardView.module.css'

function fmtMoney(cents: number | null | undefined) {
  if (cents == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(
    cents / 100,
  )
}

export function CapDashboardView() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const role = useAuthStore((s) => s.role)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() => primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports))

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])
  const fy = useMemo(() => new Date().getFullYear(), [])
  const [util, setUtil] = useState<Awaited<ReturnType<typeof fetchCapUtilization>> | null>(null)
  const [contracts, setContracts] = useState<CapContract[]>([])
  const [outlook, setOutlook] = useState<Awaited<ReturnType<typeof fetchCapOutlook>> | null>(null)
  const [rollup, setRollup] = useState<Awaited<ReturnType<typeof fetchCapRollup>> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!organizationId) {
      setErr('No organization linked to this account. Apply migration 006 and set user_accounts.organization_id.')
      return
    }
    setErr(null)
    try {
      const [u, c, o] = await Promise.all([
        fetchCapUtilization(organizationId, sport, fy),
        fetchCapContracts(organizationId, sport),
        fetchCapOutlook(organizationId, sport),
      ])
      setUtil(u)
      setContracts(c.contracts)
      setOutlook(o)
      if (role === 'admin' || role === 'school_admin') {
        const r = await fetchCapRollup(organizationId)
        setRollup(r)
      } else {
        setRollup(null)
      }
    } catch (e) {
      setErr(String(e))
    }
  }, [organizationId, sport, fy, role])

  useEffect(() => {
    void load()
  }, [load])

  const pct = util?.utilization_pct ?? null
  const ringStyle = {
    ['--pct' as string]: String(pct != null ? Math.min(pct, 100) : 0),
  } as CSSProperties

  let banner: { kind: 'warn' | 'bad' | 'info'; text: string } | null = null
  if (pct != null) {
    if (pct > 100) banner = { kind: 'bad', text: 'Over cap — committed spend exceeds allocation.' }
    else if (pct >= 95) banner = { kind: 'bad', text: 'Critical — under 5% cap headroom.' }
    else if (pct >= 80) banner = { kind: 'warn', text: 'Elevated utilization (80–95%).' }
  }

  const leaderboard = useMemo(() => {
    return [...contracts].filter((c) => !c.third_party_flag && c.base_comp > 0).slice(0, 12)
  }, [contracts])

  return (
    <div className={styles.root}>
      <header>
        <h1 className={styles.title}>CAPIQ — ROSTER CAP</h1>
        <p className={styles.muted}>Utilization, official contracts, and five-year outlook.</p>
      </header>

      {err && <div className={styles.banner}>{err}</div>}
      {banner && (
        <div className={`${styles.banner} ${banner.kind === 'bad' ? styles.bannerBad : styles.bannerWarn}`}>
          {banner.text}
        </div>
      )}

      <div className={styles.controls}>
        <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
          <option value="CFB">CFB</option>
          <option value="NCAAB">NCAAB</option>
          <option value="NCAAW">NCAAW</option>
        </select>
        <span className={styles.muted}>Fiscal year {fy}</span>
        <Link className={styles.linkBtn} to="/cap/scenarios">
          SCENARIOS
        </Link>
        <Link className={styles.linkBtn} to="/cap/school-data">
          SCHOOL DATA
        </Link>
      </div>

      <div className={styles.row}>
        <div className={styles.ringWrap} style={ringStyle}>
          <div className={styles.ringInner}>
            <span className={styles.ringPct}>{pct != null ? `${pct.toFixed(0)}%` : '—'}</span>
            <span className={styles.ringLabel}>UTILIZATION</span>
          </div>
        </div>
        <div>
          <div className={styles.muted}>Committed (cap)</div>
          <div style={{ fontSize: 20, fontWeight: 600 }}>{fmtMoney(util?.committed_cents)}</div>
          <div className={styles.muted} style={{ marginTop: 8 }}>
            Allocation {fmtMoney(util?.total_allocation_cents)}
          </div>
          <div className={styles.muted} style={{ marginTop: 8 }}>
            Third-party (ex cap) {fmtMoney(util?.third_party_cents)}
          </div>
          <div className={styles.muted} style={{ marginTop: 8 }}>
            Incentive exposure {fmtMoney(util?.incentive_exposure_cents)}
          </div>
        </div>
      </div>

      {(role === 'admin' || role === 'school_admin') && rollup && (
        <section>
          <h2 className={styles.title} style={{ fontSize: 12 }}>
            MULTI-SPORT ROLLUP
          </h2>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>SPORT</th>
                <th>YEAR</th>
                <th>COMMITTED</th>
                <th>ALLOCATION</th>
                <th>PCT</th>
              </tr>
            </thead>
            <tbody>
              {(rollup.sports as Array<Record<string, unknown>>).map((s) => (
                <tr key={String(s.sport)}>
                  <td>{String(s.sport)}</td>
                  <td>{s.fiscal_year != null ? String(s.fiscal_year) : '—'}</td>
                  <td>{fmtMoney(s.committed_cents as number)}</td>
                  <td>{fmtMoney(s.total_allocation_cents as number | null)}</td>
                  <td>{s.utilization_pct != null ? `${Number(s.utilization_pct).toFixed(1)}%` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <h2 className={styles.title} style={{ fontSize: 12 }}>
          FIVE-YEAR OUTLOOK
        </h2>
        {outlook && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>YEAR</th>
                <th>COMMITTED</th>
                <th>INCENTIVE EXP</th>
                <th>HEADCOUNT</th>
                <th>AVAILABLE</th>
              </tr>
            </thead>
            <tbody>
              {outlook.years.map((y) => (
                <tr key={y.fiscal_year}>
                  <td>{y.fiscal_year}</td>
                  <td>{fmtMoney(y.committed_cents)}</td>
                  <td>{fmtMoney(y.incentive_exposure_cents)}</td>
                  <td>{y.headcount}</td>
                  <td>{fmtMoney(y.available_cap_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2 className={styles.title} style={{ fontSize: 12 }}>
          OFFICIAL CONTRACTS
        </h2>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ATHLETE</th>
              <th>BASE</th>
              <th>3P</th>
              <th>FY</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c) => (
              <tr key={c.id}>
                <td>{c.athlete_name ?? c.athlete_id}</td>
                <td>{fmtMoney(c.base_comp)}</td>
                <td>{c.third_party_flag ? 'Y' : ''}</td>
                <td>{c.fiscal_year_start}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2 className={styles.title} style={{ fontSize: 12 }}>
          GRAVITY / DOLLAR (PLACEHOLDER)
        </h2>
        <p className={styles.muted}>
          Wire athlete scores into this table in a follow-up; slots reserved for gravity-per-dollar leaderboard.
        </p>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ATHLETE</th>
              <th>COMMIT</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard.map((c) => (
              <tr key={c.id}>
                <td>{c.athlete_name ?? c.athlete_id}</td>
                <td>{fmtMoney(c.base_comp)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}

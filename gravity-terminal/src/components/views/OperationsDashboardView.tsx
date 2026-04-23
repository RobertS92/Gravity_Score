import { useCallback, useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchOperationsDashboard, type OperationsDashboard } from '../../api/operations'
import styles from './OperationsDashboardView.module.css'

function num(n: unknown): string {
  if (n == null) return '—'
  if (typeof n === 'number' && Number.isFinite(n)) return n.toLocaleString()
  if (typeof n === 'string') return n
  return String(n)
}

function statusClass(s: string | undefined) {
  if (!s) return ''
  if (s === 'running') return styles.badgeRun
  if (s === 'failed') return styles.badgeFail
  return styles.badgeDone
}

export function OperationsDashboardView() {
  const [data, setData] = useState<OperationsDashboard | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setErr(null)
    void fetchOperationsDashboard()
      .then(setData)
      .catch((e: unknown) => setErr(String(e)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [load])

  const d = data?.database
  const sc = data?.scrapers
  const jobs = d?.scraper_jobs_recent ?? []
  const chartRows = jobs.slice(0, 10).map((j, i) => ({
    name: (j.job_type ?? `job${i}`).replace(/_/g, ' ').slice(0, 14),
    processed: j.processed_count ?? 0,
    failed: j.failed_count ?? 0,
  }))

  const prog = sc?.jobs_progress as Record<string, unknown> | undefined
  const progJob = prog?.job as Record<string, unknown> | undefined
  const progressPayload = (progJob?.progress ?? null) as Record<string, unknown> | null

  return (
    <div className={styles.root}>
      <div className={styles.toolbar}>
        <div>
          <div className={styles.title}>DATA PIPELINE</div>
          <div className={styles.meta}>
            {loading ? 'Loading…' : data?.generated_at ? `Updated ${data.generated_at}` : ''}
          </div>
        </div>
        <button type="button" className={styles.refreshBtn} onClick={() => void load()}>
          REFRESH
        </button>
      </div>

      {err && <div className={styles.warn}>{err}</div>}
      {data?.scrapers_error && (
        <div className={styles.warn}>
          Scrapers HTTP: {data.scrapers_error}
          <div className={styles.meta} style={{ marginTop: 6 }}>
            Set SCRAPERS_SERVICE_URL + SCRAPERS_SERVICE_API_KEY on the Gravity API process (same as terminal .env for local).
          </div>
        </div>
      )}

      <div className={styles.sectionTitle}>DATABASE</div>
      <div className={styles.grid}>
        <div className={styles.card}>
          <div className={styles.cardLabel}>ATHLETES</div>
          <div className={styles.cardValue}>{num(d?.athletes_total)}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>WITH GRAVITY SCORES</div>
          <div className={styles.cardValue}>{num(d?.athletes_with_scores)}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>SCRAPED (7D)</div>
          <div className={styles.cardValue}>{num(d?.athletes_scraped_7d)}</div>
          <div className={styles.cardSub}>ever: {num(d?.athletes_last_scraped_set)}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>AVG DATA QUALITY</div>
          <div className={styles.cardValue}>
            {d?.avg_data_quality_score != null ? num(d.avg_data_quality_score) : '—'}
          </div>
          <div className={styles.cardSub}>with score: {num(d?.athletes_with_dqs)}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>RAW PAYLOAD ROWS</div>
          <div className={styles.cardValue}>{num(d?.raw_athlete_data_rows)}</div>
          <div className={styles.cardSub}>latest: {d?.raw_athlete_data_latest ?? '—'}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>ROSTER SNAPSHOTS</div>
          <div className={styles.cardValue}>{num(d?.roster_snapshots_rows)}</div>
          <div className={styles.cardSub}>latest date: {d?.roster_snapshots_latest ?? '—'}</div>
        </div>
        <div className={styles.card}>
          <div className={styles.cardLabel}>ROSTER VERIFIED (180D)</div>
          <div className={styles.cardValue}>{num(d?.athletes_roster_verified_180d)}</div>
          <div className={styles.cardSub}>any: {num(d?.athletes_roster_verified)}</div>
        </div>
      </div>

      {chartRows.length > 0 && (
        <>
          <div className={styles.sectionTitle}>RECENT JOBS — PROCESSED VS FAILED</div>
          <div className={styles.chartWrap}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartRows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.5} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    background: 'var(--bg-secondary)',
                    border: '1px solid var(--border-default)',
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="processed" name="Processed" fill="#00ff88" radius={[2, 2, 0, 0]} />
                <Bar dataKey="failed" name="Failed" fill="#ff6b6b" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}

      <div className={styles.sectionTitle}>SCRAPER JOBS (DB)</div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th className={styles.th}>JOB</th>
              <th className={styles.th}>STATUS</th>
              <th className={styles.thR}>OK</th>
              <th className={styles.thR}>FAIL</th>
              <th className={styles.th}>STARTED</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j, idx) => (
              <tr key={`${j.job_type}-${j.started_at}-${idx}`}>
                <td className={styles.td}>{j.job_type ?? '—'}</td>
                <td className={`${styles.td} ${statusClass(j.status)}`}>{j.status ?? '—'}</td>
                <td className={styles.tdR}>{num(j.processed_count)}</td>
                <td className={styles.tdR}>{num(j.failed_count)}</td>
                <td className={styles.td}>{j.started_at?.slice(0, 19) ?? '—'}</td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td className={styles.td} colSpan={5}>
                  No scraper_jobs rows (table missing or empty).
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {prog && Object.keys(prog).length > 0 && (
        <>
          <div className={styles.sectionTitle}>LIVE PROGRESS (SCRAPERS HTTP)</div>
          <div className={styles.jsonBox}>{JSON.stringify(prog, null, 2)}</div>
        </>
      )}

      {progressPayload && Object.keys(progressPayload).length > 0 && (
        <>
          <div className={styles.sectionTitle}>ROSTER SYNC PROGRESS</div>
          <div className={styles.grid}>
            {typeof progressPayload.percent === 'number' && (
              <div className={styles.card}>
                <div className={styles.cardLabel}>PERCENT</div>
                <div className={styles.cardValue}>{progressPayload.percent}%</div>
              </div>
            )}
            {progressPayload.eta_seconds != null && (
              <div className={styles.card}>
                <div className={styles.cardLabel}>ETA (SEC)</div>
                <div className={styles.cardValue}>{num(progressPayload.eta_seconds)}</div>
              </div>
            )}
            {progressPayload.phase != null && (
              <div className={styles.card}>
                <div className={styles.cardLabel}>PHASE</div>
                <div className={styles.cardValue} style={{ fontSize: 14 }}>
                  {String(progressPayload.phase)}
                </div>
              </div>
            )}
            {progressPayload.team_name != null && (
              <div className={styles.card}>
                <div className={styles.cardLabel}>CURRENT TEAM</div>
                <div className={styles.cardValue} style={{ fontSize: 14 }}>
                  {String(progressPayload.team_name)}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {sc?.health && (
        <>
          <div className={styles.sectionTitle}>SCRAPERS /HEALTH</div>
          <div className={styles.jsonBox}>{JSON.stringify(sc.health, null, 2)}</div>
        </>
      )}
    </div>
  )
}

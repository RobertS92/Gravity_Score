import { useCallback, useEffect, useState } from 'react'
import { fetchCapRollup } from '../../api/cap'
import { useAuthStore } from '../../stores/authStore'
import styles from './CapWorkspace.module.css'

function money(cents: number | null | undefined) {
  if (cents == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(cents / 100)
}

export function CapAdminRollupView() {
  const orgId = useAuthStore((s) => s.organizationId)
  const role = useAuthStore((s) => s.role)
  const [sports, setSports] = useState<Array<Record<string, unknown>>>([])
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!orgId) return
    setErr(null)
    try {
      const r = await fetchCapRollup(orgId)
      setSports((r.sports as Array<Record<string, unknown>>) ?? [])
    } catch (e) {
      setErr(String(e))
    }
  }, [orgId])

  useEffect(() => {
    void load()
  }, [load])

  if (role !== 'admin' && role !== 'school_admin') {
    return <section className={styles.page}><div className={styles.card}>Admin rollup is restricted to administrators.</div></section>
  }

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Admin Rollup</div>
        <button className={styles.btnMuted} onClick={() => void load()}>Refresh</button>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Sport</th>
              <th>Year</th>
              <th>Committed</th>
              <th>Allocation</th>
              <th>Remaining</th>
              <th>Utilization</th>
            </tr>
          </thead>
          <tbody>
            {sports.map((s) => {
              const committed = Number(s.committed_cents ?? 0)
              const allocation = s.total_allocation_cents == null ? null : Number(s.total_allocation_cents)
              return (
                <tr key={String(s.sport)}>
                  <td>{String(s.sport)}</td>
                  <td>{s.fiscal_year == null ? '—' : String(s.fiscal_year)}</td>
                  <td>{money(committed)}</td>
                  <td>{money(allocation)}</td>
                  <td>{money(allocation == null ? null : allocation - committed)}</td>
                  <td>{s.utilization_pct == null ? '—' : `${Number(s.utilization_pct).toFixed(1)}%`}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

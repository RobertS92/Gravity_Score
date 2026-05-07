import { useCallback, useEffect, useMemo, useState } from 'react'
import { fetchCapBudgets, type CapSport, upsertCapBudget } from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

function money(cents: number | null | undefined) {
  if (cents == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(cents / 100)
}

export function CapAllocationView() {
  const orgId = useAuthStore((s) => s.organizationId)
  const role = useAuthStore((s) => s.role)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() => primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports))
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([])
  const [year, setYear] = useState<number>(new Date().getFullYear())
  const [allocation, setAllocation] = useState<string>('0')
  const [notes, setNotes] = useState('')
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])

  const load = useCallback(async () => {
    if (!orgId) return
    setErr(null)
    try {
      const r = await fetchCapBudgets(orgId, sport)
      setRows((r.budgets as Array<Record<string, unknown>>) ?? [])
    } catch (e) {
      setErr(String(e))
    }
  }, [orgId, sport])

  useEffect(() => {
    void load()
  }, [load])

  const save = async () => {
    if (!orgId) return
    setErr(null)
    try {
      await upsertCapBudget({
        org_id: orgId,
        sport,
        fiscal_year: year,
        total_allocation: Number(allocation) || 0,
        notes: notes || null,
      })
      setNotes('')
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  if (role !== 'admin' && role !== 'school_admin') {
    return <section className={styles.page}><div className={styles.card}>Cap allocation editing is admin-only.</div></section>
  }

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Cap Allocation</div>
        <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
          <option value="CFB">CFB</option>
          <option value="NCAAB">NCAAB</option>
          <option value="NCAAW">NCAAW</option>
        </select>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.card}>
        <div className={styles.controls}>
          <input className={styles.input} value={year} onChange={(e) => setYear(Number(e.target.value) || new Date().getFullYear())} />
          <input className={styles.input} value={allocation} onChange={(e) => setAllocation(e.target.value)} placeholder="Allocation in cents" />
          <input className={styles.input} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes" />
          <button className={styles.btn} onClick={() => void save()}>Set Allocation</button>
        </div>
      </div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Year</th>
              <th>Allocation</th>
              <th>Notes</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.id)}>
                <td>{String(r.fiscal_year)}</td>
                <td>{money(Number(r.total_allocation ?? 0))}</td>
                <td>{String(r.notes ?? '')}</td>
                <td>{String(r.updated_at ?? '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

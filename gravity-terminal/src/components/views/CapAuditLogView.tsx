import { useCallback, useEffect, useState } from 'react'
import { fetchCapAuditLog, type CapAuditEvent, type CapSport } from '../../api/cap'
import { useAuthStore } from '../../stores/authStore'
import styles from './CapWorkspace.module.css'

export function CapAuditLogView() {
  const orgId = useAuthStore((s) => s.organizationId)
  const role = useAuthStore((s) => s.role)
  const [sport, setSport] = useState<CapSport | ''>('')
  const [events, setEvents] = useState<CapAuditEvent[]>([])
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!orgId) return
    setErr(null)
    try {
      const r = await fetchCapAuditLog(orgId, { sport: sport || undefined, limit: 200 })
      setEvents(r.events)
    } catch (e) {
      setErr(String(e))
    }
  }, [orgId, sport])

  useEffect(() => {
    void load()
  }, [load])

  if (role !== 'admin' && role !== 'school_admin') {
    return <section className={styles.page}><div className={styles.card}>Audit log access is admin-only.</div></section>
  }

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Audit Log</div>
        <div className={styles.controls}>
          <select className={styles.select} value={sport} onChange={(e) => setSport((e.target.value as CapSport) || '')}>
            <option value="">All sports</option>
            <option value="CFB">CFB</option>
            <option value="NCAAB">NCAAB</option>
            <option value="NCAAW">NCAAW</option>
          </select>
          <button className={styles.btnMuted} onClick={() => void load()}>Refresh</button>
        </div>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>When</th>
              <th>Action</th>
              <th>Table</th>
              <th>Record</th>
              <th>User</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td>{e.created_at ?? '—'}</td>
                <td>{e.action}</td>
                <td>{e.table_name}</td>
                <td>{e.record_id.slice(0, 10)}…</td>
                <td>{e.user_id.slice(0, 10)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

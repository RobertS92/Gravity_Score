import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  approveCapScenario,
  fetchCapWorkflowQueue,
  promoteCapScenario,
  type CapSport,
} from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

export function CapWorkflowView() {
  const orgId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() => primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports))
  const [queue, setQueue] = useState<Awaited<ReturnType<typeof fetchCapWorkflowQueue>> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])

  const load = useCallback(async () => {
    if (!orgId) return
    setErr(null)
    try {
      setQueue(await fetchCapWorkflowQueue(orgId, sport))
    } catch (e) {
      setErr(String(e))
    }
  }, [orgId, sport])

  useEffect(() => {
    void load()
  }, [load])

  const onApprove = async (id: string) => {
    try {
      await approveCapScenario(id)
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  const onPromote = async (id: string) => {
    if (!window.confirm('Promote this approved scenario to official?')) return
    try {
      await promoteCapScenario(id)
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  const canApprove = queue?.permissions.can_approve ?? false

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Approvals / Workflow</div>
        <div className={styles.controls}>
          <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
            <option value="CFB">CFB</option>
            <option value="NCAAB">NCAAB</option>
            <option value="NCAAW">NCAAW</option>
          </select>
          <span className={styles.muted}>
            {queue
              ? `Permissions: ${queue.permissions.can_view ? 'V' : '-'}${queue.permissions.can_edit ? 'E' : '-'}${queue.permissions.can_approve ? 'A' : '-'}`
              : ''}
          </span>
        </div>
      </div>
      {err && <div className={styles.card}>{err}</div>}
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Status</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {(queue?.pending ?? []).map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.status}</td>
                <td>{p.updated_at ?? '—'}</td>
                <td>
                  <div className={styles.controls}>
                    {canApprove && p.status === 'draft' && (
                      <button className={styles.btn} onClick={() => void onApprove(p.id)}>Approve</button>
                    )}
                    {canApprove && p.status === 'approved' && (
                      <button className={styles.btn} onClick={() => void onPromote(p.id)}>Promote</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={styles.card}>
        <div className={styles.muted} style={{ marginBottom: 8 }}>Recent Workflow Activity</div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Scenario</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {(queue?.events ?? []).map((e, idx) => (
                <tr key={`${e.scenario_id ?? 'none'}-${idx}`}>
                  <td>{e.created_at ?? '—'}</td>
                  <td>{e.action}</td>
                  <td>{e.scenario_id?.slice(0, 8) ?? '—'}</td>
                  <td>{e.notes ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

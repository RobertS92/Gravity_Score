import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { computeOrgScore, listDataSubmissions, submitAthleteData } from '../../api/data'
import { useAuthStore } from '../../stores/authStore'
import styles from './CapScenariosView.module.css'

export function CapSchoolDataView() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const [athleteId, setAthleteId] = useState('')
  const [fieldsJson, setFieldsJson] = useState('{\n  "instagram_handle": "@example"\n}')
  const [notes, setNotes] = useState('')
  const [verify, setVerify] = useState(false)
  const [subs, setSubs] = useState<Array<Record<string, unknown>>>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const loadSubs = useCallback(async () => {
    if (!organizationId) return
    try {
      const r = await listDataSubmissions(organizationId)
      setSubs((r.submissions as Array<Record<string, unknown>>) ?? [])
    } catch {
      /* ignore */
    }
  }, [organizationId])

  useEffect(() => {
    void loadSubs()
  }, [loadSubs])

  const onSubmit = async () => {
    if (!organizationId || !athleteId.trim()) {
      setErr('organization_id and athlete_id required')
      return
    }
    let fields: Record<string, unknown>
    try {
      fields = JSON.parse(fieldsJson) as Record<string, unknown>
    } catch {
      setErr('Invalid JSON in fields')
      return
    }
    setErr(null)
    setMsg(null)
    try {
      const r = await submitAthleteData({
        org_id: organizationId,
        athlete_id: athleteId.trim(),
        fields,
        source_notes: notes || null,
        run_verification: verify,
      })
      setMsg(`Saved submission ${r.id} — status ${r.status}`)
      await loadSubs()
    } catch (e) {
      setErr(String(e))
    }
  }

  const onOrgScore = async () => {
    if (!organizationId || !athleteId.trim()) return
    setErr(null)
    setMsg(null)
    try {
      const r = await computeOrgScore(organizationId, athleteId.trim())
      setMsg(`Org-enhanced gravity: ${String(r.gravity_score ?? '')}`)
    } catch (e) {
      setErr(String(e))
    }
  }

  return (
    <div className={styles.root}>
      <header className={styles.row}>
        <h1 className={styles.title}>SCHOOL DATA & VERIFICATION</h1>
        <Link className={styles.btn} to="/cap">
          DASHBOARD
        </Link>
      </header>
      <p className={styles.muted}>
        Submissions stay private to your org until verified. Optional stub auto-verification when enabled.
      </p>
      {err && <div className={styles.muted}>{err}</div>}
      {msg && <div className={styles.muted}>{msg}</div>}

      <label className={styles.muted}>Athlete ID (UUID)</label>
      <input className={styles.input} value={athleteId} onChange={(e) => setAthleteId(e.target.value)} />

      <label className={styles.muted}>Fields (JSON)</label>
      <textarea
        className={styles.input}
        style={{ width: '100%', minHeight: 120, fontFamily: 'monospace' }}
        value={fieldsJson}
        onChange={(e) => setFieldsJson(e.target.value)}
      />

      <label className={styles.muted}>Source notes</label>
      <input className={styles.input} value={notes} onChange={(e) => setNotes(e.target.value)} />

      <label className={styles.row}>
        <input type="checkbox" checked={verify} onChange={(e) => setVerify(e.target.checked)} />
        <span className={styles.muted}>Run stub auto-verification</span>
      </label>

      <div className={styles.row}>
        <button type="button" className={styles.btn} onClick={() => void onSubmit()}>
          SUBMIT
        </button>
        <button type="button" className={styles.btn} onClick={() => void onOrgScore()}>
          ORG-ENHANCED SCORE
        </button>
      </div>

      <h2 className={styles.title} style={{ fontSize: 11 }}>
        RECENT SUBMISSIONS
      </h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>ID</th>
            <th>ATHLETE</th>
            <th>STATUS</th>
            <th>CREATED</th>
          </tr>
        </thead>
        <tbody>
          {subs.map((s) => (
            <tr key={String(s.id)}>
              <td>{String(s.id).slice(0, 8)}…</td>
              <td>{String(s.athlete_id).slice(0, 8)}…</td>
              <td>{String(s.status)}</td>
              <td>{String(s.created_at ?? '')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

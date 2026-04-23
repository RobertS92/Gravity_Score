import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  type CapSport,
  createCapScenario,
  fetchCapCompare,
  fetchCapScenarios,
  promoteCapScenario,
} from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapScenariosView.module.css'

export function CapScenariosView() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const role = useAuthStore((s) => s.role)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() => primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports))

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])
  const [name, setName] = useState('New scenario')
  const [list, setList] = useState<Array<Record<string, unknown>>>([])
  const [compareId, setCompareId] = useState<string | null>(null)
  const [compareJson, setCompareJson] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!organizationId) {
      setErr('No organization_id on account.')
      return
    }
    setErr(null)
    try {
      const r = await fetchCapScenarios(organizationId, sport)
      setList((r.scenarios as Array<Record<string, unknown>>) ?? [])
    } catch (e) {
      setErr(String(e))
    }
  }, [organizationId, sport])

  useEffect(() => {
    void load()
  }, [load])

  const onCreate = async () => {
    if (!organizationId) return
    try {
      await createCapScenario({ org_id: organizationId, sport, name: name.trim() || 'Scenario' })
      setName('New scenario')
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  const onCompare = async (id: string) => {
    try {
      const c = await fetchCapCompare(id)
      setCompareId(id)
      setCompareJson(JSON.stringify(c, null, 2))
    } catch (e) {
      setErr(String(e))
    }
  }

  const onPromote = async (id: string) => {
    if (!window.confirm('Promote this scenario to the official roster?')) return
    try {
      await promoteCapScenario(id)
      await load()
      setCompareJson(null)
      setCompareId(null)
    } catch (e) {
      setErr(String(e))
    }
  }

  const canPromote = role === 'admin' || role === 'school_admin'

  return (
    <div className={styles.root}>
      <header className={styles.row}>
        <h1 className={styles.title}>CAPIQ — SCENARIOS</h1>
        <Link className={styles.btn} to="/cap">
          DASHBOARD
        </Link>
      </header>
      {err && <div className={styles.muted}>{err}</div>}

      <div className={styles.row}>
        <select className={styles.input} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
          <option value="CFB">CFB</option>
          <option value="NCAAB">NCAAB</option>
          <option value="NCAAW">NCAAW</option>
        </select>
        <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
        <button type="button" className={styles.btn} onClick={() => void onCreate()}>
          CREATE
        </button>
      </div>

      <table className={styles.table}>
        <thead>
          <tr>
            <th>NAME</th>
            <th>STATUS</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {list.map((s) => {
            const id = String(s.id)
            return (
              <tr key={id}>
                <td>{String(s.name)}</td>
                <td>{String(s.status)}</td>
                <td>
                  <button type="button" className={styles.btn} onClick={() => void onCompare(id)}>
                    COMPARE
                  </button>
                  {canPromote && String(s.status) === 'draft' && (
                    <button type="button" className={styles.btn} onClick={() => void onPromote(id)}>
                      PROMOTE
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {compareJson && (
        <section>
          <h2 className={styles.title} style={{ fontSize: 11 }}>
            COMPARE {compareId}
          </h2>
          <pre className={styles.pre}>{compareJson}</pre>
        </section>
      )}
    </div>
  )
}

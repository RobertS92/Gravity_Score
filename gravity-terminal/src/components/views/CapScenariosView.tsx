import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  approveCapScenario,
  type CapSport,
  createCapScenario,
  fetchCapCompare,
  fetchCapScenarios,
  promoteCapScenario,
} from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

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
  const [list, setList] = useState<Awaited<ReturnType<typeof fetchCapScenarios>>['scenarios']>([])
  const [compareId, setCompareId] = useState<string | null>(null)
  const [compare, setCompare] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!organizationId) {
      setErr('No organization linked yet. Complete onboarding or ask an admin for CapIQ access.')
      return
    }
    setErr(null)
    try {
      const r = await fetchCapScenarios(organizationId, sport)
      setList(r.scenarios ?? [])
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
      setCompare(c)
    } catch (e) {
      setErr(String(e))
    }
  }

  const onPromote = async (id: string) => {
    if (!window.confirm('Promote this scenario to the official roster?')) return
    try {
      await promoteCapScenario(id)
      await load()
      setCompare(null)
      setCompareId(null)
    } catch (e) {
      setErr(String(e))
    }
  }

  const canPromote = role === 'admin' || role === 'school_admin'
  const onApprove = async (id: string) => {
    try {
      await approveCapScenario(id)
      await load()
    } catch (e) {
      setErr(String(e))
    }
  }

  const compareRows = useMemo(() => {
    if (!compare) return []
    const official = (compare.official as { athletes?: Array<Record<string, unknown>> } | undefined)?.athletes ?? []
    const scenario = (compare.scenario as { athletes?: Array<Record<string, unknown>> } | undefined)?.athletes ?? []
    const officialMap = new Map<string, Record<string, unknown>>(
      official.map((r) => [String(r.athlete_id), r]),
    )
    const scenarioMap = new Map<string, Record<string, unknown>>(
      scenario.map((r) => [String(r.athlete_id), r]),
    )
    const ids = new Set<string>([...officialMap.keys(), ...scenarioMap.keys()])
    return Array.from(ids).map((aid) => {
      const o = officialMap.get(aid)
      const s = scenarioMap.get(aid)
      const name = String((s?.athlete_name ?? o?.athlete_name ?? aid) || aid)
      const oBase = Number(o?.base_comp ?? 0)
      const sBase = Number(s?.base_comp ?? 0)
      return {
        athlete_id: aid,
        athlete_name: name,
        official_base: oBase,
        scenario_base: sBase,
        delta_base: sBase - oBase,
        movement: !o ? 'ADD' : !s ? 'REMOVE' : sBase !== oBase ? 'ADJUST' : 'UNCHANGED',
      }
    })
  }, [compare])

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Scenarios</h1>
      </header>
      {err && <div className={styles.muted}>{err}</div>}

      <div className={styles.controls}>
        <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
          <option value="CFB">CFB</option>
          <option value="NCAAB">NCAAB</option>
          <option value="NCAAW">NCAAW</option>
        </select>
        <input className={styles.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
        <button type="button" className={styles.btn} onClick={() => void onCreate()}>
          CREATE
        </button>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Impact</th>
              <th>Actions</th>
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
                    Gravity {s.aggregate_gravity_score != null ? Number(s.aggregate_gravity_score).toFixed(2) : '—'}
                  </td>
                  <td>
                    <div className={styles.controls}>
                      <button type="button" className={styles.btn} onClick={() => void onCompare(id)}>
                        Compare
                      </button>
                      {canPromote && String(s.status) === 'draft' && (
                        <button type="button" className={styles.btnMuted} onClick={() => void onApprove(id)}>
                          Approve
                        </button>
                      )}
                      {canPromote && String(s.status) === 'approved' && (
                        <button type="button" className={styles.btn} onClick={() => void onPromote(id)}>
                          Promote
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {compare && (
        <section className={styles.card}>
          <h2 className={styles.title}>Scenario vs Official ({compareId?.slice(0, 8)})</h2>
          <div className={styles.grid2}>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Gravity Delta</div>
              <div className={styles.metricValue}>{Number((compare.delta as Record<string, unknown> | undefined)?.gravity ?? 0).toFixed(2)}</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Cost Delta</div>
              <div className={styles.metricValue}>
                {Number((compare.delta as Record<string, unknown> | undefined)?.cost_cents ?? 0).toLocaleString()}
              </div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Risk Delta</div>
              <div className={styles.metricValue}>{Number((compare.delta as Record<string, unknown> | undefined)?.risk ?? 0).toFixed(2)}</div>
            </div>
          </div>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Athlete</th>
                  <th>Official Base</th>
                  <th>Scenario Base</th>
                  <th>Delta</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {compareRows.map((r) => (
                  <tr key={r.athlete_id}>
                    <td>{r.athlete_name}</td>
                    <td>{r.official_base.toLocaleString()}</td>
                    <td>{r.scenario_base.toLocaleString()}</td>
                    <td>{r.delta_base.toLocaleString()}</td>
                    <td>{r.movement}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

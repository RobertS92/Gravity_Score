import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createCapContract,
  deleteCapContract,
  fetchCapContracts,
  type CapContract,
  type CapSport,
  patchCapContract,
} from '../../api/cap'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './CapWorkspace.module.css'

function money(cents: number | null | undefined) {
  if (cents == null) return '—'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(
    cents / 100,
  )
}

export function CapRosterView() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const preferredSport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [sport, setSport] = useState<CapSport>(() =>
    primaryCapSportFromPrefs(usePreferencesStore.getState().activeSports),
  )
  const [contracts, setContracts] = useState<CapContract[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, Partial<CapContract>>>({})
  const [newAthleteId, setNewAthleteId] = useState('')
  const [newBase, setNewBase] = useState('0')
  const [newThirdParty, setNewThirdParty] = useState(false)

  useEffect(() => {
    if (!activeSports.includes(sport)) setSport(preferredSport)
  }, [activeSports, sport, preferredSport])

  const load = useCallback(async () => {
    if (!organizationId) {
      setErr('No organization linked yet. Complete onboarding or ask an admin for CapIQ access.')
      return
    }
    setErr(null)
    try {
      const r = await fetchCapContracts(organizationId, sport)
      setContracts(r.contracts)
      setDrafts({})
    } catch (e) {
      setErr(String(e))
    }
  }, [organizationId, sport])

  useEffect(() => {
    void load()
  }, [load])

  const patchDraft = (id: string, patch: Partial<CapContract>) => {
    setDrafts((s) => ({ ...s, [id]: { ...s[id], ...patch } }))
  }

  const saveRow = async (c: CapContract) => {
    const d = drafts[c.id]
    if (!d) return
    setSavingId(c.id)
    try {
      await patchCapContract(c.id, {
        base_comp: d.base_comp ?? c.base_comp,
        status: d.status ?? c.status,
        third_party_flag: d.third_party_flag ?? c.third_party_flag,
      })
      await load()
    } catch (e) {
      setErr(String(e))
    } finally {
      setSavingId(null)
    }
  }

  const expireRow = async (id: string) => {
    setSavingId(id)
    try {
      await deleteCapContract(id)
      await load()
    } catch (e) {
      setErr(String(e))
    } finally {
      setSavingId(null)
    }
  }

  const addNew = async () => {
    if (!organizationId || !newAthleteId.trim()) return
    setSavingId('new')
    try {
      await createCapContract({
        org_id: organizationId,
        athlete_id: newAthleteId.trim(),
        sport,
        base_comp: Number(newBase) || 0,
        incentives: [],
        third_party_flag: newThirdParty,
        payment_schedule: {},
        fiscal_year_start: new Date().getFullYear(),
      })
      setNewAthleteId('')
      setNewBase('0')
      setNewThirdParty(false)
      await load()
    } catch (e) {
      setErr(String(e))
    } finally {
      setSavingId(null)
    }
  }

  return (
    <section className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>Roster Management</div>
        <div className={styles.controls}>
          <select className={styles.select} value={sport} onChange={(e) => setSport(e.target.value as CapSport)}>
            <option value="CFB">CFB</option>
            <option value="NCAAB">NCAAB</option>
            <option value="NCAAW">NCAAW</option>
          </select>
          <span className={styles.muted}>Official contracts: {contracts.length}</span>
        </div>
      </div>
      {err && <div className={styles.card}>{err}</div>}

      <div className={styles.card}>
        <div className={styles.muted} style={{ marginBottom: 8 }}>
          Add player (official roster)
        </div>
        <div className={styles.controls}>
          <input
            className={styles.input}
            placeholder="Athlete UUID"
            value={newAthleteId}
            onChange={(e) => setNewAthleteId(e.target.value)}
          />
          <input className={styles.input} value={newBase} onChange={(e) => setNewBase(e.target.value)} />
          <label className={styles.muted}>
            <input
              type="checkbox"
              checked={newThirdParty}
              onChange={(e) => setNewThirdParty(e.target.checked)}
            />{' '}
            Third-party
          </label>
          <button className={styles.btn} onClick={() => void addNew()} disabled={savingId === 'new'}>
            {savingId === 'new' ? 'Saving…' : 'Add'}
          </button>
        </div>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Athlete</th>
              <th>Status</th>
              <th>Base</th>
              <th>Third-party</th>
              <th>FY</th>
              <th>Gravity</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {contracts.map((c) => {
              const d = drafts[c.id] ?? {}
              return (
                <tr key={c.id}>
                  <td>
                    <div>{c.athlete_name ?? c.athlete_id}</div>
                    <div className={styles.muted}>{c.athlete_id.slice(0, 8)}…</div>
                  </td>
                  <td>
                    <select
                      className={styles.select}
                      value={(d.status as string) ?? c.status}
                      onChange={(e) => patchDraft(c.id, { status: e.target.value })}
                    >
                      <option value="active">Active</option>
                      <option value="draft">Prospect</option>
                      <option value="expired">Expired</option>
                    </select>
                  </td>
                  <td>
                    <input
                      className={styles.input}
                      value={String((d.base_comp as number) ?? c.base_comp)}
                      onChange={(e) => patchDraft(c.id, { base_comp: Number(e.target.value) || 0 })}
                    />
                    <div className={styles.muted}>{money((d.base_comp as number) ?? c.base_comp)}</div>
                  </td>
                  <td>
                    <label className={styles.muted}>
                      <input
                        type="checkbox"
                        checked={(d.third_party_flag as boolean) ?? c.third_party_flag}
                        onChange={(e) => patchDraft(c.id, { third_party_flag: e.target.checked })}
                      />
                      {' '}Yes
                    </label>
                  </td>
                  <td>{c.fiscal_year_start}</td>
                  <td>{c.gravity_score != null ? c.gravity_score.toFixed(1) : '—'}</td>
                  <td>
                    <div className={styles.controls}>
                      <button
                        className={styles.btn}
                        onClick={() => void saveRow(c)}
                        disabled={savingId === c.id}
                      >
                        Save
                      </button>
                      <button
                        className={styles.btnDanger}
                        onClick={() => void expireRow(c.id)}
                        disabled={savingId === c.id}
                      >
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {contracts.length === 0 && (
              <tr>
                <td colSpan={7} className={styles.muted}>
                  No official roster contracts.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

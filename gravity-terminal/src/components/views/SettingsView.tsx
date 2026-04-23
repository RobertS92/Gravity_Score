import { useEffect, useState } from 'react'
import { fetchUserPreferences, patchUserPreferences, type UserPreferences } from '../../api/userPreferences'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './SettingsView.module.css'

const DASH_TABS = [
  { id: 'roster', label: 'CapIQ / Roster' },
  { id: 'market', label: 'Market scan' },
  { id: 'athletes', label: 'NIL intelligence (athletes)' },
  { id: 'deals', label: 'CSC / Deals' },
] as const

const SPORTS = [
  { id: 'CFB', label: 'CFB' },
  { id: 'NCAAB', label: 'NCAAB' },
  { id: 'NCAAW', label: 'NCAAW' },
] as const

function orgLabel(org: string | null): string {
  if (!org) return '—'
  return org.replace(/_/g, ' ')
}

export function SettingsView() {
  const applyFromApi = usePreferencesStore((s) => s.applyFromApi)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [prefs, setPrefs] = useState<UserPreferences | null>(null)
  const [sports, setSports] = useState<string[]>(['CFB'])
  const [orgName, setOrgName] = useState('')
  const [seed, setSeed] = useState('')
  const [tab, setTab] = useState<string>('athletes')
  const [goal, setGoal] = useState('')

  useEffect(() => {
    void (async () => {
      setLoading(true)
      setErr(null)
      try {
        const p = await fetchUserPreferences()
        setPrefs(p)
        setSports(p.sport_preferences?.length ? [...p.sport_preferences] : ['CFB'])
        setOrgName(p.org_name ?? '')
        setSeed(p.team_or_athlete_seed ?? '')
        setTab(p.default_dashboard_tab ?? 'athletes')
        setGoal(p.onboarding_goal ?? '')
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load preferences')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const toggleSport = (id: string) => {
    setSports((prev) => {
      const on = prev.includes(id)
      if (on && prev.length === 1) return prev
      if (on) return prev.filter((x) => x !== id)
      return [...prev, id]
    })
  }

  const onSave = async () => {
    if (!sports.length) {
      setErr('Select at least one sport.')
      return
    }
    setSaving(true)
    setErr(null)
    try {
      const updated = await patchUserPreferences({
        sport_preferences: sports,
        org_name: orgName.trim() || null,
        team_or_athlete_seed: seed.trim() || null,
        default_dashboard_tab: tab,
        onboarding_goal: goal.trim() || null,
      })
      setPrefs(updated)
      applyFromApi(updated)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className={styles.root}>
        <p className={styles.muted}>Loading preferences…</p>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <h1 className={styles.title}>SETTINGS</h1>
      <p className={styles.lead}>Profile and dashboard defaults (saved to your account).</p>
      {err && <div className={styles.error}>{err}</div>}

      <section className={styles.section}>
        <h2 className={styles.h2}>Organization</h2>
        <label className={styles.label}>Organization type</label>
        <div className={styles.readonly}>{orgLabel(prefs?.org_type ?? null)}</div>
        <label className={styles.label}>Organization name</label>
        <input className={styles.input} value={orgName} onChange={(e) => setOrgName(e.target.value)} />
        <label className={styles.label}>Team or program seed (optional)</label>
        <input className={styles.input} value={seed} onChange={(e) => setSeed(e.target.value)} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Sports coverage</h2>
        <div className={styles.row}>
          {SPORTS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`${styles.chip} ${sports.includes(s.id) ? styles.chipOn : ''}`}
              onClick={() => toggleSport(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Default dashboard tab</h2>
        <select className={styles.select} value={tab} onChange={(e) => setTab(e.target.value)}>
          {DASH_TABS.map((t) => (
            <option key={t.id} value={t.id}>
              {t.label}
            </option>
          ))}
        </select>
        {prefs?.athletes_default_sort != null && prefs.athletes_default_sort !== '' && (
          <>
            <label className={styles.label}>Athletes default sort (from onboarding)</label>
            <div className={styles.readonly}>{prefs.athletes_default_sort}</div>
          </>
        )}
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>Goal</h2>
        <textarea
          className={styles.textarea}
          rows={3}
          maxLength={150}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="What you are trying to accomplish in Gravity"
        />
      </section>

      <div className={styles.actions}>
        <button type="button" className={styles.btnPrimary} disabled={saving} onClick={() => void onSave()}>
          {saving ? 'SAVING…' : 'SAVE CHANGES'}
        </button>
      </div>
    </div>
  )
}

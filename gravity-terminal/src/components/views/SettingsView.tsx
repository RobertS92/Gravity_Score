import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchUserPreferences, patchUserPreferences, type UserPreferences } from '../../api/userPreferences'
import {
  capiqFeaturesForMembership,
  formatAccountRole,
  membershipStatusLabel,
  resolveMissingOrgAccessSteps,
} from '../../lib/orgAccess'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './SettingsView.module.css'

type DensityMode = 'comfortable' | 'default' | 'compact'

const DENSITY_STORAGE_KEY = 'gravity.density.v1'

function readDensity(): DensityMode {
  if (typeof window === 'undefined') return 'default'
  const stored = window.localStorage.getItem(DENSITY_STORAGE_KEY)
  if (stored === 'comfortable' || stored === 'default' || stored === 'compact') return stored
  return 'default'
}

function applyDensity(mode: DensityMode) {
  if (typeof document === 'undefined') return
  // `data-density` is consumed by tokens.css / globals.css which scale
  // --space-3, --space-4, etc. depending on the mode.
  if (mode === 'default') {
    document.documentElement.removeAttribute('data-density')
  } else {
    document.documentElement.setAttribute('data-density', mode)
  }
  try {
    window.localStorage.setItem(DENSITY_STORAGE_KEY, mode)
  } catch {
    // ignore storage failures (private mode, full disk, etc.)
  }
}

/** Initialize density from localStorage on first import so the choice
 * survives reloads without waiting for the user to open Settings. */
if (typeof window !== 'undefined') {
  applyDensity(readDensity())
}

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
  const organizationId = useAuthStore((s) => s.organizationId)
  const organizationName = useAuthStore((s) => s.organizationName)
  const organizationSlug = useAuthStore((s) => s.organizationSlug)
  const role = useAuthStore((s) => s.role)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [prefs, setPrefs] = useState<UserPreferences | null>(null)
  const [sports, setSports] = useState<string[]>(['CFB'])
  const [orgName, setOrgName] = useState('')
  const [seed, setSeed] = useState('')
  const [tab, setTab] = useState<string>('athletes')
  const [goal, setGoal] = useState('')
  const [density, setDensity] = useState<DensityMode>(() => readDensity())

  const onDensityChange = (mode: DensityMode) => {
    setDensity(mode)
    applyDensity(mode)
  }

  useEffect(() => {
    void (async () => {
      setLoading(true)
      setErr(null)
      try {
        // Ensure CapIQ membership fields are current when opening Settings.
        await useAuthStore.getState().hydrate()
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

  const hasOrg = Boolean(organizationId)
  const features = useMemo(() => capiqFeaturesForMembership(hasOrg, role), [hasOrg, role])
  const resolveSteps = useMemo(
    () =>
      resolveMissingOrgAccessSteps({
        organizationId,
        orgType: prefs?.org_type ?? null,
        profileOrgName: orgName || prefs?.org_name || null,
      }),
    [organizationId, prefs?.org_type, prefs?.org_name, orgName],
  )

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
        <h2 className={styles.h2}>Profile organization label</h2>
        <p className={styles.hint}>
          This label personalizes your account. It is <strong>not</strong> CapIQ membership and does not unlock
          roster budgets, scenarios, or school data.
        </p>
        <label className={styles.label}>Organization type</label>
        <div className={styles.readonly}>{orgLabel(prefs?.org_type ?? null)}</div>
        <label className={styles.label}>Organization display name (profile only)</label>
        <input
          className={styles.input}
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          placeholder="e.g. SMU — profile label only"
          aria-describedby="org-name-hint"
        />
        <p id="org-name-hint" className={styles.hint}>
          Editing this field updates your preference label only. CapIQ stays linked (or unlinked) based on the
          membership status below.
        </p>
        <label className={styles.label}>Team or program seed (optional)</label>
        <input className={styles.input} value={seed} onChange={(e) => setSeed(e.target.value)} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>CapIQ organization access</h2>
        <p className={styles.hint}>
          CapIQ tools use a linked organization membership on your account, separate from the profile label above.
        </p>
        <label className={styles.label}>Membership status</label>
        <div className={hasOrg ? styles.statusOk : styles.statusWarn}>{membershipStatusLabel(hasOrg)}</div>
        <label className={styles.label}>Linked organization</label>
        <div className={styles.readonly}>
          {hasOrg
            ? `${organizationName?.trim() || 'Linked organization'}${organizationSlug ? ` (${organizationSlug})` : ''}`
            : 'None — CapIQ shows “no organization linked” until membership is attached'}
        </div>
        <label className={styles.label}>Account role</label>
        <div className={styles.readonly}>{formatAccountRole(role)}</div>
        <label className={styles.label}>Available CapIQ features</label>
        <ul className={styles.list}>
          {features.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
        <label className={styles.label}>{hasOrg ? 'Using CapIQ' : 'How to resolve missing access'}</label>
        <ul className={styles.list}>
          {resolveSteps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
        {!hasOrg && (
          <p className={styles.hint}>
            School / collective accounts: complete{' '}
            <Link className={styles.inlineLink} to="/onboarding">
              onboarding
            </Link>{' '}
            with your organization name, or ask a school admin to add you. Then open{' '}
            <Link className={styles.inlineLink} to="/cap">
              CapIQ
            </Link>
            .
          </p>
        )}
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
        <h2 className={styles.h2}>Display density</h2>
        <p className={styles.muted} style={{ marginBottom: 8 }}>
          Scales section padding across the terminal. Comfortable adds room for
          long-form reading sessions; Compact maximizes table density.
        </p>
        <div className={styles.row}>
          {(['comfortable', 'default', 'compact'] as DensityMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              className={`${styles.chip} ${density === mode ? styles.chipOn : ''}`}
              onClick={() => onDensityChange(mode)}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
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

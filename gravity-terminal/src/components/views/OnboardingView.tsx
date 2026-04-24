import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { completeOnboarding, registerAccount } from '../../api/auth'
import { getSessionToken } from '../../api/client'
import { useAuthStore } from '../../stores/authStore'
import { mapDashboardTabToPath, usePreferencesStore } from '../../stores/preferencesStore'
import styles from './OnboardingView.module.css'

const ORG_OPTIONS: { id: string; label: string; sub: string }[] = [
  { id: 'school', label: 'School / Athletic Department', sub: 'Campus athletic department operations.' },
  { id: 'nil_collective', label: 'NIL Collective', sub: 'Collective funding and roster economics.' },
  { id: 'brand_agency', label: 'Brand / Agency', sub: 'Brand partnerships and athlete marketing.' },
  { id: 'law_firm_agent', label: 'Law Firm / Agent', sub: 'Representing athletes in NIL negotiations.' },
  { id: 'insurance_finance', label: 'Insurance / Finance', sub: 'Risk and financial diligence on athletes.' },
  { id: 'media_research', label: 'Media / Research', sub: 'Coverage, rankings, and market intelligence.' },
]

const SPORTS: { id: string; label: string }[] = [
  { id: 'CFB', label: 'College Football' },
  { id: 'NCAAB', label: "Men's Basketball" },
  { id: 'NCAAW', label: "Women's Basketball" },
]

function orgNameLabel(orgType: string | null): string {
  switch (orgType) {
    case 'brand_agency':
      return 'Your company'
    case 'law_firm_agent':
      return 'Your firm'
    case 'school':
    case 'nil_collective':
      return 'Organization name'
    default:
      return 'Organization name'
  }
}

export function OnboardingView() {
  const navigate = useNavigate()
  const applyFromApi = usePreferencesStore((s) => s.applyFromApi)
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [orgType, setOrgType] = useState<string | null>(null)
  const [sports, setSports] = useState<string[]>(['CFB'])
  const [teamSeed, setTeamSeed] = useState('')
  const [orgName, setOrgName] = useState('')
  const [goal, setGoal] = useState('')
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (getSessionToken()) setStep(2)
  }, [])

  const toggleSport = (id: string) => {
    setSports((prev) => {
      const on = prev.includes(id)
      if (on && prev.length === 1) return prev
      if (on) return prev.filter((x) => x !== id)
      return [...prev, id]
    })
  }

  const onRegister = async () => {
    setErr(null)
    try {
      const r = await registerAccount({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
      })
      // Seed the auth store synchronously so the next route guard already
      // sees an authenticated session — no race against fetchMe().
      useAuthStore.getState().applySessionFromAuth({
        access_token: r.access_token,
        user_id: r.user_id,
        email: r.email ?? email.trim(),
        role: 'agent',
      })
      setStep(2)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Registration failed')
    }
  }

  const onFinish = async (skipOrgStep: boolean) => {
    if (!orgType) {
      setErr('Select organization type.')
      return
    }
    if (!sports.length) {
      setErr('Select at least one sport.')
      return
    }
    setErr(null)
    try {
      const res = await completeOnboarding({
        org_type: orgType,
        sport_preferences: sports,
        org_name: skipOrgStep ? null : orgName.trim() || null,
        team_or_athlete_seed:
          orgType === 'school' || orgType === 'nil_collective' ? teamSeed.trim() || null : null,
        onboarding_goal: skipOrgStep ? null : goal.trim() || null,
      })
      applyFromApi({
        org_type: res.org_type as string | null,
        sport_preferences: (res.sport_preferences as string[]) ?? sports,
        org_name: (res.org_name as string) ?? null,
        team_or_athlete_seed: (res.team_or_athlete_seed as string) ?? null,
        default_dashboard_tab: (res.default_dashboard_tab as string) ?? null,
        athletes_default_sort: (res.athletes_default_sort as string) ?? null,
        onboarding_completed_at: (res.onboarding_completed_at as string) ?? null,
        display_name: (res.display_name as string) ?? null,
        onboarding_goal: (res.onboarding_goal as string | null) ?? null,
      })
      const path = mapDashboardTabToPath((res.default_dashboard_tab as string) ?? null)
      navigate(path, { replace: true })
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Onboarding failed')
    }
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.card}>
        <div className={styles.title}>GRAVITY — GET STARTED</div>
        <div className={styles.progress}>
          Step {step} of 4
        </div>
        {err && <div className={styles.error}>{err}</div>}

        {step === 1 && (
          <>
            <label className={styles.sub}>Display name</label>
            <input className={styles.input} value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            <label className={styles.sub}>Email</label>
            <input className={styles.input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <label className={styles.sub}>Password (min 8 characters)</label>
            <input
              className={styles.input}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <div className={styles.actions}>
              <span />
              <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={() => void onRegister()}>
                CREATE ACCOUNT
              </button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className={styles.sub}>Who are you?</div>
            <div className={styles.grid}>
              {ORG_OPTIONS.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className={`${styles.cardPick} ${orgType === o.id ? styles.cardPickActive : ''}`}
                  onClick={() => setOrgType(o.id)}
                >
                  <strong>{o.label}</strong>
                  <span className={styles.sub}>{o.sub}</span>
                </button>
              ))}
            </div>
            <div className={styles.actions}>
              <span />
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                disabled={!orgType}
                onClick={() => setStep(3)}
              >
                CONTINUE
              </button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className={styles.sub}>Which sports?</div>
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
            {(orgType === 'school' || orgType === 'nil_collective') && (
              <>
                <label className={styles.sub}>Your school or program (optional)</label>
                <input className={styles.input} value={teamSeed} onChange={(e) => setTeamSeed(e.target.value)} />
              </>
            )}
            <div className={styles.actions}>
              <button type="button" className={styles.btn} onClick={() => setStep(2)}>
                BACK
              </button>
              <button
                type="button"
                className={`${styles.btn} ${styles.btnPrimary}`}
                disabled={!sports.length}
                onClick={() => setStep(4)}
              >
                CONTINUE
              </button>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <label className={styles.sub}>{orgNameLabel(orgType)}</label>
            <input className={styles.input} value={orgName} onChange={(e) => setOrgName(e.target.value)} />
            <label className={styles.sub}>What are you trying to accomplish? (optional, 150 characters)</label>
            <textarea
              className={styles.input}
              rows={3}
              maxLength={150}
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
            />
            <div className={styles.actions}>
              <button type="button" className={styles.btn} onClick={() => setStep(3)}>
                BACK
              </button>
              <div style={{ display: 'flex', gap: 10 }}>
                <button type="button" className={styles.btn} onClick={() => void onFinish(true)}>
                  SKIP
                </button>
                <button type="button" className={`${styles.btn} ${styles.btnPrimary}`} onClick={() => void onFinish(false)}>
                  FINISH
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

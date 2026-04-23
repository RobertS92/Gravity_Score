import { NavLink, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { isMockMode, setSessionToken } from '../../api/client'
import { etTimeString } from '../../lib/time'
import { useAlertStore } from '../../stores/alertStore'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './TopBar.module.css'

const TABS: { path: string; label: string }[] = [
  { path: '/', label: 'NIL INTELLIGENCE' },
  { path: '/csc', label: 'CSC REPORTS' },
  { path: '/brand-match', label: 'BRAND MATCH' },
  { path: '/monitoring', label: 'MONITORING' },
  { path: '/data-pipeline', label: 'DATA PIPELINE' },
  { path: '/market-scan', label: 'MARKET SCAN' },
  { path: '/cap', label: 'CAPIQ' },
  { path: '/gravity-ai', label: 'GRAVITY AI' },
]

const SPORT_CHIPS: { id: string; label: string }[] = [
  { id: 'CFB', label: 'CFB' },
  { id: 'NCAAB', label: 'MBB' },
  { id: 'NCAAW', label: 'WBB' },
]

export function TopBar() {
  const navigate = useNavigate()
  const [clock, setClock] = useState(etTimeString)
  const [online, setOnline] = useState(navigator.onLine)
  const unread = useAlertStore((s) => s.unreadCount)
  const pulse = useAlertStore((s) => s.badgePulse)
  const email = useAuthStore((s) => s.email)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const queueSportPreferencesPatch = usePreferencesStore((s) => s.queueSportPreferencesPatch)

  useEffect(() => {
    const t = setInterval(() => setClock(etTimeString()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const goOnline  = () => setOnline(true)
    const goOffline = () => setOnline(false)
    window.addEventListener('online',  goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online',  goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  const handleLogout = () => {
    setSessionToken('')
    navigate('/login', { replace: true })
  }

  const toggleSportChip = (id: string) => {
    const on = activeSports.includes(id)
    if (on && activeSports.length === 1) return
    const next = on ? activeSports.filter((x) => x !== id) : [...activeSports, id]
    queueSportPreferencesPatch(next)
  }

  return (
    <header className={styles.bar}>
      <NavLink to="/" className={styles.brand}>GRAVITY</NavLink>
      <div className={styles.sports} aria-label="Sports filter">
        {SPORT_CHIPS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`${styles.sportChip} ${activeSports.includes(id) ? styles.sportChipOn : ''}`}
            onClick={() => toggleSportChip(id)}
          >
            {label}
          </button>
        ))}
      </div>
      <nav className={styles.tabs} aria-label="Primary">
        {TABS.map(({ path, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) => (isActive ? styles.tabActive : styles.tab)}
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <div className={styles.right}>
        {isMockMode() && (
          <span className={styles.demoBadge} title="MSW / fixtures">
            DEMO DATA
          </span>
        )}
        <div className={styles.liveRow}>
          <span className={online ? styles.dot : styles.dotOffline} aria-hidden />
          <span className={online ? undefined : styles.offlineLabel}>
            {online ? 'LIVE' : 'OFFLINE'}
          </span>
        </div>
        <span className={styles.clock}>{clock} ET</span>
        {unread > 0 && (
          <span className={`${styles.badge} ${pulse ? styles.badgePulse : ''}`}>{unread} ALERTS</span>
        )}
        <NavLink to="/settings" className={styles.settingsLink}>
          SETTINGS
        </NavLink>
        {email && (
          <button className={styles.logoutBtn} onClick={handleLogout} title={`Signed in as ${email}`}>
            SIGN OUT
          </button>
        )}
      </div>
    </header>
  )
}

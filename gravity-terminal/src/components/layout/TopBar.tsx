import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { isMockMode, setSessionToken } from '../../api/client'
import { etTimeString } from '../../lib/time'
import { useAlertStore } from '../../stores/alertStore'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import styles from './TopBar.module.css'

type Tab = { path: string; label: string; adminOnly?: boolean }

// Two-layer separation: Gravity Intelligence (valuation/what is the
// athlete worth and why) vs Cap Management (decision/what do we do with
// that number). Gravity AI sits standalone since it's a cross-layer
// assistant.
const INTELLIGENCE_TABS: Tab[] = [
  { path: '/', label: 'NIL INTELLIGENCE' },
  { path: '/csc', label: 'CSC REPORTS' },
  { path: '/brand-match', label: 'BRAND MATCH' },
  { path: '/monitoring', label: 'MONITORING' },
  { path: '/market-scan', label: 'MARKET SCAN' },
  { path: '/data-pipeline', label: 'DATA PIPELINE', adminOnly: true },
]
const CAP_TABS: Tab[] = [
  { path: '/cap', label: 'CAPIQ' },
  { path: '/cap/deal-desk', label: 'DEAL DESK' },
]
const STANDALONE_TABS: Tab[] = [
  { path: '/gravity-ai', label: 'GRAVITY AI' },
]

const INTELLIGENCE_PREFIXES = ['/csc', '/brand-match', '/monitoring', '/market-scan', '/data-pipeline']
const CAP_PREFIXES = ['/cap']

function activeLayer(pathname: string): 'intelligence' | 'cap' | 'standalone' {
  if (CAP_PREFIXES.some((p) => pathname.startsWith(p))) return 'cap'
  if (pathname.startsWith('/gravity-ai')) return 'standalone'
  if (pathname === '/' || INTELLIGENCE_PREFIXES.some((p) => pathname.startsWith(p))) {
    return 'intelligence'
  }
  return 'intelligence'
}

const SPORT_CHIPS: { id: string; label: string }[] = [
  { id: 'CFB', label: 'CFB' },
  { id: 'NCAAB', label: 'MBB' },
  { id: 'NCAAW', label: 'WBB' },
]

export function TopBar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [clock, setClock] = useState(etTimeString)
  const [online, setOnline] = useState(navigator.onLine)
  const unread = useAlertStore((s) => s.unreadCount)
  const pulse = useAlertStore((s) => s.badgePulse)
  const email = useAuthStore((s) => s.email)
  const role = useAuthStore((s) => s.role)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const queueSportPreferencesPatch = usePreferencesStore((s) => s.queueSportPreferencesPatch)
  const layer = activeLayer(location.pathname)

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
      <NavLink to="/" className={styles.brand} aria-label="Gravity home">
        <span className={styles.brandLogoWrap} aria-hidden>
          <img
            src="/brand/gravity-logo.png"
            alt=""
            className={styles.brandLogo}
            loading="eager"
            decoding="async"
          />
        </span>
        <span className={styles.brandText}>
          {layer === 'cap' ? (
            <>
              GRAVITY{' '}
              <span className={styles.brandSeparator}>/</span>{' '}
              <span className={styles.brandCapiq}>CAPIQ</span>
            </>
          ) : (
            'GRAVITY'
          )}
        </span>
      </NavLink>
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
        <div
          className={`${styles.tabCluster} ${
            layer === 'intelligence' ? styles.tabClusterActive : styles.tabClusterDim
          }`}
          aria-label="Gravity Intelligence"
        >
          <span className={styles.tabClusterLabel}>GRAVITY · INTELLIGENCE</span>
          {INTELLIGENCE_TABS.filter((t) => !t.adminOnly || role === 'admin').map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/'}
              className={({ isActive }) => (isActive ? styles.tabActive : styles.tab)}
            >
              {label}
            </NavLink>
          ))}
        </div>
        <div
          className={`${styles.tabCluster} ${
            layer === 'cap' ? styles.tabClusterActive : styles.tabClusterDim
          }`}
          aria-label="Cap Management"
        >
          <span className={styles.tabClusterLabel}>CAP · MANAGEMENT</span>
          {CAP_TABS.map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/cap'}
              className={({ isActive }) => (isActive ? styles.tabActive : styles.tab)}
            >
              {label}
            </NavLink>
          ))}
        </div>
        <div className={styles.tabCluster} aria-label="Cross-layer">
          {STANDALONE_TABS.map(({ path, label }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) => (isActive ? styles.tabActive : styles.tab)}
            >
              {label}
            </NavLink>
          ))}
        </div>
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

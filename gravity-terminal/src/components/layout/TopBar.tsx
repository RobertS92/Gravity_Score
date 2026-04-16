import { NavLink, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { isMockMode, setSessionToken } from '../../api/client'
import { etTimeString } from '../../lib/time'
import { useAlertStore } from '../../stores/alertStore'
import { useAuthStore } from '../../stores/authStore'
import styles from './TopBar.module.css'

const TABS: { path: string; label: string }[] = [
  { path: '/', label: 'NIL INTELLIGENCE' },
  { path: '/csc', label: 'CSC REPORTS' },
  { path: '/brand-match', label: 'BRAND MATCH' },
  { path: '/monitoring', label: 'MONITORING' },
  { path: '/market-scan', label: 'MARKET SCAN' },
  { path: '/roster', label: 'ROSTER BUILDER' },
  { path: '/gravity-ai', label: 'GRAVITY AI' },
]

export function TopBar() {
  const navigate = useNavigate()
  const [clock, setClock] = useState(etTimeString)
  const [online, setOnline] = useState(navigator.onLine)
  const unread = useAlertStore((s) => s.unreadCount)
  const pulse = useAlertStore((s) => s.badgePulse)
  const email = useAuthStore((s) => s.email)

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

  return (
    <header className={styles.bar}>
      <NavLink to="/" className={styles.brand}>GRAVITY</NavLink>
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
        {email && (
          <button className={styles.logoutBtn} onClick={handleLogout} title={`Signed in as ${email}`}>
            SIGN OUT
          </button>
        )}
      </div>
    </header>
  )
}

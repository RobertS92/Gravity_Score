import { NavLink, Outlet } from 'react-router-dom'
import styles from './CapWorkspace.module.css'

const TABS: Array<{ to: string; label: string }> = [
  { to: '/cap', label: 'Dashboard' },
  { to: '/cap/roster', label: 'Roster' },
  { to: '/cap/scenarios', label: 'Scenarios' },
  { to: '/cap/outlook', label: '5-Year Outlook' },
  { to: '/cap/cash-flow', label: 'Cash Flow' },
  { to: '/cap/admin-rollup', label: 'Admin Rollup' },
  { to: '/cap/allocation', label: 'Cap Allocation' },
  { to: '/cap/workflow', label: 'Approvals' },
  { to: '/cap/audit-log', label: 'Audit Log' },
  { to: '/cap/alerts', label: 'Alerts Center' },
]

export function CapLayout() {
  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>CAPIQ</div>
        <div className={styles.muted}>Decision layer for roster + cap planning</div>
      </div>
      <nav className={styles.tabs} aria-label="CapIQ sections">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.to === '/cap'}
            className={({ isActive }) => (isActive ? styles.tabActive : styles.tab)}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
}

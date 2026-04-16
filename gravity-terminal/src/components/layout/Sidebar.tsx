import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { formatScore } from '../../lib/formatters'
import { useAthleteStore } from '../../stores/athleteStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { useUiStore } from '../../stores/uiStore'
import { WatchlistModal } from './WatchlistModal'
import styles from './Sidebar.module.css'

function scoreBadgeClass(gs: number | null | undefined) {
  if (gs == null) return styles.badge
  if (gs > 80) return `${styles.badge} ${styles.badgeHi}`
  if (gs >= 60) return `${styles.badge} ${styles.badgeMid}`
  return `${styles.badge} ${styles.badgeLo}`
}

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const athletes = useWatchlistStore((s) => s.athletes)
  const removeFromWatchlist = useWatchlistStore((s) => s.removeFromWatchlist)
  const activeId = useAthleteStore((s) => s.activeAthleteId)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)
  const { activeSidebarItem, setActiveSidebarItem } = useUiStore()
  const [showModal, setShowModal] = useState(false)
  const [hoveredRow, setHoveredRow] = useState<string | null>(null)

  const nav = (id: string, section: 'csc' | 'research' | 'alerts') => {
    setActiveSidebarItem({ section, id })
  }

  return (
    <>
      <aside className={styles.sidebar}>
        <div className={styles.scroll}>
          <div className={styles.sectionHeader}>
            <span>WATCHLIST</span>
            <button
              type="button"
              className={styles.addBtn}
              onClick={() => setShowModal(true)}
              title="Add player to watchlist"
            >
              + ADD
            </button>
          </div>
          {athletes.map((a) => (
            <div
              key={a.athlete_id}
              className={a.athlete_id === activeId ? styles.watchRowActiveWrap : styles.watchRowWrap}
              onMouseEnter={() => setHoveredRow(a.athlete_id)}
              onMouseLeave={() => setHoveredRow(null)}
            >
              <button
                type="button"
                className={a.athlete_id === activeId ? styles.watchRowActive : styles.watchRow}
                onClick={() => void setActive(a.athlete_id)}
              >
                <span className={styles.name}>{a.name}</span>
                <span className={scoreBadgeClass(a.gravity_score ?? null)}>
                  {formatScore(a.gravity_score ?? null)}
                </span>
              </button>
              {hoveredRow === a.athlete_id && (
                <button
                  type="button"
                  className={styles.removeBtn}
                  onClick={(e) => {
                    e.stopPropagation()
                    void removeFromWatchlist(a.athlete_id)
                  }}
                  title="Remove from watchlist"
                >
                  ×
                </button>
              )}
            </div>
          ))}
          {athletes.length === 0 && (
            <div className={styles.emptyHint}>No players — click + ADD</div>
          )}

          <div className={styles.sectionHeader}>
            <span>CSC &amp; DEALS</span>
          </div>
          <button
            type="button"
            className={
              activeSidebarItem?.section === 'csc' && activeSidebarItem.id === 'csc'
                ? styles.navItemActive
                : styles.navItem
            }
            onClick={() => {
              nav('csc', 'csc')
              navigate('/csc')
            }}
          >
            CSC REPORTS
          </button>
          <button type="button" className={styles.navItem} onClick={() => nav('deal', 'csc')}>
            DEAL FILES
          </button>

          <div className={styles.sectionHeader}>
            <span>RESEARCH</span>
          </div>
          <button
            type="button"
            className={location.pathname.startsWith('/market-scan') ? styles.navItemActive : styles.navItem}
            onClick={() => {
              setActiveSidebarItem({ section: 'research', id: 'scan' })
              navigate('/market-scan')
            }}
          >
            MARKET SCAN
          </button>
          <button type="button" className={styles.navItem} onClick={() => nav('cohort', 'research')}>
            COHORT COMPARE
          </button>

          <div className={styles.sectionHeader}>
            <span>ALERTS</span>
          </div>
          <button
            type="button"
            className={location.pathname === '/monitoring' ? styles.navItemActive : styles.navItem}
            onClick={() => {
              setActiveSidebarItem({ section: 'alerts', id: 'center' })
              navigate('/monitoring')
            }}
          >
            ALERT CENTER
          </button>
        </div>
        <footer className={styles.footer}>
          <div>CFB · NCAAB · NCAAWB</div>
          <div>POWER 5 ONLY</div>
        </footer>
      </aside>

      {showModal && <WatchlistModal onClose={() => setShowModal(false)} />}
    </>
  )
}

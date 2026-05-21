import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { ActionButton } from '../shared/ActionButton'
import styles from './QuickActions.module.css'

function rosterBadgeLabel(status: string | null | undefined, inactive: boolean): string | null {
  if (!inactive) return null
  if (status === 'transferred') return 'Transferred'
  if (status === 'pro' || status === 'entered_draft') return 'No longer in college'
  if (status === 'graduated') return 'Graduated'
  return 'No longer on roster'
}

export function QuickActions() {
  const navigate = useNavigate()
  const activeId = useAthleteStore((s) => s.activeAthleteId)
  const activeAthlete = useAthleteStore((s) => s.activeAthlete)
  const refresh = useAthleteStore((s) => s.refreshActiveAthlete)
  const add = useWatchlistStore((s) => s.addToWatchlist)
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    if (!activeId || refreshing) return
    setRefreshing(true)
    try { await refresh() } finally { setRefreshing(false) }
  }

  const inactive = activeAthlete?.roster_inactive === true
  const badge = rosterBadgeLabel(activeAthlete?.roster_status, inactive)

  const handleGenerateCsc = () => {
    if (inactive) {
      const proceed = window.confirm(
        `${activeAthlete?.name ?? 'This athlete'} is ${badge ?? 'inactive'} — CSC valuations against stale rosters may be misleading. Continue?`,
      )
      if (!proceed) return
    }
    navigate('/csc')
  }

  return (
    <div className={styles.stack}>
      {badge && (
        <div
          style={{
            fontFamily: 'var(--font-data)',
            fontSize: 11,
            padding: '4px 8px',
            border: '1px solid var(--border-strong, #b85c00)',
            color: 'var(--text-warning, #b85c00)',
            background: 'var(--bg-warning, rgba(184,92,0,0.08))',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
          aria-label="roster-status"
        >
          {badge}
        </div>
      )}
      <ActionButton variant="primary" onClick={handleGenerateCsc}>
        Generate CSC report PDF
      </ActionButton>
      <ActionButton variant="secondary" onClick={() => navigate('/brand-match')}>
        Run brand match
      </ActionButton>
      <ActionButton
        variant="secondary"
        onClick={() => { if (activeId) void add(activeId) }}
      >
        Add to watchlist
      </ActionButton>
      <ActionButton
        variant="secondary"
        onClick={() => void handleRefresh()}
        disabled={refreshing || !activeId}
      >
        {refreshing ? 'Refreshing…' : '↻ Refresh signals'}
      </ActionButton>
    </div>
  )
}

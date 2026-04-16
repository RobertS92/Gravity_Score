import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { ActionButton } from '../shared/ActionButton'
import styles from './QuickActions.module.css'

export function QuickActions() {
  const navigate = useNavigate()
  const activeId = useAthleteStore((s) => s.activeAthleteId)
  const refresh = useAthleteStore((s) => s.refreshActiveAthlete)
  const add = useWatchlistStore((s) => s.addToWatchlist)
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = async () => {
    if (!activeId || refreshing) return
    setRefreshing(true)
    try { await refresh() } finally { setRefreshing(false) }
  }

  return (
    <div className={styles.stack}>
      <ActionButton variant="primary" onClick={() => navigate('/csc')}>
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

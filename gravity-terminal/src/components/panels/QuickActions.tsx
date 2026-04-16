import { useNavigate } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { ActionButton } from '../shared/ActionButton'
import styles from './QuickActions.module.css'

export function QuickActions() {
  const navigate = useNavigate()
  const activeId = useAthleteStore((s) => s.activeAthleteId)
  const add = useWatchlistStore((s) => s.addToWatchlist)

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
        onClick={() => {
          if (activeId) void add(activeId)
        }}
      >
        Add to watchlist
      </ActionButton>
    </div>
  )
}

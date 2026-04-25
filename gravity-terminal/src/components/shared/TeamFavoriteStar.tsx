import { useState } from 'react'
import { useTeamFavoritesStore } from '../../stores/teamFavoritesStore'
import styles from './TeamFavoriteStar.module.css'

type Props = {
  teamId: string | null | undefined
  /** Optional name shown in the tooltip (e.g. "Texas Longhorns"). */
  teamName?: string | null
  /** "sm" (table cells) | "md" (profile chip). */
  size?: 'sm' | 'md'
}

/** Toggle a team in the user's favorites — used by the live feed `teams` source. */
export function TeamFavoriteStar({ teamId, teamName, size = 'sm' }: Props) {
  const isFavorite = useTeamFavoritesStore((s) => (teamId ? s.isFavorite(teamId) : false))
  const add = useTeamFavoritesStore((s) => s.add)
  const remove = useTeamFavoritesStore((s) => s.remove)
  const [busy, setBusy] = useState(false)

  if (!teamId) {
    return null
  }

  const onClick = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (busy) return
    setBusy(true)
    try {
      if (isFavorite) await remove(teamId)
      else await add(teamId)
    } catch {
      /* error already surfaced by the store */
    } finally {
      setBusy(false)
    }
  }

  const label = isFavorite
    ? `Unfavorite ${teamName ?? 'team'}`
    : `Favorite ${teamName ?? 'team'} for live feed`

  const cls = [
    styles.btn,
    size === 'md' ? styles.md : styles.sm,
    isFavorite ? styles.active : '',
    busy ? styles.busy : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <button type="button" className={cls} aria-label={label} title={label} onClick={onClick}>
      {isFavorite ? '★' : '☆'}
    </button>
  )
}

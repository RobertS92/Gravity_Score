import type { FeedEventType } from '../../types/feed'
import styles from './FeedTag.module.css'

const LABEL: Record<FeedEventType, string> = {
  NIL_DEAL: 'NIL DEAL',
  BRAND: 'BRAND',
  RISK: 'RISK',
  VELOCITY: 'VELOCITY',
  SCORE_UPDATE: 'SCORE UPDATE',
  TRANSFER: 'TRANSFER',
  INJURY: 'INJURY',
  NEWS: 'NEWS',
  AWARD: 'AWARD',
  RECRUITING: 'RECRUITING',
  PERFORMANCE: 'PERFORMANCE',
  ANNOUNCEMENT: 'ANNOUNCEMENT',
  BUSINESS: 'BUSINESS',
  INCIDENT: 'INCIDENT',
  SCORE: 'SCORE',
  ROSTER: 'ROSTER',
  SOCIAL: 'SOCIAL',
  RANKING: 'RANKING',
  OTHER: 'OTHER',
}

const CLS: Record<FeedEventType, string> = {
  NIL_DEAL: styles.nil,
  BRAND: styles.brand,
  RISK: styles.risk,
  VELOCITY: styles.velocity,
  SCORE_UPDATE: styles.score,
  TRANSFER: styles.info,
  INJURY: styles.risk,
  NEWS: styles.info,
  AWARD: styles.accent,
  RECRUITING: styles.accent,
  PERFORMANCE: styles.velocity,
  ANNOUNCEMENT: styles.accent,
  BUSINESS: styles.accent,
  INCIDENT: styles.risk,
  SCORE: styles.score,
  ROSTER: styles.info,
  SOCIAL: styles.info,
  RANKING: styles.info,
  OTHER: styles.info,
}

export function FeedTag({ type }: { type: FeedEventType }) {
  return <span className={`${styles.tag} ${CLS[type]}`}>{LABEL[type]}</span>
}

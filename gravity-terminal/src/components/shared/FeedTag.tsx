import type { FeedEventType } from '../../types/feed'
import styles from './FeedTag.module.css'

const LABEL: Record<FeedEventType, string> = {
  NIL_DEAL: 'NIL DEAL',
  BRAND: 'BRAND',
  RISK: 'RISK',
  VELOCITY: 'VELOCITY',
  SCORE_UPDATE: 'SCORE UPDATE',
}

const CLS: Record<FeedEventType, string> = {
  NIL_DEAL: styles.nil,
  BRAND: styles.brand,
  RISK: styles.risk,
  VELOCITY: styles.velocity,
  SCORE_UPDATE: styles.score,
}

export function FeedTag({ type }: { type: FeedEventType }) {
  return <span className={`${styles.tag} ${CLS[type]}`}>{LABEL[type]}</span>
}

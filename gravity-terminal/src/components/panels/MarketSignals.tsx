import { formatInteger, formatScore } from '../../lib/formatters'
import type { AthleteRecord } from '../../types/athlete'
import styles from './MarketSignals.module.css'

export function MarketSignals({ athlete }: { athlete: AthleteRecord }) {
  const rows: { k: string; v: string }[] = [
    { k: 'Social reach', v: formatInteger(athlete.social_combined_reach) },
    {
      k: 'Engagement rate (IG)',
      v: athlete.instagram_engagement_rate != null ? `${formatScore(athlete.instagram_engagement_rate)}%` : '\u2014',
    },
    { k: 'News mentions 30d', v: formatInteger(athlete.news_mentions_30d) },
    { k: 'On3 NIL rank', v: athlete.on3_nil_rank ?? 'N/A' },
    { k: 'Deals on file', v: formatInteger(athlete.verified_deals_count) },
  ]
  return (
    <div>
      <div className={styles.label}>MARKET SIGNALS</div>
      {rows.map((r, i) => (
        <div key={r.k} className={styles.row} style={i === rows.length - 1 ? { borderBottom: 'none' } : undefined}>
          <span className={styles.k}>{r.k}</span>
          <span className={styles.v}>{r.v}</span>
        </div>
      ))}
    </div>
  )
}

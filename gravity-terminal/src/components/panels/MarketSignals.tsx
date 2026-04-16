import { formatInteger, formatScore } from '../../lib/formatters'
import type { AthleteRecord } from '../../types/athlete'
import styles from './MarketSignals.module.css'

function fmtFollowers(n: number | null | undefined): string {
  if (n == null) return 'N/A'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`
  return String(n)
}

function fmtTrends(n: number | null | undefined): string {
  if (n == null) return 'N/A'
  return `${Math.round(n)}/100`
}

type Row = { k: string; v: string; highlight?: boolean }

export function MarketSignals({ athlete }: { athlete: AthleteRecord }) {
  const ig = athlete.instagram_followers
  const tw = athlete.twitter_followers
  const tt = athlete.tiktok_followers

  // Build social breakdown string
  const socialParts: string[] = []
  if (ig != null) socialParts.push(`IG ${fmtFollowers(ig)}`)
  if (tw != null) socialParts.push(`X ${fmtFollowers(tw)}`)
  if (tt != null) socialParts.push(`TT ${fmtFollowers(tt)}`)

  const socialReachStr = athlete.social_combined_reach != null
    ? `${fmtFollowers(athlete.social_combined_reach)} total`
    : socialParts.length ? socialParts.join(' · ') : 'N/A'

  const rows: Row[] = [
    {
      k: 'Social reach',
      v: socialReachStr,
    },
    {
      k: 'IG · X · TikTok',
      v: socialParts.length
        ? socialParts.join(' · ')
        : (ig == null && tw == null && tt == null ? 'N/A' : '—'),
    },
    {
      k: 'Engagement rate (IG)',
      v: athlete.instagram_engagement_rate != null
        ? `${formatScore(athlete.instagram_engagement_rate)}%`
        : '—',
    },
    { k: 'News mentions 30d', v: formatInteger(athlete.news_mentions_30d) },
    { k: 'Google Trends', v: fmtTrends(athlete.google_trends_score) },
    {
      k: 'Wikipedia views 30d',
      v: athlete.wikipedia_page_views_30d != null
        ? fmtFollowers(athlete.wikipedia_page_views_30d)
        : 'N/A',
    },
    {
      k: 'On3 NIL rank',
      v: athlete.on3_nil_rank != null ? `#${athlete.on3_nil_rank}` : 'N/A',
      highlight: athlete.on3_nil_rank != null,
    },
    { k: 'Deals on file', v: formatInteger(athlete.verified_deals_count) },
    {
      k: 'Data quality',
      v: athlete.data_quality_score != null
        ? `${Math.round(athlete.data_quality_score * 100)}%`
        : '—',
    },
  ]

  return (
    <div>
      <div className={styles.label}>MARKET SIGNALS</div>
      {rows.map((r, i) => (
        <div
          key={r.k}
          className={styles.row}
          style={i === rows.length - 1 ? { borderBottom: 'none' } : undefined}
        >
          <span className={styles.k}>{r.k}</span>
          <span className={r.highlight ? styles.vHighlight : styles.v}>{r.v}</span>
        </div>
      ))}
    </div>
  )
}

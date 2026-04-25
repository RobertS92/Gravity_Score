/**
 * Renders the trust signal for a feed item:
 *   - 1-3 filled dots indicating source tier (1 = wire/official, 3 = blog)
 *   - Verification chip (OFFICIAL / 2-SOURCE / 1-SOURCE / LOW / UNVERIFIED)
 *   - Source name as an outbound link (when source_url is present)
 *   - Tooltip with the exact quote returned by the LLM fact-check (if any)
 *
 * Pure presentational — accepts only the four provenance fields off
 * `FeedItem` so we can reuse it in lists, panels, and detail views.
 */
import type { VerificationLevel } from '../../api/feed'
import styles from './TrustBadge.module.css'

type Props = {
  source: string | null | undefined
  sourceUrl: string | null | undefined
  sourceTier: number | null | undefined
  verification: VerificationLevel | null | undefined
  exactQuote?: string | null
  correctionNote?: string | null
  compact?: boolean
}

const VERIF_LABEL: Record<VerificationLevel, string> = {
  OFFICIAL: 'OFFICIAL',
  MULTI_SOURCE: '2+ SOURCES',
  SINGLE_SOURCE: '1 SOURCE',
  LOW_CONFIDENCE: 'LOW CONF',
  UNVERIFIED: 'UNVERIFIED',
}

const VERIF_CLASS: Record<VerificationLevel, string> = {
  OFFICIAL: styles.official,
  MULTI_SOURCE: styles.multi,
  SINGLE_SOURCE: styles.single,
  LOW_CONFIDENCE: styles.low,
  UNVERIFIED: styles.unverified,
}

function tierDots(tier: number | null | undefined) {
  // Tier 1 = 3 filled dots (wire/official), 2 = 2, 3 = 1, else 0.
  const filled =
    tier === 1 ? 3 :
    tier === 2 ? 2 :
    tier === 3 ? 1 : 0
  return (
    <span className={styles.dots} aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`${styles.dot} ${i < filled ? styles.dotActive : ''}`}
        />
      ))}
    </span>
  )
}

function tooltip(
  source: string | null | undefined,
  tier: number | null | undefined,
  verification: VerificationLevel | null | undefined,
  exactQuote?: string | null,
  correctionNote?: string | null,
): string {
  const lines: string[] = []
  if (source) lines.push(`Source: ${source}${tier ? ` (tier ${tier})` : ''}`)
  if (verification) lines.push(`Verification: ${VERIF_LABEL[verification] ?? verification}`)
  if (exactQuote) lines.push(`Quote: "${exactQuote}"`)
  if (correctionNote) lines.push(`Correction: ${correctionNote}`)
  return lines.join('\n')
}

export function TrustBadge({
  source,
  sourceUrl,
  sourceTier,
  verification,
  exactQuote,
  correctionNote,
  compact = false,
}: Props) {
  const v = (verification || 'UNVERIFIED') as VerificationLevel
  const cls = `${styles.badge} ${VERIF_CLASS[v]} ${compact ? styles.compact : ''}`
  const title = tooltip(source, sourceTier, v, exactQuote, correctionNote)

  return (
    <span className={cls} title={title}>
      {tierDots(sourceTier)}
      <span>{VERIF_LABEL[v] ?? 'UNVERIFIED'}</span>
      {source && sourceUrl ? (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.sourceLink}
          onClick={(e) => e.stopPropagation()}
        >
          {source}
        </a>
      ) : source ? (
        <span>{source}</span>
      ) : null}
    </span>
  )
}

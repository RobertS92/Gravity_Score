import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLiveFeedStore } from '../../stores/liveFeedStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { formatFeedTime } from '../../lib/time'
import { TrustBadge } from '../shared/TrustBadge'
import styles from './LiveFeedV2.module.css'

const COMPACT_LIMIT = 12

const CATEGORY_LABEL: Record<string, string> = {
  NIL_DEAL: 'NIL',
  TRANSFER: 'TRANSFER',
  INJURY: 'INJURY',
  NEWS: 'NEWS',
  AWARD: 'AWARD',
  RECRUITING: 'RECRUITING',
  PERFORMANCE: 'PERF',
  ANNOUNCEMENT: 'ANNOUNCE',
  BUSINESS: 'BUSINESS',
  INCIDENT: 'INCIDENT',
  SCORE: 'SCORE',
  SCORE_UPDATE: 'SCORE',
  ROSTER: 'ROSTER',
  SOCIAL: 'SOCIAL',
  RANKING: 'RANK',
  RISK: 'RISK',
  OTHER: 'OTHER',
}

const CATEGORY_CLASS: Record<string, string> = {
  NIL_DEAL: styles.tagNil,
  TRANSFER: styles.tagTransfer,
  INJURY: styles.tagRisk,
  INCIDENT: styles.tagRisk,
  RISK: styles.tagRisk,
  NEWS: styles.tagInfo,
  ROSTER: styles.tagInfo,
  SOCIAL: styles.tagInfo,
  RANKING: styles.tagInfo,
  PERFORMANCE: styles.tagPerf,
  AWARD: styles.tagAccent,
  RECRUITING: styles.tagAccent,
  ANNOUNCEMENT: styles.tagAccent,
  BUSINESS: styles.tagAccent,
  SCORE: styles.tagAccent,
  SCORE_UPDATE: styles.tagAccent,
  OTHER: styles.tagInfo,
}

function CategoryTag({ category }: { category: string }) {
  const label = CATEGORY_LABEL[category] ?? category
  const cls = CATEGORY_CLASS[category] ?? styles.tagInfo
  return <span className={`${styles.tag} ${cls}`}>{label}</span>
}

export function LiveFeedV2({ compact = true }: { compact?: boolean }) {
  const navigate = useNavigate()
  const items = useLiveFeedStore((s) => s.items)
  const isLoading = useLiveFeedStore((s) => s.isLoading)
  const isHydrated = useLiveFeedStore((s) => s.isHydrated)
  const error = useLiveFeedStore((s) => s.error)
  const sources = useLiveFeedStore((s) => s.sources)
  const categories = useLiveFeedStore((s) => s.categories)
  const toggleSource = useLiveFeedStore((s) => s.toggleSource)
  const load = useLiveFeedStore((s) => s.load)
  const setSports = useLiveFeedStore((s) => s.setSports)
  const activeSports = usePreferencesStore((s) => s.activeSports)

  useEffect(() => {
    setSports(activeSports.map((s) => s.toLowerCase()))
  }, [activeSports.join(','), setSports])

  useEffect(() => {
    if (!isHydrated) {
      void load()
    }
  }, [isHydrated, load])

  useEffect(() => {
    const t = setInterval(() => {
      void load()
    }, 60_000)
    return () => clearInterval(t)
  }, [load])

  const top = compact ? items.slice(0, COMPACT_LIMIT) : items

  return (
    <div>
      <div className={styles.header}>
        <span className={styles.label}>LIVE FEED</span>
        {compact && (
          <button
            type="button"
            className={styles.expandBtn}
            onClick={() => navigate('/feed')}
            title="Open full live feed"
          >
            EXPAND →
          </button>
        )}
      </div>

      <div className={styles.toggleRow}>
        <ToggleChip active={sources.has('watchlist')} onClick={() => toggleSource('watchlist')}>
          WATCH
        </ToggleChip>
        <ToggleChip active={sources.has('teams')} onClick={() => toggleSource('teams')}>
          TEAMS
        </ToggleChip>
        <ToggleChip active={sources.has('general')} onClick={() => toggleSource('general')}>
          GENERAL
        </ToggleChip>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {isLoading && top.length === 0 && (
        <div className={styles.empty}>Loading…</div>
      )}

      {!isLoading && isHydrated && top.length === 0 && (
        <div className={styles.empty}>
          No matching events.{' '}
          {!sources.has('general') && 'Enable GENERAL to widen your feed.'}
        </div>
      )}

      {top.map((it) => (
        <div key={it.id} className={styles.item}>
          <div className={styles.tsRow}>
            <span className={styles.ts}>
              {it.occurred_at ? formatFeedTime(it.occurred_at) : ''}
            </span>
            <CategoryTag category={it.category || 'OTHER'} />
          </div>
          <div className={styles.body}>
            {it.title || it.body || it.category}
            {it.athlete_name && (
              <>
                {' · '}
                <span className={styles.entity}>{it.athlete_name}</span>
              </>
            )}
            {it.team_name && !it.athlete_name && (
              <>
                {' · '}
                <span className={styles.entity}>{it.team_name}</span>
              </>
            )}
          </div>
          {it.body && it.body !== it.title && (
            <div className={styles.subBody}>{it.body}</div>
          )}
          <div className={styles.trustRow}>
            <TrustBadge
              source={it.source}
              sourceUrl={it.source_url}
              sourceTier={it.source_tier ?? null}
              verification={it.verification ?? null}
              exactQuote={it.exact_quote}
              correctionNote={it.correction_note}
              compact
            />
          </div>
        </div>
      ))}

      {compact && categories.size > 0 && (
        <div className={styles.filterHint}>
          {categories.size} category filter{categories.size === 1 ? '' : 's'} active
        </div>
      )}
    </div>
  )
}

function ToggleChip({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      className={active ? styles.chipActive : styles.chip}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

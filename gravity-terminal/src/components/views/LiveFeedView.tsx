import { useEffect } from 'react'
import { useLiveFeedStore } from '../../stores/liveFeedStore'
import { useTeamFavoritesStore } from '../../stores/teamFavoritesStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { formatFeedTime } from '../../lib/time'
import { TrustBadge } from '../shared/TrustBadge'
import type { VerificationLevel } from '../../api/feed'
import styles from './LiveFeedView.module.css'

const CATEGORY_LABEL: Record<string, string> = {
  NIL_DEAL: 'NIL & BRAND DEALS',
  TRANSFER: 'TRANSFER',
  INJURY: 'INJURY',
  NEWS: 'BIG NEWS',
  AWARD: 'AWARDS',
  RECRUITING: 'RECRUITING',
  PERFORMANCE: 'PERFORMANCE',
  ANNOUNCEMENT: 'ANNOUNCEMENTS',
  BUSINESS: 'BUSINESS',
  INCIDENT: 'INCIDENTS',
  SCORE: 'SCORE CHANGES',
  SCORE_UPDATE: 'SCORE CHANGES',
  ROSTER: 'ROSTER',
  SOCIAL: 'SOCIAL',
  RANKING: 'RANKINGS',
  RISK: 'RISK',
  OTHER: 'OTHER',
}

const SOURCE_LABEL: Record<string, string> = {
  watchlist: 'WATCHLIST',
  teams: 'FAVORITED TEAMS',
  general: 'GENERAL',
}

const VERIF_LABEL: Record<VerificationLevel, string> = {
  OFFICIAL: 'OFFICIAL ONLY',
  MULTI_SOURCE: 'MULTI-SOURCE+',
  SINGLE_SOURCE: 'VERIFIED+',
  LOW_CONFIDENCE: 'INCLUDE LOW',
  UNVERIFIED: 'ALL (incl. unverified)',
}

export function LiveFeedView() {
  const items = useLiveFeedStore((s) => s.items)
  const isLoading = useLiveFeedStore((s) => s.isLoading)
  const isLoadingMore = useLiveFeedStore((s) => s.isLoadingMore)
  const isHydrated = useLiveFeedStore((s) => s.isHydrated)
  const error = useLiveFeedStore((s) => s.error)
  const hasMore = useLiveFeedStore((s) => s.hasMore)
  const sources = useLiveFeedStore((s) => s.sources)
  const categories = useLiveFeedStore((s) => s.categories)
  const catalogCategories = useLiveFeedStore((s) => s.catalogCategories)
  const catalogSources = useLiveFeedStore((s) => s.catalogSources)
  const catalogVerificationLevels = useLiveFeedStore((s) => s.catalogVerificationLevels)
  const minVerification = useLiveFeedStore((s) => s.minVerification)
  const setMinVerification = useLiveFeedStore((s) => s.setMinVerification)
  const toggleSource = useLiveFeedStore((s) => s.toggleSource)
  const toggleCategory = useLiveFeedStore((s) => s.toggleCategory)
  const clearCategories = useLiveFeedStore((s) => s.clearCategories)
  const load = useLiveFeedStore((s) => s.load)
  const loadMore = useLiveFeedStore((s) => s.loadMore)
  const loadCatalog = useLiveFeedStore((s) => s.loadCatalog)
  const setSports = useLiveFeedStore((s) => s.setSports)

  const activeSports = usePreferencesStore((s) => s.activeSports)
  const watchlist = useWatchlistStore((s) => s.athletes)
  const teams = useTeamFavoritesStore((s) => s.teams)
  const loadTeamFavorites = useTeamFavoritesStore((s) => s.load)
  const isTeamFavoritesHydrated = useTeamFavoritesStore((s) => s.isHydrated)

  useEffect(() => {
    void loadCatalog()
    if (!isTeamFavoritesHydrated) void loadTeamFavorites()
  }, [loadCatalog, loadTeamFavorites, isTeamFavoritesHydrated])

  useEffect(() => {
    setSports(activeSports.map((s) => s.toLowerCase()))
  }, [activeSports.join(','), setSports])

  useEffect(() => {
    if (!isHydrated) void load()
  }, [isHydrated, load])

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>LIVE FEED</h1>
          <p className={styles.subtitle}>
            News and signals from your watchlist, favorited teams, and general league activity.
          </p>
        </div>
        <div className={styles.headerStats}>
          <div className={styles.stat}>
            <span className={styles.statLabel}>WATCHLIST</span>
            <span className={styles.statValue}>{watchlist.length}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>TEAMS</span>
            <span className={styles.statValue}>{teams.length}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>SPORTS</span>
            <span className={styles.statValue}>
              {activeSports.length ? activeSports.join('·') : '—'}
            </span>
          </div>
        </div>
      </header>

      <section className={styles.controls}>
        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>SOURCES</span>
          <div className={styles.chipRow}>
            {(['watchlist', 'teams', 'general'] as const)
              .filter((s) => catalogSources.includes(s))
              .map((s) => (
                <button
                  key={s}
                  type="button"
                  className={sources.has(s) ? styles.chipActive : styles.chip}
                  onClick={() => toggleSource(s)}
                >
                  {SOURCE_LABEL[s] ?? s.toUpperCase()}
                </button>
              ))}
          </div>
        </div>

        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>TRUST</span>
          <div className={styles.chipRow}>
            {catalogVerificationLevels.map((v) => (
              <button
                key={v}
                type="button"
                className={minVerification === v ? styles.chipActive : styles.chip}
                onClick={() => setMinVerification(v)}
                title={`Minimum verification: ${v}`}
              >
                {VERIF_LABEL[v] ?? v}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.controlGroup}>
          <span className={styles.controlLabel}>CATEGORIES</span>
          <div className={styles.chipRow}>
            <button
              type="button"
              className={categories.size === 0 ? styles.chipActive : styles.chip}
              onClick={clearCategories}
            >
              ALL
            </button>
            {catalogCategories.map((c) => (
              <button
                key={c}
                type="button"
                className={categories.has(c) ? styles.chipActive : styles.chip}
                onClick={() => toggleCategory(c)}
              >
                {CATEGORY_LABEL[c] ?? c}
              </button>
            ))}
          </div>
        </div>
      </section>

      {error && <div className={styles.error}>Error: {error}</div>}

      <section className={styles.feed}>
        {isLoading && items.length === 0 && (
          <div className={styles.empty}>Loading…</div>
        )}

        {!isLoading && isHydrated && items.length === 0 && (
          <div className={styles.empty}>
            <p>No matching events.</p>
            <p className={styles.emptyHint}>
              Try widening your sources or clearing category filters.
              {watchlist.length === 0 && ' Add players to your watchlist to track per-athlete events.'}
            </p>
          </div>
        )}

        {items.map((it) => (
          <article key={it.id} className={styles.row}>
            <div className={styles.rowHead}>
              <span className={styles.cat}>{CATEGORY_LABEL[it.category] ?? it.category}</span>
              <span className={styles.ts}>
                {it.occurred_at ? formatFeedTime(it.occurred_at) : ''}
              </span>
            </div>
            <div className={styles.rowTitle}>
              {it.title || it.body || it.category}
            </div>
            {(it.athlete_name || it.team_name) && (
              <div className={styles.rowMeta}>
                {it.athlete_name && <span>{it.athlete_name}</span>}
                {it.athlete_name && it.team_name && <span> · </span>}
                {it.team_name && <span>{it.team_name}</span>}
                {it.sport && <span> · {it.sport.toUpperCase()}</span>}
              </div>
            )}
            {it.body && it.body !== it.title && (
              <div className={styles.rowBody}>{it.body}</div>
            )}
            <div className={styles.rowFooter}>
              <TrustBadge
                source={it.source}
                sourceUrl={it.source_url}
                sourceTier={it.source_tier ?? null}
                verification={it.verification ?? null}
                exactQuote={it.exact_quote}
                correctionNote={it.correction_note}
              />
              {it.exact_quote && (
                <span className={styles.quote} title={it.exact_quote}>
                  &ldquo;{it.exact_quote.length > 140 ? it.exact_quote.slice(0, 140) + '…' : it.exact_quote}&rdquo;
                </span>
              )}
              {it.correction_note && (
                <span className={styles.correction}>
                  Correction: {it.correction_note}
                </span>
              )}
            </div>
          </article>
        ))}

        {hasMore && (
          <div className={styles.loadMoreWrap}>
            <button
              type="button"
              className={styles.loadMoreBtn}
              disabled={isLoadingMore}
              onClick={() => void loadMore()}
            >
              {isLoadingMore ? 'LOADING…' : 'LOAD MORE'}
            </button>
          </div>
        )}
      </section>
    </div>
  )
}

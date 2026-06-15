import { Link } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { AlternativesPanel } from '../panels/AlternativesPanel'
import { ConfidenceCard } from '../panels/ConfidenceCard'
import { DealActionPanel } from '../panels/DealActionPanel'
import { NilValuation } from '../panels/NilValuation'
import styles from './CapDealDeskView.module.css'

/**
 * Cap Management → Deal Desk
 *
 * Synthesizes the Gravity Intelligence valuation for the currently-active
 * athlete with the cap-side decision blocks (recommended deal, confidence,
 * alternatives). This is where the Intelligence layer "hands off" to the
 * Cap layer — a single screen that an operator uses to actually decide
 * whether to write a deal and at what number.
 *
 * The decision-oriented panels (DealAction / Confidence / Alternatives)
 * previously rendered on the NIL Intelligence home (`/`). They've moved
 * here so the Intelligence home stays focused on "what is this athlete
 * worth and why", while the Cap layer owns the "what do we do about it"
 * surface.
 */
export function CapDealDeskView() {
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const athleteId = typeof athlete?.athlete_id === 'string' && athlete.athlete_id.length > 0
    ? athlete.athlete_id
    : null

  if (!athlete) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyTitle}>DEAL DESK</div>
        <div className={styles.emptyBody}>
          Select an athlete from the watchlist or{' '}
          <Link to="/">NIL Intelligence</Link> to bring their valuation into
          the desk for deal construction.
        </div>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <header className={styles.header}>
        <div className={styles.eyebrow}>$$ CAP &middot; DEAL DESK</div>
        <h1 className={styles.title}>{athlete.name}</h1>
        <div className={styles.sub}>
          {[athlete.school, athlete.position, athlete.conference].filter(Boolean).join(' · ') || 'Athlete'}
          <span className={styles.linkSep}> · </span>
          <Link to="/" className={styles.link}>view intelligence →</Link>
          {athleteId ? (
            <>
              <span className={styles.linkSep}> · </span>
              <Link to="/csc" className={styles.link}>CSC report →</Link>
            </>
          ) : null}
        </div>
      </header>

      <section className={styles.grid}>
        <div className={styles.column}>
          <div className={styles.sectionTitle}>&gt;&gt; VALUATION</div>
          <NilValuation athlete={athlete} />
        </div>

        <div className={styles.column}>
          <div className={styles.sectionTitle}>$$ RECOMMENDED DEAL</div>
          {athleteId ? (
            <DealActionPanel athleteId={athleteId} />
          ) : (
            <EmptyBlock label="Deal recommendation unavailable for this athlete." />
          )}
        </div>

        <div className={styles.column}>
          <div className={styles.sectionTitle}>&gt;&gt; CONFIDENCE</div>
          {athleteId ? (
            <ConfidenceCard athleteId={athleteId} />
          ) : (
            <EmptyBlock label="Confidence details unavailable for this athlete." />
          )}
        </div>

        <div className={styles.column}>
          <div className={styles.sectionTitle}>&gt;&gt; ALTERNATIVES</div>
          {athleteId ? (
            <AlternativesPanel athleteId={athleteId} />
          ) : (
            <EmptyBlock label="Alternatives unavailable for this athlete." />
          )}
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.footerNote}>
          Valuation sourced from Gravity Intelligence · decision/alternatives
          modelled against current cap utilization. Approvals run through{' '}
          <Link to="/cap/workflow" className={styles.link}>/cap/workflow</Link>.
        </div>
      </footer>
    </div>
  )
}

function EmptyBlock({ label }: { label: string }) {
  return <div className={styles.emptyBlock}>{label}</div>
}

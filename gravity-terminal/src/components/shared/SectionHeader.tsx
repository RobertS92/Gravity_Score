import type { ReactNode } from 'react'
import styles from './SectionHeader.module.css'

type SectionTone = 'intel' | 'cap' | 'neutral' | 'warn' | 'positive'

interface SectionHeaderProps {
  /** Tone drives the prefix glyph + accent color:
   *   intel    → `>>` cyan/green (read / analyze surfaces)
   *   cap      → `$$` amber (decision / money surfaces)
   *   warn     → `!!` amber/red (validation, errors, low data)
   *   positive → `++` green (success outcomes, approvals)
   *   neutral  → `..` muted (collapsed detail sections)
   */
  tone?: SectionTone
  /** Heading scale — h2 is the default (panel title); h3 for sub-sections. */
  level?: 'h2' | 'h3'
  /** Right-rail content (badges, action buttons). */
  trailing?: ReactNode
  children: ReactNode
}

const PREFIX_BY_TONE: Record<SectionTone, string> = {
  intel: '>>',
  cap: '$$',
  warn: '!!',
  positive: '++',
  neutral: '..',
}

/**
 * Standardized section header with terminal-style prefix glyphs.
 *
 * Using a shared component instead of one-off `<div className={styles.title}>`
 * blocks lets us keep the prefix vocabulary consistent across the app
 * (`>>` for intelligence surfaces, `$$` for cap/decision surfaces, `!!`
 * for warnings/validation) and reliably scale to alternate themes.
 *
 * @example
 *   <SectionHeader tone="intel">Key Value Drivers</SectionHeader>
 *   <SectionHeader tone="cap" trailing={<button>Approve</button>}>Recommended Deal</SectionHeader>
 */
export function SectionHeader({
  tone = 'intel',
  level = 'h2',
  trailing,
  children,
}: SectionHeaderProps) {
  const HeadingTag = level === 'h3' ? 'h3' : 'h2'
  return (
    <div className={`${styles.header} ${styles[tone]} ${styles[level]}`}>
      <HeadingTag className={styles.title}>
        <span className={styles.prefix} aria-hidden>
          {PREFIX_BY_TONE[tone]}
        </span>
        {children}
      </HeadingTag>
      {trailing && <div className={styles.trailing}>{trailing}</div>}
    </div>
  )
}

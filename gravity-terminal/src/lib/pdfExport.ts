/**
 * PDF export — generates a real downloadable PDF from athlete/report data.
 * Uses jsPDF for layout. Falls back to window.print() if jsPDF fails to load.
 */
import type { AthleteRecord, ComparableRecord } from '../types/athlete'
import type { CscReportJson } from '../types/reports'
import { formatComparableConfidence, normalizeComparableRows } from './cscComparables'
import { conferenceTierDisplayLabel, shouldSuppressPercentile } from './cscReportTags'
import { formatNilValue, formatNilRangeAligned, formatScore } from './formatters'

function nilFmt(v: number | null | undefined) {
  if (v == null) return '—'
  return formatNilValue(v)
}

function scoreFmt(v: number | null | undefined) {
  if (v == null) return '—'
  return formatScore(v)
}

/** Download a CSC-style report PDF for an athlete. */
export async function downloadCscPdf(
  athlete: AthleteRecord,
  comparables: ComparableRecord[],
  report: CscReportJson | null,
): Promise<void> {
  try {
    const { jsPDF } = await import('jspdf')
    const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'letter' })

    const W = 612
    const margin = 48
    const colW = W - margin * 2
    const pageHeight = 792
    const bottomMargin = 52
    let y = margin

    const ensureSpace = (requiredHeight: number) => {
      if (y + requiredHeight <= pageHeight - bottomMargin) return
      doc.addPage()
      doc.setFillColor('#0d1117')
      doc.rect(0, 0, W, pageHeight, 'F')
      y = margin
    }

    const line = (text: string, fontSize = 10, bold = false, color = '#c9d1d9') => {
      ensureSpace(fontSize * 1.6)
      doc.setFontSize(fontSize)
      doc.setFont('helvetica', bold ? 'bold' : 'normal')
      doc.setTextColor(color)
      doc.text(text, margin, y)
      y += fontSize * 1.5
    }

    const rule = () => {
      ensureSpace(10)
      doc.setDrawColor('#30363d')
      doc.setLineWidth(0.5)
      doc.line(margin, y, margin + colW, y)
      y += 8
    }

    const writeWrapped = (text: string, fontSize = 9, color = '#c9d1d9', lineHeight = 13) => {
      doc.setFontSize(fontSize)
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(color)
      const wrapped = doc.splitTextToSize(text, colW) as string[]
      for (const segment of wrapped) {
        ensureSpace(lineHeight)
        doc.text(segment, margin, y)
        y += lineHeight
      }
    }

    // ── Header ────────────────────────────────────────────────────────────────
    doc.setFillColor('#0d1117')
    doc.rect(0, 0, W, 792, 'F')

    line('GRAVITY', 20, true, '#3fb950')
    y += 2
    line('NIL COMMERCIAL INTELLIGENCE — CSC REPORT', 8, false, '#6e7681')
    line(`Generated: ${new Date().toLocaleString('en-US', { timeZone: 'America/New_York' })} ET`, 8, false, '#6e7681')
    const reportIdHeader = report?.metadata?.report_id
    if (reportIdHeader) {
      line(`Report ID: ${reportIdHeader}`, 8, false, '#8b949e')
    }
    y += 8
    rule()

    // ── Fallback model banner (if applicable) ────────────────────────────────
    if (report?.metadata?.model_status === 'fallback') {
      const versionSuffix = report.metadata.model_version ? ` (${report.metadata.model_version})` : ''
      writeWrapped(
        `FALLBACK SCORER ACTIVE${versionSuffix}. This report is informational only and must not be used for binding decisions.`,
        9,
        '#f85149',
        13,
      )
      y += 4
      rule()
    }

    // ── Athlete identity ──────────────────────────────────────────────────────
    line(athlete.name.toUpperCase(), 16, true, '#e6edf3')
    y += 2
    const conferenceTierLabelText = conferenceTierDisplayLabel(report?.metadata?.conference_tier)
    const meta = [
      athlete.position,
      athlete.school,
      athlete.class_year,
      athlete.conference,
      conferenceTierLabelText,
    ].filter(Boolean).join(' · ')
    line(meta, 9, false, '#8b949e')
    y += 4

    // ── Value benchmark ───────────────────────────────────────────────────────
    rule()
    line('TOTAL NIL VALUE BENCHMARK', 9, true, '#6e7681')
    const value = report?.value
    const benchmark = value?.total_benchmark ?? athlete.dollar_p50_usd ?? athlete.nil_valuation_consensus
    const rangeLow = value?.range_low ?? athlete.dollar_p10_usd ?? athlete.nil_range_low
    const rangeHigh = value?.range_high ?? athlete.dollar_p90_usd ?? athlete.nil_range_high
    line(nilFmt(benchmark), 30, true, '#d29922')
    line(formatNilRangeAligned(benchmark, rangeLow, rangeHigh), 10, false, '#8b949e')
    const tagBits: string[] = []
    if (value?.tier_tag) tagBits.push(value.tier_tag)
    if (value?.confidence_tag) tagBits.push(value.confidence_tag)
    if (conferenceTierLabelText) tagBits.push(conferenceTierLabelText)
    if (tagBits.length) {
      line(`TAGS: ${tagBits.join(' · ')}`, 8, false, '#6e7681')
    }
    y += 4

    // ── Executive summary ─────────────────────────────────────────────────────
    rule()
    line('EXECUTIVE SUMMARY', 9, true, '#6e7681')
    writeWrapped(
      report?.explanation?.executive_summary || report?.executive_summary || 'Summary unavailable.',
      9,
      '#c9d1d9',
      13,
    )

    // ── Key value drivers ─────────────────────────────────────────────────────
    rule()
    line('KEY VALUE DRIVERS', 9, true, '#6e7681')
    const drivers = report?.explanation?.key_value_drivers ?? []
    if (!drivers.length) {
      line(`Brand Strength: ${formatScore(athlete.brand_score)} (Moderate)`, 9, false, '#c9d1d9')
      line(`Market Proof: ${formatScore(athlete.proof_score)} (Moderate)`, 9, false, '#c9d1d9')
      line(`Exposure: ${formatScore(athlete.proximity_score)} (Moderate)`, 9, false, '#c9d1d9')
      line(`Risk: ${formatScore(athlete.risk_score)} (Moderate)`, 9, false, '#c9d1d9')
    } else {
      for (const d of drivers) {
        line(`${d.label}: ${d.signal}`, 9, true, '#c9d1d9')
        writeWrapped(d.explanation, 8, '#8b949e', 11)
      }
    }
    if (report?.explanation?.driver_takeaway) {
      writeWrapped(report.explanation.driver_takeaway, 8, '#8b949e', 12)
    }

    // ── Validation: market + comparables + confidence/risk ───────────────────
    const comparablesForExport = normalizeComparableRows(
      report?.validation?.example_comparables?.length
        ? report.validation.example_comparables
        : comparables,
    )
    if (report?.validation?.market_context) {
      rule()
      line('MARKET & COMPARABLE ANALYSIS', 9, true, '#6e7681')
      if (shouldSuppressPercentile(report.metadata?.cohort_fit)) {
        writeWrapped(
          `${athlete.name}'s benchmark exceeds the peer cohort distribution; reference the positional peer range below in lieu of percentile.`,
          8,
          '#8b949e',
          12,
        )
      } else {
        writeWrapped(report.validation.market_context, 8, '#8b949e', 12)
      }
      if (report.validation.comparable_tier) {
        writeWrapped(report.validation.comparable_tier, 8, '#8b949e', 12)
      }
    }
    if (report?.validation?.comparable_state === 'none' && report.validation.positional_reference_athletes.length) {
      rule()
      line('POSITIONAL REFERENCE ATHLETES', 9, true, '#6e7681')
      const refs = normalizeComparableRows(report.validation.positional_reference_athletes).slice(0, 3)
      for (const c of refs) {
        line(`${c.name} · ${c.school ?? ''} · ${scoreFmt(c.gravity_score)} · ${nilFmt(c.nil_valuation_consensus)}`, 8, false, '#c9d1d9')
      }
      y += 4
    } else if (comparablesForExport.length) {
      rule()
      line('COMPARABLE ATHLETES', 9, true, '#6e7681')
      y += 4

      const headers = ['ATHLETE', 'GS', 'NIL EST.', 'CONF.']
      const colWidths = [200, 50, 90, 60]
      let x = margin
      for (let i = 0; i < headers.length; i++) {
        doc.setFontSize(8)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor('#6e7681')
        doc.text(headers[i], x, y)
        x += colWidths[i]
      }
      y += 12

      for (const c of comparablesForExport.slice(0, 12)) {
        ensureSpace(14)
        x = margin
        const vals = [
          `${c.name} · ${c.school ?? ''}`,
          scoreFmt(c.gravity_score),
          nilFmt(c.nil_valuation_consensus),
          formatComparableConfidence(c.confidence),
        ]
        for (let i = 0; i < vals.length; i++) {
          doc.setFontSize(8)
          doc.setFont('helvetica', 'normal')
          doc.setTextColor('#c9d1d9')
          const cell = vals[i].length > 28 ? vals[i].slice(0, 26) + '…' : vals[i]
          doc.text(cell, x, y)
          x += colWidths[i]
        }
        y += 12
      }
      y += 4
    }
    if (report?.confidence_risk) {
      line('CONFIDENCE & RISK', 9, true, '#6e7681')
      line(`Confidence: ${report.confidence_risk.confidence_level}`, 8, true, '#c9d1d9')
      writeWrapped(report.confidence_risk.confidence_note, 8, '#8b949e', 12)
      line(`Risk: ${report.confidence_risk.risk_level}`, 8, true, '#c9d1d9')
      writeWrapped(report.confidence_risk.risk_note, 8, '#8b949e', 12)
    }
    if (report?.validation?.takeaway) {
      line('VALUE INTERPRETATION', 9, true, '#6e7681')
      writeWrapped(report.validation.takeaway, 8, '#8b949e', 12)
    }

    // ── Detail appendix ───────────────────────────────────────────────────────
    rule()
    line('MODEL DETAILS (APPENDIX)', 9, true, '#6e7681')
    const blocks = report?.detail?.blocks
    if (blocks) {
      // Methodology
      if (blocks.methodology) {
        line(blocks.methodology.title || 'Methodology', 9, true, '#c9d1d9')
        if (blocks.methodology.summary) {
          writeWrapped(blocks.methodology.summary, 8, '#8b949e', 12)
        }
        for (const c of blocks.methodology.components ?? []) {
          writeWrapped(`• ${c}`, 8, '#8b949e', 12)
        }
        if (blocks.methodology.tier_methodology_version) {
          writeWrapped(
            `Tier methodology: ${blocks.methodology.tier_methodology_version}`,
            8,
            '#6e7681',
            12,
          )
        }
        y += 4
      }
      // Cohort
      if (blocks.cohort) {
        line(blocks.cohort.title || 'Cohort', 9, true, '#c9d1d9')
        const cohortBits = [
          blocks.cohort.sport,
          blocks.cohort.position_group,
          blocks.cohort.conference,
          blocks.cohort.conference_tier ? conferenceTierDisplayLabel(blocks.cohort.conference_tier) : null,
        ].filter(Boolean) as string[]
        if (cohortBits.length) {
          writeWrapped(cohortBits.join(' · '), 8, '#8b949e', 12)
        }
        const cohortStats = [
          blocks.cohort.size != null ? `n=${blocks.cohort.size}` : null,
          blocks.cohort.window_days != null ? `window=${blocks.cohort.window_days}d` : null,
          blocks.cohort.season_state ? `season=${blocks.cohort.season_state}` : null,
          blocks.cohort.fallback_step != null ? `fallback_step=${blocks.cohort.fallback_step}` : null,
        ].filter(Boolean) as string[]
        if (cohortStats.length) {
          writeWrapped(cohortStats.join(' · '), 8, '#6e7681', 12)
        }
        y += 4
      }
      // Comparables
      if (blocks.comparables) {
        line(blocks.comparables.title || 'Comparables', 9, true, '#c9d1d9')
        const compBits = [
          blocks.comparables.state ? `state=${blocks.comparables.state}` : null,
          blocks.comparables.computed_at ? `computed_at=${blocks.comparables.computed_at}` : null,
        ].filter(Boolean) as string[]
        if (compBits.length) writeWrapped(compBits.join(' · '), 8, '#8b949e', 12)
        y += 4
      }
      // Provenance
      if (blocks.provenance) {
        line(blocks.provenance.title || 'Provenance', 9, true, '#c9d1d9')
        const provBits = [
          blocks.provenance.report_id ? `report_id=${blocks.provenance.report_id}` : null,
          blocks.provenance.rollout_phase ? `rollout_phase=${blocks.provenance.rollout_phase}` : null,
          blocks.provenance.tier_version ? `tier_version=${blocks.provenance.tier_version}` : null,
          blocks.provenance.exposure_formula_version
            ? `exposure_formula=${blocks.provenance.exposure_formula_version}`
            : null,
          blocks.provenance.model_version ? `model=${blocks.provenance.model_version}` : null,
          blocks.provenance.model_status ? `model_status=${blocks.provenance.model_status}` : null,
        ].filter(Boolean) as string[]
        if (provBits.length) writeWrapped(provBits.join(' · '), 8, '#6e7681', 12)
        y += 4
      }
      // SHAP attribution
      const shap = blocks.shap_attribution
      if (shap) {
        if (typeof shap === 'string') {
          line('SHAP Attribution', 9, true, '#c9d1d9')
          writeWrapped(shap, 8, '#8b949e', 12)
        } else {
          line(shap.title || 'SHAP Attribution', 9, true, '#c9d1d9')
          if (shap.narrative) {
            writeWrapped(shap.narrative, 8, '#8b949e', 12)
          }
          for (const row of shap.rows ?? []) {
            writeWrapped(
              `${row.feature}: ${row.contribution.toFixed(2)}`,
              8,
              '#6e7681',
              12,
            )
          }
        }
      }
    } else {
      const shapText = report?.detail?.shap_attribution
      const methodology = report?.detail?.methodology
      const inputs = report?.detail?.inputs
      if (shapText) writeWrapped(`SHAP: ${shapText}`, 8, '#6e7681', 12)
      if (methodology) writeWrapped(`Methodology: ${methodology}`, 8, '#6e7681', 12)
      if (inputs) writeWrapped(`Inputs: ${inputs}`, 8, '#6e7681', 12)
      if (report?.metadata) {
        writeWrapped(
          `Provenance: tier_version=${report.metadata.tier_version}, cohort_window_days=${report.metadata.cohort_window_days_used}, ` +
            `season_state=${report.metadata.season_state}, cohort_size=${report.metadata.cohort_size}, ` +
            `cohort_fallback_step=${report.metadata.cohort_fallback_step}, comparable_state=${report.metadata.comparable_state}, ` +
            `comparable_sets_computed_at=${report.metadata.comparable_sets_computed_at ?? 'n/a'}, ` +
            `exposure_formula_version=${report.metadata.exposure_formula_version}.`,
          8,
          '#6e7681',
          12,
        )
      }
    }
    y += 8

    line(
      'DISCLAIMER: This is a commercial intelligence estimate used to inform NIL valuation discussions; it ' +
        'is not legal, tax, or financial advice. Final NIL agreement terms remain subject to House v. NCAA ' +
        'settlement compliance review and the College Sports Commission (CSC) Deal Approval process. ' +
        "Gravity Score is not the deal counterparty and is not liable for decisions made from this report's outputs.",
      8,
      false,
      '#484f58',
    )

    doc.save(`gravity_csc_${athlete.name.replace(/\s+/g, '_')}_${Date.now()}.pdf`)
  } catch (err) {
    console.error('PDF generation failed, falling back to print:', err)
    window.print()
  }
}

/** Quick athlete score card PDF — used from MainHeader / QuickActions */
export async function downloadAthleteScoreCardPdf(athlete: AthleteRecord): Promise<void> {
  await downloadCscPdf(athlete, [], null)
}

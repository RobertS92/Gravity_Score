/**
 * PDF export — generates a real downloadable PDF from athlete/report data.
 * Uses jsPDF for layout. Falls back to window.print() if jsPDF fails to load.
 */
import type { AthleteRecord, ComparableRecord } from '../types/athlete'
import type { CscReportJson } from '../types/reports'
import { formatNilMillions, formatScore } from './formatters'

function fmt(v: number | null | undefined) {
  return v != null ? String(Math.round(v)) : '—'
}

function nilFmt(v: number | null | undefined) {
  if (v == null) return '—'
  return formatNilMillions(v)
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
    let y = margin

    const line = (text: string, fontSize = 10, bold = false, color = '#c9d1d9') => {
      doc.setFontSize(fontSize)
      doc.setFont('helvetica', bold ? 'bold' : 'normal')
      doc.setTextColor(color)
      doc.text(text, margin, y)
      y += fontSize * 1.5
    }

    const rule = () => {
      doc.setDrawColor('#30363d')
      doc.setLineWidth(0.5)
      doc.line(margin, y, margin + colW, y)
      y += 8
    }

    // ── Header ────────────────────────────────────────────────────────────────
    doc.setFillColor('#0d1117')
    doc.rect(0, 0, W, 792, 'F')

    line('GRAVITY', 20, true, '#3fb950')
    y += 2
    line('NIL COMMERCIAL INTELLIGENCE — CSC REPORT', 8, false, '#6e7681')
    line(`Generated: ${new Date().toLocaleString('en-US', { timeZone: 'America/New_York' })} ET`, 8, false, '#6e7681')
    y += 8
    rule()

    // ── Athlete identity ──────────────────────────────────────────────────────
    line(athlete.name.toUpperCase(), 16, true, '#e6edf3')
    y += 2
    const meta = [
      athlete.position,
      athlete.school,
      athlete.class_year,
      athlete.conference,
    ].filter(Boolean).join(' · ')
    line(meta, 9, false, '#8b949e')
    y += 4

    // ── Gravity Score ─────────────────────────────────────────────────────────
    rule()
    line('GRAVITY SCORE', 9, true, '#6e7681')
    line(scoreFmt(athlete.gravity_score), 24, true, '#3fb950')
    line(`TIER: ${athlete.gravity_tier ?? '—'}  ·  PCT: ${athlete.gravity_percentile != null ? athlete.gravity_percentile + 'th' : '—'}`, 9)
    if (athlete.updated_at) {
      line(`Scored: ${new Date(athlete.updated_at).toLocaleDateString()}`, 8, false, '#6e7681')
    }
    y += 4

    // ── Component scores ──────────────────────────────────────────────────────
    rule()
    line('COMPONENT SCORES', 9, true, '#6e7681')
    y += 4

    const components: [string, number | null | undefined, string][] = [
      ['BRAND (B)', athlete.brand_score, '#58a6ff'],
      ['PROOF (P)', athlete.proof_score, '#c9d1d9'],
      ['PROXIMITY (X)', athlete.proximity_score, '#a371f7'],
      ['VELOCITY (V)', athlete.velocity_score, '#3fb950'],
      ['RISK (R)', athlete.risk_score, '#f85149'],
    ]

    for (const [label, score, color] of components) {
      doc.setFontSize(9)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor('#6e7681')
      doc.text(label, margin, y)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(color)
      doc.text(fmt(score), margin + 120, y)
      y += 14
    }
    y += 4

    // ── NIL valuation ─────────────────────────────────────────────────────────
    rule()
    line('NIL VALUATION', 9, true, '#6e7681')
    line(`P50 ESTIMATE: ${nilFmt(athlete.dollar_p50_usd ?? athlete.nil_valuation_consensus)}`, 11, true, '#d29922')
    line(
      `RANGE: ${nilFmt(athlete.dollar_p10_usd ?? athlete.nil_range_low)} – ${nilFmt(athlete.dollar_p90_usd ?? athlete.nil_range_high)}`,
      9,
      false,
      '#8b949e',
    )
    const confScore = athlete.dollar_confidence?.dollar_confidence_score
    if (confScore != null) {
      const confLabel = confScore >= 0.7 ? 'HIGH' : confScore >= 0.45 ? 'MODERATE' : 'LOW'
      line(`CONFIDENCE: ${confLabel} (${Math.round(confScore * 100)}%)`, 9)
    }
    line(`COMPARABLE DEALS: ${athlete.verified_deals_count ?? '—'}`, 9)
    y += 4

    // ── Report narrative (if generated) ───────────────────────────────────────
    if (report?.executive_summary) {
      rule()
      line('EXECUTIVE SUMMARY', 9, true, '#6e7681')
      const wrapped = doc.splitTextToSize(report.executive_summary, colW)
      doc.setFontSize(9)
      doc.setFont('helvetica', 'normal')
      doc.setTextColor('#c9d1d9')
      doc.text(wrapped, margin, y)
      y += wrapped.length * 13
    }

    if (report?.risk_assessment) {
      rule()
      line('RISK ASSESSMENT', 9, true, '#6e7681')
      const wrapped = doc.splitTextToSize(report.risk_assessment, colW)
      doc.setFontSize(9)
      doc.setFont('helvetica', 'normal')
      doc.setTextColor('#c9d1d9')
      doc.text(wrapped, margin, y)
      y += wrapped.length * 13
    }

    // ── Comparables ───────────────────────────────────────────────────────────
    if (comparables.length) {
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

      for (const c of comparables.slice(0, 12)) {
        if (y > 700) { doc.addPage(); doc.setFillColor('#0d1117'); doc.rect(0, 0, W, 792, 'F'); y = margin }
        x = margin
        const confLabel = c.confidence != null
          ? (c.confidence >= 0.7 ? 'HIGH' : c.confidence >= 0.45 ? 'MOD' : 'LOW')
          : '—'
        const vals = [
          `${c.name} · ${c.school ?? ''}`,
          scoreFmt(c.gravity_score),
          nilFmt(c.nil_valuation_consensus),
          confLabel,
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

    // ── Methodology + disclaimer ──────────────────────────────────────────────
    if (y > 680) { doc.addPage(); doc.setFillColor('#0d1117'); doc.rect(0, 0, W, 792, 'F'); y = margin }
    rule()
    line('METHODOLOGY', 9, true, '#6e7681')
    const methodology =
      'Gravity Scores are computed by a neural network trained on Power 5 athlete data. ' +
      'Component scores (Brand, Proof, Proximity, Velocity, Risk) are aggregated using SHAP-attributed feature weights. ' +
      'NIL valuations are estimated from verified comparable deal data and market distribution models.'
    const mWrapped = doc.splitTextToSize(methodology, colW)
    doc.setFontSize(8)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor('#6e7681')
    doc.text(mWrapped, margin, y)
    y += mWrapped.length * 12 + 8

    line(
      'DISCLAIMER: This report contains commercial intelligence data, not legal or financial advice. ' +
        'Gravity is not liable for decisions made based on this data.',
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

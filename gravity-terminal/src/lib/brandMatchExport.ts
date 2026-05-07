import type { BrandMatchResult } from '../types/reports'

function fileStamp() {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`
}

function downloadText(filename: string, mime: string, text: string) {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function nilP50(row: BrandMatchResult): number | null {
  if (typeof row.deal_range_low === 'number' && typeof row.deal_range_high === 'number') {
    return (row.deal_range_low + row.deal_range_high) / 2
  }
  return null
}

export function exportBrandMatchShortlistCsv(rows: BrandMatchResult[]) {
  const header = [
    'rank',
    'athlete_name',
    'school',
    'sport',
    'position',
    'match_score',
    'nil_range_low',
    'nil_range_high',
    'nil_p50_estimate',
    'social_combined_reach',
    'instagram_engagement_rate',
    'verified_deals_count',
  ]
  const csvRows = rows.map((r, idx) => [
    idx + 1,
    r.name ?? '',
    r.school ?? '',
    r.sport ?? '',
    r.position ?? '',
    r.match_score ?? '',
    r.deal_range_low ?? '',
    r.deal_range_high ?? '',
    nilP50(r) ?? '',
    r.social_combined_reach ?? '',
    r.instagram_engagement_rate ?? '',
    r.verified_deals_count ?? '',
  ])
  const escapeCell = (v: unknown) => {
    const s = String(v ?? '')
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
      return `"${s.replaceAll('"', '""')}"`
    }
    return s
  }
  const body = [header, ...csvRows].map((row) => row.map(escapeCell).join(',')).join('\n')
  downloadText(`brand_match_shortlist_${fileStamp()}.csv`, 'text/csv;charset=utf-8', body)
}

export async function exportBrandMatchShortlistPdf(rows: BrandMatchResult[]) {
  const { jsPDF } = await import('jspdf')
  const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'letter' })
  doc.setFillColor('#0d1117')
  doc.rect(0, 0, 612, 792, 'F')
  doc.setTextColor('#3fb950')
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(16)
  doc.text('GRAVITY BRAND MATCH SHORTLIST', 42, 48)
  doc.setTextColor('#8b949e')
  doc.setFontSize(9)
  doc.text(`Generated ${new Date().toLocaleString()}`, 42, 64)

  const headers = ['ATHLETE', 'MATCH', 'NIL P50', 'REACH']
  const widths = [250, 70, 110, 90]
  let y = 92

  const drawHeader = () => {
    let x = 42
    doc.setTextColor('#6e7681')
    doc.setFontSize(8)
    doc.setFont('helvetica', 'bold')
    for (let i = 0; i < headers.length; i++) {
      doc.text(headers[i], x, y)
      x += widths[i]
    }
    y += 14
    doc.setDrawColor('#30363d')
    doc.line(42, y - 8, 570, y - 8)
  }

  drawHeader()
  for (const r of rows) {
    if (y > 740) {
      doc.addPage()
      doc.setFillColor('#0d1117')
      doc.rect(0, 0, 612, 792, 'F')
      y = 48
      drawHeader()
    }
    const values = [
      `${r.name} · ${r.school ?? ''}`,
      String(r.match_score ?? '—'),
      (() => {
        const p50 = nilP50(r)
        if (p50 == null) return '—'
        if (p50 >= 1_000_000) return `$${(p50 / 1_000_000).toFixed(1)}M`
        return `$${Math.round(p50 / 1000)}K`
      })(),
      (() => {
        const reach = r.social_combined_reach
        if (reach == null) return '—'
        if (reach >= 1_000_000) return `${(reach / 1_000_000).toFixed(1)}M`
        return `${Math.round(reach / 1000)}K`
      })(),
    ]
    let x = 42
    doc.setTextColor('#c9d1d9')
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    for (let i = 0; i < values.length; i++) {
      doc.text(values[i], x, y)
      x += widths[i]
    }
    y += 14
  }

  doc.save(`brand_match_shortlist_${fileStamp()}.pdf`)
}

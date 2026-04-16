import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from 'recharts'
import type { AthleteRecord } from '../../types/athlete'
import { formatScore } from '../../lib/formatters'

const DIMS: { key: keyof Pick<AthleteRecord, 'brand_score' | 'proof_score' | 'proximity_score' | 'velocity_score' | 'risk_score'>; label: string }[] = [
  { key: 'brand_score', label: 'Brand' },
  { key: 'proof_score', label: 'Proof' },
  { key: 'proximity_score', label: 'Proximity' },
  { key: 'velocity_score', label: 'Velocity' },
  { key: 'risk_score', label: 'Risk' },
]

export default function CohortRadar({ athletes }: { athletes: AthleteRecord[] }) {
  const data = DIMS.map((d) => {
    const row: Record<string, string | number> = { dim: d.label }
    for (const a of athletes) {
      row[a.name] = a[d.key] ?? 0
    }
    return row
  })

  const colors = ['#58a6ff', '#3fb950', '#a371f7', '#d29922', '#f85149']

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#1c2128" />
          <PolarAngleAxis dataKey="dim" tick={{ fill: '#484f58', fontSize: 9, fontFamily: 'Courier New' }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          {athletes.map((a, i) => (
            <Radar
              key={a.athlete_id}
              name={a.name}
              dataKey={a.name}
              stroke={colors[i % colors.length]}
              fill={colors[i % colors.length]}
              fillOpacity={0.12}
              isAnimationActive={false}
            />
          ))}
          <Legend wrapperStyle={{ fontFamily: 'Arial', fontSize: 10, color: '#8b949e' }} />
        </RadarChart>
      </ResponsiveContainer>
      <div style={{ marginTop: 12, fontFamily: 'Courier New', fontSize: 10, color: '#c9d1d9' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', color: '#484f58', fontSize: 8 }}>ATHLETE</th>
              <th style={{ textAlign: 'right', color: '#484f58', fontSize: 8 }}>B</th>
              <th style={{ textAlign: 'right', color: '#484f58', fontSize: 8 }}>P</th>
              <th style={{ textAlign: 'right', color: '#484f58', fontSize: 8 }}>X</th>
              <th style={{ textAlign: 'right', color: '#484f58', fontSize: 8 }}>V</th>
              <th style={{ textAlign: 'right', color: '#484f58', fontSize: 8 }}>R</th>
            </tr>
          </thead>
          <tbody>
            {athletes.map((a) => (
              <tr key={a.athlete_id}>
                <td style={{ padding: '6px 0' }}>{a.name}</td>
                <td style={{ textAlign: 'right' }}>{formatScore(a.brand_score)}</td>
                <td style={{ textAlign: 'right' }}>{formatScore(a.proof_score)}</td>
                <td style={{ textAlign: 'right' }}>{formatScore(a.proximity_score)}</td>
                <td style={{ textAlign: 'right' }}>{formatScore(a.velocity_score)}</td>
                <td style={{ textAlign: 'right' }}>{formatScore(a.risk_score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

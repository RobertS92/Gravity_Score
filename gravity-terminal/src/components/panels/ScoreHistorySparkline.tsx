import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts'
import type { ScoreHistoryPoint } from '../../types/athlete'

export function ScoreHistorySparkline({ data }: { data: ScoreHistoryPoint[] }) {
  const chartData = data.map((d) => ({ x: d.date, y: d.gravity_score }))
  if (!chartData.length) return null
  return (
    <div style={{ width: '100%', height: 48 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <YAxis hide domain={['dataMin - 2', 'dataMax + 2']} />
          <Line type="monotone" dataKey="y" stroke="#3fb950" strokeWidth={1} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

import React from 'react'
import { usePlayers } from '../hooks/useMarketData'
import { DataMode } from '../types'

interface PlayersOverviewProps {
  dataMode: DataMode
}

export const PlayersOverview: React.FC<PlayersOverviewProps> = ({ dataMode }) => {
  const { data, isLoading, isError, error } = usePlayers(dataMode, 20)
  const players = data?.players ?? []

  const formatCurrency = (value: number | undefined) => {
    if (!value) return '$0'

    if (value >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`
    }

    if (value >= 1_000) {
      return `$${(value / 1_000).toFixed(0)}K`
    }

    return `$${value.toFixed(0)}`
  }

  const formatGravity = (value: number | undefined) => {
    if (!value) return '0.0'
    return value.toFixed(2)
  }

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="space-y-3">
          {[...Array(6)].map((_, index) => (
            <div key={index} className="animate-pulse h-12 bg-dark-border rounded" />
          ))}
        </div>
      )
    }

    if (isError) {
      const message = error instanceof Error ? error.message : 'Unable to load players right now.'
      return <div className="text-danger">{message}</div>
    }

    if (players.length === 0) {
      return <div className="text-dark-muted">No players available for the selected mode.</div>
    }

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-dark-muted border-b border-dark-border">
              <th className="py-3 pr-4 font-medium">Player</th>
              <th className="py-3 pr-4 font-medium">Position</th>
              <th className="py-3 pr-4 font-medium">Team</th>
              <th className="py-3 pr-4 font-medium text-right">Brand Value</th>
              <th className="py-3 font-medium text-right">Gravity Score</th>
            </tr>
          </thead>
          <tbody>
            {players.map((player) => (
              <tr key={player.id ?? player.name} className="border-b border-dark-border last:border-b-0">
                <td className="py-3 pr-4 text-dark-text font-semibold">{player.name}</td>
                <td className="py-3 pr-4 text-dark-muted">{player.position}</td>
                <td className="py-3 pr-4 text-dark-muted uppercase">{player.team}</td>
                <td className="py-3 pr-4 text-success text-right font-semibold">
                  {formatCurrency(player.brand_value)}
                </td>
                <td className="py-3 text-right text-info font-semibold">
                  {formatGravity(player.total_gravity ?? player.brand_power)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <section>
      <h2 className="text-lg lg:text-xl font-semibold text-dark-text mb-4">Players</h2>
      <div className="bg-dark-card border border-dark-border rounded-2xl p-6">
        {renderContent()}
      </div>
    </section>
  )
}

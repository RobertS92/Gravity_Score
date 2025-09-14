import React from 'react'
import { DollarSign, FileText, TrendingUp, Activity } from 'lucide-react'
import { useFinancialOverview } from '../hooks/useMarketData'
import { DataMode } from '../types'

interface FinancialOverviewProps {
  dataMode: DataMode
}

export const FinancialOverview: React.FC<FinancialOverviewProps> = ({ dataMode }) => {
  const { data, isLoading, error } = useFinancialOverview(dataMode)

  const formatCurrency = (value: number): string => {
    if (value >= 1_000_000_000) {
      return `$${(value / 1_000_000_000).toFixed(2)}B`
    } else if (value >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`
    } else if (value >= 1_000) {
      return `$${(value / 1_000).toFixed(0)}K`
    } else {
      return `$${value.toFixed(0)}`
    }
  }

  const metrics = [
    {
      icon: DollarSign,
      label: 'Total Market Value',
      value: data ? formatCurrency(data.total_market_value) : '$0',
      change: '+12.3%',
      changeType: 'positive' as const,
      footer: data ? `Across ${data.athlete_count} athletes` : 'Loading...',
      testId: 'metric-total-market-value'
    },
    {
      icon: FileText,
      label: 'Active Contracts',
      value: data ? data.active_contracts.toString() : '0',
      change: '+5.7%',
      changeType: 'positive' as const,
      footer: data ? `Worth ${formatCurrency(data.total_market_value * 0.8)} combined` : 'Loading...',
      testId: 'metric-active-contracts'
    },
    {
      icon: TrendingUp,
      label: 'Avg. Brand Value',
      value: data ? formatCurrency(data.avg_brand_value) : '$0',
      change: '-2.1%',
      changeType: 'negative' as const,
      footer: 'Per athlete this quarter',
      testId: 'metric-avg-brand-value'
    },
    {
      icon: Activity,
      label: 'Market Activity',
      value: data ? `${data.market_activity.toFixed(1)}%` : '0%',
      change: '+8.4%',
      changeType: 'positive' as const,
      footer: 'Trading confidence index',
      testId: 'metric-market-activity'
    }
  ]

  if (error) {
    return (
      <div className="bg-red-900 border border-red-700 text-red-100 p-4 rounded-lg">
        Error loading financial overview: {error instanceof Error ? error.message : 'Unknown error'}
      </div>
    )
  }

  return (
    <section>
      <h2 className="text-lg lg:text-xl font-semibold text-dark-text mb-4">Financial Overview</h2>
      <div 
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6"
        data-testid="financial-overview"
      >
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className={`
              bg-dark-card border border-dark-border rounded-2xl p-4 lg:p-5 relative transition-all
              ${isLoading ? 'opacity-60 pointer-events-none' : 'hover:bg-dark-card/80'}
            `}
            data-testid={metric.testId}
          >
            {/* Loading overlay */}
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-dark-border border-t-dark-accent rounded-full animate-spin" />
              </div>
            )}

            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
              <metric.icon size={16} className="text-dark-muted" />
              <span className="text-xs lg:text-sm text-dark-muted font-medium">
                {metric.label}
              </span>
            </div>

            {/* Value */}
            <div className="text-2xl lg:text-3xl font-bold text-dark-text mb-1">
              {metric.value}
            </div>

            {/* Change */}
            <div className={`
              flex items-center gap-1 text-xs font-semibold mb-2
              ${metric.changeType === 'positive' ? 'text-success' : 'text-danger'}
            `}>
              <span>{metric.changeType === 'positive' ? '↗' : '↘'}</span>
              <span>{metric.change}</span>
            </div>

            {/* Footer */}
            <div className="text-xs text-dark-muted">
              {metric.footer}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
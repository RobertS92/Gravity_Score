import React from 'react'
import { useQuickStats, useSystemStatus } from '../hooks/useMarketData'
import { DataMode } from '../types'

interface DataAnalysisProps {
  dataMode: DataMode
}

export const DataAnalysis: React.FC<DataAnalysisProps> = ({ dataMode }) => {
  const { data: stats, isLoading: statsLoading } = useQuickStats(dataMode)
  const { data: systemStatus, isLoading: systemLoading } = useSystemStatus()

  return (
    <section>
      <h2 className="text-lg lg:text-xl font-semibold text-dark-text mb-4">Data Analysis</h2>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
        
        {/* Performance Charts Placeholder */}
        <div 
          className="lg:col-span-2 bg-dark-card border border-dark-border rounded-2xl p-8 lg:p-12 text-center"
          data-testid="analysis-charts"
        >
          <h3 className="text-lg font-semibold text-dark-text mb-2">Performance Charts</h3>
          <p className="text-dark-muted text-sm">
            Chart Component Placeholder<br />
            Interactive performance data visualization
          </p>
        </div>

        {/* Quick Stats and System Status */}
        <div className="space-y-4">
          {/* Quick Stats */}
          <div 
            className="bg-dark-card border border-dark-border rounded-2xl p-4"
            data-testid="quick-stats"
          >
            <h4 className="text-sm font-semibold text-dark-text mb-3">Quick Stats</h4>
            {statsLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex justify-between items-center py-2 animate-pulse">
                    <div className="h-3 bg-dark-border rounded w-20" />
                    <div className="h-3 bg-dark-border rounded w-8" />
                  </div>
                ))}
              </div>
            ) : stats ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-dark-border">
                  <span className="text-xs text-dark-muted">Teams Tracked</span>
                  <span className="text-xs font-semibold text-dark-text">{stats.teams_tracked}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-dark-border">
                  <span className="text-xs text-dark-muted">Data Points</span>
                  <span className="text-xs font-semibold text-dark-text">{stats.data_points}</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-xs text-dark-muted">Update Freq.</span>
                  <span className="text-xs font-semibold text-success">{stats.update_freq}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-dark-muted text-xs">
                No stats available
              </div>
            )}
          </div>

          {/* System Status */}
          <div 
            className="bg-dark-card border border-dark-border rounded-2xl p-4"
            data-testid="system-status"
          >
            <h4 className="text-sm font-semibold text-dark-text mb-3">System Status</h4>
            {systemLoading ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex justify-between items-center py-2 animate-pulse">
                    <div className="h-3 bg-dark-border rounded w-20" />
                    <div className="h-3 bg-dark-border rounded w-12" />
                  </div>
                ))}
              </div>
            ) : systemStatus ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center py-2 border-b border-dark-border">
                  <span className="text-xs text-dark-muted">API Status</span>
                  <span className="text-xs font-semibold text-success">● {systemStatus.api_status}</span>
                </div>
                <div className="flex justify-between items-center py-2 border-b border-dark-border">
                  <span className="text-xs text-dark-muted">Data Freshness</span>
                  <span className="text-xs font-semibold text-dark-text">{systemStatus.data_freshness}</span>
                </div>
                <div className="flex justify-between items-center py-2">
                  <span className="text-xs text-dark-muted">Sync Rate</span>
                  <span className="text-xs font-semibold text-dark-text">{systemStatus.sync_rate}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-dark-muted text-xs">
                System status unavailable
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
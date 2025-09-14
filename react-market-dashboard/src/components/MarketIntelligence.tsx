import React from 'react'
import { useTopPerformers, useMarketActivity } from '../hooks/useMarketData'
import { DataMode } from '../types'

interface MarketIntelligenceProps {
  dataMode: DataMode
}

export const MarketIntelligence: React.FC<MarketIntelligenceProps> = ({ dataMode }) => {
  const { data: performers, isLoading: performersLoading } = useTopPerformers(dataMode)
  const { data: activities, isLoading: activitiesLoading } = useMarketActivity(dataMode)

  const formatCurrency = (value: number): string => {
    if (value >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`
    } else if (value >= 1_000) {
      return `$${(value / 1_000).toFixed(0)}K`
    } else {
      return `$${value.toFixed(0)}`
    }
  }

  const getTagStyles = (tagClass: string, priority: string) => {
    const priorityOpacity = priority === 'High' ? 'opacity-100' : priority === 'Medium' ? 'opacity-80' : 'opacity-60'
    
    switch (tagClass) {
      case 'tag-contract':
        return `bg-green-900 text-success ${priorityOpacity}`
      case 'tag-endorsement':
        return `bg-yellow-900 text-warning ${priorityOpacity}`
      case 'tag-trade':
        return `bg-red-900 text-danger ${priorityOpacity}`
      case 'tag-performance':
        return `bg-purple-900 text-purple ${priorityOpacity}`
      case 'tag-social':
        return `bg-cyan-900 text-info ${priorityOpacity}`
      default:
        return `bg-gray-900 text-dark-muted ${priorityOpacity}`
    }
  }

  return (
    <section>
      <h2 className="text-lg lg:text-xl font-semibold text-dark-text mb-4">Market Intelligence</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6">
        
        {/* Top Brand Performers */}
        <div 
          className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden"
          data-testid="mi-top-performers"
        >
          <div className="bg-dark-bg px-5 py-4 border-b border-dark-border">
            <h3 className="text-base font-semibold text-dark-text">Top Brand Performers</h3>
            <p className="text-xs text-dark-muted">Last 24 hours</p>
          </div>
          <div className="p-5">
            {performersLoading ? (
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="flex items-center gap-4 animate-pulse">
                    <div className="w-6 h-6 bg-dark-border rounded-full" />
                    <div className="flex-1">
                      <div className="h-4 bg-dark-border rounded w-20 mb-1" />
                      <div className="h-3 bg-dark-border rounded w-16" />
                    </div>
                    <div className="text-right">
                      <div className="h-4 bg-dark-border rounded w-16 mb-1" />
                      <div className="h-3 bg-dark-border rounded w-10" />
                    </div>
                  </div>
                ))}
              </div>
            ) : performers && performers.length > 0 ? (
              <div className="space-y-3">
                {performers.map((performer) => (
                  <div key={performer.rank} className="flex items-center gap-4 py-3 border-b border-dark-border last:border-b-0">
                    <div className="w-6 h-6 bg-gray-600 text-dark-text rounded-full flex items-center justify-center text-xs font-semibold">
                      {performer.rank}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-dark-text">{performer.name}</p>
                      <p className="text-xs text-dark-muted">{performer.position} • {performer.team.toUpperCase()}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-dark-text">{formatCurrency(performer.brand_value)}</p>
                      <p className="text-xs text-success">+{performer.change_pct.toFixed(1)}%</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-dark-muted">
                No performers data available
              </div>
            )}
          </div>
        </div>

        {/* Market Activity */}
        <div 
          className="bg-dark-card border border-dark-border rounded-2xl overflow-hidden"
          data-testid="mi-activity-feed"
        >
          <div className="bg-dark-bg px-5 py-4 border-b border-dark-border">
            <h3 className="text-base font-semibold text-dark-text">Market Activity</h3>
            <p className="text-xs text-dark-muted">Real-time updates</p>
          </div>
          <div className="p-5">
            {activitiesLoading ? (
              <div className="space-y-4">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="flex items-start gap-3 animate-pulse">
                    <div className="w-10 h-3 bg-dark-border rounded" />
                    <div className="flex-1">
                      <div className="flex gap-2 mb-1">
                        <div className="h-4 bg-dark-border rounded w-16" />
                        <div className="h-4 bg-dark-border rounded w-12" />
                      </div>
                      <div className="h-3 bg-dark-border rounded w-48" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activities && activities.length > 0 ? (
              <div className="space-y-3">
                {activities.map((activity, index) => (
                  <div key={index} className="flex items-start gap-3 py-3 border-b border-dark-border last:border-b-0">
                    <div className="text-xs text-dark-muted min-w-[40px] mt-1">
                      {activity.time}
                    </div>
                    <div className="flex-1">
                      <div className="flex gap-2 mb-1">
                        <span className={`
                          px-2 py-1 rounded-full text-xs font-semibold uppercase
                          ${getTagStyles(activity.tag_class, activity.priority)}
                        `}>
                          {activity.type}
                        </span>
                        <span className={`
                          px-2 py-1 rounded-full text-xs font-semibold
                          ${activity.priority === 'High' ? 'bg-red-900 text-danger' : 
                            activity.priority === 'Medium' ? 'bg-yellow-900 text-warning' : 
                            'bg-gray-900 text-dark-muted'}
                        `}>
                          {activity.priority}
                        </span>
                      </div>
                      <p className="text-sm text-dark-text">{activity.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-dark-muted">
                No market activity available
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
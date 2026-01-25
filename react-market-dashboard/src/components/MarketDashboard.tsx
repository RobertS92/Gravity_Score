import React, { useState } from 'react'
import { Sidebar, type SidebarSection } from './Sidebar'
import { Header } from './Header'
import { FinancialOverview } from './FinancialOverview'
import { MarketIntelligence } from './MarketIntelligence'
import { DataAnalysis } from './DataAnalysis'
import { PlayersOverview } from './PlayersOverview'
import { DataMode } from '../types'

export const MarketDashboard: React.FC = () => {
  const [dataMode, setDataMode] = useState<DataMode>('ecos')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<SidebarSection>('dashboard')

  const handleModeChange = (mode: DataMode) => {
    setDataMode(mode)
  }

  const handleNavigation = (section: SidebarSection) => {
    setActiveSection(section)
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const renderPlaceholder = (title: string, description: string) => (
    <section>
      <h2 className="text-lg lg:text-xl font-semibold text-dark-text mb-4">{title}</h2>
      <div className="bg-dark-card border border-dark-border rounded-2xl p-6 text-dark-muted">
        {description}
      </div>
    </section>
  )

  const renderContent = () => {
    switch (activeSection) {
      case 'dashboard':
        return (
          <>
            <FinancialOverview dataMode={dataMode} />
            <MarketIntelligence dataMode={dataMode} />
            <DataAnalysis dataMode={dataMode} />
          </>
        )
      case 'market-data':
        return (
          <>
            <FinancialOverview dataMode={dataMode} />
            <MarketIntelligence dataMode={dataMode} />
          </>
        )
      case 'players':
        return <PlayersOverview dataMode={dataMode} />
      case 'analytics':
        return <DataAnalysis dataMode={dataMode} />
      case 'search':
        return renderPlaceholder(
          'Search',
          'Search tools are coming soon. Use the dashboard filters to explore players until then.',
        )
      case 'system-status':
        return renderPlaceholder(
          'System Status',
          'Live system telemetry will appear here in a future update. All systems are operating normally.',
        )
      case 'settings':
        return renderPlaceholder(
          'Settings',
          'Settings controls are not yet available in the preview experience.',
        )
      default:
        return null
    }
  }

  return (
    <div className="flex min-h-screen bg-dark-bg">
      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeSection={activeSection}
        onNavigate={handleNavigation}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col lg:ml-60">
        {/* Header */}
        <Header 
          dataMode={dataMode}
          onModeChange={handleModeChange}
          onMenuClick={() => setSidebarOpen(true)}
        />

        {/* Dashboard Content */}
        <main className="flex-1 p-4 lg:p-6 space-y-6 lg:space-y-8">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}
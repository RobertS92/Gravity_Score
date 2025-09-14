import React, { useState } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { FinancialOverview } from './FinancialOverview'
import { MarketIntelligence } from './MarketIntelligence'
import { DataAnalysis } from './DataAnalysis'
import { DataMode } from '../types'

export const MarketDashboard: React.FC = () => {
  const [dataMode, setDataMode] = useState<DataMode>('ecos')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleModeChange = (mode: DataMode) => {
    setDataMode(mode)
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
          <FinancialOverview dataMode={dataMode} />
          <MarketIntelligence dataMode={dataMode} />
          <DataAnalysis dataMode={dataMode} />
        </main>
      </div>
    </div>
  )
}
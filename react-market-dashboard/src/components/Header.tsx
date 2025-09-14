import React from 'react'
import { Bell, Menu } from 'lucide-react'
import { DataMode } from '../types'

interface HeaderProps {
  dataMode: DataMode
  onModeChange: (mode: DataMode) => void
  onMenuClick: () => void
}

export const Header: React.FC<HeaderProps> = ({ dataMode, onModeChange, onMenuClick }) => {
  return (
    <header className="bg-dark-card border-b border-dark-border px-4 lg:px-6 py-4 sticky top-0 z-30">
      <div className="flex items-center justify-between">
        {/* Left side */}
        <div className="flex items-center gap-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 text-dark-muted hover:text-dark-text transition-colors"
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>
          
          <div>
            <h1 className="text-xl lg:text-2xl font-semibold text-dark-text">
              Market Dashboard
            </h1>
            <p className="text-sm text-dark-muted hidden sm:block">
              Professional athlete brand performance and financial evaluation
            </p>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3 lg:gap-4">
          {/* Status Chips */}
          <div className="hidden sm:flex items-center gap-2 lg:gap-3">
            <span className="px-3 py-1 bg-green-900 text-success border border-success rounded-full text-xs font-semibold uppercase">
              ● Market Open
            </span>
            <span className="px-3 py-1 bg-blue-900 text-dark-accent border border-dark-accent rounded-full text-xs font-semibold uppercase">
              Data Sync: Live
            </span>
          </div>

          {/* Bell Icon */}
          <button className="p-2 text-dark-muted hover:text-dark-text transition-colors">
            <Bell size={18} />
          </button>

          {/* Global ECOS↔NFL Toggle */}
          <div className="flex items-center bg-dark-border rounded-full p-1">
            <button
              onClick={() => onModeChange('ecos')}
              className={`px-3 lg:px-4 py-2 rounded-full text-xs font-semibold uppercase transition-all ${
                dataMode === 'ecos'
                  ? 'bg-dark-accent text-dark-bg'
                  : 'text-dark-muted hover:text-dark-text'
              }`}
              data-testid="toggle-ecos"
            >
              ECOS
            </button>
            <button
              onClick={() => onModeChange('nfl')}
              className={`px-3 lg:px-4 py-2 rounded-full text-xs font-semibold uppercase transition-all ${
                dataMode === 'nfl'
                  ? 'bg-dark-accent text-dark-bg'
                  : 'text-dark-muted hover:text-dark-text'
              }`}
              data-testid="toggle-nfl"
            >
              NFL
            </button>
          </div>
        </div>
      </div>
      
      {/* Mobile Status Chips */}
      <div className="sm:hidden flex items-center gap-2 mt-3">
        <span className="px-2 py-1 bg-green-900 text-success border border-success rounded-full text-xs font-semibold uppercase">
          ● Market Open
        </span>
        <span className="px-2 py-1 bg-blue-900 text-dark-accent border border-dark-accent rounded-full text-xs font-semibold uppercase">
          Live
        </span>
      </div>
    </header>
  )
}
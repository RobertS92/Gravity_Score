import React from 'react'
import { 
  TrendingUp, 
  BarChart3, 
  Users, 
  Search, 
  PieChart, 
  Server, 
  Settings,
  X
} from 'lucide-react'

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

const navigationItems = [
  { icon: TrendingUp, label: 'Dashboard', href: '#', active: true },
  { icon: BarChart3, label: 'Market Data', href: '#' },
  { icon: Users, label: 'Players', href: '#' },
  { icon: Search, label: 'Search', href: '#' },
  { icon: PieChart, label: 'Analytics', href: '#' },
]

const systemItems = [
  { icon: Server, label: 'System Status', href: '#' },
  { icon: Settings, label: 'Settings', href: '#' },
]

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  return (
    <>
      {/* Sidebar */}
      <aside 
        className={`
          fixed inset-y-0 left-0 z-50 w-60 bg-dark-card border-r border-dark-border transform transition-transform duration-300 ease-in-out
          lg:translate-x-0 lg:static lg:inset-0
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <div className="flex flex-col h-full">
          {/* Mobile Header */}
          <div className="lg:hidden flex items-center justify-between p-4 border-b border-dark-border">
            <span className="font-semibold text-dark-text">Menu</span>
            <button
              onClick={onClose}
              className="p-2 text-dark-muted hover:text-dark-text transition-colors"
              aria-label="Close menu"
            >
              <X size={20} />
            </button>
          </div>

          {/* Navigation Content */}
          <div className="flex-1 py-6 lg:py-8">
            {/* Athlete Analytics Section */}
            <div className="mb-8">
              <h3 className="px-6 mb-3 text-xs font-semibold text-dark-muted uppercase tracking-wider">
                Athlete Analytics
              </h3>
              <nav className="space-y-1">
                {navigationItems.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    className={`
                      flex items-center gap-3 px-6 py-2.5 text-sm font-medium transition-colors
                      ${item.active 
                        ? 'bg-dark-border text-dark-text' 
                        : 'text-dark-muted hover:text-dark-text hover:bg-dark-border'
                      }
                    `}
                    data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                  >
                    <item.icon size={16} />
                    <span>{item.label}</span>
                  </a>
                ))}
              </nav>
            </div>

            {/* System Section */}
            <div>
              <h3 className="px-6 mb-3 text-xs font-semibold text-dark-muted uppercase tracking-wider">
                System
              </h3>
              <nav className="space-y-1">
                {systemItems.map((item) => (
                  <a
                    key={item.label}
                    href={item.href}
                    className="flex items-center gap-3 px-6 py-2.5 text-sm font-medium text-dark-muted hover:text-dark-text hover:bg-dark-border transition-colors"
                    data-testid={`nav-${item.label.toLowerCase().replace(' ', '-')}`}
                  >
                    <item.icon size={16} />
                    <span>{item.label}</span>
                  </a>
                ))}
              </nav>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
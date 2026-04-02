import type { View } from '../hooks/useTerminalState'

interface SidebarProps {
  watchlist: { athletes?: unknown[] }
  alerts: { unread?: number }
  onSetView: (v: View) => void
  activeView: View
}

export function Sidebar({ watchlist, alerts, onSetView, activeView }: SidebarProps) {
  const wl = watchlist.athletes?.length ?? 0

  const nav = (view: View, label: string) => (
    <button
      type="button"
      key={view}
      onClick={() => onSetView(view)}
      className={`w-full text-left px-3 py-2 text-xs rounded border mb-1 ${
        activeView === view
          ? 'bg-[#1A2433] border-[#6EA8FE] text-[#6EA8FE]'
          : 'border-transparent text-[#94A3B8] hover:bg-[#121821]'
      }`}
    >
      {label}
    </button>
  )

  return (
    <aside className="w-52 shrink-0 bg-[#121821] border-r border-[#202938] flex flex-col p-2">
      <div className="text-[10px] uppercase tracking-wider text-[#4A5568] mb-2 px-2">
        Navigation
      </div>
      {nav('leaderboard', 'Leaderboard')}
      {nav('watchlist', `Watchlist (${wl})`)}
      {nav('alerts', `Alerts (${alerts.unread ?? 0})`)}

      <div className="text-[10px] uppercase tracking-wider text-[#4A5568] mt-4 mb-2 px-2">
        API
      </div>
      <p className="text-[10px] text-[#4A5568] px-2 leading-relaxed">
        Set <code className="text-[#6EA8FE]">VITE_API_URL</code> to your FastAPI host.
      </p>
    </aside>
  )
}

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MainPanel } from './components/MainPanel'
import { QueryBar } from './components/QueryBar'
import { Sidebar } from './components/Sidebar'
import { useTerminalState } from './hooks/useTerminalState'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <GravityTerminal />
    </QueryClientProvider>
  )
}

function GravityTerminal() {
  const {
    activeView,
    setActiveView,
    selectedAthlete,
    setSelectedAthlete,
    queryResult,
    isQuerying,
    submitQuery,
    watchlist,
    alerts,
  } = useTerminalState()

  return (
    <div className="h-screen bg-[#0B0F14] text-[#E6EDF3] flex flex-col overflow-hidden font-mono">
      <div className="h-10 bg-[#121821] border-b border-[#202938] flex items-center px-4 gap-3 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#22C55E]" />
          <span className="text-xs font-semibold tracking-widest text-[#22C55E]">
            GRAVITY
          </span>
          <span className="text-xs text-[#94A3B8]">NIL Intelligence Terminal</span>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-4 text-xs text-[#94A3B8]">
          <span>{new Date().toLocaleTimeString()}</span>
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" />
            <span>LIVE</span>
          </div>
          {alerts.unread > 0 && (
            <span className="bg-[#D85A30] text-white px-2 py-0.5 rounded text-xs">
              {alerts.unread} ALERTS
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          watchlist={watchlist}
          alerts={alerts}
          onSetView={setActiveView}
          activeView={activeView}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <MainPanel
            view={activeView}
            selectedAthlete={selectedAthlete}
            queryResult={queryResult}
            onSelectAthlete={setSelectedAthlete}
            onSetView={setActiveView}
            isQuerying={isQuerying}
          />
          <QueryBar onSubmit={submitQuery} isQuerying={isQuerying} />
        </div>
      </div>
    </div>
  )
}

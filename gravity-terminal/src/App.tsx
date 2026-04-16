import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { Shell } from './components/layout/Shell'
import { BrandMatchView } from './components/views/BrandMatchView'
import { CscReportsView } from './components/views/CscReportsView'
import { GravityAiView } from './components/views/GravityAiView'
import { LoginView } from './components/views/LoginView'
import { MarketScanView } from './components/views/MarketScanView'
import { MonitoringView } from './components/views/MonitoringView'
import { NilIntelligenceView } from './components/views/NilIntelligenceView'
import { RosterBuilderView } from './components/views/RosterBuilderView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginView />} />

        {/* Protected — everything inside Shell */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Shell />}>
            <Route path="/" element={<NilIntelligenceView />} />
            <Route path="/csc" element={<CscReportsView />} />
            <Route path="/brand-match" element={<BrandMatchView />} />
            <Route path="/monitoring" element={<MonitoringView />} />
            <Route path="/market-scan" element={<MarketScanView />} />
            <Route path="/roster" element={<RosterBuilderView />} />
            <Route path="/gravity-ai" element={<GravityAiView />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { RequireOnboardingComplete } from './components/layout/RequireOnboardingComplete'
import { Shell } from './components/layout/Shell'
import { BrandMatchView } from './components/views/BrandMatchView'
import { CapDashboardView } from './components/views/CapDashboardView'
import { CapScenariosView } from './components/views/CapScenariosView'
import { CapSchoolDataView } from './components/views/CapSchoolDataView'
import { CscReportsView } from './components/views/CscReportsView'
import { GravityAiView } from './components/views/GravityAiView'
import { LoginView } from './components/views/LoginView'
import { MarketScanView } from './components/views/MarketScanView'
import { MonitoringView } from './components/views/MonitoringView'
import { OperationsDashboardView } from './components/views/OperationsDashboardView'
import { NilIntelligenceView } from './components/views/NilIntelligenceView'
import { OnboardingView } from './components/views/OnboardingView'
import { SettingsView } from './components/views/SettingsView'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginView />} />

        {/* Protected: onboarding is full-screen without Shell */}
        <Route element={<ProtectedRoute />}>
          <Route path="/onboarding" element={<OnboardingView />} />
          <Route element={<RequireOnboardingComplete />}>
            <Route element={<Shell />}>
              <Route path="/" element={<NilIntelligenceView />} />
              <Route path="/csc" element={<CscReportsView />} />
              <Route path="/brand-match" element={<BrandMatchView />} />
              <Route path="/monitoring" element={<MonitoringView />} />
              <Route path="/data-pipeline" element={<OperationsDashboardView />} />
              <Route path="/market-scan" element={<MarketScanView />} />
              <Route path="/cap" element={<CapDashboardView />} />
              <Route path="/cap/scenarios" element={<CapScenariosView />} />
              <Route path="/cap/school-data" element={<CapSchoolDataView />} />
              <Route path="/roster" element={<Navigate to="/cap/scenarios" replace />} />
              <Route path="/gravity-ai" element={<GravityAiView />} />
              <Route path="/settings" element={<SettingsView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

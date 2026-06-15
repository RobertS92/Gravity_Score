import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { RequireOnboardingComplete } from './components/layout/RequireOnboardingComplete'
import { Shell } from './components/layout/Shell'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { BrandMatchView } from './components/views/BrandMatchView'
import { CapAdminRollupView } from './components/views/CapAdminRollupView'
import { CapAlertsCenterView } from './components/views/CapAlertsCenterView'
import { CapAllocationView } from './components/views/CapAllocationView'
import { CapAuditLogView } from './components/views/CapAuditLogView'
import { CapCashFlowView } from './components/views/CapCashFlowView'
import { CapDashboardView } from './components/views/CapDashboardView'
import { CapDealDeskView } from './components/views/CapDealDeskView'
import { CapLayout } from './components/views/CapLayout'
import { CapOutlookView } from './components/views/CapOutlookView'
import { CapRosterView } from './components/views/CapRosterView'
import { CapScenariosView } from './components/views/CapScenariosView'
import { CapWorkflowView } from './components/views/CapWorkflowView'
import { CscReportsView } from './components/views/CscReportsView'
import { GravityAiView } from './components/views/GravityAiView'
import { LiveFeedView } from './components/views/LiveFeedView'
import { LoginView } from './components/views/LoginView'
import { MarketScanView } from './components/views/MarketScanView'
import { MonitoringView } from './components/views/MonitoringView'
import { OperationsDashboardView } from './components/views/OperationsDashboardView'
import { NilIntelligenceView } from './components/views/NilIntelligenceView'
import { OnboardingView } from './components/views/OnboardingView'
import { ForgotPasswordView } from './components/views/ForgotPasswordView'
import { ResetPasswordView } from './components/views/ResetPasswordView'
import { SettingsView } from './components/views/SettingsView'

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary name="App">
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginView />} />
        <Route path="/forgot-password" element={<ForgotPasswordView />} />
        <Route path="/reset-password" element={<ResetPasswordView />} />
        {/* Onboarding is public so new users can register here. Step 1 of
            OnboardingView creates the account and stores the JWT; step 2+
            runs under that token and calls POST /v1/auth/onboarding. */}
        <Route path="/onboarding" element={<OnboardingView />} />

        {/* Protected: everything inside Shell requires an authenticated session. */}
        <Route element={<ProtectedRoute />}>
          <Route element={<RequireOnboardingComplete />}>
            <Route element={<Shell />}>
              <Route path="/" element={<NilIntelligenceView />} />
              <Route path="/csc" element={<CscReportsView />} />
              <Route path="/brand-match" element={<BrandMatchView />} />
              <Route path="/monitoring" element={<MonitoringView />} />
              <Route path="/data-pipeline" element={<OperationsDashboardView />} />
              <Route path="/market-scan" element={<MarketScanView />} />
              <Route path="/cap" element={<CapLayout />}>
                <Route index element={<CapDashboardView />} />
                <Route path="roster" element={<CapRosterView />} />
                <Route path="scenarios" element={<CapScenariosView />} />
                <Route path="outlook" element={<CapOutlookView />} />
                <Route path="cash-flow" element={<CapCashFlowView />} />
                <Route path="deal-desk" element={<CapDealDeskView />} />
                <Route path="admin-rollup" element={<CapAdminRollupView />} />
                <Route path="allocation" element={<CapAllocationView />} />
                <Route path="workflow" element={<CapWorkflowView />} />
                <Route path="audit-log" element={<CapAuditLogView />} />
                <Route path="alerts" element={<CapAlertsCenterView />} />
              </Route>
              <Route path="/gravity-ai" element={<GravityAiView />} />
              <Route path="/feed" element={<LiveFeedView />} />
              <Route path="/settings" element={<SettingsView />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Route>
        </Route>
      </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/globals.css'
import App from './App.tsx'
import { useAuthStore } from './stores/authStore'
import { getRawViteApiUrl } from './lib/apiBaseUrl'

function preflightConfigError(): string | null {
  const useMocks = import.meta.env.VITE_USE_MOCKS === 'true'
  if (!useMocks) {
    const api = (getRawViteApiUrl() || '').trim()
    if (!api) return 'Configuration error: VITE_API_URL is required when VITE_USE_MOCKS=false.'
  }
  // Production must use proxy-only AI traffic.
  if (!import.meta.env.DEV) {
    if (import.meta.env.VITE_AGENT_USE_PROXY !== 'true') {
      return 'Configuration error: production requires VITE_AGENT_USE_PROXY=true.'
    }
  }
  return null
}

const rootEl = document.getElementById('root')!
const cfgError = preflightConfigError()

if (!cfgError) {
  // Eagerly hydrate auth before first render — eliminates the ProtectedRoute null flash.
  // hydrate() is synchronous when no localStorage token (just reads ENV_USER).
  void useAuthStore.getState().hydrate()
  createRoot(rootEl).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
} else {
  createRoot(rootEl).render(
    <StrictMode>
      <div style={{ padding: 24, fontFamily: 'monospace', color: '#ff8b8b' }}>{cfgError}</div>
    </StrictMode>,
  )
}

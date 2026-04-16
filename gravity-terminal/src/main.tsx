import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/globals.css'
import App from './App.tsx'
import { useAuthStore } from './stores/authStore'

// Eagerly hydrate auth before first render — eliminates the ProtectedRoute null flash.
// hydrate() is synchronous when no localStorage token (just reads ENV_USER).
void useAuthStore.getState().hydrate()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_AGENT_USE_PROXY?: string
  readonly VITE_ANTHROPIC_API_KEY?: string
  readonly VITE_USE_MOCKS?: string
  readonly VITE_TERMINAL_USER_ID?: string
  readonly VITE_API_BEARER_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

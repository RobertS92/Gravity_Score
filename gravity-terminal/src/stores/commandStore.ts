import { create } from 'zustand'

export type CommandStore = {
  isProcessing: boolean
  lastCommand: string
  lastResponse: string | null
  error: string | null
  setProcessing: (v: boolean) => void
  setLast: (cmd: string, res: string | null, err: string | null) => void
  clearError: () => void
  clearLastOutput: () => void
}

export const useCommandStore = create<CommandStore>((set) => ({
  isProcessing: false,
  lastCommand: '',
  lastResponse: null,
  error: null,
  setProcessing: (v) => set({ isProcessing: v }),
  setLast: (cmd, res, err) =>
    set({ lastCommand: cmd, lastResponse: res, error: err ?? null }),
  clearError: () => set({ error: null }),
  clearLastOutput: () => set({ lastResponse: null }),
}))

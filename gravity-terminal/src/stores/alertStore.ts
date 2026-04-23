import { create } from 'zustand'
import { getAlerts } from '../api/alerts'
import type { AlertRecord } from '../types/alerts'
import { getTerminalUserId } from './authStore'
import { usePreferencesStore } from './preferencesStore'

let pollTimer: ReturnType<typeof setInterval> | null = null
let alertsBootstrapped = false

export type AlertStore = {
  alerts: AlertRecord[]
  unreadCount: number
  badgePulse: boolean
  readIds: Set<string>
  loadAlerts: () => Promise<void>
  markAllRead: () => void
  markRead: (id: string) => void
}

export const useAlertStore = create<AlertStore>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  badgePulse: false,
  readIds: new Set(),

  loadAlerts: async () => {
    try {
      const sportsCsv = usePreferencesStore.getState().activeSports.join(',')
      const alerts = await getAlerts(getTerminalUserId(), sportsCsv || null)
      const { readIds } = get()
      const unread = alerts.filter((a) => !readIds.has(a.alert_id)).length
      const prevUnread = get().unreadCount
      const pulse = alertsBootstrapped && unread > prevUnread
      alertsBootstrapped = true
      set({
        alerts,
        unreadCount: unread,
        badgePulse: pulse,
      })
      if (pulse) {
        window.setTimeout(() => set({ badgePulse: false }), 400)
      }
    } catch {
      /* ignore */
    }
  },

  markAllRead: () => {
    const all = new Set(get().alerts.map((a) => a.alert_id))
    set({ readIds: all, unreadCount: 0 })
  },

  markRead: (id: string) => {
    const readIds = new Set(get().readIds)
    readIds.add(id)
    const unread = get().alerts.filter((a) => !readIds.has(a.alert_id)).length
    set({ readIds, unreadCount: unread })
  },
}))

export function startAlertPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(() => {
    void useAlertStore.getState().loadAlerts()
  }, 60_000)
}

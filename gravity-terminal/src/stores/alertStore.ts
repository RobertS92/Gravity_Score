import { create } from 'zustand'
import { getAlerts, isPersistedAlertId, markAlertsRead } from '../api/alerts'
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
  isLoading: boolean
  error: string | null
  loadAlerts: () => Promise<void>
  markAllRead: () => void
  markRead: (id: string) => void
}

function unreadFor(alerts: AlertRecord[], readIds: Set<string>) {
  return alerts.filter((a) => !a.read && !readIds.has(a.alert_id)).length
}

export const useAlertStore = create<AlertStore>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  badgePulse: false,
  readIds: new Set(),
  isLoading: false,
  error: null,

  loadAlerts: async () => {
    const userId = getTerminalUserId()
    if (!userId) {
      set({ alerts: [], unreadCount: 0, isLoading: false, error: null })
      return
    }
    set({ isLoading: true, error: null })
    try {
      const sportsCsv = usePreferencesStore.getState().activeSports.join(',')
      const alerts = await getAlerts(userId, sportsCsv || null)
      const { readIds } = get()
      const unread = unreadFor(alerts, readIds)
      const prevUnread = get().unreadCount
      const pulse = alertsBootstrapped && unread > prevUnread
      alertsBootstrapped = true
      set({
        alerts,
        unreadCount: unread,
        badgePulse: pulse,
        isLoading: false,
        error: null,
      })
      if (pulse) {
        window.setTimeout(() => set({ badgePulse: false }), 400)
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      set({ isLoading: false, error: msg })
      if (msg.includes('401')) {
        stopAlertPolling()
      }
    }
  },

  markAllRead: () => {
    const all = new Set(get().alerts.map((a) => a.alert_id))
    set({
      readIds: all,
      unreadCount: 0,
      alerts: get().alerts.map((a) => ({ ...a, read: true })),
    })
    void markAlertsRead({ mark_all: true }).catch(() => undefined)
  },

  markRead: (id: string) => {
    const readIds = new Set(get().readIds)
    readIds.add(id)
    const alerts = get().alerts.map((a) => (a.alert_id === id ? { ...a, read: true } : a))
    set({ readIds, alerts, unreadCount: unreadFor(alerts, readIds) })
    if (isPersistedAlertId(id)) {
      void markAlertsRead({ alert_ids: [id] }).catch(() => undefined)
    }
  },
}))

export function startAlertPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(() => {
    void useAlertStore.getState().loadAlerts()
  }, 60_000)
}

export function stopAlertPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

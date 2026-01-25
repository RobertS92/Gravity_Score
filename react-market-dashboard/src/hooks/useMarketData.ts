import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import {
  DataMode,
  FinancialOverview,
  TopPerformer,
  MarketActivity,
  QuickStats,
  SystemStatus,
  type PlayersResponse,
} from '../types'
import {
  getFallbackFinancialOverview,
  getFallbackMarketActivity,
  getFallbackPlayers,
  getFallbackQuickStats,
  getFallbackSystemStatus,
  getFallbackTopPerformers,
} from '../mocks/marketData'

const resolveBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL?.trim()
  if (envUrl && envUrl.length > 0) {
    return envUrl.replace(/\/+$/, '')
  }

  if (typeof window !== 'undefined' && window.location) {
    return `${window.location.origin}/api`
  }

  return 'http://localhost:5000/api'
}

const API_BASE_URL = resolveBaseUrl()

const api = axios.create({
  baseURL: API_BASE_URL,
})

const useFallback = <T>(error: unknown, fallback: T): T => {
  if (import.meta.env.DEV) {
    console.warn('[useMarketData] Falling back to mock data:', error)
  }
  return fallback
}

export const useFinancialOverview = (mode: DataMode) => {
  return useQuery({
    queryKey: ['financial-overview', mode],
    queryFn: async (): Promise<FinancialOverview> => {
      try {
        const response = await api.get(`/financial-overview?mode=${mode}`)
        return response.data
      } catch (error) {
        return useFallback(error, getFallbackFinancialOverview(mode))
      }
    },
  })
}

export const useTopPerformers = (mode: DataMode) => {
  return useQuery({
    queryKey: ['top-performers', mode],
    queryFn: async (): Promise<TopPerformer[]> => {
      try {
        const response = await api.get(`/top-performers?mode=${mode}`)
        return response.data
      } catch (error) {
        return useFallback(error, getFallbackTopPerformers(mode))
      }
    },
  })
}

export const useMarketActivity = (mode: DataMode) => {
  return useQuery({
    queryKey: ['market-activity', mode],
    queryFn: async (): Promise<MarketActivity[]> => {
      try {
        const response = await api.get(`/market-activity?mode=${mode}`)
        return response.data
      } catch (error) {
        return useFallback(error, getFallbackMarketActivity(mode))
      }
    },
  })
}

export const useQuickStats = (mode: DataMode) => {
  return useQuery({
    queryKey: ['quick-stats', mode],
    queryFn: async (): Promise<QuickStats> => {
      try {
        const response = await api.get(`/quick-stats?mode=${mode}`)
        return response.data
      } catch (error) {
        return useFallback(error, getFallbackQuickStats(mode))
      }
    },
  })
}

export const useSystemStatus = () => {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: async (): Promise<SystemStatus> => {
      try {
        const response = await api.get('/system-status')
        return response.data
      } catch (error) {
        return useFallback(error, getFallbackSystemStatus())
      }
    },
    refetchInterval: 60000, // Refetch every minute
  })
}

export const usePlayers = (mode: DataMode, limit = 20) => {
  return useQuery({
    queryKey: ['players', mode, limit],
    queryFn: async (): Promise<PlayersResponse> => {
      try {
        const response = await api.get(`/players?mode=${mode}&limit=${limit}`)
        return response.data
      } catch (error) {
        return useFallback(error, getFallbackPlayers(mode))
      }
    },
  })
}

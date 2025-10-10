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

export const useFinancialOverview = (mode: DataMode) => {
  return useQuery({
    queryKey: ['financial-overview', mode],
    queryFn: async (): Promise<FinancialOverview> => {
      const response = await api.get(`/financial-overview?mode=${mode}`)
      return response.data
    },
  })
}

export const useTopPerformers = (mode: DataMode) => {
  return useQuery({
    queryKey: ['top-performers', mode],
    queryFn: async (): Promise<TopPerformer[]> => {
      const response = await api.get(`/top-performers?mode=${mode}`)
      return response.data
    },
  })
}

export const useMarketActivity = (mode: DataMode) => {
  return useQuery({
    queryKey: ['market-activity', mode],
    queryFn: async (): Promise<MarketActivity[]> => {
      const response = await api.get(`/market-activity?mode=${mode}`)
      return response.data
    },
  })
}

export const useQuickStats = (mode: DataMode) => {
  return useQuery({
    queryKey: ['quick-stats', mode],
    queryFn: async (): Promise<QuickStats> => {
      const response = await api.get(`/quick-stats?mode=${mode}`)
      return response.data
    },
  })
}

export const useSystemStatus = () => {
  return useQuery({
    queryKey: ['system-status'],
    queryFn: async (): Promise<SystemStatus> => {
      const response = await api.get('/system-status')
      return response.data
    },
    refetchInterval: 60000, // Refetch every minute
  })
}

export const usePlayers = (mode: DataMode, limit = 20) => {
  return useQuery({
    queryKey: ['players', mode, limit],
    queryFn: async (): Promise<PlayersResponse> => {
      const response = await api.get(`/players?mode=${mode}&limit=${limit}`)
      return response.data
    },
  })
}

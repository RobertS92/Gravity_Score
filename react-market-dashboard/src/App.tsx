// React imports handled by components
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MarketDashboard } from './components/MarketDashboard'
import './App.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30 seconds
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-dark-bg text-dark-text">
        <MarketDashboard />
      </div>
    </QueryClientProvider>
  )
}

export default App
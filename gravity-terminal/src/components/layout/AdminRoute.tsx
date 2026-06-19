import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'

export function AdminRoute() {
  const role = useAuthStore((s) => s.role)

  if (role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { readClaims } from '../auth/token'

export default function ProtectedRoute() {
  const { token } = useAuth()
  const location = useLocation()
  return readClaims(token)
    ? <Outlet />
    : <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />
}

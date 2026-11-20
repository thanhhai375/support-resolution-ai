
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { readClaims } from '../auth/token'

export default function ProtectedRoute() {
  const location = useLocation()
  const { token, role } = useAuth()

  const claims = readClaims(token)

  // Kiểm tra JWT và vai trò đã được AuthProvider xác thực
  if (!claims || !role) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location.pathname + location.search + location.hash,
        }}
      />
    )
  }

  return <Outlet />
}


import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import type { UserRole } from '../auth/token'

interface RequireRoleProps {
  allowedRoles: UserRole[]
  children: ReactNode
}

export default function RequireRole({
  allowedRoles,
  children,
}: RequireRoleProps) {
  const { role } = useAuth()

  // Không có role hoặc role không được phép
  if (!role || !allowedRoles.includes(role)) {
    return (
      <Navigate
        to="/dashboard"
        replace
        state={{ roleDenied: true }}
      />
    )
  }

  return <>{children}</>
}

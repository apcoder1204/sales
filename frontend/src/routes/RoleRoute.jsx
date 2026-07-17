import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '@hooks/useAuth'
import { hasPermission } from '@utils/permissions'

export default function RoleRoute({ children, permissions = [], any = false }) {
  const { user } = useAuth()

  const allowed = any
    ? permissions.some((p) => hasPermission(user, p))
    : permissions.every((p) => hasPermission(user, p))

  if (!allowed) return <Navigate to="/dashibodi" replace />
  return children
}

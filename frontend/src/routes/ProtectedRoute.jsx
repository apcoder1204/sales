import React from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@hooks/useAuth'
import Spinner from '@components/feedback/Spinner'

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-bg">
        <Spinner size="lg" />
      </div>
    )
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />
}

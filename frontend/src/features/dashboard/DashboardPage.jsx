import React from 'react'
import { useAuth } from '@hooks/useAuth'
import SuperAdminDash from './SuperAdminDash'
import AdminDash from './AdminDash'
import ManagerDash from './ManagerDash'
import StoreKeeperDash from './StoreKeeperDash'
import CashierDash from './CashierDash'

export default function DashboardPage() {
  const { user } = useAuth()

  switch (user?.role) {
    case 'super_admin': return <SuperAdminDash />
    case 'admin': return <AdminDash />
    case 'general_manager': return <ManagerDash />
    case 'store_keeper': return <StoreKeeperDash />
    case 'cashier': return <CashierDash />
    default: return null
  }
}

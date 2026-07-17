import { useAuth } from './useAuth'
import { hasPermission, isGlobalRole } from '@utils/permissions'

export function usePermission() {
  const { user } = useAuth()

  return {
    can: (permission) => hasPermission(user, permission),
    isGlobal: isGlobalRole(user),
    role: user?.role,
  }
}

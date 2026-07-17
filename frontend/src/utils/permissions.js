export const ROLES = {
  SUPER_ADMIN: 'super_admin',
  ADMIN: 'admin',
  STORE_KEEPER: 'store_keeper',
  GENERAL_MANAGER: 'general_manager',
  CASHIER: 'cashier',
}

export const GLOBAL_ROLES = [ROLES.SUPER_ADMIN, ROLES.ADMIN, ROLES.GENERAL_MANAGER]

export const PERMISSION_MAP = {
  super_admin: [
    'products.read', 'products.write', 'products.delete', 'products.cost',
    'inventory.read', 'inventory.adjust',
    'sales.read', 'sales.create', 'sales.void',
    'transfers.read', 'transfers.request', 'transfers.approve', 'transfers.execute',
    'reports.sales', 'reports.inventory', 'reports.branch', 'reports.cashier',
    'audit.read',
    'users.read', 'users.write',
    'branches.read',
    'closing.close', 'closing.view', 'closing.reopen', 'reports.closing',
  ],
  admin: [
    'products.read', 'products.write', 'products.delete', 'products.cost',
    'inventory.read', 'inventory.adjust',
    'sales.read', 'sales.create', 'sales.void',
    'transfers.read', 'transfers.request', 'transfers.approve', 'transfers.execute',
    'reports.sales', 'reports.inventory', 'reports.branch', 'reports.cashier',
    'audit.read',
    'users.read', 'users.write',
    'branches.read',
    'closing.close', 'closing.view', 'closing.reopen', 'reports.closing',
  ],
  general_manager: [
    'products.read', 'products.cost',
    'inventory.read',
    'sales.read',
    'transfers.read', 'transfers.request', 'transfers.approve', 'transfers.execute',
    'reports.sales', 'reports.inventory', 'reports.branch', 'reports.cashier',
    'reports.closing',
    'audit.read',
    'branches.read',
    'closing.view',
  ],
  store_keeper: [
    'products.read', 'products.cost',
    'inventory.read', 'inventory.adjust',
    'transfers.read', 'transfers.request', 'transfers.execute',
    'reports.inventory',
    'audit.read',
    'branches.read',
  ],
  cashier: [
    'products.read',
    'inventory.read',
    'sales.read', 'sales.create',
    'transfers.read', 'transfers.request',
    'closing.close', 'closing.view',
  ],
}

export const hasPermission = (user, permission) => {
  if (!user?.role) return false
  return PERMISSION_MAP[user.role]?.includes(permission) ?? false
}

export const isGlobalRole = (user) => {
  return user?.role && GLOBAL_ROLES.includes(user.role)
}

export const canViewAllBranches = (user) => isGlobalRole(user)

export const canApproveTransfer = (user) => {
  return hasPermission(user, 'transfers.approve')
}

export const canExecuteTransfer = (user) => {
  return hasPermission(user, 'transfers.execute')
}

export const canManageUsers = (user) => {
  return hasPermission(user, 'users.write')
}

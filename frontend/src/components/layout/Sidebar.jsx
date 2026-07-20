import React, { useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Package, ShoppingCart, ArrowLeftRight,
  BarChart3, ScrollText, Users, LogOut, ChevronLeft, ChevronDown, Zap,
  List, Tag, RefreshCw, Activity, Lock,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuth } from '@hooks/useAuth'
import { usePermission } from '@hooks/usePermission'
import { useToast } from '@hooks/useToast'
import Avatar from '@components/ui/Avatar'
import SW from '@constants/sw'

const bidhaaChildren = [
  { to: '/bidhaa', label: SW.nav.orodhaYaBidhaa, icon: List, permission: 'products.read', exact: true },
  { to: '/bidhaa/jamii', label: SW.nav.jamiiYaBidhaa, icon: Tag, permission: 'products.read' },
  { to: '/bidhaa/marekebisho', label: SW.nav.marekebishoYaBidhaa, icon: RefreshCw, permission: 'inventory.adjust' },
  { to: '/hifadhi/harakati', label: 'Harakati', icon: Activity, permission: 'inventory.read' },
]

const topNavItems = [
  { to: '/dashibodi', icon: LayoutDashboard, label: SW.nav.dashibodi, permission: null },
]
const bottomNavItems = [
  { to: '/mauzo', icon: ShoppingCart, label: SW.nav.mauzo, permission: 'sales.create' },
  { to: '/uhamisho', icon: ArrowLeftRight, label: SW.nav.uhamisho, permission: 'transfers.read' },
  { to: '/ufungaji', icon: Lock, label: SW.nav.ufungaji, permission: 'closing.view' },
  { to: '/ripoti', icon: BarChart3, label: SW.nav.ripoti, permission: ['reports.sales', 'reports.inventory', 'reports.closing'] },
  { to: '/kumbukumbu', icon: ScrollText, label: SW.nav.kumbukumbu, permission: 'audit.read' },
  { to: '/watumiaji', icon: Users, label: SW.nav.watumiaji, permission: 'users.read' },
]

export default function Sidebar({ open, onToggle }) {
  const { user, logout } = useAuth()
  const { can } = usePermission()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [bidhaaOpen, setBidhaaOpen] = useState(location.pathname.startsWith('/bidhaa'))

  const handleLogout = async () => {
    await logout()
    navigate('/login')
    toast.info('Umefanikiwa kutoka')
  }

  const showBidhaa = bidhaaChildren.some((c) => !c.permission || can(c.permission))
  const isBidhaaActive = location.pathname.startsWith('/bidhaa')

  const renderNavItem = (item) => {
    const hasAccess = !item.permission
      || (Array.isArray(item.permission) ? item.permission.some(can) : can(item.permission))
    if (!hasAccess) return null
    return (
      <NavLink
        key={item.to}
        to={item.to}
        className={({ isActive }) =>
          clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-150',
            isActive
              ? 'bg-primary/15 text-primary-light border border-primary/20'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
          )
        }
      >
        {({ isActive }) => (
          <>
            <item.icon size={18} className={clsx('flex-shrink-0', isActive && 'text-primary-light')} />
            <AnimatePresence>
              {open && (
                <motion.span
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 'auto' }}
                  exit={{ opacity: 0, width: 0 }}
                  className="text-sm font-medium truncate"
                >
                  {item.label}
                </motion.span>
              )}
            </AnimatePresence>
          </>
        )}
      </NavLink>
    )
  }

  return (
    <motion.aside
      animate={{ width: open ? 240 : 64 }}
      transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      className="flex flex-col bg-bg-card border-r border-border overflow-hidden flex-shrink-0 relative z-10"
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-border flex-shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-primary flex items-center justify-center flex-shrink-0">
          <Zap size={16} className="text-white" />
        </div>
        <AnimatePresence>
          {open && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="min-w-0">
              <p className="font-bold text-text-primary text-sm leading-tight">DUKANI POS</p>
              <p className="text-text-muted text-[10px] truncate">Mfumo wa Uuzaji</p>
            </motion.div>
          )}
        </AnimatePresence>
        <button
          onClick={onToggle}
          className={clsx(
            'ml-auto text-text-muted hover:text-text-primary transition-colors flex-shrink-0',
            !open && 'absolute right-2 top-5'
          )}
        >
          <motion.span style={{ display: 'inline-flex' }} animate={{ rotate: open ? 0 : 180 }}>
            <ChevronLeft size={18} />
          </motion.span>
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-1 px-2">
        {topNavItems.map(renderNavItem)}

        {/* Bidhaa collapsible group */}
        {showBidhaa && (
          <div>
            {open ? (
              <>
                <button
                  onClick={() => setBidhaaOpen((v) => !v)}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-150',
                    isBidhaaActive
                      ? 'bg-primary/10 text-primary-light'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                  )}
                >
                  <Package size={18} className={clsx('flex-shrink-0', isBidhaaActive && 'text-primary-light')} />
                  <span className="text-sm font-medium truncate flex-1 text-left">{SW.nav.bidhaa}</span>
                  <motion.span
                    style={{ display: 'inline-flex' }}
                    animate={{ rotate: bidhaaOpen ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronDown size={14} />
                  </motion.span>
                </button>

                <AnimatePresence>
                  {bidhaaOpen && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-1 ml-4 pl-3 border-l border-border space-y-1">
                        {bidhaaChildren.map((child) => {
                          if (child.permission && !can(child.permission)) return null
                          return (
                            <NavLink
                              key={child.to}
                              to={child.to}
                              end={child.exact}
                              className={({ isActive }) =>
                                clsx(
                                  'flex items-center gap-2 px-2 py-2 rounded-lg transition-colors duration-150 text-xs',
                                  isActive
                                    ? 'bg-primary/15 text-primary-light border border-primary/20'
                                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                                )
                              }
                            >
                              {({ isActive }) => (
                                <>
                                  <child.icon size={14} className={clsx('flex-shrink-0', isActive && 'text-primary-light')} />
                                  <span className="font-medium truncate">{child.label}</span>
                                </>
                              )}
                            </NavLink>
                          )
                        })}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            ) : (
              <NavLink
                to="/bidhaa"
                className={clsx(
                  'flex items-center justify-center px-3 py-2.5 rounded-lg transition-colors duration-150',
                  isBidhaaActive
                    ? 'bg-primary/15 text-primary-light border border-primary/20'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                )}
              >
                <Package size={18} />
              </NavLink>
            )}
          </div>
        )}

        {bottomNavItems.map(renderNavItem)}
      </nav>

      {/* User */}
      <div className="border-t border-border px-2 py-3 space-y-1 flex-shrink-0">
        <div className={clsx('flex items-center gap-3 px-3 py-2 rounded-lg', open && 'bg-bg-hover')}>
          <Avatar name={user?.full_name || ''} size="sm" className="flex-shrink-0" />
          <AnimatePresence>
            {open && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex-1 min-w-0">
                <p className="text-xs font-medium text-text-primary truncate">{user?.full_name}</p>
                <p className="text-[10px] text-text-muted truncate">{SW.majukumu[user?.role] || user?.role}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-text-secondary hover:text-accent-red hover:bg-accent-red-muted transition-colors"
        >
          <LogOut size={18} className="flex-shrink-0" />
          <AnimatePresence>
            {open && (
              <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-sm">
                {SW.nav.toka}
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>
    </motion.aside>
  )
}

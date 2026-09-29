import React, { useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Package, ShoppingCart, ArrowLeftRight,
  BarChart3, ScrollText, Users, LogOut, ChevronLeft, ChevronDown, Zap,
  List, Tag, RefreshCw, Activity, Lock, Receipt,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuth } from '@hooks/useAuth'
import { usePermission } from '@hooks/usePermission'
import { useToast } from '@hooks/useToast'
import Avatar from '@components/ui/Avatar'
import SW from '@constants/sw'

// Every nav item that isn't the Dashboard (always first, for everyone —
// it's the one page that makes sense as a universal anchor) or the Bidhaa
// group (order controlled separately below, since it's rendered specially).
// Visibility is still decided purely by permission, same as before — this
// map only controls display metadata, never access.
const NAV_ITEMS = {
  mauzo: { to: '/mauzo', icon: ShoppingCart, label: SW.nav.mauzo, permission: 'sales.create' },
  historiaMauzo: { to: '/mauzo/historia', icon: Receipt, label: SW.nav.historiaMauzo, permission: 'sales.read' },
  uhamisho: { to: '/uhamisho', icon: ArrowLeftRight, label: SW.nav.uhamisho, permission: 'transfers.read' },
  ufungaji: { to: '/ufungaji', icon: Lock, label: SW.nav.ufungaji, permission: 'closing.view' },
  ripoti: { to: '/ripoti', icon: BarChart3, label: SW.nav.ripoti, permission: ['reports.sales', 'reports.inventory', 'reports.closing'] },
  kumbukumbu: { to: '/kumbukumbu', icon: ScrollText, label: SW.nav.kumbukumbu, permission: 'audit.read' },
  watumiaji: { to: '/watumiaji', icon: Users, label: SW.nav.watumiaji, permission: 'users.read' },
}

// Order reflects each role's actual day-to-day sequence, not one generic
// list with irrelevant items just hidden — a cashier's whole job is
// selling, so Sales/Sales History/Closing lead; a store_keeper never sells
// anything, so Bidhaa (their stock-management home) and Uhamisho lead
// instead. This is purely presentational — `can()` below is still what
// actually decides whether an item renders at all, exactly as before.
const ROLE_NAV_ORDER = {
  cashier: ['mauzo', 'historiaMauzo', 'ufungaji', 'bidhaa', 'uhamisho', 'ripoti'],
  store_keeper: ['bidhaa', 'uhamisho', 'ripoti', 'kumbukumbu'],
  general_manager: ['uhamisho', 'ripoti', 'ufungaji', 'bidhaa', 'kumbukumbu'],
  admin: ['mauzo', 'historiaMauzo', 'bidhaa', 'uhamisho', 'ufungaji', 'ripoti', 'kumbukumbu', 'watumiaji'],
  super_admin: ['mauzo', 'historiaMauzo', 'bidhaa', 'uhamisho', 'ufungaji', 'ripoti', 'kumbukumbu', 'watumiaji'],
}
const DEFAULT_NAV_ORDER = ['mauzo', 'historiaMauzo', 'bidhaa', 'uhamisho', 'ufungaji', 'ripoti', 'kumbukumbu', 'watumiaji']

export default function Sidebar({ open, onToggle }) {
  const { user, logout } = useAuth()
  const { can, role } = usePermission()
  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const [bidhaaOpen, setBidhaaOpen] = useState(location.pathname.startsWith('/bidhaa'))

  const bidhaaChildren = [
    { to: '/bidhaa', label: SW.nav.orodhaYaBidhaa, icon: List, permission: 'products.read', exact: true },
    { to: '/bidhaa/jamii', label: SW.nav.jamiiYaBidhaa, icon: Tag, permission: 'products.read' },
    { to: '/bidhaa/marekebisho', label: SW.nav.marekebishoYaBidhaa, icon: RefreshCw, permission: 'inventory.adjust' },
    { to: '/hifadhi/harakati', label: SW.nav.harakatiZaBidhaa, icon: Activity, permission: 'inventory.read' },
  ]

  const topNavItems = [
    { to: '/dashibodi', icon: LayoutDashboard, label: SW.nav.dashibodi, permission: null },
  ]
  const navOrder = ROLE_NAV_ORDER[role] || DEFAULT_NAV_ORDER

  const handleLogout = async () => {
    await logout()
    navigate('/login')
    toast.info(SW.mafanikio.umefanikiwaKutoka)
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

  const renderBidhaaGroup = () => {
    if (!showBidhaa) return null
    return (
      <div key="bidhaa">
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
              <p className="font-bold text-text-primary text-sm leading-tight">{SW.appName}</p>
              <p className="text-text-muted text-[10px] truncate">{SW.tagline}</p>
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

      {/* Nav — Dashboard always first, then role-ordered (see ROLE_NAV_ORDER) */}
      <nav className="flex-1 overflow-y-auto py-3 space-y-1 px-2">
        {topNavItems.map(renderNavItem)}
        {navOrder.map((key) => (key === 'bidhaa' ? renderBidhaaGroup() : renderNavItem(NAV_ITEMS[key])))}
      </nav>

      {/* User */}
      <div className="border-t border-border px-2 py-3 space-y-1 flex-shrink-0">
        <button
          onClick={() => navigate('/wasifu')}
          title={SW.nav.wasifu}
          className={clsx(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
            open && 'bg-bg-hover hover:bg-bg-panel'
          )}
        >
          <Avatar name={user?.full_name || ''} size="sm" className="flex-shrink-0" />
          <AnimatePresence>
            {open && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex-1 min-w-0 text-left">
                <p className="text-xs font-medium text-text-primary truncate">{user?.full_name}</p>
                <p className="text-[10px] text-text-muted truncate">{SW.majukumu[user?.role] || user?.role}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </button>
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

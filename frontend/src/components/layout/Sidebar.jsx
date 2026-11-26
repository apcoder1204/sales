import React, { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Package, ShoppingCart, ArrowLeftRight,
  BarChart3, ScrollText, Users, ChevronLeft, ChevronDown, Zap,
  List, Tag, RefreshCw, Activity, Lock, Receipt, Building2, Contact, BookOpen, HandCoins,
} from 'lucide-react'
import { clsx } from 'clsx'
import { usePermission } from '@hooks/usePermission'
import SW from '@constants/sw'

// Every nav item that isn't the Dashboard (always first, for everyone —
// it's the one page that makes sense as a universal anchor) or a group with
// sub-items (Bidhaa, Madeni — see navGroups, rendered by NavGroup).
// Visibility is still decided purely by permission, same as before — this
// map only controls display metadata, never access.
const NAV_ITEMS = {
  mauzo: { to: '/mauzo', icon: ShoppingCart, label: SW.nav.mauzo, permission: 'sales.create' },
  historiaMauzo: { to: '/mauzo/historia', icon: Receipt, label: SW.nav.historiaMauzo, permission: 'sales.read' },
  wateja: { to: '/wateja', icon: Contact, label: SW.nav.wateja, permission: 'customers.read' },
  uhamisho: { to: '/uhamisho', icon: ArrowLeftRight, label: SW.nav.uhamisho, permission: 'transfers.read' },
  ufungaji: { to: '/ufungaji', icon: Lock, label: SW.nav.ufungaji, permission: 'closing.view' },
  ripoti: { to: '/ripoti', icon: BarChart3, label: SW.nav.ripoti, permission: ['reports.sales', 'reports.inventory', 'reports.closing'] },
  kumbukumbu: { to: '/kumbukumbu', icon: ScrollText, label: SW.nav.kumbukumbu, permission: 'audit.read' },
  watumiaji: { to: '/watumiaji', icon: Users, label: SW.nav.watumiaji, permission: 'users.read' },
  matawi: { to: '/matawi', icon: Building2, label: SW.nav.matawi, permission: 'branches.manage' },
}

// Order reflects each role's actual day-to-day sequence, not one generic
// list with irrelevant items just hidden — a cashier's whole job is
// selling, so Sales/Sales History/Closing lead; a store_keeper never sells
// anything, so Bidhaa (their stock-management home) and Uhamisho lead
// instead. This is purely presentational — `can()` below is still what
// actually decides whether an item renders at all, exactly as before.
const ROLE_NAV_ORDER = {
  cashier: ['mauzo', 'historiaMauzo', 'wateja', 'madeni', 'ufungaji', 'bidhaa', 'uhamisho', 'ripoti'],
  store_keeper: ['bidhaa', 'uhamisho', 'ripoti', 'kumbukumbu'],
  general_manager: ['uhamisho', 'ripoti', 'ufungaji', 'wateja', 'madeni', 'bidhaa', 'kumbukumbu'],
  admin: ['mauzo', 'historiaMauzo', 'wateja', 'madeni', 'bidhaa', 'uhamisho', 'ufungaji', 'ripoti', 'kumbukumbu', 'watumiaji', 'matawi'],
  super_admin: ['mauzo', 'historiaMauzo', 'wateja', 'madeni', 'bidhaa', 'uhamisho', 'ufungaji', 'ripoti', 'kumbukumbu', 'watumiaji', 'matawi'],
}
const DEFAULT_NAV_ORDER = ['mauzo', 'historiaMauzo', 'wateja', 'madeni', 'bidhaa', 'uhamisho', 'ufungaji', 'ripoti', 'kumbukumbu', 'watumiaji', 'matawi']

// Groups with sub-items. `prefix` decides when the group counts as active
// (and starts expanded); a group shows only if one of its children does.
// Built per render so labels follow a language switch.
const navGroups = () => ({
  bidhaa: {
    label: SW.nav.bidhaa, icon: Package, prefix: '/bidhaa',
    children: [
      { to: '/bidhaa', label: SW.nav.orodhaYaBidhaa, icon: List, permission: 'products.read', exact: true },
      { to: '/bidhaa/jamii', label: SW.nav.jamiiYaBidhaa, icon: Tag, permission: 'products.read' },
      { to: '/bidhaa/marekebisho', label: SW.nav.marekebishoYaBidhaa, icon: RefreshCw, permission: 'inventory.adjust' },
      { to: '/hifadhi/harakati', label: SW.nav.harakatiZaBidhaa, icon: Activity, permission: 'inventory.read' },
    ],
  },
  madeni: {
    label: SW.nav.madeni, icon: HandCoins, prefix: '/madeni',
    children: [
      { to: '/madeni', label: SW.nav.madeniYote, icon: List, permission: 'customers.read', exact: true },
      { to: '/madeni/zamani', label: SW.nav.madeniYaZamani, icon: BookOpen, permission: 'opening_balances.enter' },
    ],
  },
})

function NavGroup({ group, open, can, pathname }) {
  const children = group.children.filter((c) => !c.permission || can(c.permission))
  const isActive = pathname.startsWith(group.prefix)
  const [expanded, setExpanded] = useState(isActive)
  if (children.length === 0) return null
  const Icon = group.icon

  if (!open) {
    return (
      <NavLink
        to={children[0].to}
        title={group.label}
        className={clsx(
          'flex items-center justify-center px-3 py-2.5 rounded-lg transition-colors duration-150',
          isActive
            ? 'bg-primary/15 text-primary-light border border-primary/20'
            : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
        )}
      >
        <Icon size={18} />
      </NavLink>
    )
  }

  return (
    <div>
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className={clsx(
          'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-150',
          isActive
            ? 'bg-primary/10 text-primary-light'
            : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
        )}
      >
        <Icon size={18} className={clsx('flex-shrink-0', isActive && 'text-primary-light')} />
        <span className="text-sm font-medium truncate flex-1 text-left">{group.label}</span>
        <motion.span
          style={{ display: 'inline-flex' }}
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown size={14} />
        </motion.span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-1 ml-4 pl-3 border-l border-border space-y-1">
              {children.map((child) => (
                <NavLink
                  key={child.to}
                  to={child.to}
                  end={child.exact}
                  className={({ isActive: on }) =>
                    clsx(
                      'flex items-center gap-2 px-2 py-2 rounded-lg transition-colors duration-150 text-xs',
                      on
                        ? 'bg-primary/15 text-primary-light border border-primary/20'
                        : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover'
                    )
                  }
                >
                  {({ isActive: on }) => (
                    <>
                      <child.icon size={14} className={clsx('flex-shrink-0', on && 'text-primary-light')} />
                      <span className="font-medium truncate">{child.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function Sidebar({ open, onToggle }) {
  const { can, role } = usePermission()
  const location = useLocation()
  const topNavItems = [
    { to: '/dashibodi', icon: LayoutDashboard, label: SW.nav.dashibodi, permission: null },
  ]
  const navOrder = ROLE_NAV_ORDER[role] || DEFAULT_NAV_ORDER
  const groups = navGroups()

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
      <nav className="flex-1 overflow-y-auto py-3 space-y-1 px-2 pb-3">
        {topNavItems.map(renderNavItem)}
        {navOrder.map((key) => (groups[key]
          ? <NavGroup key={key} group={groups[key]} open={open} can={can} pathname={location.pathname} />
          : renderNavItem(NAV_ITEMS[key])))}
      </nav>
    </motion.aside>
  )
}

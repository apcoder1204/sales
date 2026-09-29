import React from 'react'
import { Link } from 'react-router-dom'
import { clsx } from 'clsx'
import { Zap, CheckCircle2, Lock, AlertTriangle, ArrowLeftRight, Package } from 'lucide-react'
import { usePermission } from '@hooks/usePermission'
import { formatDate } from '@utils/formatters'
import SW from '@constants/sw'

function ActionRow({ icon: Icon, color, text, to }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 py-2 px-2 -mx-2 rounded-lg hover:bg-bg-hover transition-colors"
    >
      <Icon size={16} className={clsx('flex-shrink-0', color === 'red' ? 'text-accent-red' : 'text-accent-yellow')} />
      <span className="text-sm text-text-secondary flex-1">{text}</span>
    </Link>
  )
}

// "What needs my attention right now" — consolidated across the signals
// that already exist scattered across other cards (pending requests, low
// stock) plus two that previously weren't surfaced proactively anywhere: a
// register still open from a *past* business day (cash never reconciled),
// and "you haven't opened today's register yet". Visibility of each row is
// gated by permission, not role name, so it stays correct if the
// permission map changes — a store_keeper (no closing.view) never sees the
// register rows; a cashier (no inventory.adjust, but has inventory.read)
// still sees the low-stock signal since it's informational either way.
export default function ActionCenter({ data, loading }) {
  const { can } = usePermission()
  if (loading || !data) return null

  const showClosing = can('closing.view')
  const showTransfers = can('transfers.read')
  const showStock = can('inventory.read')

  const staleRegisters = showClosing ? (data.stale_registers || []) : []
  const registerNotOpen = showClosing && data.register_open_today === false
  const pendingCount = showTransfers ? (data.pending_requests || 0) : 0
  const lowStockCount = showStock ? (data.low_stock_count || 0) : 0

  const hasAny = staleRegisters.length > 0 || registerNotOpen || pendingCount > 0 || lowStockCount > 0

  return (
    <div className="glass-card p-4">
      <p className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-1">
        <Zap size={16} className="text-primary-light" />
        {SW.dashibodi.kituoChaVitendo}
      </p>
      {!hasAny ? (
        <div className="flex items-center gap-2 py-2 text-sm text-text-muted">
          <CheckCircle2 size={16} className="text-accent-green flex-shrink-0" />
          {SW.dashibodi.kilaKituKikoSawa}
        </div>
      ) : (
        <div className="divide-y divide-border/50">
          {registerNotOpen && (
            <ActionRow icon={Lock} color="yellow" text={SW.dashibodi.rejistaHaijafunguliwaLeo} to="/ufungaji" />
          )}
          {staleRegisters.map((r) => (
            <ActionRow
              key={r.id} icon={AlertTriangle} color="red"
              text={SW.dashibodi.rejistaTangu(r.branch_name, formatDate(r.business_date))}
              to="/ufungaji"
            />
          ))}
          {pendingCount > 0 && (
            <ActionRow icon={ArrowLeftRight} color="yellow" text={SW.dashibodi.maombiYanasubiriIdhini(pendingCount)} to="/uhamisho" />
          )}
          {lowStockCount > 0 && (
            <ActionRow icon={Package} color="red" text={SW.dashibodi.bidhaaZenyeHisaChiniKiasi(lowStockCount)} to="/bidhaa" />
          )}
        </div>
      )}
    </div>
  )
}

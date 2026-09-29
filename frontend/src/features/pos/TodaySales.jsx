import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { CalendarCheck, Banknote, Smartphone, Landmark, ChevronRight } from 'lucide-react'
import { reportService } from '@services/reportService'
import { usePermission } from '@hooks/usePermission'
import { formatCurrency } from '@utils/formatters'
import SW from '@constants/sw'

const PAYMENT_ROWS = [
  { key: 'cash', icon: Banknote, label: SW.hali.malipo.cash },
  { key: 'bank_transfer', icon: Landmark, label: SW.hali.malipo.bank_transfer },
  { key: 'mobile_money', icon: Smartphone, label: SW.hali.malipo.mobile_money },
]

export default function TodaySales({ refreshKey }) {
  const [summary, setSummary] = useState(null)
  const { can } = usePermission()

  useEffect(() => {
    let cancelled = false
    reportService.dashboard()
      .then((d) => { if (!cancelled) setSummary(d) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [refreshKey])

  if (!summary) return null

  const breakdown = summary.today_payment_breakdown || {}
  const revenue = summary.today_revenue || 0

  return (
    <div className="border-t border-border px-3 py-3 flex-shrink-0 space-y-3">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <CalendarCheck size={14} className="text-primary-light" />
        {SW.mauzo.mauzoYaLeo}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-sm font-bold text-accent-green leading-tight">{formatCurrency(revenue)}</p>
          <p className="text-[10px] text-text-muted mt-0.5">{SW.mauzo.mauzo}</p>
        </div>
        <div>
          <p className="text-sm font-bold text-primary-light leading-tight">{summary.today_transactions}</p>
          <p className="text-[10px] text-text-muted mt-0.5">{SW.mauzo.miamala}</p>
        </div>
        <div>
          <p className="text-sm font-bold text-accent-purple leading-tight">{summary.today_items_sold ?? 0}</p>
          <p className="text-[10px] text-text-muted mt-0.5">{SW.mauzo.bidhaaZilizouzwa}</p>
        </div>
      </div>

      {revenue > 0 && (
        <div className="space-y-1.5">
          {PAYMENT_ROWS.map(({ key, icon: Icon, label }) => {
            const amount = breakdown[key] || 0
            const pct = revenue > 0 ? Math.round((amount / revenue) * 100) : 0
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <Icon size={13} className="text-text-muted flex-shrink-0" />
                <span className="text-text-secondary flex-1 truncate">{label}</span>
                <span className="text-text-muted">{pct}%</span>
                <span className="font-semibold text-text-primary w-20 text-right">{formatCurrency(amount)}</span>
              </div>
            )
          })}
        </div>
      )}

      {(can('reports.sales') || can('reports.closing') || can('reports.inventory')) && (
        <Link
          to="/ripoti"
          className="flex items-center justify-center gap-1 text-xs font-medium text-primary-light hover:text-primary py-1.5 border-t border-border/50 pt-2.5"
        >
          {SW.mauzo.angaliaRipotiKamili}
          <ChevronRight size={13} />
        </Link>
      )}
    </div>
  )
}

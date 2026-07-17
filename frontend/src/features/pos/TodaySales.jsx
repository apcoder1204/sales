import React, { useState, useEffect } from 'react'
import { CalendarCheck } from 'lucide-react'
import { reportService } from '@services/reportService'
import { formatCurrency } from '@utils/formatters'
import SW from '@constants/sw'

export default function TodaySales({ refreshKey }) {
  const [summary, setSummary] = useState(null)

  useEffect(() => {
    let cancelled = false
    reportService.dashboard()
      .then((d) => { if (!cancelled) setSummary(d) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [refreshKey])

  if (!summary) return null

  return (
    <div className="border-t border-border px-3 py-3 flex-shrink-0 space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <CalendarCheck size={14} className="text-primary-light" />
        {SW.mauzo.mauzoYaLeo}
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-sm font-bold text-accent-green leading-tight">{formatCurrency(summary.today_revenue)}</p>
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
    </div>
  )
}

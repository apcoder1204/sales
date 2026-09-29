import React, { useState, useEffect } from 'react'
import KpiDrillDownModal from '@components/ui/KpiDrillDownModal'
import { inventoryService } from '@services/inventoryService'
import { formatNumber, formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

// Shared "why does this number exist" drill-downs, reused across every
// dashboard that shows the same KPI (revenue, low stock, pending requests)
// so the breakdown logic and layout stay in one place instead of four.

export function PaymentBreakdownModal({ open, onClose, title, breakdown, count }) {
  const rows = [
    { label: SW.mauzo.taslimu, value: breakdown?.cash || 0 },
    { label: SW.mauzo.simuLipa, value: breakdown?.mobile_money || 0 },
    { label: SW.mauzo.benki, value: breakdown?.bank_transfer || 0 },
    { label: SW.mauzo.miamala, value: formatNumber(count || 0), isCurrency: false },
  ]
  return <KpiDrillDownModal open={open} onClose={onClose} title={title} subtitle={SW.dashibodi.mchanganyikoMalipo} rows={rows} />
}

export function LowStockDrillDownModal({ open, onClose, items }) {
  return (
    <KpiDrillDownModal open={open} onClose={onClose} title={SW.hifadhi.hisaChini} subtitle={SW.dashibodi.hisaChiniOrodha}>
      <div className="space-y-2">
        {(items || []).map((it) => (
          <div key={it.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
            <div>
              <p className="text-sm font-medium text-text-primary">{it.product_name}</p>
              <p className="text-xs text-text-muted">{it.branch_name}</p>
            </div>
            <span className="text-sm font-semibold text-accent-red">{formatNumber(it.available_qty)}</span>
          </div>
        ))}
        {(!items || items.length === 0) && (
          <p className="text-sm text-text-muted text-center py-4">{SW.common.hakuna}</p>
        )}
      </div>
    </KpiDrillDownModal>
  )
}

// Unlike the others, this one fetches its own data on open rather than
// reading it out of the dashboard payload — inventory/summary is a
// separate, on-demand query (per-branch valuation), not something every
// dashboard load needs to compute.
export function InventoryValueDrillDownModal({ open, onClose }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    if (!open) { setRows(null); return }
    inventoryService.summary().then(setRows).catch(() => setRows([]))
  }, [open])

  return (
    <KpiDrillDownModal open={open} onClose={onClose} title={SW.ripoti.thamaniYaInventory} subtitle={SW.dashibodi.thamaniKwaTawi}>
      <div className="space-y-2">
        {(rows || []).map((r) => (
          <div key={r.branch_id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
            <div>
              <p className="text-sm font-medium text-text-primary">{r.branch_name}</p>
              <p className="text-xs text-text-muted">{SW.bidhaa.idadiBidhaa(r.product_count)}</p>
            </div>
            <span className="text-sm font-semibold text-text-primary">{r.total_value}</span>
          </div>
        ))}
        {rows === null && <p className="text-sm text-text-muted text-center py-4">{SW.common.pakia}</p>}
        {rows && rows.length === 0 && <p className="text-sm text-text-muted text-center py-4">{SW.common.hakuna}</p>}
      </div>
    </KpiDrillDownModal>
  )
}

export function PendingRequestsDrillDownModal({ open, onClose, items }) {
  return (
    <KpiDrillDownModal open={open} onClose={onClose} title={SW.dashibodi.maombiYanayosubiri} subtitle={SW.dashibodi.maombiOrodha}>
      <div className="space-y-2">
        {(items || []).map((r) => (
          <div key={r.id} className="py-2 border-b border-border/50 last:border-0">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-text-primary">{r.request_no}</p>
              <p className="text-xs text-text-muted">{formatDateTime(r.created_at)}</p>
            </div>
            <p className="text-xs text-text-muted">{SW.dashibodi.ombiKutokaKwenda(r.from_branch, r.to_branch)}</p>
            <p className="text-xs text-text-muted">{SW.dashibodi.aliyeomba}: {r.requested_by}</p>
          </div>
        ))}
        {(!items || items.length === 0) && (
          <p className="text-sm text-text-muted text-center py-4">{SW.common.hakuna}</p>
        )}
      </div>
    </KpiDrillDownModal>
  )
}

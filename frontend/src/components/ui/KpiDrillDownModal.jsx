import React from 'react'
import Modal from './Modal'
import { formatCurrency } from '@utils/formatters'

// The "why does this number exist" drill-down for a dashboard KPI card —
// `rows` is the common case (a simple label/value breakdown, e.g. revenue
// split by payment method); pass `children` instead for a list-shaped
// breakdown (low-stock items, pending requests) that doesn't fit rows.
export default function KpiDrillDownModal({ open, onClose, title, subtitle, rows, children }) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm">
      {subtitle && <p className="text-sm text-text-muted mb-4">{subtitle}</p>}
      {rows && (
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.label} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
              <span className="text-sm text-text-secondary">{r.label}</span>
              <span className="text-sm font-semibold text-text-primary">
                {r.isCurrency === false ? r.value : formatCurrency(r.value)}
              </span>
            </div>
          ))}
        </div>
      )}
      {children}
    </Modal>
  )
}

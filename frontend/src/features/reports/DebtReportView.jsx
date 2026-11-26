import React from 'react'
import { normaliseReport } from '@utils/reportExport'

// Debt reports render straight from the export normaliser, so what is on
// screen is exactly what the PDF, Excel file and WhatsApp copy carry.
export default function DebtReportView({ type, data, period }) {
  const { sheets } = normaliseReport(type, data, period)
  const [summary, ...tables] = sheets
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {summary.rows.map((r, i) => (
          <div key={i} className="glass-card p-4">
            <p className="text-xs text-text-secondary">{r[0]}</p>
            <p className="text-lg font-semibold text-text-primary whitespace-nowrap">{r.slice(1).join(' · ')}</p>
          </div>
        ))}
      </div>
      {tables.map((t) => (
        <div key={t.name} className="glass-card overflow-x-auto">
          <p className="px-4 pt-3 text-sm font-medium text-text-primary">{t.name}</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-text-muted border-b border-border">
                {t.head[0].map((h, i) => <th key={i} className={`px-3 py-2 ${i === 0 ? 'text-left' : 'text-right'}`}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {t.rows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/50">
                  {row.map((c, ci) => (
                    <td key={ci} className={`px-3 py-2 ${ci === 0 ? 'text-left' : 'text-right whitespace-nowrap'}`}>{c}</td>
                  ))}
                </tr>
              ))}
              {t.rows.length === 0 && (
                <tr><td colSpan={t.head[0].length} className="px-3 py-4 text-center text-text-muted">—</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

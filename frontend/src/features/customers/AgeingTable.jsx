import React from 'react'
import { useNavigate } from 'react-router-dom'
import { formatCurrency } from '@utils/formatters'
import SW from '@constants/sw'

export const BUCKETS = ['not_due', '1_30', '31_60', '61_90', '90_plus']

// Debt ageing (brief §14): each customer's open debt split by how many days
// it is past its due date, with a totals row.
export default function AgeingTable({ data }) {
  const navigate = useNavigate()
  if (!data) return null
  const cell = 'px-3 py-2 text-right whitespace-nowrap'
  const amount = (v) => (Number(v) ? formatCurrency(v) : '-')
  return (
    <div className="glass-card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-text-muted border-b border-border">
            <th className="px-3 py-2 text-left">{SW.wateja.mteja}</th>
            {BUCKETS.map((b) => <th key={b} className={cell}>{SW.madeni.umri[b]}</th>)}
            <th className={cell}>{SW.madeni.jumlaFupi}</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.customer.id} className="border-b border-border/50 cursor-pointer hover:bg-bg-hover"
              onClick={() => navigate(`/wateja/${r.customer.id}`)}>
              <td className="px-3 py-2">
                <p className="font-medium text-text-primary">{r.customer.name}</p>
                <p className="text-xs text-text-muted">{r.customer.customer_no}</p>
              </td>
              {BUCKETS.map((b) => (
                <td key={b} className={`${cell} ${b === '90_plus' && Number(r.buckets[b]) ? 'text-accent-red font-medium' : ''}`}>
                  {amount(r.buckets[b])}
                </td>
              ))}
              <td className={`${cell} font-semibold`}>{formatCurrency(r.total)}</td>
            </tr>
          ))}
          {data.rows.length === 0 && (
            <tr><td colSpan={7} className="px-3 py-4 text-center text-text-muted">{SW.madeni.hakuna}</td></tr>
          )}
          <tr className="font-semibold border-t border-border">
            <td className="px-3 py-2">{SW.madeni.jumlaFupi}</td>
            {BUCKETS.map((b) => <td key={b} className={cell}>{amount(data.totals[b])}</td>)}
            <td className={cell}>{formatCurrency(data.total)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

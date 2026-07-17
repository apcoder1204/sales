import React from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { formatNumber } from '@utils/formatters'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="glass-card px-3 py-2 text-xs">
      <p className="text-text-secondary mb-1">{label}</p>
      <p className="font-semibold text-accent-green">Idadi: {formatNumber(payload[0]?.value)}</p>
    </div>
  )
}

export default function TopProductsChart({ data = [] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 80, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1E2D4A" horizontal={false} />
        <XAxis type="number" tick={{ fill: '#475569', fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="product_name" tick={{ fill: '#94A3B8', fontSize: 11 }} axisLine={false} tickLine={false} width={75} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="quantity_sold" fill="#10B981" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

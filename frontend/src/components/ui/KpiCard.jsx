import React from 'react'
import { clsx } from 'clsx'
import { TrendingUp, TrendingDown } from 'lucide-react'

export default function KpiCard({ title, value, icon: Icon, trend, trendLabel, color = 'blue', loading }) {
  const colorMap = {
    blue: { icon: 'text-primary bg-primary-muted', trend: 'text-primary' },
    green: { icon: 'text-accent-green bg-accent-green-muted', trend: 'text-accent-green' },
    yellow: { icon: 'text-accent-yellow bg-accent-yellow-muted', trend: 'text-accent-yellow' },
    red: { icon: 'text-accent-red bg-accent-red-muted', trend: 'text-accent-red' },
    purple: { icon: 'text-accent-purple bg-accent-purple-muted', trend: 'text-accent-purple' },
  }
  const c = colorMap[color] || colorMap.blue

  if (loading) {
    return (
      <div className="glass-card p-5 animate-pulse">
        <div className="h-4 bg-bg-hover rounded w-24 mb-3" />
        <div className="h-8 bg-bg-hover rounded w-32 mb-2" />
        <div className="h-3 bg-bg-hover rounded w-20" />
      </div>
    )
  }

  return (
    <div className="glass-card p-5 hover:border-border-light transition-colors">
      <div className="flex items-start justify-between mb-3">
        <p className="text-sm text-text-secondary">{title}</p>
        {Icon && (
          <div className={clsx('p-2 rounded-lg', c.icon)}>
            <Icon size={18} />
          </div>
        )}
      </div>
      <p className="text-2xl font-bold text-text-primary mb-1">{value}</p>
      {(trend !== undefined || trendLabel) && (
        <div className={clsx('flex items-center gap-1 text-xs', trend > 0 ? 'text-accent-green' : trend < 0 ? 'text-accent-red' : 'text-text-muted')}>
          {trend > 0 ? <TrendingUp size={12} /> : trend < 0 ? <TrendingDown size={12} /> : null}
          <span>{trendLabel}</span>
        </div>
      )}
    </div>
  )
}

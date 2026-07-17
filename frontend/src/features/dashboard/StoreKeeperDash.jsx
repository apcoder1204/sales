import React from 'react'
import { Package, AlertTriangle, ArrowLeftRight, Activity } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import KpiCard from '@components/ui/KpiCard'
import Card from '@components/ui/Card'
import { formatNumber, formatCurrency } from '@utils/formatters'
import { useDashboard } from './useDashboard'

export default function StoreKeeperDash() {
  const { data, loading } = useDashboard()

  return (
    <PageWrapper title="Dashibodi ya Mhusika wa Hifadhi" subtitle="Usimamizi wa bidhaa na uhamisho">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="Bidhaa Zote" value={formatNumber(data?.total_products)} icon={Package} color="blue" loading={loading} />
        <KpiCard title="Thamani ya Inventory" value={formatCurrency(data?.inventory_value)} icon={Activity} color="green" loading={loading} />
        <KpiCard title="Maombi Yanayosubiri" value={formatNumber(data?.pending_requests)} icon={ArrowLeftRight} color="yellow" loading={loading} />
        <KpiCard title="Bidhaa Chini" value={formatNumber(data?.low_stock_count)} icon={AlertTriangle} color="red" loading={loading} />
      </div>

      <Card title="Bidhaa za Idadi Chini">
        <div className="space-y-2">
          {(data?.low_stock_items || []).slice(0, 8).map((item) => (
            <div key={item.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
              <div>
                <p className="text-sm font-medium text-text-primary">{item.product_name}</p>
                <p className="text-xs text-text-muted">{item.branch_name}</p>
              </div>
              <span className="text-sm font-bold text-accent-red">{item.available_qty} zilizobaki</span>
            </div>
          ))}
          {(!data?.low_stock_items || data.low_stock_items.length === 0) && !loading && (
            <p className="text-sm text-text-muted text-center py-4">Bidhaa ziko sawa</p>
          )}
        </div>
      </Card>
    </PageWrapper>
  )
}

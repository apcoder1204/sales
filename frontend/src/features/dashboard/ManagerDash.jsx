import React, { useState } from 'react'
import { ShoppingBag, TrendingUp, ArrowLeftRight, AlertTriangle } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import KpiCard from '@components/ui/KpiCard'
import Card from '@components/ui/Card'
import BranchSalesChart from '@components/charts/BranchSalesChart'
import { PaymentBreakdownModal, LowStockDrillDownModal, PendingRequestsDrillDownModal } from './DrillDowns'
import ActionCenter from './ActionCenter'
import { formatCurrency, formatNumber } from '@utils/formatters'
import { useDashboard } from './useDashboard'
import SW from '@constants/sw'

export default function ManagerDash() {
  const { data, loading } = useDashboard()
  const [drillDown, setDrillDown] = useState(null)

  return (
    <PageWrapper title={SW.dashibodi.menejaMkuu} subtitle={SW.dashibodi.subtitleManager}>
      <ActionCenter data={data} loading={loading} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title={SW.dashibodi.mauzoLeo} value={formatCurrency(data?.today_revenue)} icon={ShoppingBag} color="blue" loading={loading} onClick={() => setDrillDown('today')} />
        <KpiCard title={SW.dashibodi.mauzoMwezi} value={formatCurrency(data?.month_revenue)} icon={TrendingUp} color="green" loading={loading} onClick={() => setDrillDown('month')} />
        <KpiCard title={SW.dashibodi.maombiYanayosubiri} value={formatNumber(data?.pending_requests)} icon={ArrowLeftRight} color="yellow" loading={loading} onClick={() => setDrillDown('pending')} />
        <KpiCard title={SW.hifadhi.hisaChini} value={formatNumber(data?.low_stock_count)} icon={AlertTriangle} color="red" loading={loading} onClick={() => setDrillDown('low_stock')} />
      </div>

      <PaymentBreakdownModal
        open={drillDown === 'today'} onClose={() => setDrillDown(null)}
        title={SW.dashibodi.mauzoLeo} breakdown={data?.today_payment_breakdown} count={data?.today_transactions}
      />
      <PaymentBreakdownModal
        open={drillDown === 'month'} onClose={() => setDrillDown(null)}
        title={SW.dashibodi.mauzoMwezi} breakdown={data?.month_payment_breakdown} count={data?.month_transactions}
      />
      <LowStockDrillDownModal
        open={drillDown === 'low_stock'} onClose={() => setDrillDown(null)}
        items={data?.low_stock_items}
      />
      <PendingRequestsDrillDownModal
        open={drillDown === 'pending'} onClose={() => setDrillDown(null)}
        items={data?.pending_requests_list}
      />
      <Card title={SW.ripoti.mauzoKwaTawi}>
        {data?.branch_sales?.length > 0 || loading ? (
          <BranchSalesChart data={data?.branch_sales || []} />
        ) : (
          <p className="text-sm text-text-muted text-center py-16">{SW.common.hakuna}</p>
        )}
      </Card>
    </PageWrapper>
  )
}

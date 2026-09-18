import React from 'react'
import { ShoppingBag, TrendingUp, ArrowLeftRight, AlertTriangle } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import KpiCard from '@components/ui/KpiCard'
import Card from '@components/ui/Card'
import BranchSalesChart from '@components/charts/BranchSalesChart'
import { formatCurrency, formatNumber } from '@utils/formatters'
import { useDashboard } from './useDashboard'
import SW from '@constants/sw'

export default function ManagerDash() {
  const { data, loading } = useDashboard()

  return (
    <PageWrapper title={SW.dashibodi.menejaMkuu} subtitle={SW.dashibodi.subtitleManager}>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title={SW.dashibodi.mauzoLeo} value={formatCurrency(data?.today_revenue)} icon={ShoppingBag} color="blue" loading={loading} />
        <KpiCard title={SW.dashibodi.mauzoMwezi} value={formatCurrency(data?.month_revenue)} icon={TrendingUp} color="green" loading={loading} />
        <KpiCard title={SW.dashibodi.maombiYanayosubiri} value={formatNumber(data?.pending_requests)} icon={ArrowLeftRight} color="yellow" loading={loading} />
        <KpiCard title={SW.hifadhi.hisaChini} value={formatNumber(data?.low_stock_count)} icon={AlertTriangle} color="red" loading={loading} />
      </div>
      <Card title={SW.ripoti.mauzoKwaTawi}>
        <BranchSalesChart data={data?.branch_sales || []} />
      </Card>
    </PageWrapper>
  )
}

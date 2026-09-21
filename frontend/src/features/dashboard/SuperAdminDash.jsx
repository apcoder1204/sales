import React, { useState } from 'react'
import { ShoppingBag, TrendingUp, Package, Users, AlertTriangle, Building2 } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import KpiCard from '@components/ui/KpiCard'
import Card from '@components/ui/Card'
import SalesTrendChart from '@components/charts/SalesTrendChart'
import BranchSalesChart from '@components/charts/BranchSalesChart'
import TopProductsChart from '@components/charts/TopProductsChart'
import { PaymentBreakdownModal, LowStockDrillDownModal } from './DrillDowns'
import { formatCurrency, formatNumber } from '@utils/formatters'
import { useDashboard } from './useDashboard'
import SW from '@constants/sw'

export default function SuperAdminDash() {
  const { data, loading } = useDashboard()
  const [drillDown, setDrillDown] = useState(null)

  return (
    <PageWrapper title={SW.nav.dashibodi} subtitle={SW.dashibodi.subtitleSuperAdmin}>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title={SW.dashibodi.mauzoLeo} value={formatCurrency(data?.today_revenue)} icon={ShoppingBag} color="blue" loading={loading} trendLabel={SW.ripoti.leo} onClick={() => setDrillDown('today')} />
        <KpiCard title={SW.dashibodi.mauzoMwezi} value={formatCurrency(data?.month_revenue)} icon={TrendingUp} color="green" loading={loading} trendLabel={SW.ripoti.mwezi} onClick={() => setDrillDown('month')} />
        <KpiCard title={SW.ripoti.bidhaaZote} value={formatNumber(data?.total_products)} icon={Package} color="purple" loading={loading} />
        <KpiCard title={SW.hifadhi.hisaChini} value={formatNumber(data?.low_stock_count)} icon={AlertTriangle} color="red" loading={loading} trendLabel={SW.bidhaa.bidhaa} onClick={() => setDrillDown('low_stock')} />
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title={SW.dashibodi.mwelekeoWikiHii}>
          {data?.sales_trend?.length > 0 || loading ? (
            <SalesTrendChart data={data?.sales_trend || []} />
          ) : (
            <p className="text-sm text-text-muted text-center py-16">{SW.common.hakuna}</p>
          )}
        </Card>
        <Card title={SW.ripoti.mauzoKwaTawi}>
          {data?.branch_sales?.length > 0 || loading ? (
            <BranchSalesChart data={data?.branch_sales || []} />
          ) : (
            <p className="text-sm text-text-muted text-center py-16">{SW.common.hakuna}</p>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title={SW.dashibodi.bidhaaTanoZaJuu}>
          {data?.top_products?.length > 0 || loading ? (
            <TopProductsChart data={data?.top_products || []} />
          ) : (
            <p className="text-sm text-text-muted text-center py-16">{SW.common.hakuna}</p>
          )}
        </Card>
        <Card title={SW.dashibodi.haliYaMatawi}>
          <div className="space-y-3">
            {(data?.branches || []).map((b) => (
              <div key={b.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <div className="flex items-center gap-3">
                  <div className="p-1.5 bg-primary-muted rounded-lg">
                    <Building2 size={14} className="text-primary-light" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-text-primary">{b.name}</p>
                    <p className="text-xs text-text-muted">{b.code}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-text-primary">{formatCurrency(b.today_revenue)}</p>
                  <p className="text-xs text-text-muted">{SW.dashibodi.mauzoCount(b.today_transactions)}</p>
                </div>
              </div>
            ))}
            {(!data?.branches || data.branches.length === 0) && !loading && (
              <p className="text-sm text-text-muted text-center py-4">{SW.common.hakuna}</p>
            )}
          </div>
        </Card>
      </div>
    </PageWrapper>
  )
}

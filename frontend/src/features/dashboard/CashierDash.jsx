import React from 'react'
import { ShoppingBag, Receipt, TrendingUp, Clock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import PageWrapper from '@components/layout/PageWrapper'
import KpiCard from '@components/ui/KpiCard'
import Card from '@components/ui/Card'
import Button from '@components/ui/Button'
import SalesTrendChart from '@components/charts/SalesTrendChart'
import { formatCurrency, formatNumber, formatDateTime } from '@utils/formatters'
import { useDashboard } from './useDashboard'
import SW from '@constants/sw'

export default function CashierDash() {
  const { data, loading } = useDashboard()
  const navigate = useNavigate()

  return (
    <PageWrapper
      title={SW.dashibodi.mhusikaFedha}
      subtitle={SW.dashibodi.subtitleCashier}
      action={
        <Button onClick={() => navigate('/mauzo')} leftIcon={<ShoppingBag size={16} />}>
          {SW.nav.mauzo}
        </Button>
      }
    >
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title={SW.dashibodi.mauzoLeo} value={formatCurrency(data?.today_revenue)} icon={TrendingUp} color="green" loading={loading} />
        <KpiCard title={SW.dashibodi.muamalaLeo} value={formatNumber(data?.today_transactions)} icon={Receipt} color="blue" loading={loading} />
        <KpiCard title={SW.ripoti.wastaniWaUuzaji} value={formatCurrency(data?.avg_sale_value)} icon={ShoppingBag} color="purple" loading={loading} />
        <KpiCard title={SW.dashibodi.muamalaWaMwisho} value={data?.last_sale_time ? formatDateTime(data.last_sale_time) : '-'} icon={Clock} color="yellow" loading={loading} />
      </div>

      <Card title={SW.dashibodi.mwelekeoMauzoLeo}>
        <SalesTrendChart data={data?.sales_trend || []} />
      </Card>

      <Card title={SW.dashibodi.mauzoHivKaribuni}>
        <div className="space-y-2">
          {(data?.recent_sales || []).map((sale) => (
            <div key={sale.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
              <div>
                <p className="text-sm font-medium text-text-primary">{sale.transaction_no}</p>
                <p className="text-xs text-text-muted">{formatDateTime(sale.created_at)}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold text-accent-green">{formatCurrency(sale.total_amount)}</p>
                <p className="text-xs text-text-muted">{SW.bidhaa.idadiBidhaa(sale.items_count)}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </PageWrapper>
  )
}

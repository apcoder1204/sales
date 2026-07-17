import React, { useState, useEffect, useCallback } from 'react'
import { BarChart3, FileDown, FileSpreadsheet } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import Button from '@components/ui/Button'
import Card from '@components/ui/Card'
import DataTable from '@components/tables/DataTable'
import SalesTrendChart from '@components/charts/SalesTrendChart'
import BranchSalesChart from '@components/charts/BranchSalesChart'
import TopProductsChart from '@components/charts/TopProductsChart'
import { reportService } from '@services/reportService'
import { usePermission } from '@hooks/usePermission'
import { formatCurrency, formatDateTime, formatNumber } from '@utils/formatters'
import { REPORT_PERIODS } from '@utils/constants'
import { downloadPDF, downloadExcel } from '@utils/reportExport'
import SW from '@constants/sw'

const REPORT_TYPES = [
  { value: 'sales', label: SW.ripoti.mauzo, permission: 'reports.sales' },
  { value: 'inventory', label: SW.ripoti.hifadhi, permission: 'reports.inventory' },
  { value: 'stock_movements', label: SW.ripoti.harakati, permission: 'reports.inventory' },
  { value: 'branch_performance', label: SW.ripoti.tawi, permission: 'reports.branch' },
  { value: 'cashier_performance', label: SW.ripoti.mhusika, permission: 'reports.cashier' },
  { value: 'low_stock', label: SW.ripoti.hisaChini, permission: 'reports.inventory' },
  { value: 'closing', label: SW.ripoti.ufungaji, permission: 'reports.closing' },
]

export default function ReportsPage() {
  const { can } = usePermission()
  const [reportType, setReportType] = useState('sales')
  const [period, setPeriod] = useState('today')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const availableTypes = REPORT_TYPES.filter((t) => can(t.permission))

  const fetchReport = useCallback(async () => {
    setLoading(true)
    setData(null)
    try {
      const params = { period, date_from: dateFrom || undefined, date_to: dateTo || undefined }
      let result
      switch (reportType) {
        case 'sales': result = await reportService.sales(params); break
        case 'inventory': result = await reportService.inventory(params); break
        case 'stock_movements': result = await reportService.stockMovements(params); break
        case 'branch_performance': result = await reportService.branchPerformance(params); break
        case 'cashier_performance': result = await reportService.cashierPerformance(params); break
        case 'low_stock': result = await reportService.lowStock(params); break
        case 'closing': result = await reportService.closing(params); break
        default: result = null
      }
      setData(result)
    } finally {
      setLoading(false)
    }
  }, [reportType, period, dateFrom, dateTo])

  useEffect(() => { fetchReport() }, [fetchReport])

  return (
    <PageWrapper title={SW.nav.ripoti} subtitle="Ripoti na uchambuzi wa biashara">
      {/* Filters */}
      <Card>
        <div className="flex flex-wrap gap-3 items-end">
          <Select
            label="Aina ya Ripoti"
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            options={availableTypes}
            containerClassName="min-w-48"
          />
          {reportType !== 'stock_movements' && reportType !== 'inventory' && reportType !== 'low_stock' && (
            <Select
              label="Kipindi"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              options={REPORT_PERIODS}
              containerClassName="min-w-36"
            />
          )}
          {period === 'custom' && (
            <>
              <Input label="Tarehe ya Kwanza" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              <Input label="Tarehe ya Mwisho" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </>
          )}
          <Button onClick={fetchReport} loading={loading} leftIcon={<BarChart3 size={16} />}>
            Onyesha Ripoti
          </Button>
          {data && !loading && (
            <div className="flex gap-2 ml-auto">
              <Button
                variant="secondary"
                leftIcon={<FileDown size={15} />}
                onClick={() => downloadPDF(reportType, data, period)}
                title="Pakua PDF"
              >
                PDF
              </Button>
              <Button
                variant="secondary"
                leftIcon={<FileSpreadsheet size={15} />}
                onClick={() => downloadExcel(reportType, data, period)}
                title="Pakua Excel"
              >
                Excel
              </Button>
            </div>
          )}
        </div>
      </Card>

      {loading && (
        <div className="glass-card p-8 text-center text-text-muted animate-pulse">
          Inapakia ripoti...
        </div>
      )}

      {data && !loading && <ReportContent type={reportType} data={data} />}
    </PageWrapper>
  )
}

function ReportContent({ type, data }) {
  switch (type) {
    case 'sales': return <SalesReport data={data} />
    case 'inventory': return <InventoryReport data={data} />
    case 'stock_movements': return <StockMovementsReport data={data} />
    case 'branch_performance': return <BranchReport data={data} />
    case 'cashier_performance': return <CashierReport data={data} />
    case 'low_stock': return <LowStockReport data={data} />
    case 'closing': return <ClosingReport data={data} />
    default: return null
  }
}

function KpiCard({ label, value }) {
  return (
    <Card>
      <p className="text-text-muted text-sm">{label}</p>
      <p className="text-2xl font-bold text-text-primary mt-1">{value}</p>
    </Card>
  )
}

function SalesReport({ data }) {
  const s = data.summary || {}

  // SalesTrendChart uses dataKey="total"; chart_data has {label, value}
  const trendData = (data.chart_data || []).map((p) => ({ label: p.label, total: p.value }))

  // TopProductsChart uses dataKey="product_name" and "quantity_sold"
  const topData = (data.top_products || []).map((p) => ({
    product_name: p.product,
    quantity_sold: p.qty_sold,
    revenue: p.revenue,
  }))

  const paymentCols = [
    { key: 'method', header: 'Njia ya Malipo' },
    { key: 'count', header: 'Idadi', render: (v) => formatNumber(v) },
    { key: 'total', header: 'Jumla', render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
  ]

  const topProductCols = [
    { key: 'product_name', header: 'Bidhaa' },
    { key: 'quantity_sold', header: 'Idadi Iliyouzwa', render: (v) => formatNumber(v) },
    { key: 'revenue', header: 'Mapato', render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard label="Mauzo Yote" value={<span className="text-accent-green">{formatCurrency(s.total_revenue)}</span>} />
        <KpiCard label="Muamala" value={formatNumber(s.total_transactions)} />
        <KpiCard label="Wastani wa Uuzaji" value={<span className="text-primary-light">{formatCurrency(s.avg_transaction)}</span>} />
      </div>

      {trendData.length > 0 && (
        <Card title="Mwelekeo wa Mauzo">
          <SalesTrendChart data={trendData} />
        </Card>
      )}

      {topData.length > 0 && (
        <Card title="Bidhaa Zinazouzwa Zaidi">
          <TopProductsChart data={topData} />
          <DataTable columns={topProductCols} data={topData} emptyTitle="Hakuna data" />
        </Card>
      )}

      {data.payment_breakdown && data.payment_breakdown.length > 0 && (
        <Card title="Njia za Malipo">
          <DataTable columns={paymentCols} data={data.payment_breakdown} emptyTitle="Hakuna data" />
        </Card>
      )}

      {!trendData.length && !topData.length && (
        <div className="glass-card p-8 text-center text-text-muted">Hakuna data kwa kipindi hiki</div>
      )}
    </div>
  )
}

function InventoryReport({ data }) {
  const s = data.summary || {}

  const branchCols = [
    { key: 'branch', header: 'Tawi' },
    { key: 'total_quantity', header: 'Kiasi Chote', render: (v) => formatNumber(v) },
    { key: 'total_value', header: 'Thamani', render: (v) => <span className="font-semibold">{formatCurrency(v)}</span> },
  ]

  const lowStockCols = [
    { key: 'product', header: 'Bidhaa' },
    { key: 'product_code', header: 'Msimbo' },
    { key: 'branch', header: 'Tawi' },
    { key: 'current_stock', header: 'Bidhaa Iliyobaki', render: (v) => <span className="font-bold text-accent-red">{formatNumber(v)}</span> },
    { key: 'minimum_stock', header: 'Kiwango cha Chini', render: (v) => formatNumber(v) },
    { key: 'deficit', header: 'Upungufu', render: (v) => <span className="text-accent-red">{formatNumber(v)}</span> },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <KpiCard label="Bidhaa Zote" value={formatNumber(s.total_products)} />
        <KpiCard label="Kiasi Chote" value={formatNumber(s.total_quantity)} />
        <KpiCard label="Thamani ya Inventory" value={<span className="text-text-primary">{formatCurrency(s.total_value)}</span>} />
        <KpiCard label="Bidhaa za Hisaa Chini" value={<span className="text-accent-red">{formatNumber(s.low_stock_count)}</span>} />
      </div>

      <Card title="Inventory kwa Tawi">
        <DataTable columns={branchCols} data={data.by_branch || []} emptyTitle="Hakuna data" />
      </Card>

      {data.low_stock_items && data.low_stock_items.length > 0 && (
        <Card title="Bidhaa za Hisaa Chini">
          <DataTable columns={lowStockCols} data={data.low_stock_items} emptyTitle="Hakuna bidhaa" />
        </Card>
      )}
    </div>
  )
}

function StockMovementsReport({ data }) {
  const TX_LABELS = {
    sale: 'Uuzaji',
    adjustment: 'Marekebisho',
    transfer_in: 'Uhamisho (Ndani)',
    transfer_out: 'Uhamisho (Nje)',
    purchase: 'Ununuzi',
    return: 'Urejesho',
  }

  const cols = [
    { key: 'product', header: 'Bidhaa' },
    { key: 'branch', header: 'Tawi' },
    {
      key: 'transaction_type',
      header: 'Aina',
      render: (v) => (
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          v === 'sale' ? 'bg-accent-red/10 text-accent-red' :
          v === 'transfer_in' || v === 'purchase' ? 'bg-accent-green/10 text-accent-green' :
          'bg-bg-hover text-text-muted'
        }`}>
          {TX_LABELS[v] || v}
        </span>
      ),
    },
    {
      key: 'quantity_change',
      header: 'Mabadiliko',
      render: (v) => (
        <span className={`font-semibold ${v > 0 ? 'text-accent-green' : 'text-accent-red'}`}>
          {v > 0 ? `+${formatNumber(v)}` : formatNumber(v)}
        </span>
      ),
    },
    { key: 'quantity_after', header: 'Kiasi Kipya', render: (v) => formatNumber(v) },
    { key: 'performed_by', header: 'Aliyefanya' },
    { key: 'created_at', header: 'Tarehe', render: (v) => formatDateTime(v) },
  ]

  return (
    <Card title="Harakati za Bidhaa">
      <DataTable columns={cols} data={data.items || []} emptyTitle="Hakuna harakati" />
    </Card>
  )
}

function BranchReport({ data }) {
  // BranchSalesChart expects {branch_name, total_revenue} with numeric total_revenue
  const chartData = (data.branches || []).map((b) => ({
    branch_name: b.branch,
    total_revenue: b.total_revenue,
  }))

  return (
    <div className="space-y-4">
      {chartData.length > 0 && (
        <Card title="Mauzo kwa Tawi">
          <BranchSalesChart data={chartData} />
        </Card>
      )}
      <DataTable
        columns={[
          { key: 'branch', header: 'Tawi' },
          { key: 'total_revenue', header: 'Mauzo', render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
          { key: 'transaction_count', header: 'Muamala', render: (v) => formatNumber(v) },
          { key: 'avg_transaction', header: 'Wastani', render: (v) => formatCurrency(v) },
          { key: 'items_sold', header: 'Bidhaa Zilizouzwa', render: (v) => formatNumber(v) },
        ]}
        data={data.branches || []}
        emptyTitle="Hakuna data"
      />
    </div>
  )
}

function CashierReport({ data }) {
  return (
    <DataTable
      columns={[
        { key: 'cashier', header: 'Mhusika' },
        { key: 'branch', header: 'Tawi' },
        { key: 'total_revenue', header: 'Mauzo', render: (v) => <span className="text-accent-green font-semibold">{formatCurrency(v)}</span> },
        { key: 'transaction_count', header: 'Muamala', render: (v) => formatNumber(v) },
        { key: 'avg_transaction', header: 'Wastani', render: (v) => formatCurrency(v) },
        { key: 'items_sold', header: 'Bidhaa Zilizouzwa', render: (v) => formatNumber(v) },
      ]}
      data={data.cashiers || []}
      emptyTitle="Hakuna data"
    />
  )
}

function ClosingReport({ data }) {
  const s = data.summary || {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        <KpiCard label={SW.ufungaji.taslimu} value={<span className="text-accent-green">{formatCurrency(s.total_cash)}</span>} />
        <KpiCard label={SW.ufungaji.simuLipa} value={formatCurrency(s.total_mobile_money)} />
        <KpiCard label={SW.ufungaji.benki} value={formatCurrency(s.total_bank_transfer)} />
        <KpiCard label={SW.ufungaji.jumlaKuu} value={<span className="text-primary-light">{formatCurrency(s.total_revenue)}</span>} />
        <KpiCard label={SW.ufungaji.historia} value={formatNumber(s.closings_count)} />
      </div>

      <DataTable
        columns={[
          { key: 'business_date', header: SW.ufungaji.tarehe },
          { key: 'branch', header: SW.ufungaji.tawi },
          {
            key: 'status', header: SW.common.hali,
            render: (v) => (
              <span className={v === 'closed' ? 'text-accent-green' : 'text-accent-yellow'}>
                {v === 'closed' ? SW.ufungaji.imefungwa : SW.ufungaji.wazi}
              </span>
            ),
          },
          { key: 'total_cash', header: SW.ufungaji.taslimu, render: (v) => formatCurrency(v) },
          { key: 'total_mobile_money', header: SW.ufungaji.simuLipa, render: (v) => formatCurrency(v) },
          { key: 'total_bank_transfer', header: SW.ufungaji.benki, render: (v) => formatCurrency(v) },
          { key: 'total_revenue', header: SW.ufungaji.jumlaKuu, render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
          {
            key: 'cash_variance', header: SW.ufungaji.tofauti,
            render: (v) => v == null ? '—' : (
              <span className={Math.abs(v) < 1 ? 'text-text-secondary' : v > 0 ? 'text-accent-green' : 'text-accent-red'}>
                {formatCurrency(v)}
              </span>
            ),
          },
          { key: 'total_expenses', header: SW.ufungaji.matumizi, render: (v) => v > 0 ? formatCurrency(v) : '—' },
          { key: 'closed_by', header: SW.ufungaji.aliyefunga, render: (v) => v || '—' },
        ]}
        data={data.closings || []}
        emptyTitle="Hakuna ufungaji kwa kipindi hiki"
      />
    </div>
  )
}

function LowStockReport({ data }) {
  return (
    <DataTable
      columns={[
        { key: 'product', header: 'Bidhaa' },
        { key: 'product_code', header: 'Msimbo' },
        { key: 'branch', header: 'Tawi' },
        { key: 'current_stock', header: 'Bidhaa Iliyobaki', render: (v) => <span className="font-bold text-accent-red">{formatNumber(v)}</span> },
        { key: 'minimum_stock', header: 'Kiwango cha Chini', render: (v) => formatNumber(v) },
        { key: 'deficit', header: 'Upungufu', render: (v) => <span className="text-accent-red">{formatNumber(v)}</span> },
      ]}
      data={data.items || []}
      emptyTitle="Hakuna bidhaa za idadi chini"
    />
  )
}

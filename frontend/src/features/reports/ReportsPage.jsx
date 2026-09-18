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
import { getReportPeriods } from '@utils/constants'
import { downloadPDF, downloadExcel, toClosingExportData } from '@utils/reportExport'
import { useToast } from '@hooks/useToast'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import SW from '@constants/sw'

export default function ReportsPage() {
  const { can } = usePermission()
  const toast = useToast()
  const branchFilter = useActiveBranchFilter()

  const REPORT_TYPES = [
    { value: 'sales', label: SW.ripoti.mauzo, permission: 'reports.sales' },
    { value: 'inventory', label: SW.ripoti.hifadhi, permission: 'reports.inventory' },
    { value: 'stock_movements', label: SW.ripoti.harakati, permission: 'reports.inventory' },
    { value: 'branch_performance', label: SW.ripoti.tawi, permission: 'reports.branch' },
    { value: 'cashier_performance', label: SW.ripoti.mhusika, permission: 'reports.cashier' },
    { value: 'low_stock', label: SW.ripoti.hisaChini, permission: 'reports.inventory' },
    { value: 'closing', label: SW.ripoti.ufungaji, permission: 'reports.closing' },
  ]

  const [reportType, setReportType] = useState('sales')
  const [period, setPeriod] = useState('today')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(null)

  const availableTypes = REPORT_TYPES.filter((t) => can(t.permission))
  const activeReportType = availableTypes.some((t) => t.value === reportType)
    ? reportType
    : availableTypes[0]?.value

  useEffect(() => {
    if (activeReportType && activeReportType !== reportType) {
      setReportType(activeReportType)
    }
  }, [activeReportType, reportType])

  const handleClosingExport = async (format, closing) => {
    const key = `${closing.business_date}-${format}`
    setExporting(key)
    try {
      const exportData = toClosingExportData([closing])
      if (format === 'pdf') await downloadPDF('closing', exportData, closing.business_date)
      else await downloadExcel('closing', exportData, closing.business_date)
    } catch {
      toast.error(SW.ripoti.imeshindwaKupakua)
    } finally {
      setExporting(null)
    }
  }

  const handleExport = async (format) => {
    if (!data) return
    setExporting(format)
    try {
      if (format === 'pdf') await downloadPDF(activeReportType, data, period)
      else await downloadExcel(activeReportType, data, period)
    } catch {
      toast.error(SW.ripoti.imeshindwaKupakua)
    } finally {
      setExporting(null)
    }
  }

  const fetchReport = useCallback(async () => {
    if (!activeReportType) return
    if (period === 'custom' && (!dateFrom || !dateTo)) {
      setData(null)
      return
    }
    setLoading(true)
    setData(null)
    try {
      const params = { period, date_from: dateFrom || undefined, date_to: dateTo || undefined, ...branchFilter }
      let result
      switch (activeReportType) {
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
  }, [activeReportType, period, dateFrom, dateTo, branchFilter.branch_id])

  useEffect(() => { fetchReport() }, [fetchReport])

  return (
    <PageWrapper title={SW.nav.ripoti} subtitle={SW.ripoti.subtitle}>
      {/* Filters */}
      <Card>
        <div className="flex flex-wrap gap-3 items-end">
          <Select
            label={SW.ripoti.aina}
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            options={availableTypes}
            containerClassName="min-w-48"
          />
          {activeReportType !== 'stock_movements' && activeReportType !== 'inventory' && activeReportType !== 'low_stock' && (
            <Select
              label={SW.ripoti.kipindiLabel}
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              options={getReportPeriods()}
              containerClassName="min-w-36"
            />
          )}
          {period === 'custom' && (
            <>
              <Input label={SW.ripoti.tareheKwanza} type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              <Input label={SW.ripoti.tareheMwisho} type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </>
          )}
          <Button onClick={fetchReport} loading={loading} leftIcon={<BarChart3 size={16} />}>
            {SW.ripoti.onyeshaRipoti}
          </Button>
        </div>
      </Card>

      {data && !loading && activeReportType !== 'closing' && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-text-muted">
            {availableTypes.find((t) => t.value === activeReportType)?.label}
          </p>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              leftIcon={<FileDown size={15} />}
              onClick={() => handleExport('pdf')}
              loading={exporting === 'pdf'}
              disabled={!!exporting}
              title={SW.ripoti.pakuaPdf}
            >
              {SW.ripoti.pakuaPdf}
            </Button>
            <Button
              variant="secondary"
              leftIcon={<FileSpreadsheet size={15} />}
              onClick={() => handleExport('excel')}
              loading={exporting === 'excel'}
              disabled={!!exporting}
              title={SW.ripoti.pakuaExcel}
            >
              {SW.ripoti.pakuaExcel}
            </Button>
          </div>
        </div>
      )}

      {data && !loading && activeReportType === 'closing' && (
        <p className="text-sm text-text-muted">
          {availableTypes.find((t) => t.value === activeReportType)?.label} — {SW.ripoti.pakuaRipotiKilaSiku}
        </p>
      )}

      {loading && (
        <div className="glass-card p-8 text-center text-text-muted animate-pulse">
          {SW.ripoti.inapakiaRipoti}
        </div>
      )}

      {data && !loading && (
        <ReportContent
          type={activeReportType}
          data={data}
          onClosingExport={handleClosingExport}
          closingExporting={exporting}
          canDownloadClosing={can('reports.closing')}
        />
      )}
    </PageWrapper>
  )
}

function ReportContent({ type, data, onClosingExport, closingExporting, canDownloadClosing }) {
  switch (type) {
    case 'sales': return <SalesReport data={data} />
    case 'inventory': return <InventoryReport data={data} />
    case 'stock_movements': return <StockMovementsReport data={data} />
    case 'branch_performance': return <BranchReport data={data} />
    case 'cashier_performance': return <CashierReport data={data} />
    case 'low_stock': return <LowStockReport data={data} />
    case 'closing': return (
      <ClosingReport
        data={data}
        onExport={onClosingExport}
        exporting={closingExporting}
        canDownload={canDownloadClosing}
      />
    )
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
    { key: 'method', header: SW.mauzo.njiaYaLipa },
    { key: 'count', header: SW.common.idadi, render: (v) => formatNumber(v) },
    { key: 'total', header: SW.common.jumla, render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
  ]

  const topProductCols = [
    { key: 'product_name', header: SW.bidhaa.bidhaa },
    { key: 'quantity_sold', header: SW.ripoti.idadiIliyouzwa, render: (v) => formatNumber(v) },
    { key: 'revenue', header: SW.ripoti.mapato, render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard label={SW.ripoti.mauzoYote} value={<span className="text-accent-green">{formatCurrency(s.total_revenue)}</span>} />
        <KpiCard label={SW.ripoti.muamala} value={formatNumber(s.total_transactions)} />
        <KpiCard label={SW.ripoti.wastaniWaUuzaji} value={<span className="text-primary-light">{formatCurrency(s.avg_transaction)}</span>} />
      </div>

      {trendData.length > 0 && (
        <Card title={SW.ripoti.mwelekeoWaMauzo}>
          <SalesTrendChart data={trendData} />
        </Card>
      )}

      {topData.length > 0 && (
        <Card title={SW.ripoti.bidhaaZinazouzwaZaidi}>
          <TopProductsChart data={topData} />
          <DataTable columns={topProductCols} data={topData} emptyTitle={SW.common.hakuna} />
        </Card>
      )}

      {data.payment_breakdown && data.payment_breakdown.length > 0 && (
        <Card title={SW.ripoti.njiaZaMalipo}>
          <DataTable columns={paymentCols} data={data.payment_breakdown} emptyTitle={SW.common.hakuna} />
        </Card>
      )}

      {!trendData.length && !topData.length && (
        <div className="glass-card p-8 text-center text-text-muted">{SW.ripoti.hakunaDataKipindi}</div>
      )}
    </div>
  )
}

function InventoryReport({ data }) {
  const s = data.summary || {}

  const branchCols = [
    { key: 'branch', header: SW.ufungaji.tawi },
    { key: 'total_quantity', header: SW.ripoti.kiasiChote, render: (v) => formatNumber(v) },
    { key: 'total_value', header: SW.ripoti.thamani, render: (v) => <span className="font-semibold">{formatCurrency(v)}</span> },
  ]

  const lowStockCols = [
    { key: 'product', header: SW.bidhaa.bidhaa },
    { key: 'product_code', header: SW.ripoti.msimbo },
    { key: 'branch', header: SW.ufungaji.tawi },
    { key: 'current_stock', header: SW.ripoti.bidhaaIliyobaki, render: (v) => <span className="font-bold text-accent-red">{formatNumber(v)}</span> },
    { key: 'minimum_stock', header: SW.ripoti.kiwangoChaChini, render: (v) => formatNumber(v) },
    { key: 'deficit', header: SW.ripoti.upungufu, render: (v) => <span className="text-accent-red">{formatNumber(v)}</span> },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <KpiCard label={SW.ripoti.bidhaaZote} value={formatNumber(s.total_products)} />
        <KpiCard label={SW.ripoti.kiasiChote} value={formatNumber(s.total_quantity)} />
        <KpiCard label={SW.ripoti.thamaniYaInventory} value={<span className="text-text-primary">{formatCurrency(s.total_value)}</span>} />
        <KpiCard label={SW.ripoti.bidhaaZaHisaaChini} value={<span className="text-accent-red">{formatNumber(s.low_stock_count)}</span>} />
      </div>

      <Card title={SW.ripoti.inventoryKwaTawi}>
        <DataTable columns={branchCols} data={data.by_branch || []} emptyTitle={SW.common.hakuna} />
      </Card>

      {data.low_stock_items && data.low_stock_items.length > 0 && (
        <Card title={SW.ripoti.bidhaaZaHisaaChini}>
          <DataTable columns={lowStockCols} data={data.low_stock_items} emptyTitle={SW.ripoti.hakunaBidhaa} />
        </Card>
      )}
    </div>
  )
}

function StockMovementsReport({ data }) {
  const cols = [
    { key: 'product', header: SW.bidhaa.bidhaa },
    { key: 'branch', header: SW.ufungaji.tawi },
    {
      key: 'transaction_type',
      header: SW.hifadhi.aina,
      render: (v) => (
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
          v === 'sale' ? 'bg-accent-red/10 text-accent-red' :
          v === 'transfer_in' || v === 'purchase' ? 'bg-accent-green/10 text-accent-green' :
          'bg-bg-hover text-text-muted'
        }`}>
          {SW.hali.harakati[v] || v}
        </span>
      ),
    },
    {
      key: 'quantity_change',
      header: SW.hifadhi.mabadiliko,
      render: (v) => (
        <span className={`font-semibold ${v > 0 ? 'text-accent-green' : 'text-accent-red'}`}>
          {v > 0 ? `+${formatNumber(v)}` : formatNumber(v)}
        </span>
      ),
    },
    { key: 'quantity_after', header: SW.ripoti.kiasiKipya, render: (v) => formatNumber(v) },
    { key: 'performed_by', header: SW.ripoti.aliyefanya },
    { key: 'created_at', header: SW.common.tarehe, render: (v) => formatDateTime(v) },
  ]

  return (
    <Card title={SW.hifadhi.harakati}>
      <DataTable columns={cols} data={data.items || []} emptyTitle={SW.ripoti.hakunaHarakati} />
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
        <Card title={SW.ripoti.mauzoKwaTawi}>
          <BranchSalesChart data={chartData} />
        </Card>
      )}
      <DataTable
        columns={[
          { key: 'branch', header: SW.ufungaji.tawi },
          { key: 'total_revenue', header: SW.mauzo.mauzo, render: (v) => <span className="font-semibold text-accent-green">{formatCurrency(v)}</span> },
          { key: 'transaction_count', header: SW.ripoti.muamala, render: (v) => formatNumber(v) },
          { key: 'avg_transaction', header: SW.ripoti.wastani, render: (v) => formatCurrency(v) },
          { key: 'items_sold', header: SW.ripoti.bidhaaZilizouzwa, render: (v) => formatNumber(v) },
        ]}
        data={data.branches || []}
        emptyTitle={SW.common.hakuna}
      />
    </div>
  )
}

function CashierReport({ data }) {
  return (
    <DataTable
      columns={[
        { key: 'cashier', header: SW.ripoti.mhusikaHeader },
        { key: 'branch', header: SW.ufungaji.tawi },
        { key: 'total_revenue', header: SW.mauzo.mauzo, render: (v) => <span className="text-accent-green font-semibold">{formatCurrency(v)}</span> },
        { key: 'transaction_count', header: SW.ripoti.muamala, render: (v) => formatNumber(v) },
        { key: 'avg_transaction', header: SW.ripoti.wastani, render: (v) => formatCurrency(v) },
        { key: 'items_sold', header: SW.ripoti.bidhaaZilizouzwa, render: (v) => formatNumber(v) },
      ]}
      data={data.cashiers || []}
      emptyTitle={SW.common.hakuna}
    />
  )
}

function ClosingReport({ data, onExport, exporting, canDownload }) {
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
          {
            key: 'expenses', header: SW.ufungaji.matumizi,
            render: (v, row) => (!v || v.length === 0) ? '—' : (
              <div className="space-y-0.5 min-w-40">
                {v.map((e, i) => (
                  <div key={i} className="flex justify-between gap-2 text-xs text-text-secondary">
                    <span className="truncate">{e.description}</span>
                    <span className="flex-shrink-0">{formatCurrency(e.amount)}</span>
                  </div>
                ))}
                <div className="flex justify-between gap-2 text-xs font-semibold text-text-primary border-t border-border pt-0.5">
                  <span>{SW.common.jumla}</span>
                  <span>{formatCurrency(row.total_expenses)}</span>
                </div>
              </div>
            ),
          },
          { key: 'closed_by', header: SW.ufungaji.aliyefunga, render: (v) => v || '—' },
          {
            key: '_download', header: '',
            render: (_, row) => row.status === 'closed' && canDownload ? (
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<FileDown size={14} />}
                  onClick={() => onExport('pdf', row)}
                  loading={exporting === `${row.business_date}-pdf`}
                  disabled={!!exporting}
                  title={SW.ripoti.pakuaPdf}
                />
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<FileSpreadsheet size={14} />}
                  onClick={() => onExport('excel', row)}
                  loading={exporting === `${row.business_date}-excel`}
                  disabled={!!exporting}
                  title={SW.ripoti.pakuaExcel}
                />
              </div>
            ) : null,
          },
        ]}
        data={data.closings || []}
        emptyTitle={SW.ripoti.hakunaUfungajiKipindi}
      />
    </div>
  )
}

function LowStockReport({ data }) {
  return (
    <DataTable
      columns={[
        { key: 'product', header: SW.bidhaa.bidhaa },
        { key: 'product_code', header: SW.ripoti.msimbo },
        { key: 'branch', header: SW.ufungaji.tawi },
        { key: 'current_stock', header: SW.ripoti.bidhaaIliyobaki, render: (v) => <span className="font-bold text-accent-red">{formatNumber(v)}</span> },
        { key: 'minimum_stock', header: SW.ripoti.kiwangoChaChini, render: (v) => formatNumber(v) },
        { key: 'deficit', header: SW.ripoti.upungufu, render: (v) => <span className="text-accent-red">{formatNumber(v)}</span> },
      ]}
      data={data.items || []}
      emptyTitle={SW.ripoti.hakunaBidhaaHisaChini}
    />
  )
}

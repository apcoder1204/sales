import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, CalendarClock, HandCoins, Search, ShieldAlert, Users, Wallet } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import KpiCard from '@components/ui/KpiCard'
import Select from '@components/ui/Select'
import { customerService } from '@services/customerService'
import { usePagination } from '@hooks/usePagination'
import { usePermission } from '@hooks/usePermission'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { formatCurrency, formatDate, formatNumber } from '@utils/formatters'
import SW from '@constants/sw'
import RecordPaymentModal from './RecordPaymentModal'
import PaymentReceiptModal from './PaymentReceiptModal'
import AgeingTable, { BUCKETS } from './AgeingTable'

const STATUS_COLOR = { UNPAID: 'yellow', PARTIALLY_PAID: 'blue', PAID: 'green', OVERDUE: 'red' }
const STATUS_FILTERS = ['OPEN', 'OVERDUE', 'UNPAID', 'PARTIALLY_PAID', 'PAID', 'ALL']

// Madeni Yote: every customer debt in one place — credit sales and approved
// old debts. The server scopes it: a cashier sees only their branch, the
// admin and manager every branch (or the one picked in the branch switcher).
export default function DebtsPage() {
  const [data, setData] = useState({ items: [], total: 0, summary: null })
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [status, setStatus] = useState('OPEN')
  const [payFor, setPayFor] = useState(null) // { customer, branchId }
  const [receiptId, setReceiptId] = useState(null)
  const [tab, setTab] = useState('orodha')
  const [dash, setDash] = useState(null)
  const [ageing, setAgeing] = useState(null)
  const pagination = usePagination(50)
  const branchFilter = useActiveBranchFilter()
  const { can } = usePermission()
  const toast = useToast()
  const navigate = useNavigate()

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q.trim()); pagination.reset() }, 300)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await customerService.allDebts({
        status, q: debouncedQ || undefined, ...branchFilter,
        page: pagination.page, per_page: pagination.pageSize,
      })
      setData(res)
      pagination.setTotal(res.total || 0)
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, debouncedQ, branchFilter.branch_id, pagination.page])

  useEffect(() => { load() }, [load])

  // Dashboard and ageing follow the branch switcher, not the list filters.
  const loadInsights = useCallback(async () => {
    try {
      const [d, a] = await Promise.all([
        customerService.debtDashboard({ period: 'month', ...branchFilter }),
        customerService.ageing(branchFilter),
      ])
      setDash(d)
      setAgeing(a)
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branchFilter.branch_id])

  useEffect(() => { loadInsights() }, [loadInsights])

  const columns = [
    {
      key: 'customer', header: SW.wateja.mteja,
      render: (v) => (
        <div>
          <p className="font-medium text-text-primary">{v.name}</p>
          <p className="text-xs text-text-muted">{v.customer_no} · {v.phone}</p>
        </div>
      ),
    },
    { key: 'branch_name', header: SW.wateja.tawi },
    {
      key: 'reference', header: SW.madeni.deni,
      render: (v, row) => (
        <div>
          <p className="font-mono text-xs">{v}</p>
          <p className="text-xs text-text-muted">{row.kind === 'sale' ? SW.madeni.mauzo : SW.madeni.zamani} · {formatDate(row.date)}</p>
        </div>
      ),
    },
    { key: 'due_date', header: SW.wateja.tareheYaKulipa, render: (v) => formatDate(v) },
    { key: 'amount', header: SW.wateja.kiasi, render: (v) => formatCurrency(v) },
    { key: 'paid', header: SW.wateja.kilicholipwa, render: (v) => formatCurrency(v) },
    {
      key: 'outstanding', header: SW.wateja.kilichobaki,
      render: (v) => <span className={Number(v) > 0 ? 'font-semibold text-accent-red' : ''}>{formatCurrency(v)}</span>,
    },
    {
      key: 'status', header: SW.wateja.hali,
      render: (v) => <Badge color={STATUS_COLOR[v] || 'gray'}>{SW.hali.deni[v] || v}</Badge>,
    },
    {
      key: '_actions', header: '',
      render: (_, row) => (Number(row.outstanding) > 0 && can('payments.collect') ? (
        <Button
          size="sm"
          variant="ghost"
          onClick={(e) => { e.stopPropagation(); setPayFor({ customer: row.customer, branchId: row.branch_id }) }}
        >
          {SW.wateja.pokeaMalipo}
        </Button>
      ) : null),
    },
  ]

  const d = dash
  const ageTotal = Number(d?.total_outstanding) || 0
  const oldest = d?.oldest_debt
  return (
    <PageWrapper title={SW.madeni.kichwa} subtitle={SW.madeni.subtitle}>
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <KpiCard title={SW.madeni.jumla} value={formatCurrency(d?.total_outstanding)} icon={HandCoins} color="red" loading={!d} />
        <KpiCard title={SW.madeni.yaliyochelewa} value={formatCurrency(d?.overdue_total)} icon={AlertTriangle} color="yellow" loading={!d} />
        <KpiCard title={SW.madeni.watejaWanaodaiwa} value={formatNumber(d?.customers_owing)} icon={Users} color="blue" loading={!d} />
        <KpiCard title={SW.madeni.yaliyokusanywaMwezi} value={formatCurrency(d?.collected_in_period)} icon={Wallet} color="green" loading={!d} />
        <KpiCard title={SW.madeni.wamezidiKikomo} value={formatNumber(d?.customers_over_limit)} icon={ShieldAlert} color="purple" loading={!d} />
        <KpiCard
          title={SW.madeni.deniLaZamaniZaidi}
          value={oldest ? `${oldest.days_overdue} ${SW.madeni.siku}` : '-'}
          trendLabel={oldest ? `${oldest.customer.name} · ${formatCurrency(oldest.outstanding)}` : undefined}
          icon={CalendarClock} color="red" loading={!d}
        />
      </div>

      {d && ageTotal > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="glass-card p-4 space-y-2">
            <p className="text-sm font-medium text-text-primary">{SW.madeni.umriWaMadeni}</p>
            {BUCKETS.map((b) => {
              const v = Number(d.ageing[b]) || 0
              return (
                <div key={b} className="grid grid-cols-[7rem_minmax(0,1fr)_8rem] items-center gap-2 text-xs">
                  <span className="text-text-secondary">{SW.madeni.umri[b]}</span>
                  <div className="h-3 rounded bg-bg-hover overflow-hidden">
                    <div className={`h-full ${b === 'not_due' ? 'bg-accent-green' : b === '90_plus' ? 'bg-accent-red' : 'bg-accent-yellow'}`}
                      style={{ width: `${(v / ageTotal) * 100}%` }} />
                  </div>
                  <span className="text-right font-medium whitespace-nowrap">{formatCurrency(v)}</span>
                </div>
              )
            })}
          </div>
          <div className="glass-card p-4 space-y-2">
            <p className="text-sm font-medium text-text-primary">{SW.madeni.wadaiwaWakubwa}</p>
            {d.top_debtors.map((t) => (
              <button key={t.customer.id} type="button" onClick={() => navigate(`/wateja/${t.customer.id}`)}
                className="w-full flex items-center justify-between gap-2 text-sm py-1 hover:text-primary-light">
                <span className="truncate">{t.customer.name}</span>
                <span className="whitespace-nowrap">
                  <b>{formatCurrency(t.outstanding)}</b>
                  {Number(t.overdue) > 0 && <span className="text-xs text-accent-red ml-2">{SW.madeni.yaliyochelewa}: {formatCurrency(t.overdue)}</span>}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 border-b border-border">
        {['orodha', 'umriWaMadeni'].map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === t ? 'border-primary text-text-primary' : 'border-transparent text-text-muted'}`}>
            {SW.madeni[t]}
          </button>
        ))}
      </div>

      {tab === 'umriWaMadeni' && <AgeingTable data={ageing} />}
      {tab === 'orodha' && (<>

      <div className="flex flex-col sm:flex-row gap-3">
        <Input
          containerClassName="flex-1"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={SW.madeni.tafuta}
          leftIcon={<Search size={14} />}
        />
        <Select
          containerClassName="w-52"
          value={status}
          onChange={(e) => { setStatus(e.target.value); pagination.reset() }}
          options={STATUS_FILTERS.map((v) => ({
            value: v,
            label: v === 'OPEN' ? SW.madeni.yanayodaiwa : v === 'ALL' ? SW.madeni.yote : SW.hali.deni[v],
          }))}
        />
      </div>

      <DataTable
        columns={columns}
        data={data.items}
        loading={loading}
        pagination={pagination}
        onRowClick={(row) => navigate(`/wateja/${row.customer.id}`)}
        emptyTitle={SW.madeni.hakuna}
      />
      </>)}

      <RecordPaymentModal
        open={!!payFor}
        onClose={() => setPayFor(null)}
        customer={payFor?.customer}
        branchId={payFor?.branchId}
        onRecorded={(p) => { load(); loadInsights(); setReceiptId(p.id) }}
      />
      <PaymentReceiptModal paymentId={receiptId} open={!!receiptId} onClose={() => setReceiptId(null)} />
    </PageWrapper>
  )
}

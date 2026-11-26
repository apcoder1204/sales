import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, HandCoins, Search, Users } from 'lucide-react'
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

  const s = data.summary
  return (
    <PageWrapper title={SW.madeni.kichwa} subtitle={SW.madeni.subtitle}>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <KpiCard title={SW.madeni.jumla} value={formatCurrency(s?.total_outstanding)} icon={HandCoins} color="red" loading={loading && !s} />
        <KpiCard title={SW.madeni.yaliyochelewa} value={formatCurrency(s?.overdue)} icon={AlertTriangle} color="yellow" loading={loading && !s} />
        <KpiCard title={SW.madeni.watejaWanaodaiwa} value={formatNumber(s?.customers_owing)} icon={Users} color="blue" loading={loading && !s} />
      </div>

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

      <RecordPaymentModal
        open={!!payFor}
        onClose={() => setPayFor(null)}
        customer={payFor?.customer}
        branchId={payFor?.branchId}
        onRecorded={(p) => { load(); setReceiptId(p.id) }}
      />
      <PaymentReceiptModal paymentId={receiptId} open={!!receiptId} onClose={() => setReceiptId(null)} />
    </PageWrapper>
  )
}

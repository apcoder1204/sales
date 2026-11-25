import React, { useState, useEffect, useCallback } from 'react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import Modal from '@components/ui/Modal'
import { saleService } from '@services/saleService'
import { usePagination } from '@hooks/usePagination'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { usePermission } from '@hooks/usePermission'
import { useToast } from '@hooks/useToast'
import { formatCurrency, formatDate, formatDateTime } from '@utils/formatters'
import { getPaymentMethods } from '@utils/constants'
import { resolveApiErrorMessage } from '@utils/apiError'
import SW from '@constants/sw'

const PAY_STATUS_COLOR = { PAID: 'green', PARTIALLY_PAID: 'blue', UNPAID: 'yellow', OVERDUE: 'red', VOIDED: 'gray' }

export default function SalesPage() {
  const [sales, setSales] = useState([])
  const [loading, setLoading] = useState(true)
  const [paymentMethod, setPaymentMethod] = useState('')
  const [details, setDetails] = useState(null)
  const [voidTarget, setVoidTarget] = useState(null)
  const [voidReason, setVoidReason] = useState('')
  const [voiding, setVoiding] = useState(false)
  const pagination = usePagination()
  const branchFilter = useActiveBranchFilter()
  const { can } = usePermission()
  const toast = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await saleService.list({
        payment_method: paymentMethod || undefined,
        ...branchFilter,
        page: pagination.page,
        per_page: pagination.pageSize,
      })
      setSales(res.items || res)
      if (res.total !== undefined) pagination.setTotal(res.total)
    } finally {
      setLoading(false)
    }
  }, [paymentMethod, branchFilter.branch_id, pagination.page])

  useEffect(() => { load() }, [load])

  const handleVoid = async () => {
    if (voidReason.trim().length < 5) return
    setVoiding(true)
    try {
      await saleService.void(voidTarget.id, voidReason.trim())
      toast.success(SW.mafanikio.imehifadhiwa)
      setVoidTarget(null)
      setVoidReason('')
      load()
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setVoiding(false)
    }
  }

  const PAYMENT_OPTIONS = [{ value: '', label: SW.mauzo.njiaZoteZaMalipo }, ...getPaymentMethods()]

  const columns = [
    { key: 'transaction_no', header: SW.mauzo.namba, render: (v) => <span className="font-mono text-xs">{v}</span> },
    { key: 'created_at', header: SW.common.tarehe, render: (v) => formatDateTime(v) },
    { key: 'branch', header: SW.mauzo.tawiLaMauzo },
    { key: 'cashier', header: SW.risiti.mhusika },
    { key: 'customer', header: SW.mauzo.mteja, render: (v) => (v ? v.name : <span className="text-text-muted">{SW.mauzo.mtejaWaKawaida}</span>) },
    { key: 'payment_method', header: SW.risiti.malipo, render: (v) => SW.hali.malipo[v] || v },
    { key: 'total_amount', header: SW.mauzo.jumlaKuu, render: (v) => <span className="font-semibold">{formatCurrency(v)}</span> },
    {
      key: 'payment_status', header: SW.mauzo.haliYaMalipo,
      render: (v, row) => (
        <div>
          <Badge color={PAY_STATUS_COLOR[v] || 'gray'}>{SW.hali.deni[v] || v}</Badge>
          {Number(row.outstanding) > 0 && <p className="text-xs text-accent-red mt-1">{SW.mauzo.salio}: {formatCurrency(row.outstanding)}</p>}
        </div>
      ),
    },
    {
      key: 'status', header: SW.bidhaa.hali,
      render: (v) => <Badge color={v === 'completed' ? 'green' : 'red'}>{v === 'completed' ? SW.mauzo.imekamilika : SW.mauzo.imebatilishwa}</Badge>,
    },
    {
      key: '_actions', header: '',
      render: (_, row) => (
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => setDetails(row)}>{SW.mauzo.angaliaBidhaa}</Button>
          {row.status === 'completed' && can('sales.void') && (
            <Button variant="ghost" size="sm" className="text-accent-red" onClick={() => { setVoidTarget(row); setVoidReason('') }}>
              {SW.mauzo.batilisha}
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <PageWrapper title={SW.nav.historiaMauzo} subtitle={SW.mauzo.subtitleHistoria}>
      <div className="flex gap-3">
        <Select
          value={paymentMethod}
          onChange={(e) => { setPaymentMethod(e.target.value); pagination.reset() }}
          options={PAYMENT_OPTIONS}
          containerClassName="w-48"
        />
      </div>

      <DataTable
        columns={columns}
        data={sales}
        loading={loading}
        pagination={pagination}
        emptyTitle={SW.mauzo.hakunaMauzo}
      />

      {details && (
        <Modal open={!!details} onClose={() => setDetails(null)} title={details.transaction_no} size="sm">
          <div className="space-y-2 mb-4">
            {details.items.map((i) => (
              <div key={i.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                <span className="text-sm text-text-secondary">{i.product} × {i.quantity}</span>
                <span className="text-sm font-medium text-text-primary">{formatCurrency(i.line_total)}</span>
              </div>
            ))}
          </div>
          {details.payments?.length > 0 && (
            <div className="glass-card p-3 space-y-1 text-xs mb-3">
              <p className="text-text-muted">{SW.mauzo.malipo}</p>
              {details.payments.map((p) => (
                <div key={p.id} className="flex justify-between">
                  <span className={p.status === 'reversed' ? 'line-through text-text-muted' : ''}>
                    {p.payment_no} · {SW.hali.malipo[p.method] || p.method}{p.reference ? ` · ${p.reference}` : ''}
                  </span>
                  <span>{formatCurrency(p.amount)}</span>
                </div>
              ))}
              {Number(details.outstanding) > 0 && (
                <div className="flex justify-between font-medium text-accent-red">
                  <span>{SW.mauzo.salio}{details.due_date ? ` (${formatDate(details.due_date)})` : ''}</span>
                  <span>{formatCurrency(details.outstanding)}</span>
                </div>
              )}
            </div>
          )}
          {details.status === 'voided' && (
            <div className="glass-card p-3 space-y-1 text-xs text-text-muted">
              <p>{SW.mauzo.aliyebatilisha}: {details.voided_by}</p>
              {details.voided_at && <p>{formatDateTime(details.voided_at)}</p>}
              {details.void_reason && <p>{SW.hifadhi.sababu}: {details.void_reason}</p>}
            </div>
          )}
        </Modal>
      )}

      {voidTarget && (
        <Modal
          open={!!voidTarget}
          onClose={() => setVoidTarget(null)}
          title={`${SW.mauzo.batilisha} — ${voidTarget.transaction_no}`}
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setVoidTarget(null)}>{SW.common.ghairi}</Button>
              <Button
                variant="danger" loading={voiding}
                disabled={voidReason.trim().length < 5}
                onClick={handleVoid}
              >
                {SW.mauzo.batilisha}
              </Button>
            </>
          }
        >
          <Input
            value={voidReason}
            onChange={(e) => setVoidReason(e.target.value)}
            placeholder={SW.mauzo.sababuYaKubatilisha}
          />
        </Modal>
      )}
    </PageWrapper>
  )
}

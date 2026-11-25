import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Pencil, Wallet, ShieldCheck, Printer, Undo2 } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import Modal from '@components/ui/Modal'
import KpiCard from '@components/ui/KpiCard'
import { customerService } from '@services/customerService'
import { paymentService } from '@services/paymentService'
import { usePermission } from '@hooks/usePermission'
import { useActiveBranchFilter } from '@hooks/useActiveBranchFilter'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { formatCurrency, formatDate, formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'
import CustomerFormModal from './CustomerFormModal'
import RecordPaymentModal from './RecordPaymentModal'
import PaymentReceiptModal from './PaymentReceiptModal'

const STATUS_COLOR = { UNPAID: 'yellow', PARTIALLY_PAID: 'blue', PAID: 'green', OVERDUE: 'red' }

export default function CustomerDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { can } = usePermission()
  const branchFilter = useActiveBranchFilter()
  const toast = useToast()
  const [detail, setDetail] = useState(null)
  const [receivables, setReceivables] = useState([])
  const [payments, setPayments] = useState([])
  const [showPaid, setShowPaid] = useState(false)
  const [tab, setTab] = useState('madeni')
  const [loading, setLoading] = useState(true)
  const [editOpen, setEditOpen] = useState(false)
  const [payOpen, setPayOpen] = useState(false)
  const [creditOpen, setCreditOpen] = useState(false)
  const [receiptId, setReceiptId] = useState(null)
  const [reverseTarget, setReverseTarget] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [d, r, p] = await Promise.all([
        customerService.get(id, branchFilter),
        customerService.receivables(id, { ...branchFilter, open_only: !showPaid }),
        customerService.payments(id, branchFilter),
      ])
      setDetail(d)
      setReceivables(r)
      setPayments(p)
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, branchFilter.branch_id, showPaid])

  useEffect(() => { load() }, [load])

  if (!detail) {
    return <PageWrapper title={SW.wateja.mteja}>{!loading && <p className="text-text-muted">{SW.wateja.mtejaHajapatikana}</p>}</PageWrapper>
  }
  const { customer: c, summary: s } = detail

  const receivableColumns = [
    { key: 'reference', header: SW.wateja.kumbukumbu, render: (v) => <span className="font-mono text-xs">{v}</span> },
    { key: 'branch_name', header: SW.wateja.tawi },
    { key: 'date', header: SW.wateja.tarehe, render: (v) => formatDate(v) },
    { key: 'due_date', header: SW.wateja.tareheYaKulipa, render: (v) => formatDate(v) },
    { key: 'amount', header: SW.wateja.kiasi, render: (v) => formatCurrency(v) },
    { key: 'paid', header: SW.wateja.kilicholipwa, render: (v) => formatCurrency(v) },
    { key: 'outstanding', header: SW.wateja.kilichobaki, render: (v) => <span className="font-semibold">{formatCurrency(v)}</span> },
    { key: 'status', header: SW.wateja.hali, render: (v) => <Badge color={STATUS_COLOR[v]}>{SW.hali.deni[v] || v}</Badge> },
  ]

  const paymentColumns = [
    { key: 'payment_no', header: SW.wateja.namba, render: (v) => <span className="font-mono text-xs">{v}</span> },
    { key: 'created_at', header: SW.wateja.tarehe, render: (v) => formatDateTime(v) },
    { key: 'kind', header: SW.wateja.aina, render: (v) => (v === 'debt' ? SW.wateja.malipoYaDeni : SW.wateja.historiaYaMauzo) },
    { key: 'branch_name', header: SW.wateja.tawi },
    { key: 'method', header: SW.wateja.njia, render: (v, row) => `${SW.hali.malipo[v] || v}${row.reference ? ` · ${row.reference}` : ''}` },
    { key: 'amount', header: SW.wateja.kiasi, render: (v) => formatCurrency(v) },
    { key: 'received_by_name', header: SW.wateja.aliyepokea },
    {
      key: 'status', header: SW.wateja.hali,
      render: (v, row) => (
        <div>
          <Badge color={v === 'active' ? 'green' : 'red'}>{SW.hali.malipoHali[v] || v}</Badge>
          {row.reversal_reason && <p className="text-xs text-text-muted mt-1">{row.reversal_reason}</p>}
        </div>
      ),
    },
    {
      key: '_actions', header: '',
      render: (_, row) => row.kind === 'debt' && (
        <div className="flex gap-1">
          <Button variant="ghost" size="sm" leftIcon={<Printer size={14} />} onClick={() => setReceiptId(row.id)}>
            {SW.wateja.risiti}
          </Button>
          {row.status === 'active' && can('payments.reverse') && (
            <Button variant="ghost" size="sm" className="text-accent-red" leftIcon={<Undo2 size={14} />} onClick={() => setReverseTarget(row)}>
              {SW.wateja.batilisha}
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <PageWrapper
      title={c.name}
      subtitle={`${c.customer_no} · ${c.phone} · ${SW.hali.ainaMteja[c.customer_type] || c.customer_type}`}
      action={
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/wateja')}>{SW.wateja.wateja}</Button>
          {can('payments.collect') && (
            <Button leftIcon={<Wallet size={16} />} onClick={() => setPayOpen(true)} disabled={Number(s.balance) <= 0}>
              {SW.wateja.pokeaMalipo}
            </Button>
          )}
          {can('customers.write') && (
            <Button variant="secondary" leftIcon={<Pencil size={16} />} onClick={() => setEditOpen(true)}>{SW.wateja.hariri}</Button>
          )}
          {can('customers.credit') && (
            <Button variant="secondary" leftIcon={<ShieldCheck size={16} />} onClick={() => setCreditOpen(true)}>{SW.wateja.mkopo}</Button>
          )}
        </div>
      }
    >
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <KpiCard title={SW.wateja.salioLaDeni} value={formatCurrency(s.balance)} color="red" />
        <KpiCard title={SW.wateja.yaliyochelewa} value={formatCurrency(s.overdue)} color="yellow" />
        <KpiCard title={SW.wateja.kikomo} value={formatCurrency(c.credit_limit)} color="blue" />
        <KpiCard title={SW.wateja.mkopoUnaopatikana} value={formatCurrency(s.available_credit)} color="green" />
        <KpiCard
          title={SW.wateja.hali}
          value={`${SW.hali.mteja[c.status] || c.status} · ${c.credit_days} ${SW.wateja.sikuZaMkopo.toLowerCase()}`}
          color="purple"
        />
      </div>

      <div className="flex items-center gap-2 border-b border-border">
        {['madeni', 'malipo'].map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === t ? 'border-primary text-text-primary' : 'border-transparent text-text-muted'}`}
          >
            {SW.wateja[t]}
          </button>
        ))}
        {tab === 'madeni' && (
          <label className="ml-auto flex items-center gap-2 text-xs text-text-secondary">
            <input type="checkbox" checked={showPaid} onChange={(e) => setShowPaid(e.target.checked)} />
            {SW.wateja.onyeshaYaliyolipwa}
          </label>
        )}
      </div>

      {tab === 'madeni' ? (
        <DataTable columns={receivableColumns} data={receivables} loading={loading} emptyTitle={SW.wateja.hakunaMadeni} />
      ) : (
        <DataTable columns={paymentColumns} data={payments} loading={loading} emptyTitle={SW.wateja.hakunaMalipo} />
      )}

      <CustomerFormModal open={editOpen} onClose={() => setEditOpen(false)} customer={c} onSaved={load} />
      <RecordPaymentModal
        open={payOpen}
        onClose={() => setPayOpen(false)}
        customer={c}
        onRecorded={(p) => { load(); setReceiptId(p.id) }}
      />
      <PaymentReceiptModal paymentId={receiptId} open={!!receiptId} onClose={() => setReceiptId(null)} />
      <CreditModal open={creditOpen} onClose={() => setCreditOpen(false)} customer={c} onSaved={load} />
      <ReverseModal target={reverseTarget} onClose={() => setReverseTarget(null)} onDone={load} />
    </PageWrapper>
  )
}

function CreditModal({ open, onClose, customer, onSaved }) {
  const [form, setForm] = useState({ credit_limit: '', credit_days: '', status: 'active', reason: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const toast = useToast()

  useEffect(() => {
    if (!open) return
    setError(null)
    setForm({
      credit_limit: String(parseInt(customer.credit_limit, 10) || 0),
      credit_days: String(customer.credit_days),
      status: customer.status,
      reason: '',
    })
  }, [open, customer])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await customerService.updateCredit(customer.id, {
        credit_limit: String(parseInt(form.credit_limit || '0', 10)),
        credit_days: parseInt(form.credit_days || '0', 10),
        status: form.status,
        reason: form.reason.trim(),
      })
      toast.success(SW.wateja.mkopoUmebadilishwa)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(resolveApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.wateja.badilishaMkopo}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={saving} disabled={form.reason.trim().length < 5} onClick={save}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-3">
        <Input
          label={SW.wateja.kikomo}
          inputMode="numeric"
          value={form.credit_limit}
          onChange={(e) => setForm({ ...form, credit_limit: e.target.value.replace(/[^0-9]/g, '') })}
          hint={SW.wateja.kikomoSifuri}
        />
        <Input
          label={SW.wateja.sikuZaMkopo}
          inputMode="numeric"
          value={form.credit_days}
          onChange={(e) => setForm({ ...form, credit_days: e.target.value.replace(/[^0-9]/g, '') })}
        />
        <Select
          label={SW.wateja.hali}
          value={form.status}
          onChange={(e) => setForm({ ...form, status: e.target.value })}
          options={[
            { value: 'active', label: SW.hali.mteja.active },
            { value: 'inactive', label: SW.hali.mteja.inactive },
          ]}
        />
        <Input
          label={SW.wateja.sababu}
          value={form.reason}
          onChange={(e) => setForm({ ...form, reason: e.target.value })}
          placeholder={SW.wateja.sababuPlaceholder}
          required
        />
        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}

function ReverseModal({ target, onClose, onDone }) {
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)
  const toast = useToast()

  useEffect(() => {
    if (target) {
      keyRef.current = crypto.randomUUID()
      setReason('')
      setError(null)
    }
  }, [target])

  if (!target) return null

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await paymentService.reverse(target.id, reason.trim(), keyRef.current)
      toast.success(SW.wateja.malipoYamebatilishwa)
      onDone?.()
      onClose()
    } catch (err) {
      setError(resolveApiErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={!!target}
      onClose={onClose}
      title={`${SW.wateja.batilishaMalipo} — ${target.payment_no}`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button variant="danger" loading={saving} disabled={reason.trim().length < 5} onClick={save}>
            {SW.wateja.batilisha}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-text-secondary">{formatCurrency(target.amount)} · {SW.hali.malipo[target.method] || target.method}</p>
        <p className="text-xs text-text-muted">{SW.wateja.batilishaOnyo}</p>
        <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={SW.wateja.sababuPlaceholder} />
        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { BookPlus, Check, X } from 'lucide-react'
import PageWrapper from '@components/layout/PageWrapper'
import DataTable from '@components/tables/DataTable'
import Badge from '@components/ui/Badge'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import Modal from '@components/ui/Modal'
import { customerService } from '@services/customerService'
import { useAuth } from '@hooks/useAuth'
import { useBranch } from '@hooks/useBranch'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { formatCurrency, formatDate } from '@utils/formatters'
import SW from '@constants/sw'
import CustomerPicker from '@features/pos/CustomerPicker'

const STATUS_COLOR = { pending: 'yellow', approved: 'green', rejected: 'red' }
const todayIso = () => new Date().toLocaleDateString('en-CA')

// Old debts (decision D5): entered by one admin, decided by another. The
// server enforces the two-person rule; hiding the buttons on your own rows
// just avoids offering an action that would be refused.
export default function OpeningBalancesPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [rows, setRows] = useState([])
  const [status, setStatus] = useState('pending')
  const [loading, setLoading] = useState(true)
  const [entryOpen, setEntryOpen] = useState(false)
  const [decision, setDecision] = useState(null) // {row, action}

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await customerService.openingBalances.list({ status: status || undefined }))
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status])

  useEffect(() => { load() }, [load])

  const columns = [
    { key: 'customer', header: SW.wateja.mteja, render: (v) => <div><p>{v.name}</p><p className="text-xs text-text-muted">{v.customer_no}</p></div> },
    { key: 'branch_name', header: SW.wateja.tawi },
    { key: 'amount', header: SW.wateja.kiasi, render: (v) => <span className="font-semibold">{formatCurrency(v)}</span> },
    { key: 'effective_date', header: SW.madeniYaZamani.tareheYaDeni, render: (v) => formatDate(v) },
    { key: 'due_date', header: SW.wateja.tareheYaKulipa, render: (v) => formatDate(v) },
    { key: 'reference', header: SW.wateja.kumbukumbu },
    { key: 'entered_by_name', header: SW.madeniYaZamani.aliyeingiza },
    {
      key: 'status', header: SW.wateja.hali,
      render: (v, row) => (
        <div>
          <Badge color={STATUS_COLOR[v]}>{SW.hali.aliyeingizaHali[v] || v}</Badge>
          {row.decided_by_name && <p className="text-xs text-text-muted mt-1">{SW.madeniYaZamani.aliyeamua}: {row.decided_by_name}</p>}
          {row.decision_note && <p className="text-xs text-text-muted">{row.decision_note}</p>}
        </div>
      ),
    },
    {
      key: '_actions', header: '',
      render: (_, row) => {
        if (row.status !== 'pending') return null
        if (row.entered_by === user?.id) {
          return <span className="text-xs text-text-muted">{SW.madeniYaZamani.umeingizaWewe}</span>
        }
        return (
          <div className="flex gap-1">
            <Button size="sm" variant="success" leftIcon={<Check size={14} />} onClick={() => setDecision({ row, action: 'approve' })}>
              {SW.madeniYaZamani.idhinisha}
            </Button>
            <Button size="sm" variant="ghost" className="text-accent-red" leftIcon={<X size={14} />} onClick={() => setDecision({ row, action: 'reject' })}>
              {SW.madeniYaZamani.kataa}
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <PageWrapper
      title={SW.madeniYaZamani.kichwa}
      subtitle={SW.madeniYaZamani.subtitle}
      action={<Button leftIcon={<BookPlus size={16} />} onClick={() => setEntryOpen(true)}>{SW.madeniYaZamani.ingiza}</Button>}
    >
      <Select
        containerClassName="w-48"
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        options={[
          { value: '', label: SW.wateja.haliZote },
          ...['pending', 'approved', 'rejected'].map((s) => ({ value: s, label: SW.hali.aliyeingizaHali[s] })),
        ]}
      />
      <DataTable columns={columns} data={rows} loading={loading} emptyTitle={SW.madeniYaZamani.hakuna} />
      <EntryModal open={entryOpen} onClose={() => setEntryOpen(false)} onSaved={load} />
      <DecisionModal decision={decision} onClose={() => setDecision(null)} onDone={load} />
    </PageWrapper>
  )
}

function EntryModal({ open, onClose, onSaved }) {
  const { branches } = useBranch()
  const toast = useToast()
  const posBranches = branches.filter((b) => b.branch_type === 'pos_point' && b.is_active !== false)
  const [customer, setCustomer] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!open) return
    setCustomer(null)
    setError(null)
    setForm({ branch_id: posBranches[0]?.id || '', amount: '', effective_date: todayIso(), reference: '', description: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const amount = parseInt(form.amount || '0', 10)
  const canSave = customer && form.branch_id && amount > 0 && form.effective_date && form.effective_date <= todayIso() && form.reference?.trim()

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await customerService.openingBalances.create(customer.id, {
        branch_id: form.branch_id,
        amount: String(amount),
        effective_date: form.effective_date,
        reference: form.reference.trim(),
        description: form.description?.trim() || null,
      })
      toast.success(SW.madeniYaZamani.limeingizwa)
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
      title={SW.madeniYaZamani.ingiza}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={saving} disabled={!canSave} onClick={save}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-3">
        <CustomerPicker value={customer} onChange={setCustomer} label={SW.wateja.mteja} />
        <div className="grid grid-cols-2 gap-3">
          <Select
            label={SW.wateja.tawi}
            value={form.branch_id || ''}
            onChange={set('branch_id')}
            options={posBranches.map((b) => ({ value: b.id, label: b.name }))}
          />
          <Input
            label={SW.wateja.kiasi}
            inputMode="numeric"
            value={form.amount || ''}
            onChange={(e) => setForm({ ...form, amount: e.target.value.replace(/[^0-9]/g, '') })}
            required
          />
          <Input
            label={SW.madeniYaZamani.tareheYaDeni}
            type="date"
            max={todayIso()}
            value={form.effective_date || ''}
            onChange={set('effective_date')}
            required
          />
          <Input label={SW.madeniYaZamani.kumbukumbu} value={form.reference || ''} onChange={set('reference')} required />
        </div>
        <Input label={SW.wateja.maelezo} value={form.description || ''} onChange={set('description')} />
        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}

function DecisionModal({ decision, onClose, onDone }) {
  const toast = useToast()
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)

  useEffect(() => {
    if (decision) {
      keyRef.current = crypto.randomUUID()
      setNote('')
      setError(null)
    }
  }, [decision])

  if (!decision) return null
  const { row, action } = decision
  const isReject = action === 'reject'

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      if (isReject) await customerService.openingBalances.reject(row.id, note.trim())
      else await customerService.openingBalances.approve(row.id, note.trim(), keyRef.current)
      toast.success(isReject ? SW.madeniYaZamani.limekataliwa : SW.madeniYaZamani.limeidhinishwa)
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
      open={!!decision}
      onClose={onClose}
      title={`${isReject ? SW.madeniYaZamani.kataa : SW.madeniYaZamani.idhinisha} — ${row.customer.name}`}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button
            variant={isReject ? 'danger' : 'success'}
            loading={saving}
            disabled={isReject && note.trim().length < 3}
            onClick={save}
          >
            {isReject ? SW.madeniYaZamani.kataa : SW.madeniYaZamani.idhinisha}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-text-secondary">
          {formatCurrency(row.amount)} · {row.branch_name} · {row.reference}
        </p>
        {!isReject && <p className="text-xs text-text-muted">{SW.madeniYaZamani.thibitishaIdhini}</p>}
        <Input
          label={isReject ? SW.madeniYaZamani.sababuYaKukataa : SW.wateja.maelezoHiari}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          required={isReject}
        />
        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}

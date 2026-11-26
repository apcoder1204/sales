import React, { useEffect, useMemo, useRef, useState } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { customerService } from '@services/customerService'
import { useAuth } from '@hooks/useAuth'
import { useBranch } from '@hooks/useBranch'
import { usePermission } from '@hooks/usePermission'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { formatCurrency, formatDate } from '@utils/formatters'
import { getPaymentMethods } from '@utils/constants'
import SW from '@constants/sw'

const NEEDS_REFERENCE = ['mobile_money', 'bank_transfer']
// What the user typed: digits only (whole shillings).
const toInt = (v) => {
  const n = parseInt(String(v ?? '').replace(/[^0-9]/g, ''), 10)
  return Number.isFinite(n) ? n : 0
}
// Amounts from the API are decimal strings ("300000.00") — parse, never
// strip characters (that would turn 300000.00 into 30000000).
const fromApi = (v) => Math.round(Number(v) || 0)

// Debt is paid at the branch that owns it (decision D2): a cashier only at
// their own branch; an admin picks one of the branches where this customer
// owes. The server re-validates everything (branch, amounts, allocation).
export default function RecordPaymentModal({ open, onClose, customer, onRecorded }) {
  const { user } = useAuth()
  const { isGlobal } = usePermission()
  const { activeBranchId } = useBranch()
  const toast = useToast()
  const [receivables, setReceivables] = useState([])
  const [branchId, setBranchId] = useState('')
  const [form, setForm] = useState({ method: 'cash', amount: '', reference: '', notes: '' })
  const [manual, setManual] = useState(false)
  const [alloc, setAlloc] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const keyRef = useRef(null)

  useEffect(() => {
    if (!open || !customer) return
    keyRef.current = crypto.randomUUID()
    setForm({ method: 'cash', amount: '', reference: '', notes: '' })
    setManual(false)
    setAlloc({})
    setError(null)
    customerService.receivables(customer.id).then((rows) => {
      setReceivables(rows)
      const owing = [...new Set(rows.map((r) => r.branch_id))]
      if (!isGlobal) setBranchId(user?.branch_id || '')
      else setBranchId(owing.includes(activeBranchId) ? activeBranchId : owing[0] || '')
    }).catch((e) => setError(resolveApiErrorMessage(e)))
  }, [open, customer, isGlobal, user, activeBranchId])

  const branchOptions = useMemo(() => {
    const seen = new Map()
    receivables.forEach((r) => seen.set(r.branch_id, r.branch_name))
    return [...seen].map(([value, label]) => ({ value, label }))
  }, [receivables])

  const open_ = receivables.filter((r) => r.branch_id === branchId)
  const owed = open_.reduce((s, r) => s + fromApi(r.outstanding), 0)
  const amount = toInt(form.amount)

  // FIFO preview — same order the server uses (receivables come FIFO-sorted).
  const fifo = useMemo(() => {
    let left = amount
    return open_.map((r) => {
      const take = Math.min(left, fromApi(r.outstanding))
      left -= take
      return { ...r, take }
    }).filter((r) => r.take > 0)
  }, [open_, amount])

  const allocSum = Object.values(alloc).reduce((s, v) => s + toInt(v), 0)
  const allocInvalid = manual && (allocSum !== amount
    || open_.some((r) => toInt(alloc[`${r.kind}:${r.id}`]) > fromApi(r.outstanding)))
  const missingRef = NEEDS_REFERENCE.includes(form.method) && !form.reference.trim()
  const canSave = branchId && amount > 0 && amount <= owed && !missingRef && !allocInvalid

  const save = async () => {
    setSaving(true)
    setError(null)
    const payload = {
      branch_id: isGlobal ? branchId : undefined,
      method: form.method,
      amount: String(amount),
      reference: form.reference.trim() || undefined,
      notes: form.notes.trim() || undefined,
    }
    if (manual) {
      payload.allocations = open_
        .filter((r) => toInt(alloc[`${r.kind}:${r.id}`]) > 0)
        .map((r) => ({
          [r.kind === 'sale' ? 'sale_id' : 'opening_balance_id']: r.id,
          amount: String(toInt(alloc[`${r.kind}:${r.id}`])),
        }))
    }
    try {
      const payment = await customerService.recordPayment(customer.id, payload, keyRef.current)
      toast.success(SW.wateja.malipoYamepokelewa)
      onRecorded?.(payment)
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
      title={`${SW.wateja.rekodiMalipo} — ${customer?.name || ''}`}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={saving} disabled={!canSave} onClick={save}>{SW.wateja.pokeaMalipo}</Button>
        </>
      }
    >
      <div className="space-y-3">
        {isGlobal ? (
          <Select
            label={SW.wateja.chaguaTawi}
            value={branchId}
            onChange={(e) => { setBranchId(e.target.value); setAlloc({}) }}
            options={branchOptions}
          />
        ) : (
          <p className="text-sm text-text-secondary">
            {SW.wateja.tawi}: <span className="text-text-primary font-medium">{open_[0]?.branch_name || '-'}</span>
          </p>
        )}

        <p className="text-sm text-text-secondary">
          {SW.wateja.deniLaTawi}: <span className="font-semibold text-accent-red">{formatCurrency(owed)}</span>
        </p>
        {owed === 0 && <p className="text-sm text-text-muted">{SW.wateja.hakunaDeniTawi}</p>}

        <div className="grid grid-cols-2 gap-3">
          <Select
            label={SW.mauzo.njiaYaLipa}
            value={form.method}
            onChange={(e) => setForm({ ...form, method: e.target.value })}
            options={getPaymentMethods()}
          />
          <Input
            label={SW.wateja.kiasi}
            inputMode="numeric"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value.replace(/[^0-9]/g, '') })}
            error={amount > owed}
            required
          />
        </div>
        {amount > owed && <p className="text-xs text-accent-red">{SW.wateja.kiasiKinazidi}</p>}
        {NEEDS_REFERENCE.includes(form.method) && (
          <Input
            label={SW.mauzo.kumbukumbuNamba}
            value={form.reference}
            onChange={(e) => setForm({ ...form, reference: e.target.value })}
            placeholder={SW.mauzo.kumbukumbuPlaceholder}
            required
          />
        )}
        <Input
          label={SW.wateja.maelezoHiari}
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />

        <label className="flex items-center gap-2 text-sm text-text-secondary">
          <input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} />
          {SW.wateja.chaguaMauzo}
        </label>

        {!manual && fifo.length > 0 && (
          <div className="glass-card p-3 text-xs space-y-1">
            <p className="text-text-muted">{SW.wateja.fifoMaelezo}</p>
            {fifo.map((r) => (
              <div key={`${r.kind}:${r.id}`} className="flex justify-between">
                <span>{r.reference} · {formatDate(r.due_date)}</span>
                <span className="font-medium">{formatCurrency(r.take)}</span>
              </div>
            ))}
          </div>
        )}

        {manual && (
          <div className="glass-card p-3 text-xs space-y-2">
            {open_.map((r) => {
              const k = `${r.kind}:${r.id}`
              return (
                <div key={k} className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-text-primary truncate">{r.reference}</p>
                    <p className="text-text-muted">{SW.wateja.kilichobaki}: {formatCurrency(r.outstanding)}</p>
                  </div>
                  <Input
                    containerClassName="w-32"
                    inputMode="numeric"
                    value={alloc[k] || ''}
                    onChange={(e) => setAlloc({ ...alloc, [k]: e.target.value.replace(/[^0-9]/g, '') })}
                  />
                </div>
              )
            })}
            {allocInvalid && <p className="text-accent-red">{SW.wateja.mgawanyoHaulingani}</p>}
          </div>
        )}

        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}

import React, { useCallback, useEffect, useState } from 'react'
import { MessageSquarePlus } from 'lucide-react'
import Button from '@components/ui/Button'
import DataTable from '@components/tables/DataTable'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import Modal from '@components/ui/Modal'
import { customerService } from '@services/customerService'
import { useBranch } from '@hooks/useBranch'
import { usePermission } from '@hooks/usePermission'
import { useToast } from '@hooks/useToast'
import { resolveApiErrorMessage } from '@utils/apiError'
import { formatDate, formatDateTime } from '@utils/formatters'
import SW from '@constants/sw'

const METHODS = ['phone', 'visit', 'sms', 'whatsapp']
const todayIso = () => new Date().toLocaleDateString('en-CA')

// Debt-collection notes (brief §16). They record what was said and promised;
// they never change what the customer owes.
export default function FollowUpsTab({ customerId, branchFilter }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState(false)
  const { can } = usePermission()
  const toast = useToast()
  const F = SW.ufuatiliaji

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await customerService.followUps.list(customerId, branchFilter))
    } catch (err) {
      toast.error(resolveApiErrorMessage(err))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customerId, branchFilter.branch_id])

  useEffect(() => { load() }, [load])

  const columns = [
    { key: 'contact_date', header: F.tareheYaMawasiliano, render: (v) => formatDate(v) },
    { key: 'method', header: F.njia, render: (v) => F.njiaZa[v] || v },
    { key: 'note', header: F.maelezo, render: (v) => <span className="whitespace-pre-wrap">{v}</span> },
    { key: 'expected_payment_date', header: F.tareheYaAhadi, render: (v) => (v ? formatDate(v) : '-') },
    { key: 'branch_name', header: SW.wateja.tawi },
    { key: 'responsible_user_name', header: F.mhusika, render: (v, row) => <div><p>{v}</p><p className="text-xs text-text-muted">{formatDateTime(row.created_at)}</p></div> },
  ]

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-text-muted">{F.haibadilishiDeni}</p>
        {can('customers.follow_up') && (
          <Button leftIcon={<MessageSquarePlus size={16} />} onClick={() => setOpen(true)}>{F.ongeza}</Button>
        )}
      </div>
      <DataTable columns={columns} data={rows} loading={loading} emptyTitle={F.hakuna} />
      <FollowUpModal open={open} onClose={() => setOpen(false)} customerId={customerId} onSaved={load} />
    </div>
  )
}

function FollowUpModal({ open, onClose, customerId, onSaved }) {
  const { isGlobal } = usePermission()
  const { branches, activeBranchId } = useBranch()
  const toast = useToast()
  const F = SW.ufuatiliaji
  const posBranches = isGlobal ? branches.filter((b) => b.branch_type === 'pos_point' && b.is_active !== false) : []
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!open) return
    setError(null)
    const preferred = posBranches.some((b) => b.id === activeBranchId) ? activeBranchId : posBranches[0]?.id
    setForm({ branch_id: preferred || '', contact_date: todayIso(), method: 'phone', note: '', expected_payment_date: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const canSave = form.note?.trim().length >= 3 && form.contact_date && form.contact_date <= todayIso()
    && (!isGlobal || form.branch_id)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await customerService.followUps.create(customerId, {
        branch_id: isGlobal ? form.branch_id : undefined,
        contact_date: form.contact_date,
        method: form.method,
        note: form.note.trim(),
        expected_payment_date: form.expected_payment_date || null,
      })
      toast.success(F.imeongezwa)
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
      title={F.ongeza}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={saving} disabled={!canSave} onClick={save}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          {isGlobal && (
            <Select label={SW.wateja.tawi} value={form.branch_id || ''} onChange={set('branch_id')}
              options={posBranches.map((b) => ({ value: b.id, label: b.name }))} />
          )}
          <Select label={F.njia} value={form.method || 'phone'} onChange={set('method')}
            options={METHODS.map((m) => ({ value: m, label: F.njiaZa[m] }))} />
          <Input label={F.tareheYaMawasiliano} type="date" max={todayIso()} value={form.contact_date || ''} onChange={set('contact_date')} required />
          <Input label={F.tareheYaAhadi} type="date" value={form.expected_payment_date || ''} onChange={set('expected_payment_date')} />
        </div>
        <Input label={F.maelezo} value={form.note || ''} onChange={set('note')} placeholder={F.maelezoPlaceholder} required />
        {error && <p className="text-sm text-accent-red">{error}</p>}
      </div>
    </Modal>
  )
}

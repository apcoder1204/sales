import React, { useEffect, useState } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { customerService } from '@services/customerService'
import { resolveApiErrorMessage } from '@utils/apiError'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

const TYPES = ['individual', 'business', 'institution', 'government']
const EMPTY = { name: '', phone: '', email: '', address: '', customer_type: 'individual', tin: '', notes: '' }

// Create or edit a customer's profile. Credit terms are not here — they
// are an admin-only, audited action on the detail page.
export default function CustomerFormModal({ open, onClose, customer, onSaved }) {
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const toast = useToast()

  useEffect(() => {
    if (!open) return
    setError(null)
    setForm(customer
      ? Object.fromEntries(Object.keys(EMPTY).map((k) => [k, customer[k] ?? '']))
      : EMPTY)
  }, [open, customer])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const save = async () => {
    setSaving(true)
    setError(null)
    const payload = Object.fromEntries(
      Object.entries(form).map(([k, v]) => [k, typeof v === 'string' && v.trim() === '' && k !== 'name' && k !== 'phone' ? null : v])
    )
    try {
      const saved = customer
        ? await customerService.update(customer.id, payload)
        : await customerService.create(payload)
      toast.success(customer ? SW.wateja.mtejaAmehifadhiwa : SW.wateja.mtejaAmeongezwa)
      onSaved?.(saved)
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
      title={customer ? SW.wateja.haririMteja : SW.wateja.ongezaMteja}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={saving} disabled={form.name.trim().length < 2 || form.phone.trim().length < 9} onClick={save}>
            {SW.common.hifadhi}
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Input label={SW.wateja.jina} value={form.name} onChange={set('name')} required />
        <Input label={SW.wateja.simu} value={form.phone} onChange={set('phone')} placeholder="07XX XXX XXX" required />
        <Select
          label={SW.wateja.aina}
          value={form.customer_type}
          onChange={set('customer_type')}
          options={TYPES.map((t) => ({ value: t, label: SW.hali.ainaMteja[t] }))}
        />
        <Input label={SW.wateja.tin} value={form.tin} onChange={set('tin')} />
        <Input label={SW.wateja.barua} value={form.email} onChange={set('email')} type="email" />
        <Input label={SW.wateja.anwani} value={form.address} onChange={set('address')} />
        <Input containerClassName="sm:col-span-2" label={SW.wateja.maelezo} value={form.notes} onChange={set('notes')} />
      </div>
      {error && <p className="text-sm text-accent-red mt-3">{error}</p>}
    </Modal>
  )
}

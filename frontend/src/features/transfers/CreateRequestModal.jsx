import React, { useState, useEffect } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import { transferService } from '@services/transferService'
import { productService } from '@services/productService'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { useAuth } from '@hooks/useAuth'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'

export default function CreateRequestModal({ open, onClose, onSaved }) {
  const { user } = useAuth()
  const { loading, call } = useApi()
  const isGlobal = isGlobalRole(user)

  const [branches, setBranches] = useState([])
  const [products, setProducts] = useState([])
  const [items, setItems] = useState([{ product_id: '', quantity: '' }])
  const [form, setForm] = useState({ to_branch_id: '', from_branch_id: '', notes: '' })

  useEffect(() => {
    if (!open) return
    userService.branches().then((b) => {
      setBranches(b)
      const mainStore = b.find((br) => br.branch_type === 'main_store')
      if (mainStore) setForm((f) => ({ ...f, from_branch_id: mainStore.id }))
    }).catch(() => {})
    productService.list({ status: 'active', page_size: 200 }).then((r) => setProducts(r.items || r)).catch(() => {})
  }, [open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setItem = (i, k) => (e) => setItems((prev) => prev.map((item, idx) => idx === i ? { ...item, [k]: e.target.value } : item))
  const addItem = () => setItems((p) => [...p, { product_id: '', quantity: '' }])
  const removeItem = (i) => setItems((p) => p.filter((_, idx) => idx !== i))

  const handleSubmit = async () => {
    const toBranch = isGlobal ? form.to_branch_id : user?.branch_id

    try {
      await call(
        () => transferService.createRequest({
          to_branch_id: toBranch,
          from_branch_id: form.from_branch_id,
          reason: form.notes || 'Ombi la bidhaa',
          items: items
            .filter((i) => i.product_id && i.quantity)
            .map((i) => ({ product_id: i.product_id, quantity: parseInt(i.quantity) })),
        }),
        { successMsg: 'Ombi limetumwa', onSuccess: onSaved }
      )
    } catch (_) {
      // error already shown by useApi toast
    }
  }

  // Requests originate from POS outlets — Main Store cannot request stock from itself
  const posOptions = branches
    .filter((b) => b.branch_type === 'pos_point')
    .map((b) => ({ value: b.id, label: b.name }))
  const sourceOptions = branches
    .map((b) => ({ value: b.id, label: b.name }))
  const productOptions = products.map((p) => ({ value: p.id, label: `${p.product_code} — ${p.name}` }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Ombi la Bidhaa"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleSubmit}>{SW.common.thibitisha}</Button>
        </>
      }
    >
      <div className="space-y-4">
        {isGlobal && (
          <Select label="Kioski Linalohitaji Bidhaa" value={form.to_branch_id} onChange={set('to_branch_id')}
            options={posOptions} placeholder="Chagua kioski..." required />
        )}

        <Select label={SW.uhamisho.chanzo} value={form.from_branch_id} onChange={set('from_branch_id')}
          options={sourceOptions} placeholder="Chagua tawi la chanzo..." required />

        <div className="space-y-2">
          <p className="text-sm font-medium text-text-secondary">{SW.uhamisho.bidhaa}</p>
          {items.map((item, i) => (
            <div key={i} className="flex gap-2 items-end">
              <Select value={item.product_id} onChange={setItem(i, 'product_id')}
                options={productOptions} placeholder="Bidhaa..." containerClassName="flex-1" />
              <Input type="number" min="1" value={item.quantity} onChange={setItem(i, 'quantity')}
                placeholder="Idadi" containerClassName="w-24" />
              {items.length > 1 && (
                <Button variant="danger" size="icon" onClick={() => removeItem(i)}>×</Button>
              )}
            </div>
          ))}
          <Button variant="ghost" size="sm" onClick={addItem}>{SW.uhamisho.ongezaBidhaa}</Button>
        </div>

        <Input label="Maelezo (hiari)" value={form.notes} onChange={set('notes')} placeholder="Sababu ya ombi..." />
      </div>
    </Modal>
  )
}

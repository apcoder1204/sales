import React, { useState, useEffect } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import { transferService } from '@services/transferService'
import { productService } from '@services/productService'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import SW from '@constants/sw'

export default function DirectTransferModal({ open, onClose, onSaved }) {
  const { loading, call } = useApi()
  const [branches, setBranches] = useState([])
  const [products, setProducts] = useState([])
  const [items, setItems] = useState([{ product_id: '', quantity: '' }])
  const [form, setForm] = useState({ from_branch_id: '', to_branch_id: '', notes: '' })

  useEffect(() => {
    if (!open) return
    userService.branches().then(setBranches).catch(() => {})
    productService.list({ status: 'active', page_size: 200 }).then((r) => setProducts(r.items || r)).catch(() => {})
  }, [open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setItem = (i, k) => (e) => setItems((prev) => prev.map((item, idx) => idx === i ? { ...item, [k]: e.target.value } : item))
  const addItem = () => setItems((p) => [...p, { product_id: '', quantity: '' }])
  const removeItem = (i) => setItems((p) => p.filter((_, idx) => idx !== i))

  const handleSubmit = async () => {
    await call(
      () => transferService.createDirect({
        from_branch_id: form.from_branch_id,
        to_branch_id: form.to_branch_id,
        notes: form.notes,
        items: items.map((i) => ({ product_id: i.product_id, quantity: parseInt(i.quantity) })),
      }),
      { successMsg: SW.mafanikio.imesafirishwa, onSuccess: onSaved }
    )
  }

  // Transfers flow: Main Store → POS (warehouse ships to outlets)
  const mainStoreOptions = branches
    .filter((b) => b.branch_type === 'main_store')
    .map((b) => ({ value: b.id, label: b.name }))
  const posOptions = branches
    .filter((b) => b.branch_type === 'pos_point')
    .map((b) => ({ value: b.id, label: b.name }))
  const productOptions = products.map((p) => ({ value: p.id, label: `${p.product_code} — ${p.name}` }))

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Uhamisho wa Moja kwa Moja"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleSubmit}>{SW.uhamisho.tekeleza}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Select label="Chanzo (Hifadhi Kuu)" value={form.from_branch_id} onChange={set('from_branch_id')}
            options={mainStoreOptions} placeholder="Chagua chanzo..." required />
          <Select label="Lengo (Kioski cha POS)" value={form.to_branch_id} onChange={set('to_branch_id')}
            options={posOptions} placeholder="Chagua kioski..." required />
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-text-secondary">Bidhaa</p>
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
          <Button variant="ghost" size="sm" onClick={addItem}>+ Ongeza Bidhaa</Button>
        </div>

        <Input label="Maelezo" value={form.notes} onChange={set('notes')} placeholder="Maelezo ya uhamisho..." />
      </div>
    </Modal>
  )
}

import React, { useState, useEffect } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import Input from '@components/ui/Input'
import { transferService } from '@services/transferService'
import { productService } from '@services/productService'
import { userService } from '@services/userService'
import { inventoryService } from '@services/inventoryService'
import { useApi } from '@hooks/useApi'
import { useBranch } from '@hooks/useBranch'
import SW from '@constants/sw'

export default function DirectTransferModal({ open, onClose, onSaved }) {
  const { loading, call } = useApi()
  const { activeBranchId } = useBranch()
  const [branches, setBranches] = useState([])
  const [products, setProducts] = useState([])
  const [availableByProduct, setAvailableByProduct] = useState({})
  const [items, setItems] = useState([{ product_id: '', quantity: '' }])
  const [form, setForm] = useState({ from_branch_id: '', to_branch_id: '', notes: '' })

  useEffect(() => {
    if (!open) return
    userService.branches().then((b) => {
      setBranches(b)
      // Default the destination to the shared branch context when it's a
      // valid POS outlet — still editable via the dropdown.
      const contextMatch = activeBranchId && b.some((br) => br.id === activeBranchId && br.branch_type === 'pos_point')
      if (contextMatch) setForm((f) => ({ ...f, to_branch_id: activeBranchId }))
    }).catch(() => {})
    productService.list({ status: 'active', per_page: 200 }).then((r) => setProducts(r.items || r)).catch(() => {})
  }, [open, activeBranchId])

  // Live stock at the source branch — a direct transfer executes
  // immediately with no approval step, so a blind submission that turns
  // out to exceed available stock is a pure round-trip failure this avoids.
  useEffect(() => {
    if (!open || !form.from_branch_id) { setAvailableByProduct({}); return }
    inventoryService.list({ branch_id: form.from_branch_id, per_page: 200 }).then((res) => {
      const map = {}
      for (const p of res.items || res) {
        const inv = (p.inventory || []).find((i) => i.branch_id === form.from_branch_id)
        if (inv) map[p.id] = inv.available_qty
      }
      setAvailableByProduct(map)
    }).catch(() => setAvailableByProduct({}))
  }, [open, form.from_branch_id])

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
      title={SW.uhamisho.uhamishoWaKumoja}
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
          <Select label={SW.uhamisho.chanzoHifadhiKuu} value={form.from_branch_id} onChange={set('from_branch_id')}
            options={mainStoreOptions} placeholder={SW.uhamisho.chaguaChanzoPlaceholder} required />
          <Select label={SW.uhamisho.lengoKioskiPos} value={form.to_branch_id} onChange={set('to_branch_id')}
            options={posOptions} placeholder={SW.hifadhi.chaguaKioskiPlaceholder} required />
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-text-secondary">{SW.uhamisho.bidhaa}</p>
          {items.map((item, i) => {
            const available = item.product_id ? availableByProduct[item.product_id] : undefined
            const exceedsAvailable = available !== undefined && item.quantity && parseInt(item.quantity) > available
            return (
              <div key={i}>
                <div className="flex gap-2 items-end">
                  <Select value={item.product_id} onChange={setItem(i, 'product_id')}
                    options={productOptions} placeholder={SW.uhamisho.bidhaaPlaceholder} containerClassName="flex-1" />
                  <Input type="number" min="1" value={item.quantity} onChange={setItem(i, 'quantity')}
                    placeholder={SW.common.idadi} containerClassName="w-24" />
                  {items.length > 1 && (
                    <Button variant="danger" size="icon" onClick={() => removeItem(i)}>×</Button>
                  )}
                </div>
                {available !== undefined && (
                  <p className={`text-xs mt-1 ${exceedsAvailable ? 'text-accent-red' : 'text-text-muted'}`}>
                    {SW.uhamisho.kiasiKinachopatikana(available)}
                  </p>
                )}
              </div>
            )
          })}
          <Button variant="ghost" size="sm" onClick={addItem}>{SW.uhamisho.ongezaBidhaa}</Button>
        </div>

        <Input label={SW.bidhaa.maelezo} value={form.notes} onChange={set('notes')} placeholder={SW.uhamisho.maelezoYaUhamishoPlaceholder} />
      </div>
    </Modal>
  )
}

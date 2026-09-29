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
import { useAuth } from '@hooks/useAuth'
import { useBranch } from '@hooks/useBranch'
import { isGlobalRole } from '@utils/permissions'
import SW from '@constants/sw'

export default function CreateRequestModal({ open, onClose, onSaved }) {
  const { user } = useAuth()
  const { loading, call } = useApi()
  const { activeBranchId } = useBranch()
  const isGlobal = isGlobalRole(user)

  const [branches, setBranches] = useState([])
  const [products, setProducts] = useState([])
  const [availableByProduct, setAvailableByProduct] = useState({})
  const [items, setItems] = useState([{ product_id: '', quantity: '' }])
  const [form, setForm] = useState({ to_branch_id: '', from_branch_id: '', notes: '' })

  useEffect(() => {
    if (!open) return
    userService.branches().then((b) => {
      setBranches(b)
      const mainStore = b.find((br) => br.branch_type === 'main_store')
      if (mainStore) setForm((f) => ({ ...f, from_branch_id: mainStore.id }))
      // Default the requesting (destination) branch to the shared branch
      // context when it's a valid POS outlet — the request should operate
      // in that context per the global selector — the field stays editable.
      const contextMatch = activeBranchId && b.some((br) => br.id === activeBranchId && br.branch_type === 'pos_point')
      if (contextMatch) setForm((f) => ({ ...f, to_branch_id: activeBranchId }))
    }).catch(() => {})
    productService.list({ status: 'active', per_page: 200 }).then((r) => setProducts(r.items || r)).catch(() => {})
  }, [open, activeBranchId])

  // Live stock at the chosen source branch — shown per item so a request
  // isn't submitted blind and then partially/fully rejected on approval
  // for something the approver could see coming from the source's own
  // stock levels but the requester couldn't.
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
    const toBranch = isGlobal ? form.to_branch_id : user?.branch_id

    try {
      await call(
        () => transferService.createRequest({
          to_branch_id: toBranch,
          from_branch_id: form.from_branch_id,
          reason: form.notes || SW.uhamisho.ombi,
          items: items
            .filter((i) => i.product_id && i.quantity)
            .map((i) => ({ product_id: i.product_id, quantity: parseInt(i.quantity) })),
        }),
        { successMsg: SW.mafanikio.ombiLimetumwa, onSuccess: onSaved }
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
      title={SW.uhamisho.ombi}
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
          <Select label={SW.uhamisho.kioskiLinalohitaji} value={form.to_branch_id} onChange={set('to_branch_id')}
            options={posOptions} placeholder={SW.hifadhi.chaguaKioskiPlaceholder} required />
        )}

        <Select label={SW.uhamisho.chanzo} value={form.from_branch_id} onChange={set('from_branch_id')}
          options={sourceOptions} placeholder={SW.uhamisho.chaguaTawiChanzoPlaceholder} required />

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

        <Input label={SW.ufungaji.maelezo} value={form.notes} onChange={set('notes')} placeholder={SW.uhamisho.sababuYaOmbiPlaceholder} />
      </div>
    </Modal>
  )
}

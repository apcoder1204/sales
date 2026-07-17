import React, { useState, useEffect } from 'react'
import { Save, X, Package, Warehouse, Hash } from 'lucide-react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Select from '@components/ui/Select'
import { inventoryService } from '@services/inventoryService'
import { productService } from '@services/productService'
import { userService } from '@services/userService'
import { useApi } from '@hooks/useApi'
import { useToast } from '@hooks/useToast'
import SW from '@constants/sw'

const empty = { product_id: '', branch_id: '', quantity: '', notes: '' }

export default function StockAdjustFormModal({ open, onClose, onSaved }) {
  const [form, setForm] = useState(empty)
  const [products, setProducts] = useState([])
  const [branches, setBranches] = useState([])
  const { loading, call } = useApi()
  const toast = useToast()

  useEffect(() => {
    if (!open) return
    productService.list({ status: 'active', per_page: 200 })
      .then((res) => setProducts((res.items || res).map((p) => ({ value: p.id, label: `${p.product_code} — ${p.name}` }))))
      .catch(() => {})
    // Stock adjustments (new purchases) go to Main Store only — POS locations get stock via transfers
    userService.branches()
      .then((b) => {
        const mainStore = b.filter((x) => x.branch_type === 'main_store')
        const opts = mainStore.map((x) => ({ value: x.id, label: x.name }))
        setBranches(opts)
        if (opts.length > 0) setForm((f) => ({ ...f, branch_id: opts[0].value }))
      })
      .catch(() => {})
  }, [open])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSave = async () => {
    if (!form.product_id || !form.branch_id || !form.quantity) {
      toast.error('Chagua bidhaa, stoo, na weka idadi')
      return
    }
    const qty = parseInt(form.quantity)
    if (isNaN(qty) || qty === 0) { toast.error('Weka idadi sahihi (si sifuri)'); return }

    await call(
      () => inventoryService.adjust({
        product_id: form.product_id,
        branch_id: form.branch_id,
        quantity: Math.abs(qty),
        type: qty > 0 ? 'stock_in' : 'stock_out',
        notes: form.notes || undefined,
      }),
      {
        successMsg: SW.mafanikio.imehifadhiwa,
        onSuccess: () => { setForm(empty); onSaved?.(); onClose() },
      }
    )
  }

  const handleClose = () => { setForm(empty); onClose() }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Marekebisho Ya Bidhaa"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={handleClose} leftIcon={<X size={15} />}>
            {SW.common.ghairi}
          </Button>
          <Button loading={loading} onClick={handleSave} leftIcon={<Save size={15} />}>
            {SW.common.hifadhi}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        <Select
          label="Bidhaa"
          value={form.product_id}
          onChange={set('product_id')}
          options={products}
          placeholder="Chagua bidhaa"
          leftIcon={<Package size={16} />}
          required
        />

        <Select
          label="Hifadhi Kuu (Duka Kuu)"
          value={form.branch_id}
          onChange={set('branch_id')}
          options={branches}
          placeholder="Hifadhi Kuu"
          leftIcon={<Warehouse size={16} />}
          required
        />

        <div className="relative">
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            Badiliko la Idadi (+/-) <span className="text-accent-red">*</span>
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted flex items-center pointer-events-none">
              <Hash size={16} />
            </span>
            <input
              type="number"
              value={form.quantity}
              onChange={set('quantity')}
              placeholder="Mfano: -5 kupunguza, 5 kuongeza"
              className="input-base pl-9 w-full"
              required
            />
          </div>
          {form.quantity && parseInt(form.quantity) !== 0 && (
            <p className={`text-xs mt-1 ${parseInt(form.quantity) > 0 ? 'text-accent-green' : 'text-accent-red'}`}>
              {parseInt(form.quantity) > 0
                ? `Itaongeza bidhaa kwa ${parseInt(form.quantity)}`
                : `Itapunguza bidhaa kwa ${Math.abs(parseInt(form.quantity))}`}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1.5">
            Sababu <span className="text-text-muted text-xs font-normal">(hiari)</span>
          </label>
          <textarea
            value={form.notes}
            onChange={set('notes')}
            rows={4}
            placeholder="Eleza sababu ya marekebisho (mfano: Imeharibika, Imeibiwa, Hesabu mbaya)"
            className="w-full rounded-lg bg-bg-panel border border-border text-text-primary placeholder-text-muted px-3 py-2.5 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
          />
        </div>
      </div>
    </Modal>
  )
}

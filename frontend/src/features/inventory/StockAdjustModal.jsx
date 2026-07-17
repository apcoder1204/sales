import React, { useState } from 'react'
import Modal from '@components/ui/Modal'
import Button from '@components/ui/Button'
import Input from '@components/ui/Input'
import Select from '@components/ui/Select'
import { inventoryService } from '@services/inventoryService'
import { useApi } from '@hooks/useApi'
import SW from '@constants/sw'
import { formatNumber } from '@utils/formatters'

const ALL_TX_TYPES = [
  { value: 'stock_in', label: 'Ongeza Bidhaa (Mapokezi)', mainOnly: true },
  { value: 'stock_out', label: 'Punguza Bidhaa' },
  { value: 'adjustment', label: 'Marekebisho ya Hesabu' },
  { value: 'damaged', label: 'Imeharibika' },
]

export default function StockAdjustModal({ open, onClose, item, onSaved }) {
  // POS outlets cannot receive new stock directly — they get it via transfers from Main Store
  const isMainStore = item?.branch_type === 'main_store'
  const TX_TYPE_OPTIONS = ALL_TX_TYPES.filter((t) => !t.mainOnly || isMainStore)
  const [form, setForm] = useState({ type: isMainStore ? 'stock_in' : 'adjustment', quantity: '', notes: '' })
  const { loading, call } = useApi()

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSave = async () => {
    await call(
      () => inventoryService.adjust({
        product_id: item.product_id,
        branch_id: item.branch_id,
        type: form.type,
        quantity: parseInt(form.quantity),
        notes: form.notes || undefined,
      }),
      { successMsg: SW.mafanikio.imehifadhiwa, onSuccess: onSaved }
    )
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={SW.hifadhi.rekebisha}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{SW.common.ghairi}</Button>
          <Button loading={loading} onClick={handleSave}>{SW.common.hifadhi}</Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="glass-card p-3">
          <p className="text-sm font-medium text-text-primary">{item.product_name}</p>
          <p className="text-xs text-text-muted mt-1">
            {item.branch_name} — Bidhaa inayopatikana: <span className="text-accent-green font-semibold">{formatNumber(item.available_qty)}</span>
          </p>
        </div>

        <Select
          label="Aina ya Marekebisho"
          value={form.type}
          onChange={set('type')}
          options={TX_TYPE_OPTIONS}
        />
        <Input
          label="Idadi"
          type="number"
          min="1"
          value={form.quantity}
          onChange={set('quantity')}

        />
        <Input
          label="Sababu / Maelezo"
          value={form.notes}
          onChange={set('notes')}
          placeholder="Eleza sababu ya marekebisho..."
        />
      </div>
    </Modal>
  )
}
